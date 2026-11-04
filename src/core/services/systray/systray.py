"""Shared tray icons collected by one monitor or hook."""

import ctypes as ct
import itertools
import logging
import threading
from ctypes import byref
from dataclasses import dataclass
from typing import override
from uuid import UUID

from PyQt6.QtCore import QCoreApplication, QObject, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtQuick import QQuickImageProvider

from core.bar.appbar import AppBarManager
from core.services.systray.systray_hook import SystrayHook
from core.services.systray.systray_monitor import IconData, SystrayMonitor
from core.services.systray.utils import hook_dll_exists, pack_i32
from core.utils.win32.bindings.user32 import (
    AllowSetForegroundWindow,
    FindWindowEx,
    GetClassName,
    GetCursorPos,
    GetForegroundWindow,
    GetWindowLong,
    GetWindowThreadProcessId,
    IsWindow,
    IsWindowVisible,
    RegisterWindowMessage,
    SendNotifyMessage,
    get_window_thread_process_id,
)
from core.utils.win32.constants import (
    GWL_STYLE,
    HWND_BROADCAST,
    NIF_GUID,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_STATE,
    NIF_TIP,
    NIN_CONTEXTMENU,
    NIN_SELECT,
    NIS_HIDDEN,
    WM_LBUTTONDBLCLK,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
    WS_CAPTION,
    WS_POPUP,
)
from core.utils.win32.utils import get_windows_host_arch, is_running_under_emulation

logger = logging.getLogger("systray_widget")

SYSTRAY_ICON_PROVIDER = "systray"
# Explorer's desktop and taskbar windows
SHELL_WINDOW_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

_ids = itertools.count(1)
_lock = threading.Lock()
_images: dict[int, QImage] = {}


def tray_icon_url(icon_id: int, revision: int) -> str:
    """Include the revision so QML reloads a changed icon."""
    return f"image://{SYSTRAY_ICON_PROVIDER}/{icon_id}/{revision}"


class SystrayIconProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    @override
    def requestImage(self, id: str | None, requestedSize: QSize) -> tuple[QImage, QSize]:
        key = (id or "").split("/", 1)[0]
        with _lock:
            image = _images.get(int(key)) if key.isdigit() else None
        if image is None:
            image = QImage(16, 16, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
        original = image.size()
        if requestedSize.width() > 0 and requestedSize.height() > 0:
            image = image.scaled(
                requestedSize, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        return image, original


@dataclass
class TrayIcon:
    id: int
    data: IconData
    revision: int = 0

    @property
    def state_key(self) -> str:
        """Stable key used to save this icon's position across restarts."""
        return str(self.data.guid) if self.data.guid is not None else self.data.exe_path

    @property
    def hidden(self) -> bool:
        return bool(self.data.dwState & NIS_HIDDEN) or self.data.icon_image is None

    @property
    def tip(self) -> str:
        return self.data.szTip or self.data.exe

    @property
    def source(self) -> str:
        return tray_icon_url(self.id, self.revision)

    @property
    def pid(self) -> int:
        return get_window_thread_process_id(self.data.hWnd)[1]

    def send_click(self, button: Qt.MouseButton) -> None:
        if button == Qt.MouseButton.LeftButton:
            self._send_action(WM_LBUTTONDOWN)
            self._send_action(WM_LBUTTONUP)
        elif button == Qt.MouseButton.RightButton:
            self._send_action(WM_RBUTTONDOWN)
            self._send_action(WM_RBUTTONUP)
        elif button == Qt.MouseButton.MiddleButton:
            self._send_action(WM_MBUTTONDOWN)
            self._send_action(WM_MBUTTONUP)

    def send_double_click(self) -> None:
        self._send_action(WM_LBUTTONDBLCLK)

    def _send_action(self, action: int) -> None:
        """Send a mouse action to the owning process."""
        if not IsWindow(self.data.hWnd):
            return
        # Lets the app bring its own window to the front
        process_id = ct.c_ulong(0)
        GetWindowThreadProcessId(self.data.hWnd, byref(process_id))
        AllowSetForegroundWindow(process_id.value)
        self._send_notify_message(action)

        if self.data.uVersion >= 3:
            if action == WM_LBUTTONUP:
                self._send_notify_message(NIN_SELECT)
            elif action == WM_RBUTTONUP:
                self._send_notify_message(NIN_CONTEXTMENU)

    def _send_notify_message(self, message: int) -> None:
        if self.data.uCallbackMessage == 0:
            return
        if self.data.uVersion > 3:
            cursor_pos = GetCursorPos()
            wparam = pack_i32(cursor_pos[0], cursor_pos[1])
            lparam = pack_i32(message, self.data.uID)
        else:
            wparam = self.data.uID
            lparam = pack_i32(message, 0)
        # Some icons (including Epic Games Store) miss this message if they predate the widget.
        SendNotifyMessage(self.data.hWnd, self.data.uCallbackMessage, wparam, lparam)


def merge_icon_data(old_data: IconData, new_data: IconData) -> None:
    """
    Update fields included in the new data, as indicated by its flags. A message without NIF_ICON, like
    NIM_SETVERSION right after NIM_ADD or a tooltip change, keeps the icon.
    """
    old_data.message_type = new_data.message_type
    old_data.uFlags = new_data.uFlags
    old_data.hWnd = new_data.hWnd or old_data.hWnd
    old_data.uID = new_data.uID or old_data.uID
    # Empty when the process could not be read this time
    if new_data.exe_path:
        old_data.exe = new_data.exe
        old_data.exe_path = new_data.exe_path
    if 0 < new_data.uVersion <= 4:
        old_data.uVersion = new_data.uVersion

    flag_dependent_attrs = {
        NIF_MESSAGE: ["uCallbackMessage"],
        NIF_ICON: ["hIcon", "icon_image"],
        NIF_TIP: ["szTip"],
        NIF_GUID: ["guid"],
        NIF_INFO: ["dwInfoFlags", "szInfoTitle", "szInfo", "uTimeout"],
    }
    for flag, attrs in flag_dependent_attrs.items():
        if new_data.uFlags & flag:
            for attr in attrs:
                setattr(old_data, attr, getattr(new_data, attr))

    # Only the bits in the mask change
    if new_data.uFlags & NIF_STATE:
        mask = new_data.dwStateMask
        old_data.dwState = (old_data.dwState & ~mask) | (new_data.dwState & mask)
        old_data.dwStateMask = mask


def foreground_pid() -> int | None:
    """Return the foreground window's process ID, or None if there is no window."""
    foreground = GetForegroundWindow()
    return get_window_thread_process_id(foreground)[1] if foreground else None


def menu_shown(pid: int) -> bool:
    """Detect a visible Win32 menu or this process's foreground popup."""
    menu = 0
    # Windows may keep hidden menu windows alongside the visible one.
    while menu := FindWindowEx(0, menu, "#32768", None):
        if IsWindowVisible(menu):
            return True
    foreground = GetForegroundWindow()
    if not foreground or not IsWindowVisible(foreground) or get_window_thread_process_id(foreground)[1] != pid:
        return False
    # Explorer's desktop and taskbar share its process and have no caption.
    if GetClassName(foreground) in SHELL_WINDOW_CLASSES:
        return False
    style = GetWindowLong(foreground, GWL_STYLE)
    return bool(style & WS_POPUP) and not style & WS_CAPTION


def other_window_in_front() -> bool:
    """Check for a captioned window, desktop, or taskbar in front."""
    foreground = GetForegroundWindow()
    if not foreground or not IsWindowVisible(foreground):
        return False
    if GetClassName(foreground) in SHELL_WINDOW_CLASSES:
        return True
    return bool(GetWindowLong(foreground, GWL_STYLE) & WS_CAPTION)


def broadcast_taskbar_created() -> None:
    """Ask every app to register its tray icons again."""
    manager = AppBarManager()
    # Our bars receive it too and would register as app bars again.
    manager.suppress()
    try:
        message = RegisterWindowMessage("TaskbarCreated")
        SendNotifyMessage(HWND_BROADCAST, message, 0, 0)
        logger.debug("Sent TaskbarCreated message: %s", message)
    finally:
        QTimer.singleShot(0, manager.unsuppress)


class _ClientThread(QThread):
    def __init__(self, client: SystrayMonitor | SystrayHook, name: str):
        super().__init__()
        self.client = client
        self.name = name

    @override
    def run(self) -> None:
        threading.current_thread().name = self.name
        logger.debug("%s thread is starting...", self.name)
        self.client.run()


def _hook_usable() -> bool:
    if is_running_under_emulation():
        logger.debug("Running under emulation. Systray hook disabled; falling back to legacy mode.")
        return False
    if get_windows_host_arch() not in ("AMD64", "ARM64"):
        logger.debug("Platform not supported by systray hook. Reverting to legacy mode.")
        return False
    if not hook_dll_exists():
        logger.warning("Systray hook DLL missing. Reverting to legacy mode.")
        return False
    return True


class SystrayIcons(QObject):
    """Shared tray monitor or hook and its icons, available to widgets on every bar."""

    iconChanged = pyqtSignal(object)
    iconRemoved = pyqtSignal(object)

    _instance: SystrayIcons | None = None

    @classmethod
    def instance(cls, use_hook: bool = True) -> SystrayIcons:
        """Create the shared instance using the first widget's hook setting."""
        if cls._instance is None:
            cls._instance = SystrayIcons(use_hook)
        return cls._instance

    def __init__(self, use_hook: bool):
        super().__init__()
        self._icons: list[TrayIcon] = []

        if use_hook and _hook_usable():
            self._client: SystrayMonitor | SystrayHook = SystrayHook()
            self._thread = _ClientThread(self._client, "SystrayHook")
        else:
            self._client = SystrayMonitor()
            self._thread = _ClientThread(self._client, "SystrayMonitor")
        self._client.icon_modified.connect(self._on_icon_modified)
        self._client.icon_deleted.connect(self._on_icon_deleted)

        # Coalesce refresh requests from widgets after Explorer restarts.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(broadcast_taskbar_created)
        self._client.update_icons.connect(self._refresh_timer.start)

        # Apps that exit without removing their icons
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self._check_icons)
        self._check_timer.start(5000)

        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self._stop)
        self._thread.start()

    @property
    def icons(self) -> list[TrayIcon]:
        return list(self._icons)

    def find(self, guid: UUID | None, hwnd: int, uid: int) -> TrayIcon | None:
        """Find an icon by GUID, or by window handle and ID."""
        if guid is not None:
            for icon in self._icons:
                if icon.data.guid == guid:
                    return icon
        for icon in self._icons:
            if icon.data.hWnd == hwnd and icon.data.uID == uid:
                return icon
        return None

    def _on_icon_modified(self, data: IconData) -> None:
        icon = self.find(data.guid, data.hWnd, data.uID)
        if icon is None:
            icon = TrayIcon(next(_ids), IconData())
            self._icons.append(icon)
        merge_icon_data(icon.data, data)
        if data.uFlags & NIF_ICON and icon.data.icon_image is not None:
            with _lock:
                _images[icon.id] = icon.data.icon_image
            icon.revision += 1
        self.iconChanged.emit(icon)

    def _on_icon_deleted(self, data: IconData) -> None:
        icon = self.find(data.guid, data.hWnd, data.uID)
        if icon is not None:
            self._remove(icon)

    def _check_icons(self) -> None:
        for icon in self.icons:
            if not IsWindow(icon.data.hWnd):
                self._remove(icon)

    def _remove(self, icon: TrayIcon) -> None:
        self._icons.remove(icon)
        with _lock:
            _images.pop(icon.id, None)
        self.iconRemoved.emit(icon)

    def _stop(self) -> None:
        """Stop the Win32 message loop thread before the app quits"""
        try:
            self._client.destroy()
            if self._thread.isRunning():
                self._thread.wait(3000)
        except Exception as e:
            logger.debug("Error during thread cleanup: %s", e)
        SystrayIcons._instance = None

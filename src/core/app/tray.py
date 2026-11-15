import ctypes
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from functools import cache, partial

from PyQt6.QtCore import QCoreApplication, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter

from core.app.controller import exit_application, reload_application
from core.app.update.installer import show_update
from core.app.update.service import ReleaseInfo, register_update_callback
from core.app.windows.about import About
from core.bar.manager import BarManager
from core.utils.shell_utils import shell_open
from core.utils.win32.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from core.utils.win32.bindings.kernel32 import GetLastError, GetModuleHandle
from core.utils.win32.bindings.shell32 import shell32
from core.utils.win32.bindings.user32 import (
    AppendMenu,
    CreatePopupMenu,
    CreateWindowEx,
    DestroyIcon,
    DestroyMenu,
    DestroyWindow,
    GetCursorPos,
    GetSystemMetrics,
    PostMessage,
    RegisterWindowMessage,
    SetForegroundWindow,
    TrackPopupMenu,
    user32,
)
from core.utils.win32.bindings.uxtheme import AllowDarkModeForWindow, FlushMenuThemes, SetPreferredAppMode
from core.utils.win32.constants import (
    MF_POPUP,
    MF_SEPARATOR,
    MF_STRING,
    NIF_ICON,
    NIF_MESSAGE,
    NIF_TIP,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    SM_CXSMICON,
    TPM_LEFTALIGN,
    TPM_NONOTIFY,
    TPM_RETURNCMD,
    WM_APP,
    WM_NULL,
    WM_RBUTTONUP,
    WS_POPUP,
)
from core.utils.win32.structs import NOTIFYICONDATAW, WNDCLASS, WNDPROC
from core.utils.win32.undocumented import PREFERRED_APP_MODE_ALLOW_DARK
from settings import (
    APP_NAME,
    DEFAULT_CONFIG_DIRECTORY,
    GITHUB_WIKI_URL,
    SCRIPT_PATH,
)

EXE_PATH = os.path.join(SCRIPT_PATH, "yasb.exe")
CLOUD_EXE_PATH = os.path.join(SCRIPT_PATH, "yasb_cloud.exe")
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None
ICON_DIR = os.path.join(SCRIPT_PATH, "assets", "images")
TRAY_WINDOW_CLASS = "YasbTray"
# The message the shell sends the tray window for clicks on the icon
TRAY_MESSAGE = WM_APP + 1
_ACTIONS = {NIM_ADD: "added", NIM_MODIFY: "updated", NIM_DELETE: "removed"}

_trays: dict[int, SystemTrayManager] = {}


def _window_procedure(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    tray = _trays.get(hwnd)
    if tray is not None:
        try:
            tray.handle_message(message, lparam)
        except Exception:
            logging.exception("Tray message %#x failed", message)
    return user32.DefWindowProcW(hwnd, message, wparam, lparam)


_procedure = WNDPROC(_window_procedure)


@cache
def _window_class() -> str:
    window_class = WNDCLASS(lpfnWndProc=_procedure, hInstance=GetModuleHandle(None), lpszClassName=TRAY_WINDOW_CLASS)
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError(GetLastError())
    return TRAY_WINDOW_CLASS


def _run_hidden(command: str) -> None:
    """Starts a command line through cmd.exe, without a console window, and does not wait for it."""
    subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _app_icon(badge: bool = False) -> int:
    """The app icon at the notification area's size, with the update dot when badge is set."""
    size = GetSystemMetrics(SM_CXSMICON)
    # The PNG, because it is what the build ships and preview builds swap in their own
    image = QImage(os.path.join(ICON_DIR, "app_icon.png")).scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    if badge:
        dot = size * 3 / 8
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#ef4747"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(round(size - dot), 0, round(dot), round(dot))
        painter.end()
    icon = image.toHICON()
    return int(icon) if icon is not None else 0


class SystemTrayManager(QObject):
    """YASB's icon in the notification area, with a native menu, made directly with Shell_NotifyIcon."""

    _update_signal = pyqtSignal(object)

    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self._bar_manager = bar_manager
        self._update_available = False
        self._pending_release_info: ReleaseInfo | None = None
        self._about: About | None = None
        self._tooltip = APP_NAME
        # Whether the icon belongs in the notification area, even while the shell refused it
        self._shown = False
        # Explorer sends this to every top-level window after it restarts, and the icon must be added again
        self._taskbar_created = RegisterWindowMessage("TaskbarCreated")
        # A hidden window: the shell sends it the icon's clicks, and it owns the menu while it is open
        self._hwnd = CreateWindowEx(
            0, _window_class(), None, WS_POPUP, 0, 0, 0, 0, None, None, GetModuleHandle(None), None
        )
        if not self._hwnd:
            raise ctypes.WinError(GetLastError())
        _trays[self._hwnd] = self
        self._icon = _app_icon()
        self._dark_menu = self._allow_dark_menu()
        self._update_signal.connect(self._set_update_badge)
        register_update_callback(self._update_signal.emit)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)

    def show(self) -> None:
        self._shown = True
        self._notify(NIM_ADD)

    def close(self) -> None:
        if self._shown:
            self._notify(NIM_DELETE)
            self._shown = False
        if self._hwnd:
            _trays.pop(self._hwnd, None)
            DestroyWindow(self._hwnd)
            self._hwnd = 0
        if self._icon:
            DestroyIcon(self._icon)
            self._icon = 0

    def handle_message(self, message: int, lparam: int) -> None:
        if message == TRAY_MESSAGE and lparam == WM_RBUTTONUP:
            self._show_context_menu()
        elif message == self._taskbar_created and self._shown:
            # After Explorer restarts the icon is gone and is added again, as is one the taskbar wasn't up for yet.
            # YASB's Systray widget sends this too, to have every app add its icons, while the icon is still there:
            # then the icon is updated instead
            if not self._shell_notify(NIM_ADD):
                self._notify(NIM_MODIFY)

    def _notify(self, action: int) -> None:
        if not self._shell_notify(action):
            logging.warning("The tray icon could not be %s", _ACTIONS[action])

    def _shell_notify(self, action: int) -> bool:
        data = NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=1,
            uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage=TRAY_MESSAGE,
            hIcon=self._icon,
            szTip=self._tooltip[:127],
        )
        return bool(shell32.Shell_NotifyIconW(action, ctypes.byref(data)))

    def _set_update_badge(self, release_info: ReleaseInfo | None = None):
        self._update_available = True
        self._pending_release_info = release_info
        badged = _app_icon(badge=True)
        if badged:
            if self._icon:
                DestroyIcon(self._icon)
            self._icon = badged
        self._tooltip = "Update available"
        if self._shown:
            self._notify(NIM_MODIFY)

    def _allow_dark_menu(self) -> bool:
        """Lets the menu follow Windows' dark mode, and tells whether it can: the uxtheme exports for it are
        undocumented, and a build without them keeps the light menu."""
        try:
            SetPreferredAppMode(PREFERRED_APP_MODE_ALLOW_DARK)
            AllowDarkModeForWindow(self._hwnd, True)
            FlushMenuThemes()
        except OSError:
            logging.debug("Native dark tray menu unavailable", exc_info=True)
            return False
        return True

    def _show_context_menu(self) -> None:
        actions: list[Callable[[], object]] = []

        def add_item(menu: int, label: str, action: Callable[[], object]) -> None:
            actions.append(action)
            AppendMenu(menu, MF_STRING, len(actions), label)

        def add_separator(menu: int) -> None:
            AppendMenu(menu, MF_SEPARATOR, 0, "")

        menu = CreatePopupMenu()
        try:
            if self._update_available:
                add_item(menu, "Update Available", self._open_update_dialog)
                add_separator(menu)
            add_item(menu, "Open Config", partial(shell_open, DEFAULT_CONFIG_DIRECTORY))
            if os.path.exists(CLOUD_EXE_PATH):
                add_item(menu, "YASB Cloud", partial(shell_open, CLOUD_EXE_PATH))
            add_item(menu, "Reload YASB", partial(reload_application, "Reloading Application from tray..."))
            add_separator(menu)

            # A submenu for each window manager that is installed and has commands set
            config = self._bar_manager.config
            for name, program, commands in (
                ("Komorebi", "komorebi", config.komorebi),
                ("GlazeWM", "glazewm", config.glazewm),
            ):
                items = [
                    (f"{verb} {name}", command)
                    for verb, command in (
                        ("Start", commands.start_command),
                        ("Stop", commands.stop_command),
                        ("Reload", commands.reload_command),
                    )
                    if command
                ]
                if not items or shutil.which(program) is None:
                    continue
                submenu = CreatePopupMenu()
                for label, command in items:
                    add_item(submenu, label, partial(_run_hidden, command))
                AppendMenu(menu, MF_POPUP, submenu, name)
                add_separator(menu)

            if AUTOSTART_FILE:
                if is_autostart_enabled(APP_NAME):
                    add_item(menu, "Disable Autostart", partial(disable_autostart, APP_NAME))
                else:
                    add_item(menu, "Enable Autostart", partial(enable_autostart, APP_NAME, AUTOSTART_FILE))
            add_item(menu, "Help", partial(shell_open, GITHUB_WIKI_URL))
            add_item(menu, "About", self._show_about_dialog)
            add_separator(menu)
            add_item(menu, "Exit", partial(exit_application, "Exiting Application from tray..."))

            if self._dark_menu:
                # Takes up a switch between light and dark mode since the last menu
                FlushMenuThemes()
            x, y = GetCursorPos()
            # A notification icon's menu closes on a click elsewhere only when its window is in front, and a second
            # menu stays open only after a message switches to that window
            SetForegroundWindow(self._hwnd)
            chosen = TrackPopupMenu(menu, TPM_LEFTALIGN | TPM_RETURNCMD | TPM_NONOTIFY, x, y, self._hwnd)
            PostMessage(self._hwnd, WM_NULL, 0, 0)
        finally:
            # Its submenus go with it
            DestroyMenu(menu)
        if chosen:
            actions[chosen - 1]()

    def _show_about_dialog(self):
        if self._about is None:
            self._about = About(self)
            self._about.updateRequested.connect(self._open_update_dialog)
        self._about.show(self._bar_manager.engine)

    def _open_update_dialog(self, release_info: ReleaseInfo | None = None):
        release_info = release_info or self._pending_release_info
        if release_info is not None:
            show_update(self._bar_manager.engine, release_info)

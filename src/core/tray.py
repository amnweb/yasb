import ctypes
import logging
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from functools import cache, partial

from PyQt6.QtCore import QCoreApplication, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter

from core.about import About
from core.bar.manager import BarManager
from core.updater import show_update
from core.utils.controller import exit_application, reload_application
from core.utils.shell_utils import shell_open
from core.utils.update_service import ReleaseInfo, register_update_callback
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
from core.utils.win32.utils import disable_autostart, enable_autostart, is_autostart_enabled
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
        self._menu_timer = QTimer(self)
        self._menu_timer.setSingleShot(True)
        self._menu_timer.timeout.connect(self._show_context_menu)
        self._load_config()
        self._update_signal.connect(self._set_update_badge)
        register_update_callback(self._update_signal.emit)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)

    def show(self) -> None:
        self._shown = self._notify(NIM_ADD)

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
            # The menu runs its own loop, so it opens after the shell's message has been answered
            self._menu_timer.start()
        elif message == self._taskbar_created and self._shown:
            self._shown = self._notify(NIM_ADD)

    def _notify(self, action: int) -> bool:
        data = NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=1,
            uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage=TRAY_MESSAGE,
            hIcon=self._icon,
            szTip=self._tooltip[:127],
        )
        if not shell32.Shell_NotifyIconW(action, ctypes.byref(data)):
            logging.warning("The tray icon could not be updated (%d)", action)
            return False
        return True

    def _load_config(self):
        config = self._bar_manager.config
        self.komorebi_enabled = False
        self.glazewm_enabled = False

        if config and config.komorebi:
            self.komorebi_start = config.komorebi.start_command
            self.komorebi_stop = config.komorebi.stop_command
            self.komorebi_reload = config.komorebi.reload_command
            self.komorebi_enabled = any([self.komorebi_start, self.komorebi_stop, self.komorebi_reload])

        if config and config.glazewm:
            self.glazewm_start = config.glazewm.start_command
            self.glazewm_stop = config.glazewm.stop_command
            self.glazewm_reload = config.glazewm.reload_command
            self.glazewm_enabled = any([self.glazewm_start, self.glazewm_stop, self.glazewm_reload])

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

    def _try_enable_dark_menu(self, hwnd: int):
        try:
            SetPreferredAppMode(PREFERRED_APP_MODE_ALLOW_DARK)
            AllowDarkModeForWindow(hwnd, True)
            FlushMenuThemes()
        except Exception:
            logging.debug("Native dark tray menu unavailable", exc_info=True)

    def _show_context_menu(self):
        """Builds and shows the system tray context menu with dynamic options based on configuration and state."""
        hmenu = None
        selected_action = None
        try:
            hmenu = CreatePopupMenu()
            actions: dict[int, Callable[[], object]] = {}
            cmd_id = [1]

            def add_item(menu: int, label: str, action: Callable[[], object]) -> None:
                AppendMenu(menu, MF_STRING, cmd_id[0], label)
                actions[cmd_id[0]] = action
                cmd_id[0] += 1

            def add_sep(menu: int) -> None:
                AppendMenu(menu, MF_SEPARATOR, 0, "")

            if self._update_available:
                add_item(hmenu, "Update Available", self._open_update_dialog)
                add_sep(hmenu)

            add_item(hmenu, "Open Config", self.open_config)
            if os.path.exists(CLOUD_EXE_PATH):
                add_item(hmenu, "YASB Cloud", lambda: shell_open(CLOUD_EXE_PATH))
            add_item(hmenu, "Reload YASB", self._reload_application)
            add_sep(hmenu)

            if self.komorebi_enabled and self.is_wm_installed("komorebi"):
                km_sub = CreatePopupMenu()
                if self.komorebi_start:
                    add_item(km_sub, "Start Komorebi", partial(self._run_wm_command, "Komorebi", self.komorebi_start))
                if self.komorebi_stop:
                    add_item(km_sub, "Stop Komorebi", partial(self._run_wm_command, "Komorebi", self.komorebi_stop))
                if self.komorebi_reload:
                    add_item(km_sub, "Reload Komorebi", partial(self._run_wm_command, "Komorebi", self.komorebi_reload))
                AppendMenu(hmenu, MF_POPUP, km_sub, "Komorebi")
                add_sep(hmenu)

            if self.glazewm_enabled and self.is_wm_installed("glazewm"):
                gw_sub = CreatePopupMenu()
                if self.glazewm_start:
                    add_item(gw_sub, "Start GlazeWM", partial(self._run_wm_command, "Glazewm", self.glazewm_start))
                if self.glazewm_stop:
                    add_item(gw_sub, "Stop GlazeWM", partial(self._run_wm_command, "Glazewm", self.glazewm_stop))
                if self.glazewm_reload:
                    add_item(gw_sub, "Reload GlazeWM", partial(self._run_wm_command, "Glazewm", self.glazewm_reload))
                AppendMenu(hmenu, MF_POPUP, gw_sub, "GlazeWM")
                add_sep(hmenu)

            if AUTOSTART_FILE:
                if self._check_startup():
                    add_item(hmenu, "Disable Autostart", self._disable_startup)
                else:
                    add_item(hmenu, "Enable Autostart", self._enable_startup)

            add_item(hmenu, "Help", lambda: self.open_in_browser(GITHUB_WIKI_URL))
            add_item(hmenu, "About", self._show_about_dialog)
            add_sep(hmenu)
            add_item(hmenu, "Exit", self._exit_application)

            hwnd = self._hwnd
            x, y = GetCursorPos()
            self._try_enable_dark_menu(hwnd)
            try:
                SetForegroundWindow(hwnd)
            except Exception:
                logging.debug("Failed to set tray menu owner as foreground window", exc_info=True)
            cmd = TrackPopupMenu(hmenu, TPM_LEFTALIGN | TPM_RETURNCMD | TPM_NONOTIFY, x, y, hwnd)
            selected_action = actions.get(cmd)
            try:
                PostMessage(hwnd, WM_NULL, 0, 0)
            except Exception:
                logging.debug("Failed to post tray menu cleanup message", exc_info=True)
        except Exception:
            logging.exception("Failed to show context menu")
        finally:
            if hmenu:
                DestroyMenu(hmenu)

        if selected_action:
            try:
                selected_action()
            except Exception:
                logging.exception("Tray menu action failed")

    def is_wm_installed(self, wm: str) -> bool:
        try:
            wm_path = shutil.which(wm)
            return wm_path is not None
        except Exception as e:
            logging.error("Error checking %s installation: %s", wm, e)
            return False

    def _enable_startup(self):
        if AUTOSTART_FILE:
            enable_autostart(APP_NAME, AUTOSTART_FILE)

    def _disable_startup(self):
        disable_autostart(APP_NAME)

    def _check_startup(self) -> bool:
        return bool(is_autostart_enabled(APP_NAME))

    def open_config(self):
        try:
            shell_open(DEFAULT_CONFIG_DIRECTORY)
        except Exception as e:
            logging.error("Failed to open config directory: %s", e)

    def _run_wm_command(self, wm: str, command: str):
        def wm_command():
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logging.error("Failed to start %s: %s", wm, e)

        threading.Thread(target=wm_command).start()

    def _reload_application(self):
        reload_application("Reloading Application from tray...")

    def _exit_application(self):
        exit_application("Exiting Application from tray...")

    def open_in_browser(self, url: str):
        try:
            shell_open(url)
        except Exception as e:
            logging.error("Failed to open browser: %s", e)

    def _show_about_dialog(self):
        if self._about is None:
            self._about = About(self)
            self._about.updateRequested.connect(self._open_update_dialog)
        self._about.show(self._bar_manager.engine)

    def _open_update_dialog(self, release_info: ReleaseInfo | None = None):
        release_info = release_info or self._pending_release_info
        if release_info is not None:
            show_update(self._bar_manager.engine, release_info)

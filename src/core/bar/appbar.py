import ctypes
import logging
import os
from typing import TYPE_CHECKING, Any, override

from PyQt6 import sip
from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer

from core.utils.win32.app_bar import APPBAR_CALLBACK_MESSAGE, AppBarNotify
from core.utils.win32.bindings.user32 import (
    GetClassName,
    GetForegroundWindow,
    RegisterWindowMessage,
    SetWindowPos,
    get_window_thread_process_id,
)
from core.utils.win32.constants import HWND_BOTTOM, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE
from core.utils.win32.structs import MSG

if TYPE_CHECKING:
    from core.bar.window import BarWindow

WM_TASKBARCREATED = RegisterWindowMessage("TaskbarCreated")

EXCLUDED_WINDOW_CLASSES = {
    "Progman",
    "WorkerW",
    "XamlWindow",
    "Shell_TrayWnd",
    "XamlExplorerHostIslandWindow",
    "CEF-OSC-WIDGET",
    "CEFCLIENT",
}
EXCLUDED_WINDOW_CLASS_SUFFIXES = ("QWindowIcon",)


class AppBarManager(QAbstractNativeEventFilter):
    """Routes fullscreen notifications and Explorer restarts to the registered bars."""

    _instance: AppBarManager | None = None
    _bars: dict[int, BarWindow]
    _intended_visible: dict[int, bool]
    _installed: bool
    _reregister_pending: bool

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._bars = {}
            instance._intended_visible = {}
            instance._installed = False
            instance._reregister_pending = False
            cls._instance = instance
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            super().__init__()
            self._initialized = True

    def register_bar(self, hwnd: int, bar: BarWindow) -> None:
        if not self._installed:
            app = QCoreApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)
                self._installed = True
        self._bars[hwnd] = bar
        self._intended_visible[hwnd] = True

    def unregister_bar(self, hwnd: int) -> None:
        self._bars.pop(hwnd, None)
        self._intended_visible.pop(hwnd, None)

    @override
    def nativeEventFilter(self, eventType: Any, message: sip.voidptr | None) -> tuple[bool, sip.voidptr]:
        try:
            if eventType == b"windows_generic_MSG" and message is not None:
                msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
                if msg.message == WM_TASKBARCREATED:
                    # Broadcast to every top-level window, so many arrive at once; re-register once
                    if not self._reregister_pending and self._bars:
                        self._reregister_pending = True
                        QTimer.singleShot(0, self._reregister)
                elif msg.message == APPBAR_CALLBACK_MESSAGE and msg.wParam == AppBarNotify.FullScreenApp:
                    self._handle_fullscreen(msg.hwnd, bool(msg.lParam))
        except Exception:
            pass
        return False, sip.voidptr(0)

    def _reregister(self) -> None:
        self._reregister_pending = False
        bars = [
            bar
            for bar in self._bars.values()
            if (bar.config.reserve_space or bar.hide_on_fullscreen) and not bar.autohide_enabled
        ]
        if not bars:
            return
        logging.info("AppBarManager re-registering %d bar(s) after Explorer restart", len(bars))
        for bar in bars:
            try:
                bar.remove_app_bar()
                bar.update_app_bar()
            except Exception as e:
                logging.error("Failed to re-register bar %s: %s", bar.bar_id, e)

    def _foreground_is_excluded(self) -> bool:
        try:
            hwnd = GetForegroundWindow()
            if not hwnd:
                return False
            _, pid = get_window_thread_process_id(hwnd)
            if pid == os.getpid():
                return True
            class_name = GetClassName(hwnd) or ""
            return class_name in EXCLUDED_WINDOW_CLASSES or class_name.endswith(EXCLUDED_WINDOW_CLASS_SUFFIXES)
        except Exception:
            return False

    def _handle_fullscreen(self, hwnd: int, opening: bool) -> None:
        bar = self._bars.get(hwnd)
        if bar is None or not bar.hide_on_fullscreen:
            return
        if opening and self._foreground_is_excluded():
            return
        flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        visible = self._intended_visible.get(hwnd, True)
        if opening and visible:
            SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
            self._intended_visible[hwnd] = False
        elif not opening and not visible:
            SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            self._intended_visible[hwnd] = True

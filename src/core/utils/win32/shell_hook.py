import ctypes
import logging
from typing import Any, override

from PyQt6 import sip
from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, pyqtBoundSignal, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QWindow

from core.utils.win32.bindings.user32 import DeregisterShellHookWindow, RegisterShellHookWindow, RegisterWindowMessage
from core.utils.win32.structs import MSG


class _ShellSignal(QObject):
    triggered = pyqtSignal(int)


class _ShellHook(QAbstractNativeEventFilter):
    def __init__(self) -> None:
        super().__init__()
        self.signals: dict[int, _ShellSignal] = {}
        self.message = 0
        self.hwnd = 0
        self._window: QWindow | None = None
        # Only a real window gets the messages, not the offscreen one the tests use
        if QGuiApplication.platformName() != "windows":
            return
        self._window = QWindow()
        hwnd = int(self._window.winId())
        message = RegisterWindowMessage("SHELLHOOK")
        if message and RegisterShellHookWindow(hwnd):
            self.message, self.hwnd = message, hwnd
        else:
            logging.error("Could not register for the shell's messages")

    @override
    def nativeEventFilter(self, eventType: Any, message: sip.voidptr | None) -> tuple[bool, sip.voidptr]:
        if self.hwnd and eventType == "windows_generic_MSG" and message is not None:
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
            if msg.message == self.message and int(msg.hwnd or 0) == self.hwnd:
                if (signal := self.signals.get(int(msg.wParam))) is not None:
                    signal.triggered.emit(int(msg.lParam or 0))
                return True, sip.voidptr(0)
        return False, sip.voidptr(0)

    def stop(self) -> None:
        if self.hwnd:
            DeregisterShellHookWindow(self.hwnd)
            self.hwnd = 0


_hook: _ShellHook | None = None


def shell_event(code: int) -> pyqtBoundSignal:
    """The signal for one HSHELL_* message, with the window it is about. Its object lives as long as the app, and Qt
    drops a connection when its receiver is destroyed."""
    global _hook
    if _hook is None:
        _hook = _ShellHook()
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(_hook)
            app.aboutToQuit.connect(_hook.stop)
    if code not in _hook.signals:
        _hook.signals[code] = _ShellSignal()
    return _hook.signals[code].triggered

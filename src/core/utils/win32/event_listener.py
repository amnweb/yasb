import ctypes
import time
import logging
import typing
from PyQt6.QtCore import QThread, QAbstractNativeEventFilter
from PyQt6.QtWidgets import QWidget, QApplication
import PyQt6.sip
from win32gui import GetForegroundWindow
from core.utils.win32.windows import WinEventProcType, WinEvent, ShellEvent, user32, ole32, msg
from core.event_service import EventService

class ShellEventFilter(QAbstractNativeEventFilter):
    def __init__(self):
        QAbstractNativeEventFilter.__init__(self)
        self._event_service = EventService()

        # We create a hidden QWidget and make it a native window with winId.
        # This is because shell events need an active windows message loop, and the
        # easiest way to do this is to create a hwnd.
        self._event_window = QWidget()
        ctypes.windll.user32.RegisterShellHookWindow(self._event_window.winId().__int__())
        self._message_num = ctypes.windll.user32.RegisterWindowMessageW("SHELLHOOK")

    def nativeEventFilter(self, eventType, message) -> typing.Tuple[bool, typing.Optional[PyQt6.sip.voidptr]]:
        if eventType == "windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == self._message_num and msg.wParam in ShellEvent:
                event_type = ShellEvent._value2member_map_[msg.wParam]
                self._event_service.emit_event(event_type, msg.lParam, event_type)
        return (False, 0)

class SystemEventListener(QThread):

    def __init__(self):
        super().__init__()
        self._hook = None
        self._event_service = EventService()
        self._win_event_process = WinEventProcType(self._event_handler)
        self._nativeEventFilter = None
        self._nativeEventFilter = ShellEventFilter()
        QApplication.instance().installNativeEventFilter(self._nativeEventFilter)

    def __str__(self):
        return "Win32 System Event Listener"

    def _event_handler(
        self,
        _win_event_hook,
        event,
        hwnd,
        _id_object,
        _id_child,
        _event_thread,
        _event_time
    ) -> None:
        if event in WinEvent:
            event_type = WinEvent._value2member_map_[event]
            try:
                self._event_service.emit_event(event_type, hwnd, event_type)
            except Exception:
                logging.exception(f"Failed to emit event {event_type} for {hwnd}")

    def _build_event_hook(self) -> int:
        return user32.SetWinEventHook(
            WinEvent.EventMin.value,
            WinEvent.EventObjectEnd.value,
            0,
            self._win_event_process,
            0,
            0,
            WinEvent.WinEventOutOfContext.value
        )

    def _emit_foreground_window_event(self):
        foreground_event = WinEvent.EventSystemForeground
        foreground_window_hwnd = GetForegroundWindow()

        if foreground_window_hwnd:
            self._event_service.emit_event(foreground_event, foreground_window_hwnd, foreground_event)

    def run(self):
        self._hook = self._build_event_hook()

        if self._hook == 0:
            logging.warning("SetWinEventHook failed. Retrying indefinitely...")

        while self._hook == 0:
            time.sleep(1)
            self._hook = self._build_event_hook()

        self._emit_foreground_window_event()

        user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)

    def stop(self):
        user32.UnhookWinEvent(self._hook)
        ole32.CoUninitialize()
        # removeNativeEventFilter should be thread-safe
        QApplication.instance().removeNativeEventFilter(self._nativeEventFilter)
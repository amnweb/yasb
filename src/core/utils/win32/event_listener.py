import ctypes
import logging
import time

from PyQt6.QtCore import QThread
from win32gui import GetForegroundWindow

from core.event_service import EventService
from core.utils.win32.bindings.kernel32 import GetCurrentThreadId
from core.utils.win32.bindings.ole32 import ole32
from core.utils.win32.bindings.user32 import user32
from core.utils.win32.structs import WINEVENTPROC
from core.utils.win32.windows import WinEvent

msg = ctypes.wintypes.MSG()


class SystemEventListener(QThread):
    def __init__(self):
        super().__init__()
        self._hook = None
        self._event_service = EventService()
        self._win_event_process = WINEVENTPROC(self._event_handler)

    def __str__(self):
        return "Win32 System Event Listener"

    def _event_handler(self, _win_event_hook, event, hwnd, _id_object, _id_child, _event_thread, _event_time) -> None:
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
            WinEvent.WinEventOutOfContext.value,
        )

    def _emit_foreground_window_event(self):
        foreground_event = WinEvent.EventSystemForeground
        foreground_window_hwnd = GetForegroundWindow()

        if foreground_window_hwnd:
            self._event_service.emit_event(foreground_event, foreground_window_hwnd, foreground_event)

    def run(self):
        ole32.CoInitialize(0)
        try:
            self._thread_id = GetCurrentThreadId()
            self._hook = self._build_event_hook()

            if self._hook == 0:
                logging.warning("SetWinEventHook failed. Retrying indefinitely...")

            while self._hook == 0:
                time.sleep(1)
                self._hook = self._build_event_hook()

            self._emit_foreground_window_event()

            user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
        finally:
            ole32.CoUninitialize()

    def stop(self):
        user32.UnhookWinEvent(self._hook)
        # Post WM_QUIT to unblock GetMessageW
        user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

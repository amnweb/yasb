import ctypes
import logging
import threading
from ctypes import wintypes

from PyQt6.QtCore import QCoreApplication, QObject, QThread, pyqtBoundSignal, pyqtSignal

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.utils.win32.bindings.kernel32 import GetCurrentThreadId
from core.utils.win32.bindings.user32 import GetAncestor, PostThreadMessage, user32
from core.utils.win32.constants import (
    CHILDID_SELF,
    GA_ROOT,
    OBJID_WINDOW,
    PM_NOREMOVE,
    WINEVENT_OUTOFCONTEXT,
    WINEVENT_SKIPOWNPROCESS,
    WM_APP,
    WM_QUIT,
    WM_USER,
)
from core.utils.win32.structs import WINEVENTPROC

# Posted to the hook thread when a widget asks for an event it doesn't hook yet
WM_HOOK_EVENTS = WM_APP + 1


class SystemEventListener(QThread):
    def __init__(self):
        super().__init__()
        self._hooks: dict[WinEvent, int] = {}
        self._event_service = EventService()
        self._win_event_process = WINEVENTPROC(self._event_handler)
        self._lock = threading.Lock()
        self._thread_id = 0
        self._stopping = False

    def __str__(self):
        return "Win32 System Event Listener"

    def _event_handler(
        self,
        _win_event_hook: int | None,
        event: int,
        hwnd: int | None,
        id_object: int,
        id_child: int,
        _event_thread: int,
        _event_time: int,
    ) -> None:
        # Only events about windows themselves, not the objects inside them
        if not hwnd or id_object != OBJID_WINDOW or id_child != CHILDID_SELF:
            return
        # Nor windows inside another window, such as a button or panel, no widget uses them
        root = GetAncestor(hwnd, GA_ROOT)
        if root and root != hwnd:
            return
        event_type = WinEvent(event)
        try:
            self._event_service.emit_event(event_type, hwnd, event_type)
        except Exception:
            logging.exception("Failed to emit event %s for %s", event_type, hwnd)

    def request_hooks(self) -> None:
        with self._lock:
            if self._thread_id:
                PostThreadMessage(self._thread_id, WM_HOOK_EVENTS, 0, 0)

    def _hook_wanted(self) -> None:
        with _wanted_lock:
            missing = [event for event in _wanted if event not in self._hooks]
        flags = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
        for event in missing:
            if hook := user32.SetWinEventHook(event.value, event.value, 0, self._win_event_process, 0, 0, flags):
                self._hooks[event] = hook
            else:
                logging.error("SetWinEventHook failed for %s", event.name)

    def run(self):
        msg = wintypes.MSG()
        try:
            # Makes the thread's message queue, so messages posted to it from now on are not lost
            user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)
            with self._lock:
                if self._stopping:
                    return
                self._thread_id = GetCurrentThreadId()
            self._hook_wanted()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOOK_EVENTS:
                    self._hook_wanted()
        finally:
            # Windows frees the id with the thread and may give it to another one, so nothing is posted to it after
            with self._lock:
                self._thread_id = 0
            # Only the thread that set a hook can remove it
            for hook in self._hooks.values():
                user32.UnhookWinEvent(hook)
            self._hooks.clear()

    def stop(self):
        with self._lock:
            self._stopping = True
            if self._thread_id:
                PostThreadMessage(self._thread_id, WM_QUIT, 0, 0)


class _WinEventSignal(QObject):
    triggered = pyqtSignal(int, WinEvent)


_listener: SystemEventListener | None = None
_signals: dict[WinEvent, _WinEventSignal] = {}
_wanted: set[WinEvent] = set()
_wanted_lock = threading.Lock()
# Set on quit, so a service stopping after the hook cannot start it again
_quitting = False


def win_event(event: WinEvent) -> pyqtBoundSignal:
    """The shared hook's signal for one WinEvent. Its object lives as long as the app, so the hook thread never
    emits into an object QML is destroying; Qt drops a connection when its receiver is destroyed."""
    if event not in _signals:
        _signals[event] = _WinEventSignal()
        EventService().register_event(event, _signals[event].triggered)
        with _wanted_lock:
            _wanted.add(event)
        if _listener is not None:
            _listener.request_hooks()
    ensure_system_event_listener()
    return _signals[event].triggered


def ensure_system_event_listener() -> None:
    """Start the one shared WinEvent hook the first time a widget needs it."""
    global _listener
    if _listener is not None or _quitting:
        return
    _listener = SystemEventListener()
    _listener.start()
    app = QCoreApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(_stop_system_event_listener)


def _stop_system_event_listener() -> None:
    global _listener, _quitting
    _quitting = True
    if _listener is None:
        return
    _listener.stop()
    _listener.wait(1000)
    _listener = None

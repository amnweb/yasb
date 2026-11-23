import os
from contextlib import suppress

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.bar.appbar import EXCLUDED_WINDOW_CLASSES
from core.utils.win32.bindings.user32 import (
    GetClassName,
    GetForegroundWindow,
    GetWindowText,
    IsWindowVisible,
    IsZoomed,
    MonitorFromWindow,
    enum_windows,
    get_window_thread_process_id,
)
from core.utils.win32.constants import HSHELL_RUDEAPPACTIVATED, HSHELL_WINDOWACTIVATED
from core.utils.win32.shell_hook import shell_event
from core.utils.win32.utils import is_window_cloaked

FOCUS_CODES = (HSHELL_WINDOWACTIVATED, HSHELL_RUDEAPPACTIVATED)
POLL_MS = 500


def _counts(hwnd: int) -> bool:
    """Whether the window is a maximized one on screen, of an app rather than of the shell or of YASB."""
    if not IsZoomed(hwnd) or not IsWindowVisible(hwnd) or not GetWindowText(hwnd):
        return False
    if GetClassName(hwnd) in EXCLUDED_WINDOW_CLASSES or get_window_thread_process_id(hwnd)[1] == os.getpid():
        return False
    return not is_window_cloaked(hwnd)


class MaximizedWindows(QObject):
    """The maximized windows of every monitor, followed only while a bar needs them."""

    changed = pyqtSignal()
    _instance: MaximizedWindows | None = None

    @classmethod
    def instance(cls) -> MaximizedWindows:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        # Each maximized window's monitor
        self._windows: dict[int, int] = {}
        self._focused = 0
        self._followers: set[QObject] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def follow(self, follower: QObject) -> None:
        if not self._followers:
            self._start()
        self._followers.add(follower)

    def unfollow(self, follower: QObject) -> None:
        if follower in self._followers:
            self._followers.discard(follower)
            if not self._followers:
                self._stop()

    def maximized_on(self, monitor: int | None) -> bool:
        return monitor in self._windows.values()

    def _start(self) -> None:
        for code in FOCUS_CODES:
            shell_event(code).connect(self._on_focus)
        self._on_focus(GetForegroundWindow())
        self._timer.start()

    def _stop(self) -> None:
        for code in FOCUS_CODES:
            with suppress(TypeError):
                shell_event(code).disconnect(self._on_focus)
        self._timer.stop()
        self._windows.clear()
        self._focused = 0

    def _on_focus(self, hwnd: int) -> None:
        # A focus change also follows a switch of virtual desktop or workspace, which shows other maximized windows
        self._focused = hwnd
        windows = {window: MonitorFromWindow(window) or 0 for window in enum_windows() if _counts(window)}
        if windows != self._windows:
            self._windows = windows
            self.changed.emit()

    def _poll(self) -> None:
        changed = [self._update(window) for window in {*self._windows, self._focused} if window]
        if any(changed):
            self.changed.emit()

    def _update(self, hwnd: int) -> bool:
        """Takes in the window's state, and tells whether a monitor gained or lost a maximized window."""
        known = self._windows.get(hwnd)
        if known is None and not IsZoomed(hwnd):
            return False
        monitor = (MonitorFromWindow(hwnd) or 0) if _counts(hwnd) else None
        if monitor == known:
            return False
        if monitor is None:
            del self._windows[hwnd]
        else:
            self._windows[hwnd] = monitor
        return True

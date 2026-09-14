import ctypes
import logging
import os
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any

from comtypes import COMError
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.utils.win32.bindings.user32 import GetClassName, GetForegroundWindow, GetWindowThreadProcessId
from core.widgets.services.windows_desktops.com import (
    DesktopInfo,
    VirtualDesktopApi,
    VirtualDesktopError,
    get_api,
)
from core.widgets.services.windows_desktops.interfaces import VirtualDesktopUnsupportedError
from core.widgets.services.windows_desktops.notification import DesktopEvent, DesktopNotificationListener

logger = logging.getLogger("windows_desktop_service")

# The shell is not always reachable: briefly during sign-in, or while a previous
# instance is still releasing its COM connection after being killed. Nothing is
# cached on failure, so a later call picks the shell up again once it answers.
SHELL_UNAVAILABLE = (VirtualDesktopError, VirtualDesktopUnsupportedError, COMError, OSError, AttributeError)

SKIP_WINDOW_CLASSES = frozenset(
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
    }
)

# How often to re-read state when the shell will not push notifications. This is
# only reached when registering a notification sink fails, which happens while
# the shell is briefly unreachable, such as when the previous instance was killed
# rather than closed. Polling covers that gap and stops as soon as a sink
# registers.
POLL_INTERVAL_MS = 500

# Events that change which desktops exist or how they are ordered.
SET_CHANGED_EVENTS = frozenset({DesktopEvent.CREATED, DesktopEvent.DESTROYED, DesktopEvent.MOVED})


def _is_own_window(hwnd: int) -> bool:
    """Does this window belong to us?

    Our own windows are never valid move or pin targets and have no application
    view, so asking the shell about them would only fail.
    """
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


@dataclass(frozen=True)
class ForegroundView:
    """A foreground window and the shell view behind it.

    The context menu reads pin state from this object to label its entries.
    """

    hwnd: int
    view: Any = field(repr=False)
    api: VirtualDesktopApi = field(repr=False)

    def is_pinned(self) -> bool:
        """Is this window pinned to every desktop?"""
        return self.api.is_view_pinned(self.view)

    def is_app_pinned(self) -> bool:
        """Is this window's whole app pinned to every desktop?"""
        return self.api.is_app_pinned(self.view)


class WindowsDesktopService(QObject):
    """Manages Windows virtual desktops and broadcasts changes.

    One instance is shared by every widget. Desktop state is cached and dropped
    whenever the shell reports a change, so redrawing a bar of buttons costs one
    enumeration rather than one per button.
    """

    _instance = None
    _init_done = False

    desktop_changed = pyqtSignal(dict)
    desktops_updated = pyqtSignal(dict, dict)

    # Carries a notification from whichever thread COM called in on to the Qt
    # main thread. Same-thread emits stay direct; cross-thread ones queue.
    _com_event = pyqtSignal(object)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if WindowsDesktopService._init_done:
            return
        super().__init__()
        WindowsDesktopService._init_done = True

        self._api = get_api()
        self._widgets: list = []
        self._timer: QTimer | None = None
        self._listener: DesktopNotificationListener | None = None

        self._com_event.connect(self._on_com_event)

        # Cached snapshot, dropped whenever the shell reports a change.
        self._desktops: list[DesktopInfo] | None = None
        self._current_guid: str | None = None

        # One user action can produce several notifications: switching desktops
        # also reports a wallpaper change and a switch. These collect what needs
        # doing so a single refresh covers all of it.
        self._pending_current_changed = False
        self._pending_set_changed = False
        self._pending_buttons = False
        self._refresh_queued = False

        # Last state broadcast, used to suppress no-op signals.
        self._last_count = 0
        self._last_number = 0
        try:
            snapshot = self._snapshot()
            self._last_count = len(snapshot)
            self._last_number = self._current_number()
        except SHELL_UNAVAILABLE:
            logger.debug("Could not read initial virtual desktop state", exc_info=True)

    def _snapshot(self) -> list[DesktopInfo]:
        """The desktop list, read from the shell only when the cache is cold."""
        if self._desktops is None:
            self._desktops = self._api.list_desktops()
        return self._desktops

    def _current(self) -> str:
        """The current desktop's GUID, cached alongside the list."""
        if self._current_guid is None:
            self._current_guid = self._api.current_guid()
        return self._current_guid

    def _current_number(self) -> int:
        """The current desktop's 1-based position.

        Raises if the current desktop is not in the snapshot, so callers skip
        the update rather than broadcasting a position no button can match.
        """
        guid = self._current()
        number = next((d.number for d in self._snapshot() if d.guid == guid), 0)
        if not number:
            raise VirtualDesktopError(f"Current desktop {guid} is not in the desktop list")
        return number

    def _invalidate(self) -> None:
        self._desktops = None
        self._current_guid = None

    def _resolve(self, number: int) -> DesktopInfo:
        """Find a desktop by its 1-based position."""
        desktop = next((d for d in self._snapshot() if d.number == number), None)
        if desktop is None:
            # The cache may predate a change we have not been told about yet.
            self._invalidate()
            desktop = next((d for d in self._snapshot() if d.number == number), None)
        if desktop is None:
            raise VirtualDesktopError(f"No desktop at position {number}")
        return desktop

    def _on_com_event(self, event: DesktopEvent) -> None:
        """Record what a notification implies, then schedule one refresh."""
        if event is DesktopEvent.CURRENT_CHANGED:
            self._pending_current_changed = True
        elif event in SET_CHANGED_EVENTS:
            self._pending_set_changed = True
        elif event is DesktopEvent.RENAMED:
            self._pending_set_changed = True
            self._pending_buttons = True
        else:
            # Wallpaper and switch notifications tell us nothing the other
            # events do not already cover.
            return

        if not self._refresh_queued:
            self._refresh_queued = True
            QTimer.singleShot(0, self._apply_pending)

    def _apply_pending(self) -> None:
        """Apply everything the notifications asked for, in one pass."""
        self._refresh_queued = False
        current_changed = self._pending_current_changed
        set_changed = self._pending_set_changed
        update_buttons = self._pending_buttons
        self._pending_current_changed = False
        self._pending_set_changed = False
        self._pending_buttons = False

        self._invalidate()
        try:
            number = self._current_number()
        except SHELL_UNAVAILABLE:
            logger.debug("Failed to read virtual desktop state after notification", exc_info=True)
            return

        if current_changed:
            self._last_number = number
            self.desktop_changed.emit({"index": number})

        if current_changed or set_changed:
            self._refresh_state(update_buttons=update_buttons)

    def _refresh_state(self, update_buttons: bool = False) -> None:
        """Emit `desktops_updated` when the desktop set or selection moved."""
        try:
            count = len(self._snapshot())
            number = self._current_number()
        except SHELL_UNAVAILABLE:
            logger.debug("Failed to refresh virtual desktop state", exc_info=True)
            return
        if count != self._last_count or number != self._last_number or update_buttons:
            self._last_count = count
            self._last_number = number
            self.desktops_updated.emit({"index": number}, {"update_buttons": update_buttons})

    def register_widget(self, widget):
        """Track a widget, starting notifications on the first one."""
        if widget not in self._widgets:
            self._widgets.append(widget)

        if self._listener is None:
            self._listener = DesktopNotificationListener(self._com_event.emit, self._api)

        # Fall back to polling only if the shell will not push to us.
        if not self._listener.active and not self._listener.start() and self._timer is None:
            logger.warning("Falling back to polling for virtual desktop changes")
            self._timer = QTimer(self)
            self._timer.setInterval(POLL_INTERVAL_MS)
            self._timer.timeout.connect(self._poll)
            self._timer.start()

    def unregister_widget(self, widget):
        """Stop tracking a widget, releasing the shell once the last one goes."""
        try:
            self._widgets.remove(widget)
        except ValueError:
            pass
        if not self._widgets:
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            if self._timer:
                self._timer.stop()
                self._timer = None

    def _poll(self):
        self._invalidate()
        try:
            number = self._current_number()
        except SHELL_UNAVAILABLE:
            logger.debug("Virtual desktop poll failed", exc_info=True)
            return

        # The shell answered, so it may now accept a notification sink. Polling
        # is only ever a fallback, so hand back to notifications as soon as one
        # registers - otherwise a shell that was briefly unreachable at startup
        # would leave us polling for the rest of the session.
        if self._listener is not None and not self._listener.active and self._listener.start():
            logger.info("Virtual desktop notifications registered, stopping the polling fallback")
            if self._timer:
                self._timer.stop()
                self._timer = None

        if number != self._last_number:
            self.desktop_changed.emit({"index": number})
        self._refresh_state(update_buttons=False)

    def notify_desktop_changed(self, index: int):
        self.desktop_changed.emit({"index": index})

    def notify_desktops_updated(self, update_buttons: bool = False):
        """Force a refresh (e.g. after rename/create/delete)."""
        self._invalidate()
        try:
            number = self._current_number()
            self._last_count = len(self._snapshot())
        except SHELL_UNAVAILABLE:
            logger.debug("Failed to read state for forced refresh", exc_info=True)
            number = self._last_number
        self._last_number = number
        self.desktops_updated.emit({"index": number}, {"update_buttons": update_buttons})

    @staticmethod
    def get_desktops() -> list[DesktopInfo]:
        """Every desktop, or an empty list while the shell is unreachable."""
        try:
            return WindowsDesktopService()._snapshot()
        except SHELL_UNAVAILABLE:
            logger.debug("Could not read the desktop list", exc_info=True)
            return []

    @staticmethod
    def get_current_desktop() -> DesktopInfo:
        """The desktop in view.

        Returns a placeholder numbered 0 while the shell is unreachable, so a
        widget can still be built and pick up the real state once it answers.
        """
        service = WindowsDesktopService()
        try:
            return service._resolve(service._current_number())
        except SHELL_UNAVAILABLE:
            logger.debug("Could not read the current desktop", exc_info=True)
            return DesktopInfo(number=0, guid="", name="")

    @staticmethod
    def get_desktop(number: int) -> DesktopInfo:
        return WindowsDesktopService()._resolve(number)

    @staticmethod
    def get_desktop_name(number: int) -> str:
        try:
            return WindowsDesktopService()._resolve(number).name
        except SHELL_UNAVAILABLE:
            return ""

    @staticmethod
    def switch_desktop(number: int):
        service = WindowsDesktopService()
        service._api.switch_to(service._resolve(number).guid)
        # The notification that follows would drop the cache anyway, but not
        # before a caller could read the previous desktop back out of it.
        service._invalidate()

    @staticmethod
    def create_desktop():
        service = WindowsDesktopService()
        guid = service._api.create()
        service._invalidate()
        return guid

    @staticmethod
    def remove_desktop(number: int):
        service = WindowsDesktopService()
        service._api.remove(service._resolve(number).guid)
        service._invalidate()

    @staticmethod
    def rename_desktop(number: int, name: str):
        service = WindowsDesktopService()
        service._api.rename(service._resolve(number).guid, name)
        service._invalidate()

    @staticmethod
    def set_wallpaper(number: int, path: str):
        service = WindowsDesktopService()
        service._api.set_wallpaper(service._resolve(number).guid, path)

    @staticmethod
    def set_wallpaper_all(path: str):
        WindowsDesktopService()._api.set_wallpaper_all(path)

    @staticmethod
    def get_foreground_app_view() -> ForegroundView | None:
        """Return the foreground window, or None if it is the desktop, taskbar,
        or a window that does not appear in the switcher."""
        service = WindowsDesktopService()
        try:
            hwnd = GetForegroundWindow()
            if not hwnd:
                return None
            if GetClassName(hwnd) in SKIP_WINDOW_CLASSES or _is_own_window(hwnd):
                return None
            # None means the foreground is not an application window: a menu,
            # a popup or the desktop. That is an ordinary outcome.
            view = service._api.try_view_for_hwnd(hwnd)
            if view is None:
                # Logged with identifying detail: which window ends up in the
                # foreground here is the only reason the move and pin entries
                # go missing from the menu, so it needs to be diagnosable.
                logger.debug(
                    "Foreground window %s (class %r) has no application view; move and pin entries will be omitted",
                    hwnd,
                    GetClassName(hwnd),
                )
                return None
            if not service._api.is_shown_in_switchers(view):
                return None
            return ForegroundView(hwnd=hwnd, view=view, api=service._api)
        except Exception:
            logger.debug("Could not read the foreground window", exc_info=True)
            return None

    @staticmethod
    def move_window(hwnd: int, desktop_number: int):
        service = WindowsDesktopService()
        view = service._api.view_for_hwnd(hwnd)
        service._api.move_view(view, service._resolve(desktop_number).guid)

    @staticmethod
    def toggle_pin_window(hwnd: int):
        service = WindowsDesktopService()
        view = service._api.view_for_hwnd(hwnd)
        if service._api.is_view_pinned(view):
            service._api.unpin_view(view)
        else:
            service._api.pin_view(view)

    @staticmethod
    def toggle_pin_app(hwnd: int):
        service = WindowsDesktopService()
        view = service._api.view_for_hwnd(hwnd)
        if service._api.is_app_pinned(view):
            service._api.unpin_app(view)
        else:
            service._api.pin_app(view)

"""Virtual desktop change notifications from the shell.

The shell pushes changes to any COM object that implements
IVirtualDesktopNotification and registers with the notification service, which
avoids polling entirely.

The sink translates the raw callbacks into a DesktopEvent and hands them to one
callable. Callback parameters are ignored: they are desktop pointers whose layout
varies by build, and consumers re-read state through the API anyway.

Callbacks arrive on whichever thread the shell calls in on, not necessarily the
one that registered, so consumers must treat them as arriving from an arbitrary
thread. The service marshals them onto the Qt main thread with a signal.
"""

import logging
from collections.abc import Callable
from ctypes import c_void_p, cast
from enum import Enum, auto
from typing import Any

import comtypes

from core.widgets.services.windows_desktops.com import VirtualDesktopApi, get_api
from core.widgets.services.windows_desktops.interfaces import DesktopInterfaces

logger = logging.getLogger("windows_desktop_service")


class DesktopEvent(Enum):
    """A desktop change reported by the shell."""

    CURRENT_CHANGED = auto()
    CREATED = auto()
    DESTROYED = auto()
    MOVED = auto()
    RENAMED = auto()
    WALLPAPER_CHANGED = auto()
    SWITCHED = auto()


_sink_class: type | None = None


def _make_sink_class(interfaces: DesktopInterfaces) -> type:
    """Build the notification sink class for the resolved interface tier.

    The sink implements every callback name used by any build; names absent from
    this build's vtable go uncalled, so one class covers all tiers.

    IVirtualDesktopNotification2 is implemented alongside the primary interface
    because on 19041 the shell reports renames through it instead.
    """

    class DesktopNotificationSink(comtypes.COMObject):
        _com_interfaces_ = [
            interfaces.IVirtualDesktopNotification,
            interfaces.IVirtualDesktopNotification2,
        ]

        def __init__(self, dispatch: Callable[[DesktopEvent], None]):
            super().__init__()
            self._dispatch = dispatch

        def _emit(self, event: DesktopEvent) -> int:
            """Pass the event to the consumer, swallowing any error.

            An exception escaping into COM crosses the boundary as a failed
            HRESULT and can make the shell drop the registration.
            """
            try:
                self._dispatch(event)
            except Exception:
                logger.exception("Virtual desktop notification handler failed for %s", event)
            return 0  # S_OK regardless; never report failure to the shell

        def VirtualDesktopCreated(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.CREATED)

        def VirtualDesktopDestroyed(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.DESTROYED)

        def VirtualDesktopMoved(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.MOVED)

        def VirtualDesktopRenamed(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.RENAMED)

        def CurrentVirtualDesktopChanged(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.CURRENT_CHANGED)

        def VirtualDesktopWallpaperChanged(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.WALLPAPER_CHANGED)

        def VirtualDesktopSwitched(self, *_args: Any) -> int:
            return self._emit(DesktopEvent.SWITCHED)

        # Callbacks we deliberately ignore. They still need implementations so
        # the shell gets S_OK rather than E_NOTIMPL.
        def VirtualDesktopDestroyBegin(self, *_args: Any) -> int:
            return 0

        def VirtualDesktopDestroyFailed(self, *_args: Any) -> int:
            return 0

        def ViewVirtualDesktopChanged(self, *_args: Any) -> int:
            return 0

        def RemoteVirtualDesktopConnected(self, *_args: Any) -> int:
            return 0

        def Proc7(self, *_args: Any) -> int:
            return 0

    return DesktopNotificationSink


def _sink_type(interfaces: DesktopInterfaces) -> type:
    """The sink class for this process, built once."""
    global _sink_class
    if _sink_class is None:
        _sink_class = _make_sink_class(interfaces)
    return _sink_class


class DesktopNotificationListener:
    """Keeps a notification sink registered with the shell.

    start() returns False rather than raising so callers can fall back to polling.
    """

    def __init__(self, on_event: Callable[[DesktopEvent], None], api: VirtualDesktopApi | None = None):
        self._on_event = on_event
        self._api = api or get_api()
        self._service: Any = None
        self._sink: Any = None
        self._cookie: int | None = None

    @property
    def active(self) -> bool:
        return self._cookie is not None

    def start(self) -> bool:
        """Register with the shell. Returns whether notifications are live."""
        if self.active:
            return True
        try:
            interfaces = self._api.interfaces
            self._service = self._api.notification_service()
            self._sink = _sink_type(interfaces)(self._on_event)
            # Register takes the raw interface pointer, not the Python object.
            pointer = cast(
                self._sink._com_pointers_[interfaces.IVirtualDesktopNotification._iid_],
                c_void_p,
            )
            self._cookie = self._service.Register(pointer)
        except Exception:
            logger.warning("Could not register for virtual desktop notifications", exc_info=True)
            self._service = None
            self._sink = None
            self._cookie = None
            return False
        logger.info("Registered for virtual desktop notifications (cookie=%s)", self._cookie)
        return True

    def stop(self) -> None:
        """Unregister and drop the sink. Safe to call when not started."""
        if self._cookie is not None and self._service is not None:
            try:
                self._service.Unregister(self._cookie)
                logger.info("Unregistered virtual desktop notifications (cookie=%s)", self._cookie)
            except Exception:
                logger.debug("Failed to unregister virtual desktop notifications", exc_info=True)
        self._cookie = None
        self._service = None
        self._sink = None

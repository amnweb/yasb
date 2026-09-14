"""COM plumbing for the virtual desktop service.

Wraps the raw interfaces from core.widgets.services.windows_desktops.interfaces in an API
that speaks plain Python values, so nothing above this layer holds a COM pointer.

Desktops are addressed by GUID rather than position. Resolving a GUID is a single
FindDesktop call, while resolving a position means enumerating every desktop.
list_desktops is the only call that enumerates, returning positions and names in
one pass.

COM objects are created on first use and held per thread, as apartment rules
require.
"""

import logging
import sys
import threading
from ctypes import POINTER
from dataclasses import dataclass
from typing import Any

import comtypes
from comtypes import GUID, COMError

from core.utils.win32.bindings.user32 import AllowSetForegroundWindow
from core.utils.win32.com_base import HSTRING, IServiceProvider
from core.widgets.services.windows_desktops.interfaces import (
    TIER_21313,
    CLSID_ImmersiveShell,
    CLSID_VirtualDesktopManagerInternal,
    CLSID_VirtualDesktopNotificationService,
    CLSID_VirtualDesktopPinnedApps,
    DesktopInterfaces,
    IApplicationViewCollection,
    IVirtualDesktop2,
    IVirtualDesktopNotificationService,
    IVirtualDesktopPinnedApps,
    VirtualDesktopUnsupportedError,
    get_interfaces,
)

logger = logging.getLogger("windows_desktop_service")

# Passing this to AllowSetForegroundWindow lets any process take the
# foreground, which stops focus lingering on the old desktop after a switch.
# See https://github.com/Ciantic/VirtualDesktopAccessor/issues/4
ASFW_ANY = 0xFFFFFFFF


class VirtualDesktopError(RuntimeError):
    """A virtual desktop operation failed."""


@dataclass(frozen=True)
class DesktopInfo:
    """One virtual desktop, as of the moment it was read."""

    number: int  # 1-based, matching the order shown in Task View
    guid: str
    name: str


class _ComObjects(threading.local):
    """Per-thread COM interface pointers, created on first access.

    A pointer acquired in one apartment cannot be used from another without
    marshaling, so each thread gets its own set.
    """

    def __init__(self):
        self.interfaces: DesktopInterfaces | None = None
        self.manager: Any = None
        self.manager2: Any = None
        self.views: Any = None
        self.pinned: Any = None


def _init_com() -> None:
    """Join the thread to a COM apartment if it is not already in one."""
    try:
        comtypes.CoInitializeEx()
    except (OSError, COMError) as e:
        # Usually means the thread is already in a multi-threaded apartment,
        # which is fine for our purposes.
        logger.debug("CoInitializeEx declined: %s", e)


class VirtualDesktopApi:
    """Plain-value wrapper over the shell's virtual desktop interfaces."""

    def __init__(self):
        self._com = _ComObjects()

    def _provider(self) -> Any:
        return comtypes.CoCreateInstance(CLSID_ImmersiveShell, IServiceProvider, comtypes.CLSCTX_LOCAL_SERVER)

    def _query(self, provider: Any, cls: Any, clsid: GUID | None = None) -> Any:
        pointer = POINTER(cls)()
        provider.QueryService(clsid or cls._iid_, cls._iid_, pointer)
        return pointer

    def _ensure(self) -> _ComObjects:
        """Create this thread's COM objects if it does not have them yet."""
        com = self._com
        if com.manager is not None:
            return com

        _init_com()
        interfaces = get_interfaces()
        provider = self._provider()

        com.interfaces = interfaces
        com.manager = self._query(
            provider, interfaces.IVirtualDesktopManagerInternal, CLSID_VirtualDesktopManagerInternal
        )
        com.views = self._query(provider, IApplicationViewCollection)
        com.pinned = self._query(provider, IVirtualDesktopPinnedApps, CLSID_VirtualDesktopPinnedApps)

        # Windows 10 only. 19041 added desktop renaming through this derived
        # interface; 21313 moved SetName onto the manager above and dropped it.
        com.manager2 = None
        if interfaces.tier < TIER_21313:
            try:
                com.manager2 = self._query(
                    provider, interfaces.IVirtualDesktopManagerInternal2, CLSID_VirtualDesktopManagerInternal
                )
            except COMError:
                logger.debug("IVirtualDesktopManagerInternal2 unavailable; desktops cannot be renamed")

        logger.info("Virtual desktop COM ready (tier %d, build %d)", interfaces.tier, sys.getwindowsversion().build)
        return com

    @property
    def interfaces(self) -> DesktopInterfaces:
        return self._ensure().interfaces

    @property
    def supports_names(self) -> bool:
        """Can desktops be named and renamed on this build?"""
        return self.interfaces.supports_names

    @property
    def supports_wallpaper(self) -> bool:
        """Can per-desktop wallpapers be set on this build? Windows 11 only."""
        return self.interfaces.supports_wallpaper

    def available(self) -> bool:
        """Is the virtual desktop API usable at all on this machine?"""
        try:
            self._ensure()
        except VirtualDesktopUnsupportedError, COMError, OSError, AttributeError:
            logger.warning("Virtual desktop API unavailable", exc_info=True)
            return False
        return True

    def _find(self, guid: str) -> Any:
        """Resolve a desktop GUID to its COM object without enumerating."""
        com = self._ensure()
        try:
            return com.manager.FindDesktop(GUID(guid))
        except (COMError, OSError, ValueError) as e:
            raise VirtualDesktopError(f"No desktop with id {guid}") from e

    def list_desktops(self) -> list[DesktopInfo]:
        """Enumerate every desktop in Task View order, with names.

        The only call that enumerates. 21313 and later expose GetName on the
        desktop itself; earlier builds reach it through IVirtualDesktop2.
        """
        com = self._ensure()
        interfaces = com.interfaces
        array = com.manager.get_all_desktops()

        if interfaces.tier >= TIER_21313:
            return [
                DesktopInfo(number=i, guid=str(d.GetID()), name=str(d.GetName()).strip())
                for i, d in enumerate(array.iter(interfaces.IVirtualDesktop), 1)
            ]

        if interfaces.supports_names:
            return [
                DesktopInfo(number=i, guid=str(d.GetID()), name=str(d.GetName()).strip())
                for i, d in enumerate(array.iter(IVirtualDesktop2), 1)
            ]

        return [
            DesktopInfo(number=i, guid=str(d.GetID()), name="")
            for i, d in enumerate(array.iter(interfaces.IVirtualDesktop), 1)
        ]

    def current_guid(self) -> str:
        """The GUID of the desktop currently in view."""
        com = self._ensure()
        return str(com.manager.get_current_desktop().GetID())

    def count(self) -> int:
        """How many desktops exist, without building the full list."""
        com = self._ensure()
        return com.manager.get_all_desktops().GetCount()

    def switch_to(self, guid: str) -> None:
        """Switch to the desktop with this GUID."""
        com = self._ensure()
        AllowSetForegroundWindow(ASFW_ANY)
        com.manager.switch_desktop(self._find(guid))

    def create(self) -> str:
        """Create a desktop and return its GUID."""
        com = self._ensure()
        return str(com.manager.create_desktop().GetID())

    def remove(self, guid: str, fallback_guid: str | None = None) -> None:
        """Delete a desktop, moving to `fallback_guid` if it was in view."""
        com = self._ensure()
        if fallback_guid is None:
            desktops = self.list_desktops()
            fallback = next((d for d in desktops if d.guid != guid), None)
            if fallback is None:
                raise VirtualDesktopError("Cannot remove the only remaining desktop")
            fallback_guid = fallback.guid
        com.manager.RemoveDesktop(self._find(guid), self._find(fallback_guid))

    def rename(self, guid: str, name: str) -> None:
        """Rename a desktop.

        SetName lives on the manager from 21313 onward. Before that it is only
        reachable through the derived Windows 10 interface.
        """
        com = self._ensure()
        if not self.supports_names:
            raise VirtualDesktopError("Renaming desktops requires Windows 10 build 19041 or later")
        target = com.manager if com.interfaces.tier >= TIER_21313 else com.manager2
        if target is None:
            raise VirtualDesktopError("This build reports no interface that can rename desktops")
        target.SetName(self._find(guid), HSTRING(name))

    def set_wallpaper(self, guid: str, path: str) -> None:
        """Set one desktop's wallpaper."""
        com = self._ensure()
        if not self.supports_wallpaper:
            raise VirtualDesktopError("Per-desktop wallpapers require Windows 11")
        com.manager.SetWallpaper(self._find(guid), HSTRING(path))

    def set_wallpaper_all(self, path: str) -> None:
        """Set the wallpaper on every desktop."""
        com = self._ensure()
        if not self.supports_wallpaper:
            raise VirtualDesktopError("Per-desktop wallpapers require Windows 11")
        com.manager.SetWallpaperForAllDesktops(HSTRING(path))

    def view_for_hwnd(self, hwnd: int) -> Any:
        """Get the shell's view object for a window handle."""
        com = self._ensure()
        return com.views.GetViewForHwnd(hwnd)

    def try_view_for_hwnd(self, hwnd: int) -> Any | None:
        """Like `view_for_hwnd`, but None when the shell tracks no view.

        Many windows have no application view: the desktop, menus and popups,
        tooltips, and most non-application shell surfaces. The shell reports that
        as "element not found", which is an answer rather than a fault.
        """
        try:
            return self.view_for_hwnd(hwnd)
        except COMError:
            # Callers that care log this with context; a bare handle here
            # would only be noise.
            return None

    def is_shown_in_switchers(self, view: Any) -> bool:
        """Does this window appear in alt-tab? Filters out shell surfaces."""
        return bool(view.GetShowInSwitchers())

    def move_view(self, view: Any, guid: str) -> None:
        """Move a window to the desktop with this GUID."""
        com = self._ensure()
        com.manager.MoveViewToDesktop(view, self._find(guid))

    def is_view_pinned(self, view: Any) -> bool:
        return bool(self._ensure().pinned.IsViewPinned(view))

    def pin_view(self, view: Any) -> None:
        self._ensure().pinned.PinView(view)

    def unpin_view(self, view: Any) -> None:
        self._ensure().pinned.UnpinView(view)

    def _app_id(self, view: Any) -> Any:
        """A view's app id, or None.

        Some windows, typically shell surfaces pinned above normal windows, have
        no app id and raise instead of returning one. The Windows UI does nothing
        for those, so None is reported and callers skip.
        """
        try:
            return view.GetAppUserModelId()
        except COMError:
            logger.debug("Window has no app user model id")
            return None

    def is_app_pinned(self, view: Any) -> bool:
        app_id = self._app_id(view)
        if app_id is None:
            return False
        return bool(self._ensure().pinned.IsAppIdPinned(app_id))

    def pin_app(self, view: Any) -> None:
        app_id = self._app_id(view)
        if app_id is not None:
            self._ensure().pinned.PinAppID(app_id)

    def unpin_app(self, view: Any) -> None:
        app_id = self._app_id(view)
        if app_id is not None:
            self._ensure().pinned.UnpinAppID(app_id)

    def notification_service(self) -> Any:
        """Acquire the service that desktop change callbacks register with."""
        self._ensure()
        return self._query(
            self._provider(), IVirtualDesktopNotificationService, CLSID_VirtualDesktopNotificationService
        )


_api: VirtualDesktopApi | None = None


def get_api() -> VirtualDesktopApi:
    """The process-wide API instance. COM work is still deferred to first use."""
    global _api
    if _api is None:
        _api = VirtualDesktopApi()
    return _api

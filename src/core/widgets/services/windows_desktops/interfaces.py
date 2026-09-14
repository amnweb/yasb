"""COM interfaces for the undocumented Windows virtual desktop API.

The shell exposes virtual desktop control through IVirtualDesktopManagerInternal,
whose GUID and vtable layout changed several times across Windows 10 and 11.
Interfaces are therefore built per build tier, resolved on first use.

Below build 26100 the tier is resolved by asking the shell which interface GUID it
supports. Build numbers alone are not reliable: 22H2 received newer shell
interfaces through Moment updates without a build change. 26100 and above always
expose the 24H2 interface and skip the probe.

Importing this module performs no COM calls.

Interfaces and GUIDs from https://github.com/Ciantic/VirtualDesktopAccessor
"""

import logging
import sys
from ctypes import HRESULT, POINTER, c_ulonglong, c_void_p
from ctypes.wintypes import BOOL, DWORD, HWND, INT, LPCWSTR, LPVOID, RECT, SIZE, UINT, ULONG
from dataclasses import dataclass
from typing import Any

from comtypes import CLSCTX_LOCAL_SERVER, COMMETHOD, GUID, STDMETHOD, CoCreateInstance, COMError, IUnknown

from core.utils.win32.com_base import HSTRING, PWSTR, REFGUID, REFIID, IObjectArray, IServiceProvider

logger = logging.getLogger("virtual_desktop")

CLSID_ImmersiveShell = GUID("{C2F03A33-21F5-47FA-B4BB-156362A2F239}")
CLSID_VirtualDesktopManagerInternal = GUID("{C5E0CDCA-7B6E-41B2-9FC4-D93975CC467B}")
CLSID_VirtualDesktopPinnedApps = GUID("{B5A399E7-1C87-46B8-88E9-FC5747B171BD}")
CLSID_VirtualDesktopNotificationService = GUID("{A501FDEC-4A09-464C-AE4E-1B9C21B84918}")

GUID_IVirtualDesktop_26100 = GUID("{3F07F4BE-B107-441A-AF0F-39D82529072C}")
GUID_IVirtualDesktop_22631 = GUID("{3F07F4BE-B107-441A-AF0F-39D82529072C}")
GUID_IVirtualDesktop_22621 = GUID("{3F07F4BE-B107-441A-AF0F-39D82529072C}")
GUID_IVirtualDesktop_21313 = GUID("{536D3495-B208-4CC9-AE26-DE8111275BF8}")
GUID_IVirtualDesktop_20231 = GUID("{62FDF88B-11CA-4AFB-8BD8-2296DFAE49E2}")
GUID_IVirtualDesktop_9000 = GUID("{FF72FFDD-BE7E-43FC-9C03-AD81681E88E4}")

GUID_IVirtualDesktopManagerInternal_26100 = GUID("{53F5CA0B-158F-4124-900C-057158060B27}")
GUID_IVirtualDesktopManagerInternal_22631 = GUID("{4970BA3D-FD4E-4647-BEA3-D89076EF4B9C}")
GUID_IVirtualDesktopManagerInternal_22621 = GUID("{A3175F2D-239C-4BD2-8AA0-EEBA8B0B138E}")
GUID_IVirtualDesktopManagerInternal_21313 = GUID("{B2F925B9-5A0F-4D2E-9F4D-2B1507593C10}")
GUID_IVirtualDesktopManagerInternal_20231 = GUID("{094AFE11-44F2-4BA0-976F-29A97E263EE0}")
GUID_IVirtualDesktopManagerInternal_9000 = GUID("{F31574D6-B682-4CDC-BD56-1827860ABEC6}")

GUID_IVirtualDesktopManagerInternal2 = GUID("{0F3A72B0-4566-487E-9A33-4ED302F6D6CE}")
GUID_IVirtualDesktop2 = GUID("{31EBDE3F-6EC3-4CBD-B9FB-0EF6D09B41F4}")

GUID_IVirtualDesktopNotification_22631 = GUID("{B9E5E94D-233E-49AB-AF5C-2B4541C3AADE}")
GUID_IVirtualDesktopNotification_22621 = GUID("{B287FA1C-7771-471A-A2DF-9B6B21F0D675}")
GUID_IVirtualDesktopNotification_20231 = GUID("{CD403E52-DEED-4C13-B437-B98380F2B1E8}")
GUID_IVirtualDesktopNotification_9000 = GUID("{C179334C-4295-40D3-BEA1-C654D965605A}")
GUID_IVirtualDesktopNotification2 = GUID("{1BA7CF30-3591-43FA-ABFA-4AAF7ABEEDB7}")

# Stable across every build.
GUID_IVirtualDesktopNotificationService = GUID("{0CD45E71-D927-4F15-8B0A-8FEF525337BF}")

# Interfaces we never call into. Declared as opaque so the vtable slots that
# reference them keep their correct positions.
IAsyncCallback = UINT
IImmersiveMonitor = UINT
APPLICATION_VIEW_COMPATIBILITY_POLICY = UINT
IApplicationViewOperation = UINT
APPLICATION_VIEW_CLOAK_TYPE = UINT
IApplicationViewPosition = UINT
IImmersiveApplication = UINT
IApplicationViewChangeListener = UINT
TrustLevel = INT
AdjacentDesktop = UINT


# Each tier is the build its interface set first appeared in, so comparisons
# against them read as "is this build at least X". The oldest set predates every
# build we care about, so it has no meaningful threshold and sorts below all of
# them.
TIER_WIN10 = 0
TIER_20231 = 20231
TIER_21313 = 21313
TIER_22449 = 22449
TIER_22621 = 22621
TIER_22631 = 22631
TIER_26100 = 26100

MANAGER_GUID_BY_TIER: dict[int, GUID] = {
    TIER_26100: GUID_IVirtualDesktopManagerInternal_26100,
    TIER_22631: GUID_IVirtualDesktopManagerInternal_22631,
    TIER_22621: GUID_IVirtualDesktopManagerInternal_22621,
    TIER_22449: GUID_IVirtualDesktopManagerInternal_21313,
    TIER_21313: GUID_IVirtualDesktopManagerInternal_21313,
    TIER_20231: GUID_IVirtualDesktopManagerInternal_20231,
    TIER_WIN10: GUID_IVirtualDesktopManagerInternal_9000,
}

# Probe order, newest first. 22449 is absent because it shares the 21313 GUID
# and is distinguished by build number once that probe succeeds.
PROBE_ORDER = (TIER_22631, TIER_22621, TIER_21313, TIER_20231, TIER_WIN10)

# Desktop naming and renaming arrived in 19041. Unlike the vtable tiers this
# is a genuine OS capability gate, so the build number is the right key.
BUILD_DESKTOP_NAMES = 19041


def supports_desktop_names(tier: int) -> bool:
    """Can desktops be named and renamed on this tier?"""
    if tier >= TIER_20231:
        return True
    return sys.getwindowsversion().build >= BUILD_DESKTOP_NAMES


def supports_wallpaper(tier: int) -> bool:
    """Can per-desktop wallpapers be set on this tier? Windows 11 only."""
    return tier >= TIER_21313


class IApplicationView(IUnknown):
    """A window as the shell sees it. Only a few of these methods are called."""

    _iid_ = GUID("{372E1D3B-38D3-42E4-A15B-8AB2B178F513}")


IApplicationView._methods_ = [
    # IInspectable
    STDMETHOD(HRESULT, "GetIids", (POINTER(ULONG), POINTER(POINTER(GUID)))),
    STDMETHOD(HRESULT, "GetRuntimeClassName", (POINTER(HSTRING),)),
    STDMETHOD(HRESULT, "GetTrustLevel", (POINTER(TrustLevel),)),
    # IApplicationView
    STDMETHOD(HRESULT, "SetFocus", ()),
    STDMETHOD(HRESULT, "SwitchTo", ()),
    STDMETHOD(HRESULT, "TryInvokeBack", (POINTER(IAsyncCallback),)),
    COMMETHOD([], HRESULT, "GetThumbnailWindow", (["out"], POINTER(HWND), "hwnd")),
    STDMETHOD(HRESULT, "GetMonitor", (POINTER(POINTER(IImmersiveMonitor)),)),
    COMMETHOD([], HRESULT, "GetVisibility", (["out"], POINTER(UINT), "pVisible")),
    STDMETHOD(HRESULT, "SetCloak", (APPLICATION_VIEW_CLOAK_TYPE, UINT)),
    STDMETHOD(HRESULT, "GetPosition", (REFIID, POINTER(LPVOID))),
    STDMETHOD(HRESULT, "SetPosition", (POINTER(IApplicationViewPosition),)),
    STDMETHOD(HRESULT, "InsertAfterWindow", (HWND,)),
    STDMETHOD(HRESULT, "GetExtendedFramePosition", (POINTER(RECT),)),
    COMMETHOD([], HRESULT, "GetAppUserModelId", (["out"], POINTER(PWSTR), "pId")),
    STDMETHOD(HRESULT, "SetAppUserModelId", (LPCWSTR,)),
    STDMETHOD(HRESULT, "IsEqualByAppUserModelId", (LPCWSTR, POINTER(UINT))),
    STDMETHOD(HRESULT, "GetViewState", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "SetViewState", (UINT,)),
    STDMETHOD(HRESULT, "GetNeediness", (POINTER(UINT),)),
    COMMETHOD([], HRESULT, "GetLastActivationTimestamp", (["out"], POINTER(c_ulonglong), "pGuid")),
    STDMETHOD(HRESULT, "SetLastActivationTimestamp", (c_ulonglong,)),
    COMMETHOD([], HRESULT, "GetVirtualDesktopId", (["out"], POINTER(GUID), "pGuid")),
    STDMETHOD(HRESULT, "SetVirtualDesktopId", (REFGUID,)),
    COMMETHOD([], HRESULT, "GetShowInSwitchers", (["out"], POINTER(UINT), "pShown")),
    STDMETHOD(HRESULT, "SetShowInSwitchers", (UINT,)),
    STDMETHOD(HRESULT, "GetScaleFactor", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "CanReceiveInput", (POINTER(BOOL),)),
    STDMETHOD(HRESULT, "GetCompatibilityPolicyType", (POINTER(APPLICATION_VIEW_COMPATIBILITY_POLICY),)),
    STDMETHOD(HRESULT, "SetCompatibilityPolicyType", (APPLICATION_VIEW_COMPATIBILITY_POLICY,)),
    STDMETHOD(HRESULT, "GetSizeConstraints", (POINTER(IImmersiveMonitor), POINTER(SIZE), POINTER(SIZE))),
    STDMETHOD(HRESULT, "GetSizeConstraintsForDpi", (UINT, POINTER(SIZE), POINTER(SIZE))),
    STDMETHOD(HRESULT, "SetSizeConstraintsForDpi", (POINTER(UINT), POINTER(SIZE), POINTER(SIZE))),
    STDMETHOD(HRESULT, "OnMinSizePreferencesUpdated", (HWND,)),
    STDMETHOD(HRESULT, "ApplyOperation", (POINTER(IApplicationViewOperation),)),
    STDMETHOD(HRESULT, "IsTray", (POINTER(BOOL),)),
    STDMETHOD(HRESULT, "IsInHighZOrderBand", (POINTER(BOOL),)),
    STDMETHOD(HRESULT, "IsSplashScreenPresented", (POINTER(BOOL),)),
    STDMETHOD(HRESULT, "Flash", ()),
    STDMETHOD(HRESULT, "GetRootSwitchableOwner", (POINTER(POINTER(IApplicationView)),)),
    STDMETHOD(HRESULT, "EnumerateOwnershipTree", (POINTER(POINTER(IObjectArray)),)),
    STDMETHOD(HRESULT, "GetEnterpriseId", (POINTER(PWSTR),)),
    STDMETHOD(HRESULT, "IsMirrored", (POINTER(BOOL),)),
    STDMETHOD(HRESULT, "GetFrameworkViewType", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "GetCanTab", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "SetCanTab", (UINT,)),
    STDMETHOD(HRESULT, "GetIsTabbed", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "SetIsTabbed", (UINT,)),
    STDMETHOD(HRESULT, "RefreshCanTab", ()),
    STDMETHOD(HRESULT, "GetIsOccluded", (POINTER(UINT),)),
    STDMETHOD(HRESULT, "SetIsOccluded", (UINT,)),
    STDMETHOD(HRESULT, "UpdateEngagementFlags", (UINT, UINT)),
    STDMETHOD(HRESULT, "SetForceActiveWindowAppearance", (UINT,)),
    STDMETHOD(HRESULT, "GetLastActivationFILETIME", (POINTER(SIZE),)),
    STDMETHOD(HRESULT, "GetPersistingStateName", (POINTER(PWSTR),)),
]


class IVirtualDesktop2(IUnknown):
    """Pre-21313 route to a desktop's name, read via the desktop array."""

    _iid_ = GUID_IVirtualDesktop2
    _methods_ = [
        STDMETHOD(HRESULT, "IsViewVisible", (POINTER(IApplicationView), POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetID", (["out"], POINTER(GUID), "pGuid")),
        COMMETHOD([], HRESULT, "GetName", (["out"], POINTER(HSTRING), "pName")),
    ]


class IVirtualDesktopPinnedApps(IUnknown):
    """Pinning of windows and apps across all desktops."""

    _iid_ = GUID("{4CE81583-1E4C-4632-A621-07A53543148F}")
    _methods_ = [
        COMMETHOD([], HRESULT, "IsAppIdPinned", (["in"], LPCWSTR, "appId"), (["out"], POINTER(BOOL), "isPinned")),
        STDMETHOD(HRESULT, "PinAppID", (LPCWSTR,)),
        STDMETHOD(HRESULT, "UnpinAppID", (LPCWSTR,)),
        COMMETHOD(
            [],
            HRESULT,
            "IsViewPinned",
            (["in"], POINTER(IApplicationView), "pView"),
            (["out"], POINTER(BOOL), "isPinned"),
        ),
        STDMETHOD(HRESULT, "PinView", (POINTER(IApplicationView),)),
        STDMETHOD(HRESULT, "UnpinView", (POINTER(IApplicationView),)),
    ]


class IApplicationViewCollection(IUnknown):
    """Maps window handles to `IApplicationView` objects."""

    _iid_ = GUID("{1841C6D7-4F9D-42C0-AF41-8747538F10E5}")
    _methods_ = [
        STDMETHOD(HRESULT, "GetViews", (POINTER(POINTER(IObjectArray)),)),
        COMMETHOD([], HRESULT, "GetViewsByZOrder", (["out"], POINTER(POINTER(IObjectArray)), "array")),
        STDMETHOD(HRESULT, "GetViewsByAppUserModelId", (LPCWSTR, POINTER(POINTER(IObjectArray)))),
        COMMETHOD(
            [],
            HRESULT,
            "GetViewForHwnd",
            (["in"], HWND, "hwnd"),
            (["out"], POINTER(POINTER(IApplicationView)), "pView"),
        ),
        STDMETHOD(
            HRESULT, "GetViewForApplication", (POINTER(IImmersiveApplication), POINTER(POINTER(IApplicationView)))
        ),
        STDMETHOD(HRESULT, "GetViewForAppUserModelId", (LPCWSTR, POINTER(POINTER(IApplicationView)))),
        COMMETHOD([], HRESULT, "GetViewInFocus", (["out"], POINTER(POINTER(IApplicationView)), "view")),
        STDMETHOD(HRESULT, "Unknown1", (POINTER(POINTER(IApplicationView)),)),
        STDMETHOD(HRESULT, "RefreshCollection", ()),
        STDMETHOD(
            HRESULT, "RegisterForApplicationViewChanges", (POINTER(IApplicationViewChangeListener), POINTER(DWORD))
        ),
        STDMETHOD(HRESULT, "UnregisterForApplicationViewChanges", (DWORD,)),
    ]


class IVirtualDesktopNotificationService(IUnknown):
    """Registration point for desktop change callbacks. Stable across builds."""

    _iid_ = GUID_IVirtualDesktopNotificationService
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "Register",
            (["in"], LPVOID, "pNotification"),
            (["out"], POINTER(DWORD), "pdwCookie"),
        ),
        COMMETHOD([], HRESULT, "Unregister", (["in"], DWORD, "dwCookie")),
    ]


def _make_virtual_desktop(tier: int) -> type[IUnknown]:
    """Build `IVirtualDesktop` for `tier`.

    22621 and later reordered the trailing methods, and everything before
    21313 has neither a name nor a wallpaper.
    """
    if tier >= TIER_26100:
        iid = GUID_IVirtualDesktop_26100
    elif tier >= TIER_22631:
        iid = GUID_IVirtualDesktop_22631
    elif tier >= TIER_22621:
        iid = GUID_IVirtualDesktop_22621
    elif tier >= TIER_21313:
        iid = GUID_IVirtualDesktop_21313
    elif tier >= TIER_20231:
        iid = GUID_IVirtualDesktop_20231
    else:
        iid = GUID_IVirtualDesktop_9000

    if tier >= TIER_22621:
        methods = [
            STDMETHOD(HRESULT, "IsViewVisible", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetID", (["out"], POINTER(GUID), "pGuid")),
            COMMETHOD([], HRESULT, "GetName", (["out"], POINTER(HSTRING), "pName")),
            COMMETHOD([], HRESULT, "GetWallpaperPath", (["out"], POINTER(HSTRING), "pPath")),
            COMMETHOD([], HRESULT, "IsRemote", (["out"], POINTER(HWND), "pW")),
        ]
    elif tier >= TIER_21313:
        methods = [
            STDMETHOD(HRESULT, "IsViewVisible", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetID", (["out"], POINTER(GUID), "pGuid")),
            COMMETHOD([], HRESULT, "IsRemote", (["out"], POINTER(HWND), "pW")),
            COMMETHOD([], HRESULT, "GetName", (["out"], POINTER(HSTRING), "pName")),
            COMMETHOD([], HRESULT, "GetWallpaperPath", (["out"], POINTER(HSTRING), "pPath")),
        ]
    else:
        methods = [
            STDMETHOD(HRESULT, "IsViewVisible", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetID", (["out"], POINTER(GUID), "pGuid")),
        ]

    return type("IVirtualDesktop", (IUnknown,), {"_iid_": iid, "_methods_": methods})


def _manager_methods(tier: int, desktop: type[IUnknown]) -> list[Any]:
    """Build the `IVirtualDesktopManagerInternal` vtable for `tier`.

    Every tier here is a distinct layout that shipped in the wild. The
    pre-22621 tiers take an extra leading HWND on several methods, and 22449
    inserted `GetAllCurrentDesktops` without changing the interface GUID.
    """
    if tier >= TIER_26100:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetCurrentDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            COMMETHOD([], HRESULT, "GetDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (POINTER(desktop),)),
            STDMETHOD(HRESULT, "SwitchDesktopAndMoveForegroundView", (POINTER(desktop),)),
            COMMETHOD([], HRESULT, "CreateDesktopW", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            STDMETHOD(HRESULT, "MoveDesktop", (POINTER(desktop), UINT)),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(
                HRESULT,
                "GetDesktopSwitchIncludeExcludeViews",
                (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
            ),
            COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            COMMETHOD([], HRESULT, "SetWallpaper", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "path")),
            COMMETHOD([], HRESULT, "SetWallpaperForAllDesktops", (["in"], HSTRING, "path")),
            COMMETHOD(
                [],
                HRESULT,
                "CopyDesktopState",
                (["in"], POINTER(IApplicationView), "pView0"),
                (["in"], POINTER(IApplicationView), "pView1"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "CreateRemoteDesktop",
                (["in"], HSTRING, "a1"),
                (["out"], POINTER(POINTER(desktop)), "out"),
            ),
            STDMETHOD(HRESULT, "pDesktop", (POINTER(desktop),)),
            STDMETHOD(HRESULT, "SwitchRemoteDesktop", (POINTER(desktop), UINT)),
            STDMETHOD(HRESULT, "SwitchDesktopWithAnimation", (POINTER(desktop),)),
            COMMETHOD([], HRESULT, "GetLastActiveDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            STDMETHOD(HRESULT, "WaitForAnimationToComplete"),
        ]

    if tier >= TIER_22631:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetCurrentDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            COMMETHOD([], HRESULT, "GetDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (POINTER(desktop),)),
            COMMETHOD([], HRESULT, "CreateDesktopW", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            STDMETHOD(HRESULT, "MoveDesktop", (POINTER(desktop), UINT)),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(
                HRESULT,
                "GetDesktopSwitchIncludeExcludeViews",
                (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
            ),
            COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            COMMETHOD([], HRESULT, "SetWallpaper", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "path")),
            COMMETHOD([], HRESULT, "SetWallpaperForAllDesktops", (["in"], HSTRING, "path")),
            COMMETHOD(
                [],
                HRESULT,
                "CopyDesktopState",
                (["in"], POINTER(IApplicationView), "pView0"),
                (["in"], POINTER(IApplicationView), "pView1"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "CreateRemoteDesktop",
                (["in"], HSTRING, "a1"),
                (["out"], POINTER(POINTER(desktop)), "out"),
            ),
            STDMETHOD(HRESULT, "pDesktop", (POINTER(desktop),)),
            STDMETHOD(HRESULT, "SwitchRemoteDesktop", (POINTER(desktop), UINT)),
            STDMETHOD(HRESULT, "SwitchDesktopWithAnimation", (POINTER(desktop),)),
            COMMETHOD([], HRESULT, "GetLastActiveDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            STDMETHOD(HRESULT, "WaitForAnimationToComplete"),
        ]

    if tier >= TIER_22621:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD([], HRESULT, "GetCurrentDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            COMMETHOD([], HRESULT, "GetDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (POINTER(desktop),)),
            COMMETHOD([], HRESULT, "CreateDesktopW", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
            STDMETHOD(HRESULT, "MoveDesktop", (POINTER(desktop), HWND, INT)),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(
                HRESULT,
                "Unknown",
                (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
            ),
            COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            COMMETHOD([], HRESULT, "SetWallpaper", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "path")),
            COMMETHOD([], HRESULT, "SetWallpaperForAllDesktops", (["in"], HSTRING, "path")),
            COMMETHOD(
                [],
                HRESULT,
                "CopyDesktopState",
                (["in"], POINTER(IApplicationView), "pView0"),
                (["in"], POINTER(IApplicationView), "pView1"),
            ),
            COMMETHOD([], HRESULT, "GetDesktopPerMonitor", (["out"], POINTER(BOOL), "state")),
            COMMETHOD([], HRESULT, "SetDesktopPerMonitor", (["in"], BOOL, "state")),
        ]

    if tier >= TIER_22449:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["in"], HWND, "hwnd"), (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD(
                [],
                HRESULT,
                "GetCurrentDesktop",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            # Added in 22449 without a GUID change.
            COMMETHOD([], HRESULT, "GetAllCurrentDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
            COMMETHOD(
                [],
                HRESULT,
                "GetDesktops",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(IObjectArray)), "array"),
            ),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (HWND, POINTER(desktop))),
            COMMETHOD(
                [],
                HRESULT,
                "CreateDesktopW",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(HRESULT, "MoveDesktop", (POINTER(desktop), HWND, INT)),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(
                HRESULT,
                "Unknown",
                (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
            ),
            COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            COMMETHOD([], HRESULT, "SetWallpaper", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "path")),
            COMMETHOD([], HRESULT, "SetWallpaperForAllDesktops", (["in"], HSTRING, "path")),
            COMMETHOD(
                [],
                HRESULT,
                "CopyDesktopState",
                (["in"], POINTER(IApplicationView), "pView0"),
                (["in"], POINTER(IApplicationView), "pView1"),
            ),
            COMMETHOD([], HRESULT, "GetDesktopPerMonitor", (["out"], POINTER(BOOL), "state")),
            COMMETHOD([], HRESULT, "SetDesktopPerMonitor", (["in"], BOOL, "state")),
        ]

    if tier >= TIER_21313:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["in"], HWND, "hwnd"), (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD(
                [],
                HRESULT,
                "GetCurrentDesktop",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetDesktops",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(IObjectArray)), "array"),
            ),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (HWND, POINTER(desktop))),
            COMMETHOD(
                [],
                HRESULT,
                "CreateDesktopW",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(HRESULT, "MoveDesktop", (POINTER(desktop), HWND, INT)),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            STDMETHOD(
                HRESULT,
                "Unknown",
                (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
            ),
            COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            COMMETHOD([], HRESULT, "SetWallpaper", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "path")),
            COMMETHOD([], HRESULT, "SetWallpaperForAllDesktops", (["in"], HSTRING, "path")),
            COMMETHOD(
                [],
                HRESULT,
                "CopyDesktopState",
                (["in"], POINTER(IApplicationView), "pView0"),
                (["in"], POINTER(IApplicationView), "pView1"),
            ),
            COMMETHOD([], HRESULT, "GetDesktopPerMonitor", (["out"], POINTER(BOOL), "state")),
            COMMETHOD([], HRESULT, "SetDesktopPerMonitor", (["in"], BOOL, "state")),
        ]

    if tier >= TIER_20231:
        return [
            COMMETHOD([], HRESULT, "GetCount", (["in"], HWND, "hwnd"), (["out"], POINTER(UINT), "pCount")),
            STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
            STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
            COMMETHOD(
                [],
                HRESULT,
                "GetCurrentDesktop",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetDesktops",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(IObjectArray)), "array"),
            ),
            STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
            STDMETHOD(HRESULT, "SwitchDesktop", (HWND, POINTER(desktop))),
            COMMETHOD(
                [],
                HRESULT,
                "CreateDesktopW",
                (["in"], HWND, "hwnd"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "RemoveDesktop",
                (["in"], POINTER(desktop), "destroyDesktop"),
                (["in"], POINTER(desktop), "fallbackDesktop"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "FindDesktop",
                (["in"], POINTER(GUID), "pGuid"),
                (["out"], POINTER(POINTER(desktop)), "pDesktop"),
            ),
        ]

    return [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pCount")),
        STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
        STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetCurrentDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
        COMMETHOD([], HRESULT, "GetDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
        STDMETHOD(HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))),
        STDMETHOD(HRESULT, "SwitchDesktop", (POINTER(desktop),)),
        COMMETHOD([], HRESULT, "CreateDesktopW", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
        COMMETHOD(
            [],
            HRESULT,
            "RemoveDesktop",
            (["in"], POINTER(desktop), "destroyDesktop"),
            (["in"], POINTER(desktop), "fallbackDesktop"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "FindDesktop",
            (["in"], POINTER(GUID), "pGuid"),
            (["out"], POINTER(POINTER(desktop)), "pDesktop"),
        ),
    ]


def _make_manager_internal(tier: int, desktop: type[IUnknown]) -> type[IUnknown]:
    """Build `IVirtualDesktopManagerInternal` for `tier`.

    The wrapper methods hide the fact that pre-22621 builds take a leading
    HWND (always passed as 0, meaning "all monitors") on the calls we make.
    """
    takes_hwnd = TIER_20231 <= tier < TIER_22621

    def get_all_desktops(self):
        return self.GetDesktops(0) if takes_hwnd else self.GetDesktops()

    def get_current_desktop(self):
        return self.GetCurrentDesktop(0) if takes_hwnd else self.GetCurrentDesktop()

    def create_desktop(self):
        return self.CreateDesktopW(0) if takes_hwnd else self.CreateDesktopW()

    def switch_desktop(self, target):
        return self.SwitchDesktop(0, target) if takes_hwnd else self.SwitchDesktop(target)

    return type(
        "IVirtualDesktopManagerInternal",
        (IUnknown,),
        {
            "_iid_": MANAGER_GUID_BY_TIER[tier],
            "_methods_": _manager_methods(tier, desktop),
            "get_all_desktops": get_all_desktops,
            "get_current_desktop": get_current_desktop,
            "create_desktop": create_desktop,
            "switch_desktop": switch_desktop,
        },
    )


def _make_manager_internal2(desktop: type[IUnknown]) -> type[IUnknown]:
    """Build `IVirtualDesktopManagerInternal2`, the 19041-era rename route."""
    return type(
        "IVirtualDesktopManagerInternal2",
        (IUnknown,),
        {
            "_iid_": GUID_IVirtualDesktopManagerInternal2,
            "_methods_": [
                COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pCount")),
                STDMETHOD(HRESULT, "MoveViewToDesktop", (POINTER(IApplicationView), POINTER(desktop))),
                STDMETHOD(HRESULT, "CanViewMoveDesktops", (POINTER(IApplicationView), POINTER(UINT))),
                COMMETHOD([], HRESULT, "GetCurrentDesktop", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
                COMMETHOD([], HRESULT, "GetDesktops", (["out"], POINTER(POINTER(IObjectArray)), "array")),
                STDMETHOD(
                    HRESULT, "GetAdjacentDesktop", (POINTER(desktop), AdjacentDesktop, POINTER(POINTER(desktop)))
                ),
                STDMETHOD(HRESULT, "SwitchDesktop", (POINTER(desktop),)),
                COMMETHOD([], HRESULT, "CreateDesktopW", (["out"], POINTER(POINTER(desktop)), "pDesktop")),
                COMMETHOD(
                    [],
                    HRESULT,
                    "RemoveDesktop",
                    (["in"], POINTER(desktop), "destroyDesktop"),
                    (["in"], POINTER(desktop), "fallbackDesktop"),
                ),
                COMMETHOD(
                    [],
                    HRESULT,
                    "FindDesktop",
                    (["in"], POINTER(GUID), "pGuid"),
                    (["out"], POINTER(POINTER(desktop)), "pDesktop"),
                ),
                STDMETHOD(
                    HRESULT,
                    "Unknown",
                    (POINTER(desktop), POINTER(POINTER(IObjectArray)), POINTER(POINTER(IObjectArray))),
                ),
                COMMETHOD([], HRESULT, "SetName", (["in"], POINTER(desktop), "pDesktop"), (["in"], HSTRING, "name")),
            ],
        },
    )


# Notification vtables. Parameters are declared opaque because the sink never
# inspects them; state is re-queried through the manager instead.
_NOTIFICATION_METHODS_WIN10 = [
    ("VirtualDesktopCreated", 1),
    ("VirtualDesktopDestroyBegin", 2),
    ("VirtualDesktopDestroyFailed", 2),
    ("VirtualDesktopDestroyed", 2),
    ("ViewVirtualDesktopChanged", 1),
    ("CurrentVirtualDesktopChanged", 2),
]

_NOTIFICATION_METHODS_21H2 = [
    ("VirtualDesktopCreated", 2),
    ("VirtualDesktopDestroyBegin", 3),
    ("VirtualDesktopDestroyFailed", 3),
    ("VirtualDesktopDestroyed", 3),
    ("Proc7", 1),
    ("VirtualDesktopMoved", 4),
    ("VirtualDesktopRenamed", 2),
    ("ViewVirtualDesktopChanged", 1),
    ("CurrentVirtualDesktopChanged", 3),
    ("VirtualDesktopWallpaperChanged", 2),
]

_NOTIFICATION_METHODS_23H2 = [
    ("VirtualDesktopCreated", 1),
    ("VirtualDesktopDestroyBegin", 2),
    ("VirtualDesktopDestroyFailed", 2),
    ("VirtualDesktopDestroyed", 2),
    ("VirtualDesktopMoved", 3),
    ("VirtualDesktopRenamed", 2),
    ("ViewVirtualDesktopChanged", 1),
    ("CurrentVirtualDesktopChanged", 2),
    ("VirtualDesktopWallpaperChanged", 2),
    ("VirtualDesktopSwitched", 1),
    ("RemoteVirtualDesktopConnected", 1),
]


def _make_notification(iid: GUID, spec: list[tuple[str, int]], name: str) -> type[IUnknown]:
    """Build a notification sink interface from a (method, arity) spec."""
    methods = [
        COMMETHOD([], HRESULT, method, *[(["in"], c_void_p, f"p{i}") for i in range(arity)]) for method, arity in spec
    ]
    return type(name, (IUnknown,), {"_iid_": iid, "_methods_": methods})


def _make_notification_ifaces(tier: int) -> tuple[type[IUnknown], type[IUnknown]]:
    """Build the notification sink interfaces for `tier`.

    The second interface is a 19041-era derived one. The shell there reports
    renames by calling QueryInterface for it rather than using the primary
    sink, so it is registered unconditionally. Its layout does not vary.
    """
    if tier >= TIER_22631:
        iid, spec = GUID_IVirtualDesktopNotification_22631, _NOTIFICATION_METHODS_23H2
    elif tier >= TIER_22621:
        iid, spec = GUID_IVirtualDesktopNotification_22621, _NOTIFICATION_METHODS_23H2
    elif tier >= TIER_20231:
        iid, spec = GUID_IVirtualDesktopNotification_20231, _NOTIFICATION_METHODS_21H2
    else:
        iid, spec = GUID_IVirtualDesktopNotification_9000, _NOTIFICATION_METHODS_WIN10

    primary = _make_notification(iid, spec, "IVirtualDesktopNotification")
    secondary = _make_notification(
        GUID_IVirtualDesktopNotification2,
        _NOTIFICATION_METHODS_WIN10 + [("VirtualDesktopRenamed", 2)],
        "IVirtualDesktopNotification2",
    )
    return primary, secondary


@dataclass(frozen=True)
class DesktopInterfaces:
    """The interface set matching one Windows build tier."""

    tier: int
    IVirtualDesktop: type[IUnknown]
    IVirtualDesktopManagerInternal: type[IUnknown]
    IVirtualDesktopManagerInternal2: type[IUnknown]
    IVirtualDesktopNotification: type[IUnknown]
    IVirtualDesktopNotification2: type[IUnknown]

    @property
    def supports_names(self) -> bool:
        return supports_desktop_names(self.tier)

    @property
    def supports_wallpaper(self) -> bool:
        return supports_wallpaper(self.tier)


class VirtualDesktopUnsupportedError(RuntimeError):
    """Raised when no known virtual desktop interface is available."""


def _service_provider() -> Any:
    """Create the Immersive Shell service provider."""
    return CoCreateInstance(CLSID_ImmersiveShell, IServiceProvider, CLSCTX_LOCAL_SERVER)


def _manager_available(provider: Any, iid: GUID) -> bool:
    """Does the shell hand out the desktop manager under this interface GUID?"""
    pointer = POINTER(IUnknown)()
    try:
        provider.QueryService(CLSID_VirtualDesktopManagerInternal, iid, pointer)
    except COMError:
        return False
    return True


def resolve_tier() -> int:
    """Determine which interface tier this machine speaks.

    Only the Windows 11 range is ambiguous, because 22H2 gained newer shell
    interfaces through Moment updates without a build change. Builds outside
    that range are decided by build number alone; inside it the shell is asked
    directly, trying each candidate GUID from newest to oldest.
    """
    build = sys.getwindowsversion().build
    if build >= TIER_26100:
        logger.debug("Virtual desktop tier %d selected from build %d", TIER_26100, build)
        return TIER_26100
    if build < TIER_20231:
        # Windows 10 shipped 19041 to 19045 on one shell generation.
        logger.debug("Virtual desktop tier %d selected from build %d", TIER_WIN10, build)
        return TIER_WIN10

    provider = _service_provider()
    for tier in PROBE_ORDER:
        if not _manager_available(provider, MANAGER_GUID_BY_TIER[tier]):
            continue
        # 22449 added a method to the 21313 interface without changing its GUID.
        if tier == TIER_21313 and build >= TIER_22449:
            tier = TIER_22449
        logger.debug("Virtual desktop tier %d resolved by probe on build %d", tier, build)
        return tier

    tried = ", ".join(str(MANAGER_GUID_BY_TIER[t]) for t in PROBE_ORDER)
    raise VirtualDesktopUnsupportedError(
        f"No supported IVirtualDesktopManagerInternal interface found on build {build}. "
        f"Tried: {tried}. Please report this at https://github.com/amnweb/yasb/issues"
    )


_interfaces: DesktopInterfaces | None = None


def get_interfaces() -> DesktopInterfaces:
    """Return the interface set for this machine, resolving it on first call.

    Only one tier is built per process. comtypes keeps a global registry keyed by
    interface GUID, and several tiers reuse the same GUID with different vtables,
    so building more than one would leave it pointing at the wrong layout.
    """
    global _interfaces
    if _interfaces is None:
        tier = resolve_tier()
        desktop = _make_virtual_desktop(tier)
        notification, notification2 = _make_notification_ifaces(tier)
        _interfaces = DesktopInterfaces(
            tier=tier,
            IVirtualDesktop=desktop,
            IVirtualDesktopManagerInternal=_make_manager_internal(tier, desktop),
            IVirtualDesktopManagerInternal2=_make_manager_internal2(desktop),
            IVirtualDesktopNotification=notification,
            IVirtualDesktopNotification2=notification2,
        )
    return _interfaces

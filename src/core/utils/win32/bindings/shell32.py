"""Wrappers for Shell32 win32 API functions to make them easier to use and have proper types.

This module exposes the `shell32` handle and sets argtypes/restype for the Shell
functions we call from Python so ctypes marshaling is explicit and safe.
"""

from collections.abc import Iterator
from ctypes import (
    HRESULT,
    POINTER,
    Array,
    WinDLL,
    byref,
    c_int,
    c_long,
    c_size_t,
    c_uint,
    c_void_p,
    c_wchar,
    c_wchar_p,
    wstring_at,
)
from ctypes.wintypes import BOOL, DWORD, HANDLE, HBITMAP, HWND, LPCWSTR, LPVOID, UINT
from typing import TYPE_CHECKING, Any, cast

import comtypes  # pyright: ignore[reportMissingTypeStubs]
from comtypes import COMMETHOD, GUID, STDMETHOD, COMError  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]

from core.utils.win32.bindings.ole32 import CoTaskMemFree, PropVariantClear
from core.utils.win32.constants import GPS_DEFAULT, SW_SHOWNORMAL, VT_LPWSTR
from core.utils.win32.structs import (
    APPBARDATA,
    PROPERTYKEY,
    PROPVARIANT,
    SHELLEXECUTEINFO,
    SHQUERYRBINFO,
    SHSTOCKICONINFO,
    SIZE,
)
from core.utils.win32.typecheck import CArgObject

shell32 = WinDLL("shell32", use_last_error=True)

# https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew
shell32.ShellExecuteW.argtypes = [c_void_p, c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p, c_int]
shell32.ShellExecuteW.restype = c_void_p

shell32.ShellExecuteExW.argtypes = [POINTER(SHELLEXECUTEINFO)]
shell32.ShellExecuteExW.restype = BOOL

shell32.SHGetFolderPathW.argtypes = [HWND, c_int, HANDLE, DWORD, c_wchar_p]
shell32.SHGetFolderPathW.restype = HRESULT

shell32.SHAppBarMessage.argtypes = [DWORD, POINTER(APPBARDATA)]
shell32.SHAppBarMessage.restype = c_size_t

shell32.IsUserAnAdmin.argtypes = []
shell32.IsUserAnAdmin.restype = BOOL

shell32.SHGetStockIconInfo.argtypes = [c_int, c_uint, POINTER(SHSTOCKICONINFO)]
shell32.SHGetStockIconInfo.restype = c_long

shell32.SHQueryRecycleBinW.argtypes = [LPCWSTR, POINTER(SHQUERYRBINFO)]
shell32.SHQueryRecycleBinW.restype = c_long

shell32.SHEmptyRecycleBinW.argtypes = [HWND, LPCWSTR, DWORD]
shell32.SHEmptyRecycleBinW.restype = c_long


def shell_execute(
    file: str,
    verb: str = "open",
    parameters: str | None = None,
    directory: str | None = None,
    show_cmd: int = SW_SHOWNORMAL,
) -> int:
    """Launch a file, URL, or shortcut via ShellExecuteW.

    Args:
        file: Path to the file, URL, or shortcut to open.
        verb: Shell verb - "open", "runas", "edit", "print", etc.
        parameters: Optional command-line arguments.
        directory: Optional working directory.
        show_cmd: Window show state (SW_SHOWNORMAL=1, SW_HIDE=0, etc).

    Returns:
        Handle value >32 on success, <=32 on error.
    """
    return shell32.ShellExecuteW(None, verb, file, parameters, directory, show_cmd)


def ShellExecuteEx(pExecInfo: CArgObject) -> bool:
    return bool(shell32.ShellExecuteExW(pExecInfo))


def SHGetFolderPath(csidl: int, pszPath: Array[c_wchar]) -> int:
    return shell32.SHGetFolderPathW(None, csidl, None, 0, pszPath)


def SHAppBarMessage(dwMessage: int, pData: APPBARDATA) -> int:
    return shell32.SHAppBarMessage(dwMessage, byref(pData))


def IsUserAnAdmin() -> bool:
    return bool(shell32.IsUserAnAdmin())


# IDesktopWallpaper COM interface for Windows 10/11
# https://docs.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-idesktopwallpaper
class IDesktopWallpaper(comtypes.IUnknown):
    """
    COM interface for managing desktop wallpapers in Windows 10/11.

    Interface IID: {B92B56A9-8B55-4E14-9A89-0199BBB6F93B}
    CLSID: {C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}
    """

    _iid_ = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
    _methods_ = [
        COMMETHOD([], HRESULT, "SetWallpaper", (["in"], c_wchar_p, "monitorID"), (["in"], c_wchar_p, "wallpaper")),
        COMMETHOD(
            [], HRESULT, "GetWallpaper", (["in"], c_wchar_p, "monitorID"), (["out"], POINTER(c_wchar_p), "wallpaper")
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorDevicePathAt",
            (["in"], c_uint, "monitorIndex"),
            (["out"], POINTER(c_wchar_p), "monitorID"),
        ),
        COMMETHOD([], HRESULT, "GetMonitorDevicePathCount", (["out"], POINTER(c_uint), "count")),
    ]

    if TYPE_CHECKING:

        def SetWallpaper(self, monitorID: str | None, wallpaper: str) -> None: ...
        def GetWallpaper(self, monitorID: str | None) -> str: ...
        def GetMonitorDevicePathAt(self, monitorIndex: int) -> str: ...
        def GetMonitorDevicePathCount(self) -> int: ...


CLSID_DesktopWallpaper = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")


IID_IPropertyStore = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")


# https://learn.microsoft.com/en-us/windows/win32/api/propsys/nn-propsys-ipropertystore
class IPropertyStore(comtypes.IUnknown):
    _iid_ = IID_IPropertyStore
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(DWORD), "cProps")),
        COMMETHOD([], HRESULT, "GetAt", (["in"], DWORD, "iProp"), (["out"], POINTER(PROPERTYKEY), "pkey")),
        COMMETHOD(
            [], HRESULT, "GetValue", (["in"], POINTER(PROPERTYKEY), "key"), (["out"], POINTER(PROPVARIANT), "pv")
        ),
        COMMETHOD(
            [], HRESULT, "SetValue", (["in"], POINTER(PROPERTYKEY), "key"), (["in"], POINTER(PROPVARIANT), "propvar")
        ),
        COMMETHOD([], HRESULT, "Commit"),
    ]

    if TYPE_CHECKING:

        def GetValue(self, key: PROPERTYKEY) -> PROPVARIANT: ...
        def SetValue(self, key: PROPERTYKEY, propvar: PROPVARIANT) -> None: ...
        def Commit(self) -> None: ...


shell32.SHGetPropertyStoreForWindow.argtypes = [HWND, POINTER(GUID), POINTER(POINTER(IPropertyStore))]
shell32.SHGetPropertyStoreForWindow.restype = c_long

shell32.SHGetPropertyStoreFromParsingName.argtypes = [
    LPCWSTR,
    c_void_p,
    c_int,
    POINTER(GUID),
    POINTER(POINTER(IPropertyStore)),
]
shell32.SHGetPropertyStoreFromParsingName.restype = c_long


def SHGetPropertyStoreForWindow(hwnd: int) -> IPropertyStore | None:
    store = POINTER(IPropertyStore)()
    if shell32.SHGetPropertyStoreForWindow(hwnd, byref(IID_IPropertyStore), byref(store)) != 0 or not store:
        return None
    return cast(IPropertyStore, store)


def SHGetPropertyStoreFromParsingName(path: str, flags: int = GPS_DEFAULT) -> IPropertyStore | None:
    store = POINTER(IPropertyStore)()
    hr = shell32.SHGetPropertyStoreFromParsingName(path, None, flags, byref(IID_IPropertyStore), byref(store))
    if hr != 0 or not store:
        return None
    return cast(IPropertyStore, store)


def get_string_property(store: IPropertyStore, key: PROPERTYKEY) -> str | None:
    try:
        value = store.GetValue(key)
    except COMError:
        return None
    try:
        # pwszVal shares the union with the other types, only read it once vt says it is a string
        if value.vt == VT_LPWSTR and value.pwszVal:
            return value.pwszVal
        return None
    finally:
        PropVariantClear(value)


IID_IShellItemImageFactory = GUID("{BCC18B79-BA16-442F-80C4-8A59C30C463B}")


# https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishellitemimagefactory
class IShellItemImageFactory(comtypes.IUnknown):
    _iid_ = IID_IShellItemImageFactory
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetImage",
            (["in"], SIZE, "size"),
            (["in"], c_int, "flags"),
            (["out"], POINTER(HBITMAP), "phbm"),
        ),
    ]

    if TYPE_CHECKING:

        def GetImage(self, size: SIZE, flags: int) -> int | None: ...


shell32.SHCreateItemFromParsingName.argtypes = [
    LPCWSTR,
    c_void_p,
    POINTER(GUID),
    POINTER(POINTER(IShellItemImageFactory)),
]
shell32.SHCreateItemFromParsingName.restype = c_long


def SHCreateItemFromParsingName(path: str) -> IShellItemImageFactory | None:
    factory = POINTER(IShellItemImageFactory)()
    hr = shell32.SHCreateItemFromParsingName(path, None, byref(IID_IShellItemImageFactory), byref(factory))
    if hr != 0 or not factory:
        return None
    return cast(IShellItemImageFactory, factory)


# https://learn.microsoft.com/en-us/windows/win32/api/servprov/nn-servprov-iserviceprovider
class IServiceProvider(comtypes.IUnknown):
    """Used to query the Immersive Shell for its internal service singletons."""

    _iid_ = GUID("{6D5140C1-7436-11CE-8034-00AA006009FA}")
    _methods_ = [
        STDMETHOD(HRESULT, "QueryService", (POINTER(GUID), POINTER(GUID), POINTER(LPVOID))),
    ]


# https://learn.microsoft.com/en-us/windows/win32/api/objectarray/nn-objectarray-iobjectarray
class IObjectArray(comtypes.IUnknown):
    """A homogeneous array of COM objects, returned by several shell interfaces."""

    _iid_ = GUID("{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pcObjects")),
        STDMETHOD(HRESULT, "GetAt", (UINT, POINTER(GUID), POINTER(LPVOID))),
    ]

    def get_at(self, index: int, cls: type[comtypes.IUnknown]) -> Any:
        """Return the item at index, cast to interface cls."""
        item = POINTER(cls)()
        self.GetAt(index, cls._iid_, item)  # type: ignore[attr-defined]
        return item

    def iter(self, cls: type[comtypes.IUnknown]) -> Iterator[Any]:
        """Iterate the array as instances of cls."""
        for i in range(self.GetCount()):  # type: ignore[attr-defined]
            yield self.get_at(i, cls)


CLSID_VirtualDesktopManager = GUID("{AA509086-5CA9-4C25-8F95-589D3C07B48A}")


# https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ivirtualdesktopmanager
class IVirtualDesktopManager(comtypes.IUnknown):
    _iid_ = GUID("{A5CD92FF-29BE-454C-8D04-D82879FB3F1B}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "IsWindowOnCurrentVirtualDesktop",
            (["in"], HWND, "topLevelWindow"),
            (["out"], POINTER(BOOL), "onCurrentDesktop"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetWindowDesktopId",
            (["in"], HWND, "topLevelWindow"),
            (["out"], POINTER(GUID), "desktopId"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "MoveWindowToDesktop",
            (["in"], HWND, "topLevelWindow"),
            (["in"], POINTER(GUID), "desktopId"),
        ),
    ]

    if TYPE_CHECKING:

        def GetWindowDesktopId(self, topLevelWindow: int) -> GUID: ...


CLSID_UIHostNoLaunch = GUID("{4CE576FA-83DC-4F88-951C-9D0782B4E376}")


# Undocumented: the touch keyboard's (TabTip) COM server
class ITipInvocation(comtypes.IUnknown):
    _iid_ = GUID("{37C994E7-432B-4834-A2F7-DCE1F13B834B}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Toggle", (["in"], HWND, "wnd")),
    ]

    if TYPE_CHECKING:

        def Toggle(self, wnd: int) -> None: ...


CLSID_QuietHoursSettings = GUID("{F53321FA-34F8-4B7F-B9A3-361877CB94CF}")


# Undocumented: the shell's Focus Assist (Do Not Disturb) settings
class IQuietHoursSettings(comtypes.IUnknown):
    _iid_ = GUID("{6BFF4732-81EC-4FFB-AE67-B6C1BC29631F}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_UserSelectedProfile", (["out"], POINTER(c_void_p), "profileId")),
        COMMETHOD([], HRESULT, "put_UserSelectedProfile", (["in"], c_wchar_p, "profileId")),
    ]

    if TYPE_CHECKING:

        def get_UserSelectedProfile(self) -> int | None: ...
        def put_UserSelectedProfile(self, profileId: str) -> None: ...


def get_user_selected_profile(settings: IQuietHoursSettings) -> str | None:
    try:
        address = settings.get_UserSelectedProfile()
    except COMError:
        return None
    if not address:
        return None
    try:
        return wstring_at(address)
    finally:
        CoTaskMemFree(address)

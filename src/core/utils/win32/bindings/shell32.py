"""Wrappers for Shell32 win32 API functions to make them easier to use and have proper types.

This module exposes the `shell32` handle and sets argtypes/restype for the Shell
functions we call from Python so ctypes marshaling is explicit and safe.
"""

from ctypes import HRESULT, POINTER, Array, c_int, c_uint, c_void_p, c_wchar, c_wchar_p, windll
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND
from typing import TYPE_CHECKING

import comtypes  # pyright: ignore[reportMissingTypeStubs]
from comtypes import COMMETHOD, GUID  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]

from core.utils.win32.constants import SW_SHOWNORMAL
from core.utils.win32.structs import SHELLEXECUTEINFO
from core.utils.win32.typecheck import CArgObject

shell32 = windll.shell32

# https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew
shell32.ShellExecuteW.argtypes = [c_void_p, c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p, c_int]
shell32.ShellExecuteW.restype = c_void_p

shell32.ShellExecuteExW.argtypes = [POINTER(SHELLEXECUTEINFO)]
shell32.ShellExecuteExW.restype = BOOL

shell32.SHGetFolderPathW.argtypes = [HWND, c_int, HANDLE, DWORD, c_wchar_p]
shell32.SHGetFolderPathW.restype = HRESULT


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

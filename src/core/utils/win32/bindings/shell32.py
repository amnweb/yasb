"""Wrappers for Shell32 win32 API functions to make them easier to use and have proper types.

This module exposes the `shell32` handle and sets argtypes/restype for the Shell
functions we call from Python so ctypes marshaling is explicit and safe.
"""

from ctypes import HRESULT, c_int, c_void_p, c_wchar_p, windll

import comtypes
from comtypes import COMMETHOD, GUID

from core.utils.win32.constants import SW_SHOWNORMAL

shell32 = windll.shell32

# https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew
shell32.ShellExecuteW.argtypes = [c_void_p, c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p, c_int]
shell32.ShellExecuteW.restype = c_void_p


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
        # Additional methods can be added here if needed:
        # GetWallpaper, GetMonitorDevicePathAt, GetMonitorDevicePathCount, etc.
    ]

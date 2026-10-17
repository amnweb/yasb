"""Wrappers for uxtheme win32 API functions"""

from ctypes import WinDLL, c_bool, c_int
from ctypes.wintypes import HWND

uxtheme = WinDLL("uxtheme", use_last_error=True)

# SetPreferredAppMode (135), AllowDarkModeForWindow (133) and FlushMenuThemes (136) are undocumented and exported
# by ordinal only, so a build without them must not break the import
_set_preferred_app_mode = None
try:
    _set_preferred_app_mode = uxtheme[135]  # pyright: ignore[reportArgumentType]
    _set_preferred_app_mode.argtypes = [c_int]
    _set_preferred_app_mode.restype = c_int
except AttributeError:
    pass

_allow_dark_mode_for_window = None
try:
    _allow_dark_mode_for_window = uxtheme[133]  # pyright: ignore[reportArgumentType]
    _allow_dark_mode_for_window.argtypes = [HWND, c_bool]
    _allow_dark_mode_for_window.restype = c_bool
except AttributeError:
    pass

_flush_menu_themes = None
try:
    _flush_menu_themes = uxtheme[136]  # pyright: ignore[reportArgumentType]
    _flush_menu_themes.argtypes = []
    _flush_menu_themes.restype = None
except AttributeError:
    pass


def SetPreferredAppMode(appMode: int) -> int:
    if _set_preferred_app_mode is None:
        raise OSError("uxtheme.dll does not export SetPreferredAppMode")
    return _set_preferred_app_mode(appMode)


def AllowDarkModeForWindow(hwnd: int, allow: bool) -> bool:
    if _allow_dark_mode_for_window is None:
        raise OSError("uxtheme.dll does not export AllowDarkModeForWindow")
    return bool(_allow_dark_mode_for_window(hwnd, allow))


def FlushMenuThemes() -> None:
    if _flush_menu_themes is None:
        raise OSError("uxtheme.dll does not export FlushMenuThemes")
    _flush_menu_themes()

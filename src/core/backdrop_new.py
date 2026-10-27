import ctypes
import logging
import sys
from ctypes import wintypes

from core.utils.win32.bindings.dwmapi import DwmExtendFrameIntoClientArea, DwmSetWindowAttribute
from core.utils.win32.bindings.kernel32 import GetLastError
from core.utils.win32.bindings.user32 import DefWindowProc, SetWindowCompositionAttribute
from core.utils.win32.constants import (
    DWMSBT_MAINWINDOW,
    DWMSBT_NONE,
    DWMSBT_TABBEDWINDOW,
    DWMSBT_TRANSIENTWINDOW,
    DWMWA_BORDER_COLOR,
    DWMWA_COLOR_DEFAULT,
    DWMWA_COLOR_NONE,
    DWMWA_SYSTEMBACKDROP_TYPE,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    DWMWA_WINDOW_CORNER_PREFERENCE,
    DWMWCP_DONOTROUND,
    DWMWCP_ROUND,
    DWMWCP_ROUNDSMALL,
    WM_NCACTIVATE,
)
from core.utils.win32.structs import ACCENTPOLICY, MARGINS, WINDOWCOMPOSITIONATTRIBDATA
from core.utils.win32.undocumented import ACCENT_DISABLED, ACCENT_ENABLE_BLURBEHIND, WCA_ACCENT_POLICY

BUILD = sys.getwindowsversion().build
# First builds with DWMWA_WINDOW_CORNER_PREFERENCE/DWMWA_BORDER_COLOR, and with DWMWA_SYSTEMBACKDROP_TYPE
WINDOWS_11 = 22000
WINDOWS_11_22H2 = 22621

SYSTEM_BACKDROPS = {"acrylic": DWMSBT_TRANSIENTWINDOW, "mica": DWMSBT_MAINWINDOW, "mica-alt": DWMSBT_TABBEDWINDOW}
CORNERS = {"square": DWMWCP_DONOTROUND, "round": DWMWCP_ROUND, "small": DWMWCP_ROUNDSMALL}
BORDERS = {"system": DWMWA_COLOR_DEFAULT, "none": DWMWA_COLOR_NONE}


def apply_backdrop(hwnd: int, backdrop: str, corners: str, border: str, dark: bool) -> None:
    if BUILD >= WINDOWS_11:
        _set_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, int(dark))
        _set_attribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, CORNERS[corners])
        _set_attribute(hwnd, DWMWA_BORDER_COLOR, BORDERS.get(border) or _colorref(border))
    set_backdrop(hwnd, backdrop)


def set_backdrop(hwnd: int, backdrop: str) -> None:
    if backdrop in SYSTEM_BACKDROPS and BUILD < WINDOWS_11_22H2:
        logging.warning("The %s backdrop needs Windows 11 22H2 or later, the bar uses blur", backdrop)
        backdrop = "blur"
    _set_accent(hwnd, ACCENT_ENABLE_BLURBEHIND if backdrop == "blur" else ACCENT_DISABLED)
    if BUILD < WINDOWS_11_22H2:
        return
    if backdrop in SYSTEM_BACKDROPS:
        # DWM draws system backdrops only on a window whose frame is active. This marks the frame active without
        # activating the window, and must come before the backdrop type is set.
        DefWindowProc(hwnd, WM_NCACTIVATE, 1, 0)
    _extend_frame(hwnd, -1 if backdrop in SYSTEM_BACKDROPS else 0)
    _set_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, SYSTEM_BACKDROPS.get(backdrop, DWMSBT_NONE))


def _colorref(color: str) -> int:
    red, green, blue = bytes.fromhex(color[1:])
    return red | green << 8 | blue << 16


def _set_attribute(hwnd: int, attribute: int, value: int) -> None:
    data = wintypes.DWORD(value)
    result = DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
    if result != 0:
        logging.warning("DwmSetWindowAttribute %d = %#x failed with %#010x", attribute, value, result & 0xFFFFFFFF)


def _extend_frame(hwnd: int, margin: int) -> None:
    result = DwmExtendFrameIntoClientArea(hwnd, MARGINS(margin, margin, margin, margin))
    if result != 0:
        logging.warning("DwmExtendFrameIntoClientArea %d failed with %#010x", margin, result & 0xFFFFFFFF)


def _set_accent(hwnd: int, state: int) -> None:
    accent = ACCENTPOLICY(AccentState=state)
    data = WINDOWCOMPOSITIONATTRIBDATA(
        Attribute=WCA_ACCENT_POLICY,
        Data=ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int)),
        SizeOfData=ctypes.sizeof(accent),
    )
    if not SetWindowCompositionAttribute(hwnd, ctypes.byref(data)):
        logging.warning("SetWindowCompositionAttribute accent %d failed with error %d", state, GetLastError())

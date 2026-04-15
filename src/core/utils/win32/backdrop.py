import ctypes
import logging
import sys

from core.utils.win32.bindings import (
    DwmExtendFrameIntoClientArea,
    DwmSetWindowAttribute,
    SetWindowCompositionAttribute,
)
from core.utils.win32.constants import (
    ACCENT_ENABLE_ACRYLICBLURBEHIND,
    ACCENT_ENABLE_BLURBEHIND,
    DWMWA_BORDER_COLOR,
    DWMWA_COLOR_DEFAULT,
    DWMWA_COLOR_NONE,
    DWMWA_MICA_EFFECT,
    DWMWA_SYSTEMBACKDROP_TYPE,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    DWMWA_WINDOW_CORNER_PREFERENCE,
    DWMWCP_ROUND,
    DWMWCP_ROUNDSMALL,
    WCA_ACCENT_POLICY,
)
from core.utils.win32.structs import ACCENTPOLICY, MARGINS, WINDOWCOMPOSITIONATTRIBDATA


def HEXtoRGBAint(HEX: str) -> int:
    """Convert #RRGGBBAA hex string to AABBGGRR integer for Win32 API."""
    alpha = HEX[7:]
    blue = HEX[5:7]
    green = HEX[3:5]
    red = HEX[1:3]
    return int(alpha + blue + green + red, base=16)


def set_accent_policy(hwnd, accent_state, gradient_color=0, accent_flags=0):
    accent = ACCENTPOLICY()
    accent.AccentState = accent_state
    accent.AccentFlags = accent_flags
    accent.GradientColor = gradient_color

    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))

    result = SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    if result == 0:
        raise ctypes.WinError()


def _set_dark_mode(hwnd):
    value = ctypes.c_int(1)
    result = DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
    if result != 0:
        raise ctypes.WinError()


def set_window_corner_preference(hwnd, preference, border_color):
    preference_value = ctypes.c_int(preference)
    result = DwmSetWindowAttribute(
        hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference_value), ctypes.sizeof(preference_value)
    )
    if result != 0:
        raise ctypes.WinError()

    if border_color == "None":
        border_color_value = ctypes.c_int(DWMWA_COLOR_NONE)
    elif border_color.lower() == "system":
        border_color_value = ctypes.c_int(DWMWA_COLOR_DEFAULT)
    else:
        border_color_value = ctypes.c_int(HEXtoRGBAint(border_color))

    result = DwmSetWindowAttribute(
        hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border_color_value), ctypes.sizeof(border_color_value)
    )
    if result != 0:
        raise ctypes.WinError()


def enable_blur(hwnd, DarkMode=False, RoundCorners=False, RoundCornersType="normal", BorderColor="System"):
    hwnd = int(hwnd)
    try:
        if sys.getwindowsversion().build >= 22000:
            set_accent_policy(hwnd, ACCENT_ENABLE_BLURBEHIND, gradient_color=0x01202020)
        else:
            set_accent_policy(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, gradient_color=0x01202020)
        if DarkMode:
            _set_dark_mode(hwnd)
        if RoundCorners:
            set_window_corner_preference(
                hwnd, DWMWCP_ROUND if RoundCornersType == "normal" else DWMWCP_ROUNDSMALL, BorderColor
            )
    except Exception as e:
        logging.debug("Failed to apply settings: %s", e)


def is_mica_supported() -> bool:
    """Return True if the current Windows build supports Mica (Win11 22000+)."""
    return sys.getwindowsversion().build >= 22000


def enable_mica(hwnd):
    """Apply Mica backdrop to a window. Requires Windows 11 build 22000+."""
    hwnd = int(hwnd)
    build = sys.getwindowsversion().build
    try:
        margins = MARGINS(-1, -1, -1, -1)
        DwmExtendFrameIntoClientArea(hwnd, margins)
        if build >= 22621:
            value = ctypes.c_int(2)  # DWMSBT_MAINWINDOW
            DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(value), ctypes.sizeof(value))
        else:
            value = ctypes.c_int(1)
            DwmSetWindowAttribute(hwnd, DWMWA_MICA_EFFECT, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as e:
        logging.debug("Failed to apply mica: %s", e)

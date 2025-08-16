import ctypes
import logging

from core.utils.win32.bindings import DwmSetWindowAttribute, SetWindowCompositionAttribute


# Define the ACCENTPOLICY structure
class ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_uint),
    ]


# Define the WINDOWCOMPOSITIONATTRIBDATA structure
class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(ctypes.c_int)), ("SizeOfData", ctypes.c_size_t)]


_SCA = SetWindowCompositionAttribute

# Define constants for DwmSetWindowAttribute
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_COLOR_NONE = 0xFFFFFFFE
DWMWA_COLOR_DEFAULT = 0xFFFFFFFF

# Accent State Constants
ACCENT_DISABLED = 0
ACCENT_ENABLE_GRADIENT = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# Window Corner Preference Constants
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


def HEXtoRGBAint(HEX: str) -> int:
    """Convert HEX color to RGBA integer."""
    alpha = HEX[7:]
    blue = HEX[5:7]
    green = HEX[3:5]
    red = HEX[1:3]
    gradientColor = alpha + blue + green + red
    return int(gradientColor, base=16)


def set_accent_policy(hwnd, accent_state, gradient_color=0, accent_flags=0):
    """Set the accent policy for a window."""
    accent = ACCENTPOLICY()
    accent.AccentState = accent_state
    accent.AccentFlags = accent_flags
    accent.GradientColor = gradient_color

    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = 19  # WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))

    result = _SCA(hwnd, ctypes.byref(data))
    if result == 0:
        raise ctypes.WinError()


def set_dark_mode(hwnd):
    """Enable dark mode for a window."""
    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = 26  # WCA_USEDARKMODECOLORS
    data.SizeOfData = ctypes.sizeof(ctypes.c_int)
    data.Data = ctypes.cast(ctypes.pointer(ctypes.c_int(1)), ctypes.POINTER(ctypes.c_int))

    result = _SCA(hwnd, ctypes.byref(data))
    if result == 0:
        raise ctypes.WinError()


def set_window_corner_preference(hwnd, preference, border_color):
    """Set the window corner preference and border color."""
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


def Blur(hwnd, Acrylic=False, DarkMode=False, RoundCorners=False, RoundCornersType="normal", BorderColor="System"):
    """Apply blur, dark mode, and corner preferences to a window."""
    hwnd = int(hwnd)
    try:
        if Acrylic:
            set_accent_policy(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, HEXtoRGBAint("#ff000000"), 2)
        else:
            set_accent_policy(hwnd, ACCENT_ENABLE_BLURBEHIND)

        if DarkMode:
            set_dark_mode(hwnd)

        if RoundCorners:
            set_window_corner_preference(
                hwnd, DWMWCP_ROUND if RoundCornersType == "normal" else DWMWCP_ROUNDSMALL, BorderColor
            )
    except Exception as e:
        logging.debug(f"Failed to apply settings: {e}")

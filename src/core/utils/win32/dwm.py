import ctypes
import logging
import sys

from core.utils.win32.bindings.dwmapi import DwmExtendFrameIntoClientArea, DwmSetWindowAttribute
from core.utils.win32.constants import DWMSBT_MAINWINDOW, DWMWA_SYSTEMBACKDROP_TYPE
from core.utils.win32.structs import MARGINS

# DWMWA_SYSTEMBACKDROP_TYPE, which draws Mica, is there from Windows 11 22H2 on
MICA_BUILD = 22621


def enable_mica(hwnd: int) -> bool:
    """Draws Mica behind the whole window, and tells whether it could; where not, the window needs a background."""
    if sys.getwindowsversion().build < MICA_BUILD:
        return False
    # Mica shows only where the frame reaches
    DwmExtendFrameIntoClientArea(hwnd, MARGINS(-1, -1, -1, -1))
    backdrop = ctypes.c_int(DWMSBT_MAINWINDOW)
    result = DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    if result:
        logging.warning("Could not enable Mica: %#010x", result & 0xFFFFFFFF)
        return False
    return True

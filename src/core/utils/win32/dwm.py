import ctypes
import logging

from core.utils.win32.bindings.dwmapi import DwmExtendFrameIntoClientArea, DwmSetWindowAttribute
from core.utils.win32.constants import DWMSBT_MAINWINDOW, DWMWA_SYSTEMBACKDROP_TYPE
from core.utils.win32.structs import MARGINS


def enable_mica(hwnd: int) -> None:
    # Mica shows only where the frame reaches, and the attribute needs Windows 11 22H2
    DwmExtendFrameIntoClientArea(hwnd, MARGINS(-1, -1, -1, -1))
    backdrop = ctypes.c_int(DWMSBT_MAINWINDOW)
    result = DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    if result:
        logging.warning("Could not enable Mica: %#010x", result & 0xFFFFFFFF)

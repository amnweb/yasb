"""Utils for systray widget"""

from __future__ import annotations

import ctypes as ct
import logging
import struct
from ctypes import byref, create_string_buffer, sizeof, windll
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HBITMAP,
    HDC,
    HICON,
    LPVOID,
    POINT,
)
from enum import Enum

from PIL import Image
from win32con import DIB_RGB_COLORS

from core.utils.systray.win_types import BITMAP, BITMAPINFO, BITMAPINFOHEADER, ICONINFO
from core.utils.systray.win_wrappers import (
    CloseHandle,
    GetWindowThreadProcessId,
    OpenProcess,
    QueryFullProcessImageNameW,
)

user32 = windll.user32
gdi32 = windll.gdi32


class MESSAGE_TYPE(Enum):
    NIM_ADD = 0x0
    NIM_MODIFY = 0x1
    NIM_DELETE = 0x2
    NIM_SETFOCUS = 0x3
    NIM_SETVERSION = 0x4


def cursor_position():
    point = POINT()
    user32.GetCursorPos(byref(point))
    return point.x, point.y


def pack_i32(low: int, high: int) -> int:
    """Pack two 16-bit signed integers into a 32-bit integer."""
    high = ct.c_short(high).value  # Ensure sign extension
    return ct.c_long((low & 0xFFFF) | (high << 16)).value


def get_exe_path_from_hwnd(hwnd: int) -> str | None:
    # Get process ID from window handle
    process_id = ct.c_ulong(0)
    GetWindowThreadProcessId(hwnd, ct.byref(process_id))

    # Open process to get module handle
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not h_process:
        logging.debug("Could not open process with PID %d", process_id.value)
        return None

    try:
        # Get process image file name
        buffer_size = ct.c_ulong(1024)
        buffer = ct.create_unicode_buffer(buffer_size.value)
        if QueryFullProcessImageNameW(h_process, 0, buffer, ct.byref(buffer_size)):
            return buffer.value
    finally:
        CloseHandle(h_process)

    return None


def array_to_str(array: bytes) -> str:
    null_pos = next((i for i, c in enumerate(array) if c == 0), len(array))
    return "".join(chr(c) for c in array[:null_pos]).replace("\r", "")


def hicon_to_image(hicon: int) -> Image.Image | None:
    user32.GetIconInfo.argtypes = [HICON, ct.POINTER(ICONINFO)]
    user32.GetIconInfo.restype = BOOL

    gdi32.GetObjectW.argtypes = [HANDLE, ct.c_int, LPVOID]
    gdi32.GetObjectW.restype = ct.c_int

    user32.GetDC.argtypes = [HANDLE]
    user32.GetDC.restype = HDC

    gdi32.GetDIBits.argtypes = [HDC, HBITMAP, DWORD, DWORD, LPVOID, ct.POINTER(BITMAPINFO), DWORD]
    gdi32.GetDIBits.restype = ct.c_int

    user32.ReleaseDC.argtypes = [HANDLE, HDC]
    user32.ReleaseDC.restype = ct.c_int

    gdi32.DeleteObject.argtypes = [HANDLE]
    gdi32.DeleteObject.restype = BOOL

    # Get icon info
    icon_info = ICONINFO()
    if not user32.GetIconInfo(hicon, byref(icon_info)):
        logging.error("GetIconInfo failed: %s", hicon)
        return None

    # Get bitmap info
    bitmap = BITMAP()
    result = gdi32.GetObjectW(icon_info.hbmColor, sizeof(BITMAP), byref(bitmap))

    if result == 0:
        gdi32.DeleteObject(icon_info.hbmMask)
        gdi32.DeleteObject(icon_info.hbmColor)
        logging.error("GetObjectW failed")
        return None

    width, height = bitmap.bmWidth, bitmap.bmHeight
    buffer_size = width * height * 4

    # Create buffers for the bitmap data
    color_buffer = create_string_buffer(buffer_size)
    mask_buffer = create_string_buffer(buffer_size)

    # Get DC
    hdc = user32.GetDC(None)
    if hdc == 0:
        gdi32.DeleteObject(icon_info.hbmMask)
        gdi32.DeleteObject(icon_info.hbmColor)
        logging.error("GetDC failed")
        return None

    # Create bitmap info
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -abs(height)
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32

    # Get color bitmap data
    color_result = gdi32.GetDIBits(
        hdc,
        icon_info.hbmColor,
        0,
        height,
        byref(color_buffer),
        byref(bi),
        DIB_RGB_COLORS,
    )

    # Get mask bitmap data
    mask_result = gdi32.GetDIBits(
        hdc,
        icon_info.hbmMask,
        0,
        height,
        byref(mask_buffer),
        byref(bi),
        DIB_RGB_COLORS,
    )

    # Release DC and delete objects
    user32.ReleaseDC(None, hdc)
    gdi32.DeleteObject(icon_info.hbmColor)
    gdi32.DeleteObject(icon_info.hbmMask)

    if color_result == 0 or mask_result == 0:
        logging.error("GetDIBits failed")
        return None

    # Convert buffer to bytes
    color_bytes = color_buffer.raw
    mask_bytes = mask_buffer.raw

    # Check if icon is mask-based
    is_mask_based = all(b == 0 for _, _, _, b in struct.iter_unpack("BBBB", color_bytes))

    # Process pixel data
    img_data = bytearray(buffer_size)
    color_view = memoryview(color_bytes)
    mask_view = memoryview(mask_bytes)

    for i in range(0, buffer_size, 4):
        # Get mask alpha
        mask_alpha = mask_view[i]

        # Unpack pixel (BGR + A)
        b, g, r, a = color_view[i : i + 4]

        # Adjust alpha if mask-based
        if is_mask_based:
            a = 0 if mask_alpha == 255 else 255

        # Store as RGBA (BGR to RGB)
        img_data[i : i + 4] = bytes((r, g, b, a))

    # Create PIL Image
    return Image.frombuffer("RGBA", (width, height), bytes(img_data), "raw", "RGBA", 0, 1)

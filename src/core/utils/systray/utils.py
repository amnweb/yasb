"""Utils for systray widget"""

import ctypes as ct
import logging
from ctypes import byref, windll
from ctypes.wintypes import (
    POINT,
)

from core.utils.win32.bindings import (
    CloseHandle,
    GetWindowThreadProcessId,
    OpenProcess,
    QueryFullProcessImageNameW,
)

user32 = windll.user32
gdi32 = windll.gdi32


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

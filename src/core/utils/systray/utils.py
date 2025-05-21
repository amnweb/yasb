"""Utils for systray widget"""

import ctypes as ct
import logging
from ctypes import GetLastError, byref, windll
from ctypes.wintypes import (
    MSG,
    POINT,
)
from typing import Callable

from win32con import (
    WM_CLOSE,
    WS_CLIPCHILDREN,
    WS_CLIPSIBLINGS,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_POPUP,
)

from core.utils.win32.bindings import (
    CloseHandle,
    CreateWindowEx,
    GetWindowThreadProcessId,
    OpenProcess,
    PostMessage,
    QueryFullProcessImageNameW,
)
from core.utils.win32.structs import WNDCLASS, WNDPROC

logger = logging.getLogger("systray_widget")

user32 = windll.user32
gdi32 = windll.gdi32
kernel32 = windll.kernel32


class NativeWindowEx:
    """
    Native window utility class
    Creates a native window with the specified parameters
    A window procedure is required to handle messages
    """

    def __init__(
        self,
        window_proc: Callable[[int, int, int, int], int],
        class_name: str,
        title: str | None = None,
        width: int = 0,
        height: int = 0,
    ):
        if not title:
            title = class_name

        self.wc = WNDCLASS()
        self.wc.lpfnWndProc = WNDPROC(window_proc)
        self.wc.hInstance = kernel32.GetModuleHandleW(None)
        self.wc.lpszClassName = class_name

        if not user32.RegisterClassW(byref(self.wc)):
            logger.debug("Window registration failed")
            return

        self.hwnd: int = CreateWindowEx(
            WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
            class_name,
            title,
            WS_POPUP | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
            0,
            0,
            width,
            height,
            None,
            None,
            self.wc.hInstance,
            None,
        )

        if not self.hwnd:
            logger.critical("Window creation failed")
            return

    def start_message_loop(self):
        """
        Start the message loop
        Call this last after everything is set set up
        """
        msg = MSG()
        while user32.GetMessageW(byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))

    def destroy(self):
        if self.hwnd != 0:
            logger.debug(f"Destroying window {self.hwnd}")
            PostMessage(self.hwnd, WM_CLOSE, 0, 0)


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

    if process_id.value == 0:
        return None

    # Open process to get module handle
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not h_process:
        logger.debug(f"Could not open process ID {process_id.value}. Err: {GetLastError()}")
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

"""Utils for systray widget"""

import ctypes
import ctypes as ct
import logging
import os
import sys
import time
from collections.abc import Callable
from ctypes import byref, windll
from ctypes.wintypes import (
    DWORD,
    HMODULE,
    MSG,
    POINT,
)
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from PIL import Image
from PIL.ImageFilter import SHARPEN
from PIL.ImageQt import ImageQt
from PyQt6.QtGui import QImage
from win32con import (
    PROCESS_QUERY_INFORMATION,
    PROCESS_VM_READ,
    WM_CLOSE,
    WS_CLIPCHILDREN,
    WS_CLIPSIBLINGS,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_POPUP,
)

from core.utils.win32.app_icons import hicon_to_image
from core.utils.win32.bindings import (
    CloseHandle,
    CreateWindowEx,
    GetWindowThreadProcessId,
    OpenProcess,
    PostMessage,
    QueryFullProcessImageNameW,
)
from core.utils.win32.bindings.kernel32 import GetLastError, GetSystemWindowsDirectoryW
from core.utils.win32.bindings.psapi import EnumProcessModulesEx, GetModuleBaseNameW
from core.utils.win32.bindings.user32 import FindWindowEx, GetShellWindow
from core.utils.win32.constants import (
    LIST_MODULES_ALL,
    NIF_GUID,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_STATE,
    NIF_TIP,
    PROCESS_QUERY_LIMITED_INFORMATION,
)
from core.utils.win32.structs import NOTIFYICONDATA, WNDCLASS, WNDPROC
from core.utils.win32.utils import get_windows_host_arch
from settings import IS_FROZEN

logger = logging.getLogger("systray_widget")

user32 = windll.user32
gdi32 = windll.gdi32
kernel32 = windll.kernel32


@dataclass
class IconData:
    """Data class for validated systray icon data"""

    message_type: int = 0
    hWnd: int = 0
    uID: int = 0
    guid: UUID | None = None
    uFlags: int = 0
    dwState: int = 0
    dwStateMask: int = 0
    hIcon: int = 0
    szTip: str = ""
    szInfo: str = ""
    szInfoTitle: str = ""
    dwInfoFlags: int = 0
    uTimeout: int = 0
    uCallbackMessage: int = 0
    uVersion: int = 0
    icon_image: QImage | None = None
    exe: str = ""
    exe_path: str = ""


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
            logger.debug("Destroying window %s", self.hwnd)
            PostMessage(self.hwnd, WM_CLOSE, 0, 0)
            self.hwnd = 0


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
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not h_process:
        logger.debug("Could not open process ID %s. Err: %s", process_id.value, GetLastError())
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


def validate_icon_data(data: NOTIFYICONDATA, icon: Image.Image | None = None) -> IconData:
    """
    Validates and processes raw icon data
    Pre-processed icon can be also passed
    """
    icon_data = IconData()
    icon_data.hWnd = data.hWnd
    icon_data.uID = data.uID
    icon_data.uFlags = data.uFlags

    exe_path = get_exe_path_from_hwnd(icon_data.hWnd)
    if exe_path is not None:
        icon_data.exe_path = exe_path
        icon_data.exe = Path(exe_path).name.split(".")[0] if exe_path else ""

    if 0 < data.anonymous.uVersion <= 4:
        icon_data.uVersion = data.anonymous.uVersion

    if data.uFlags & NIF_MESSAGE:
        icon_data.uCallbackMessage = data.uCallbackMessage

    if data.uFlags & NIF_ICON:
        icon_data.hIcon = data.hIcon
        if not icon:
            icon_image = hicon_to_image(icon_data.hIcon)
        else:
            icon_image = icon
        if icon_image is not None:
            if icon_image.size != (32, 32):  # Ensure we have consistent icon sizes
                icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS).filter(SHARPEN)  # pyright: ignore [reportUnknownMemberType]
            icon_image = QImage(ImageQt(icon_image)).copy()
        icon_data.icon_image = icon_image

    if data.uFlags & NIF_TIP:
        icon_data.szTip = array_to_str(data.szTip)

    if data.uFlags & NIF_STATE:
        icon_data.dwState = data.dwState
        icon_data.dwStateMask = data.dwStateMask

    if data.uFlags & NIF_GUID:
        icon_data.guid = data.guidItem.to_uuid()

    if data.uFlags & NIF_INFO:
        icon_data.dwInfoFlags = data.dwInfoFlags
        icon_data.szInfoTitle = array_to_str(data.szInfoTitle)
        icon_data.szInfo = array_to_str(data.szInfo)

    return icon_data


def find_real_tray_hwnd(hwnd_ignore: int | None = None):
    hwnd = 0
    while True:
        hwnd = FindWindowEx(0, hwnd, "Shell_TrayWnd", None)
        if hwnd == 0:
            break
        if hwnd == hwnd_ignore:
            continue
        exe = get_exe_path_from_hwnd(hwnd)
        if exe and os.path.basename(exe) == "explorer.exe":
            return hwnd
    return 0


def get_explorer_pid() -> int | None:
    """Finds the PID of the running explorer.exe"""
    retry_count = 10
    last_error = None
    while retry_count > 0:
        retry_count -= 1
        h_process = None
        try:
            hwnd_shell = GetShellWindow()
            if hwnd_shell == 0:
                raise Exception("Failed to get shell window")
            explorer_pid = ct.c_ulong(0)
            thread_id = GetWindowThreadProcessId(hwnd_shell, byref(explorer_pid))
            if not thread_id:
                raise Exception(f"Wrong thread process ID. Err: {GetLastError()}")
            h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, explorer_pid.value)
            if not h_process:
                raise Exception(f"Failed to open process. Err: {GetLastError()}")
            exe_path_buf = ctypes.create_unicode_buffer(1024)
            size = DWORD(1024)
            if not QueryFullProcessImageNameW(h_process, 0, exe_path_buf, byref(size)):
                raise Exception(f"Failed to get process image name. Err: {GetLastError()}")
            expected_path_buf = ctypes.create_unicode_buffer(1024)
            if not GetSystemWindowsDirectoryW(expected_path_buf, 1024):
                raise Exception(f"Failed to get system windows directory. Err: {GetLastError()}")
            exe_path = exe_path_buf.value.lower()
            expected_path = os.path.join(expected_path_buf.value, "explorer.exe").lower()
            if exe_path != expected_path:
                raise Exception(f"Unexpected process image name {exe_path}. Expected {expected_path}")
            return explorer_pid.value
        except Exception as e:
            last_error = e
            time.sleep(0.05)
            continue
        finally:
            if h_process:
                CloseHandle(h_process)
    logger.error("Get explorer PID failed after 10 retries. Err: %s", last_error)
    return None


def get_dll_path() -> str:
    """
    Check the architecture and frozen state and return the appropriate DLL path
    Will raise an exception if the architecture is unsupported
    """
    if get_windows_host_arch() == "AMD64":
        dll_name = "YASBTrayHook.dll"
    elif get_windows_host_arch() == "ARM64":
        dll_name = "YASBTrayHook_arm64.dll"
    else:
        logger.critical("Unsupported architecture")
        raise Exception("Unsupported architecture")

    # Check if we're running in a frozen environment
    if IS_FROZEN:
        dll_path = os.path.join(os.path.dirname(sys.executable), "lib", dll_name)
    else:
        dll_path = os.path.join(os.path.dirname(__file__), "hook", dll_name)
    return dll_path


def hook_dll_exists() -> bool:
    return os.path.exists(get_dll_path())


def is_dll_loaded(pid: int, dll_name: str) -> bool:
    """Checks if a DLL is already loaded in the target process."""
    h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h_process:
        return False

    try:
        # Allocate array for module handles
        hMods = (HMODULE * 1024)()
        cbNeeded = DWORD()

        if EnumProcessModulesEx(h_process, hMods, ctypes.sizeof(hMods), ctypes.byref(cbNeeded), LIST_MODULES_ALL):
            nMods = cbNeeded.value // ctypes.sizeof(HMODULE)
            target_dll = dll_name.lower()
            modName = ctypes.create_unicode_buffer(512)

            for i in range(nMods):
                if GetModuleBaseNameW(h_process, hMods[i], modName, ctypes.sizeof(modName)):
                    if modName.value.lower() == target_dll:
                        return True
    finally:
        CloseHandle(h_process)

    return False

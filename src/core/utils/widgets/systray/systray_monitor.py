"""Systray tray monitor client that intercepts systray messages"""

import atexit
import logging
import os
from ctypes import (
    POINTER,
    cast,
    windll,
)
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from PIL import Image
from PIL.ImageFilter import SHARPEN
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from win32con import (
    HWND_BROADCAST,
    HWND_TOPMOST,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    WM_ACTIVATEAPP,
    WM_CLOSE,
    WM_COMMAND,
    WM_COPYDATA,
    WM_DESTROY,
    WM_TIMER,
    WM_USER,
)

import core.utils.widgets.systray.utils as utils
from core.utils.widgets.systray.utils import (
    NativeWindowEx,
    array_to_str,
    get_exe_path_from_hwnd,
    pack_i32,
)
from core.utils.win32.app_icons import hicon_to_image
from core.utils.win32.bindings import (
    DefWindowProc,
    DestroyWindow,
    FindWindowEx,
    IsWindow,
    PostMessage,
    RegisterWindowMessage,
    SendMessage,
    SendNotifyMessage,
    SetTimer,
    SetWindowPos,
)
from core.utils.win32.bindings.user32 import SetProp
from core.utils.win32.constants import (
    NIF_GUID,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_STATE,
    NIF_TIP,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    NIM_SETVERSION,
)
from core.utils.win32.structs import (
    COPYDATASTRUCT,
    NOTIFYICONDATA,
    SHELLTRAYDATA,
    WINNOTIFYICONIDENTIFIER,
)

logger = logging.getLogger("systray_widget")

# Load necessary Windows functions
user32 = windll.user32
kernel32 = windll.kernel32

WM_TASKBARCREATED = RegisterWindowMessage("TaskbarCreated")


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
    icon_image: QPixmap | None = None
    exe: str = ""
    exe_path: str = ""


class SystrayMonitor(QObject):
    """Main class to handle systray message interception and forwarding"""

    icon_modified = pyqtSignal(IconData)
    icon_deleted = pyqtSignal(IconData)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.hwnd: int = 0
        self.real_tray_hwnd: int = 0
        self._is_destroyed: bool = False

        try:
            self.destroyed.connect(lambda: setattr(self, "_is_destroyed", True))
        except Exception:
            pass
        atexit.register(self.destroy)

    def run(self):
        # Create native win32 window
        self.tray_monitor_window = NativeWindowEx(self._window_proc, "Shell_TrayWnd")
        self.hwnd = self.tray_monitor_window.hwnd

        # Set the window as the foreground window
        SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

        # Set a timer to keep the window as a foreground window to keep receiving messages
        SetTimer(self.hwnd, 1, 100, None)

        self.tray_monitor_window.start_message_loop()

    def __del__(self):
        """Ensure proper cleanup"""
        self.destroy()

    def destroy(self):
        """Clean up window and unregister class"""
        self._is_destroyed = True
        if getattr(self, "tray_monitor_window", None):
            try:
                self.tray_monitor_window.destroy()
            except Exception:
                pass

    @staticmethod
    def send_taskbar_created():
        """Send the taskbar created message to Windows"""
        taskbar_created_msg = RegisterWindowMessage("TaskbarCreated")
        SendNotifyMessage(HWND_BROADCAST, taskbar_created_msg, 0, 0)
        logger.debug(f"Sending TaskbarCreated message: {taskbar_created_msg}")

    def set_taskbar_list_hwnd(self):
        """Set the TaskbandHWND prop to the Yasb systray window on TaskbarCreated message"""
        if self.hwnd == 0:
            logger.error("YASB systray hwnd is invalid")
            return
        logger.debug(f"Adding TaskbandHWND prop to hwnd {self.hwnd}")
        SetProp(self.hwnd, "TaskbandHWND", self.hwnd)

    def _window_proc(self, hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
        """Main window procedure for handling window messages"""
        if self._is_destroyed:
            return DefWindowProc(hwnd, uMsg, wParam, lParam)
        if uMsg == WM_CLOSE:
            logger.debug(f"WM_CLOSE received, destroying window {hwnd}")
            DestroyWindow(hwnd)
            return 0
        elif uMsg == WM_TASKBARCREATED:
            self.set_taskbar_list_hwnd()
            return 0
        elif uMsg == WM_DESTROY:
            logger.debug(f"WM_DESTROY received for window {hwnd}")
            user32.PostQuitMessage(0)
            return 0
        elif uMsg == WM_TIMER:
            # We need to set our window topmost to have the priority over the native system tray
            SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            return 0
        elif uMsg == WM_COPYDATA:
            return self.handle_copy_data(hwnd, uMsg, wParam, lParam)
        else:
            if uMsg in {WM_COPYDATA, WM_ACTIVATEAPP, WM_COMMAND} or uMsg >= WM_USER:
                return self.forward_message(hwnd, uMsg, wParam, lParam)
            else:
                return DefWindowProc(hwnd, uMsg, wParam, lParam)

    def handle_copy_data(self, hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
        """Handles the WM_COPYDATA message"""
        copy_data = cast(lParam, POINTER(COPYDATASTRUCT)).contents
        if copy_data.cbData == 0:
            return 0
        if copy_data.dwData == 1:
            tray_message = cast(copy_data.lpData, POINTER(SHELLTRAYDATA)).contents
            icon_data: NOTIFYICONDATA = tray_message.icon_data
            if tray_message.message_type in {NIM_ADD, NIM_MODIFY, NIM_SETVERSION}:
                validated_data = self.validate_icon_data(icon_data)
                validated_data.message_type = tray_message.message_type
                if not self._is_destroyed:
                    try:
                        self.icon_modified.emit(validated_data)
                    except RuntimeError:
                        return 0
            elif tray_message.message_type == NIM_DELETE:
                if not self._is_destroyed:
                    try:
                        self.icon_deleted.emit(
                            IconData(
                                hWnd=icon_data.hWnd,
                                uID=icon_data.uID,
                                guid=icon_data.guidItem.to_uuid() if icon_data.uFlags & NIF_GUID else None,
                            )
                        )
                    except RuntimeError:
                        return 0
            return self.forward_message(hwnd, uMsg, wParam, lParam)
        elif copy_data.dwData == 3 and copy_data.lpData:
            icon_identifier = cast(copy_data.lpData, POINTER(WINNOTIFYICONIDENTIFIER)).contents
            cursor_pos = utils.cursor_position()
            left = cursor_pos[0]
            top = cursor_pos[1] + 1
            right = cursor_pos[0] + 1
            bottom = cursor_pos[1] - 1
            if icon_identifier.message == 1:
                return pack_i32(left, top)
            elif icon_identifier.message == 2:
                return pack_i32(right, bottom)
            else:
                return 0
        else:
            return self.forward_message(hwnd, uMsg, wParam, lParam)

    def forward_message(self, hwnd: int, msg: int, wParam: int, lParam: int):
        """Forward messages to the real tray window"""
        if not self.real_tray_hwnd or not IsWindow(self.real_tray_hwnd):
            logger.debug("Finding real tray hwnd")
            self.real_tray_hwnd = self.find_real_tray_hwnd(hwnd)
        if self.real_tray_hwnd:
            if msg in {WM_USER + 372}:  # Specific async tray messages
                PostMessage(self.real_tray_hwnd, msg, wParam, lParam)
                return DefWindowProc(hwnd, msg, wParam, lParam)
            return SendMessage(self.real_tray_hwnd, msg, wParam, lParam)
        return DefWindowProc(hwnd, msg, wParam, lParam)

    def find_real_tray_hwnd(self, hwnd_ignore: int | None = None):
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

    def validate_icon_data(self, data: NOTIFYICONDATA) -> IconData:
        """Validates and processes raw icon data"""
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
            icon_image = hicon_to_image(icon_data.hIcon)
            if icon_image is not None:
                if icon_image.size != (32, 32):  # Ensure we have consistent icon sizes
                    icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS).filter(SHARPEN)  # pyright: ignore [reportUnknownMemberType]
                icon_image = QPixmap.fromImage(ImageQt(icon_image))
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

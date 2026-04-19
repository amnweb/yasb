"""Systray tray monitor client that intercepts systray messages"""

import atexit
import logging
from ctypes import (
    POINTER,
    cast,
    windll,
)

from PyQt6.QtCore import QObject, pyqtSignal
from win32con import (
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

import core.widgets.services.systray.utils as utils
from core.widgets.services.systray.utils import (
    IconData,
    NativeWindowEx,
    find_real_tray_hwnd,
    pack_i32,
    validate_icon_data,
)
from core.utils.win32.bindings import (
    DefWindowProc,
    DestroyWindow,
    IsWindow,
    PostMessage,
    RegisterWindowMessage,
    SendMessage,
    SetTimer,
    SetWindowPos,
)
from core.utils.win32.bindings.user32 import SetProp
from core.utils.win32.constants import (
    NIF_GUID,
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


class SystrayMonitor(QObject):
    """Main class to handle systray message interception and forwarding"""

    update_icons = pyqtSignal()
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

        self.update_icons.emit()
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

    def set_taskbar_list_hwnd(self):
        """Set the TaskbandHWND prop to the Yasb systray window on TaskbarCreated message"""
        if self.hwnd == 0:
            logger.error("YASB systray hwnd is invalid")
            return
        logger.debug("Adding TaskbandHWND prop to hwnd %s", self.hwnd)
        SetProp(self.hwnd, "TaskbandHWND", self.hwnd)

    def _window_proc(self, hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
        """Main window procedure for handling window messages"""
        if uMsg == WM_CLOSE:
            logger.debug("WM_CLOSE received, destroying window %s", hwnd)
            DestroyWindow(hwnd)
            return 0
        elif uMsg == WM_DESTROY:
            logger.debug("WM_DESTROY received for window %s", hwnd)
            user32.PostQuitMessage(0)
            return 0
        if self._is_destroyed:
            return DefWindowProc(hwnd, uMsg, wParam, lParam)
        if uMsg == WM_TASKBARCREATED:
            self.set_taskbar_list_hwnd()
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
                validated_data = validate_icon_data(icon_data)
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
            self.real_tray_hwnd = find_real_tray_hwnd(hwnd)
        if self.real_tray_hwnd:
            if msg in {WM_USER + 372}:  # Specific async tray messages
                PostMessage(self.real_tray_hwnd, msg, wParam, lParam)
                return DefWindowProc(hwnd, msg, wParam, lParam)
            return SendMessage(self.real_tray_hwnd, msg, wParam, lParam)
        return DefWindowProc(hwnd, msg, wParam, lParam)

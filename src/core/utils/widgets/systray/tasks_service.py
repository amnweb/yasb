import atexit
import logging
import os

from PyQt6.QtCore import QObject
from win32con import WM_USER

from core.utils.widgets.systray.utils import NativeWindowEx, get_exe_path_from_hwnd
from core.utils.win32.bindings import (
    DefWindowProc,
    FindWindowEx,
    RegisterShellHookWindow,
    RegisterWindowMessage,
    SetProp,
    SetTaskmanWindow,
)

WM_SHELLHOOKMESSAGE = RegisterWindowMessage("SHELLHOOK")
WM_TASKBARCREATED = RegisterWindowMessage("TaskbarCreated")
TASKBARBUTTONCREATEDMESSAGE = RegisterWindowMessage("TaskbarButtonCreated")

logger = logging.getLogger("systray_widget")


class TasksService(QObject):
    """
    Barebones tasks service to handle taskbar related messages
    Some apps will crash if these messages are not handled
    This can also be handled right in the systray monitor client but it's better to have a separate thread
    """

    def __init__(self):
        self.yasb_systray_hwnd: int | None = None
        self.hwnd = None
        self.tasks_window = None
        atexit.register(self.destroy)

    def run(self):
        self.tasks_window = NativeWindowEx(self._window_proc, "YasbTasksHookWindow")
        self.hwnd = self.tasks_window.hwnd

        # This might be unnecessary for .NET app fix
        SetTaskmanWindow(self.hwnd)
        RegisterShellHookWindow(self.hwnd)
        # ---

        self.set_taskbar_list_hwnd()
        self.tasks_window.start_message_loop()

    def __del__(self):
        """Ensure proper cleanup"""
        self.destroy()

    def destroy(self):
        """Clean up window"""
        if self.tasks_window:
            self.tasks_window.destroy()

    def find_yasb_systray_hwnd(self):
        """Find Yasb systray monitor hwnd"""
        hwnd = 0
        while True:
            hwnd = FindWindowEx(0, hwnd, "Shell_TrayWnd", None)
            if hwnd == 0:
                break
            exe = get_exe_path_from_hwnd(hwnd)
            if exe and os.path.basename(exe) != "explorer.exe":
                return hwnd
        return 0

    def set_taskbar_list_hwnd(self):
        """Set the TaskbandHWND prop to the Yasb systray window"""
        if not self.yasb_systray_hwnd:
            self.yasb_systray_hwnd = self.find_yasb_systray_hwnd()
            logging.debug(f"Found yasb systray hwnd: {self.yasb_systray_hwnd}")
        if self.yasb_systray_hwnd == 0:
            logger.error("Failed to find yasb systray hwnd")
            return

        if self.hwnd and self.yasb_systray_hwnd:
            logger.debug(f"Adding TaskbandHWND prop to hwnd {self.yasb_systray_hwnd}")
            # This redirects relevant messages from TrayMonitor to the TasksService window
            SetProp(self.yasb_systray_hwnd, "TaskbandHWND", self.hwnd)

    def _window_proc(self, hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
        """
        Window procedure for handling shell hook messages
        For now it just returns DefWindowProc on for all relevant messages
        """
        if uMsg == WM_TASKBARCREATED:
            self.set_taskbar_list_hwnd()
            return 0
        elif uMsg == WM_SHELLHOOKMESSAGE:
            return DefWindowProc(hwnd, uMsg, wParam, lParam)
        elif uMsg >= WM_USER:
            return DefWindowProc(hwnd, uMsg, wParam, lParam)
        return DefWindowProc(hwnd, uMsg, wParam, lParam)

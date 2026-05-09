import ctypes
import logging
from ctypes import POINTER, Structure, c_ulong, sizeof, windll, wintypes

import win32con
from PyQt6.QtGui import QScreen

shell32 = windll.shell32
user32 = windll.user32

# Custom callback message for AppBar notifications (WM_USER + 100)
APPBAR_CALLBACK_MESSAGE = 0x0400 + 100  # WM_USER = 0x0400

"""
Application Desktop Toolbar (with added support for PyQt6)

https://docs.microsoft.com/en-us/windows/win32/shell/application-desktop-toolbars
"""


class AppBarEdge:
    """
    A value that specifies the edge of the screen.
    Documentation: https://docs.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-appbardata#members
    """

    Left = 0
    Top = 1
    Right = 2
    Bottom = 3


class AppBarMessage:
    """
    SHAppBarMessage App Bar Messages
    Documentation: https://docs.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shappbarmessage
    """

    New = 0
    Remove = 1
    QueryPos = 2
    SetPos = 3
    GetState = 4
    GetTaskbarPos = 5
    Activate = 6
    GetAutoHideBar = 7
    SetAutoHideBar = 8
    WindowPosChanged = 9
    SetState = 10
    GetAutoHideBarEx = 11
    SetAutoHideBarEx = 12


class AppBarNotify:
    """
    AppBar notification codes sent via callback message
    Documentation: https://docs.microsoft.com/en-us/windows/win32/shell/abn-fullscreenapp
    """

    StateChange = 0  # ABN_STATECHANGE
    PosChanged = 1  # ABN_POSCHANGED
    FullScreenApp = 2  # ABN_FULLSCREENAPP
    WindowArrange = 3  # ABN_WINDOWARRANGE


class AppBarData(Structure):
    """
    AppBarData struct
    Documentation: https://docs.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-appbardata#syntax
    """

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", ctypes.c_ulong),
        ("uEdge", c_ulong),
        ("rc", wintypes.RECT),
        ("lParam", wintypes.LPARAM),
    ]


P_APPBAR_DATA = POINTER(AppBarData)


class Win32AppBar:
    def __init__(
        self,
    ):
        self.app_bar_data = None
        self.callback_message = APPBAR_CALLBACK_MESSAGE

    def create_appbar(
        self,
        hwnd: int,
        edge: AppBarEdge,
        app_bar_size: int,
        screen: QScreen,
        scale_screen: bool = False,
        bar_name: str = None,
        reserve_space: bool = True,
        always_on_top: bool = False,
    ):
        self.app_bar_data = AppBarData()
        self.app_bar_data.cbSize = wintypes.DWORD(sizeof(self.app_bar_data))
        self.app_bar_data.uEdge = edge
        self.app_bar_data.hWnd = hwnd
        self.register_new()

        current_ex_style = windll.user32.GetWindowLongPtrW(hwnd, win32con.GWL_EXSTYLE)
        updated_ex_style = current_ex_style | win32con.WS_EX_NOACTIVATE
        if always_on_top:
            updated_ex_style |= win32con.WS_EX_TOPMOST
        windll.user32.SetWindowLongPtrW(hwnd, win32con.GWL_EXSTYLE, updated_ex_style)

        self.position_bar(app_bar_size, screen, scale_screen, bar_name)
        # Only reserve screen space if requested windows_app_bar: true
        if reserve_space:
            self.set_position()

    def position_bar(
        self, app_bar_size: int, screen: QScreen, scale_screen: bool = False, bar_name: str = None
    ) -> None:
        geometry = screen.geometry()
        # Keep AppBar reservation in the same logical coordinate space as the Qt bar geometry.
        # Multiplying the reserved size by devicePixelRatio again on high-DPI displays makes
        # the workspace gap larger than the visible bar.
        bar_size = int(app_bar_size)
        screen_width = geometry.width()
        screen_height = geometry.height()

        if self.app_bar_data.uEdge == AppBarEdge.Top:
            self.app_bar_data.rc.left = geometry.x()
            self.app_bar_data.rc.right = geometry.x() + geometry.width()
            self.app_bar_data.rc.top = geometry.y()
            self.app_bar_data.rc.bottom = geometry.y() + bar_size
        elif self.app_bar_data.uEdge == AppBarEdge.Bottom:
            self.app_bar_data.rc.left = geometry.x()
            self.app_bar_data.rc.right = geometry.x() + geometry.width()
            self.app_bar_data.rc.top = geometry.y() + screen_height - bar_size
            self.app_bar_data.rc.bottom = geometry.y() + screen_height
        elif self.app_bar_data.uEdge == AppBarEdge.Left:
            self.app_bar_data.rc.left = geometry.x()
            self.app_bar_data.rc.right = geometry.x() + bar_size
            self.app_bar_data.rc.top = geometry.y()
            self.app_bar_data.rc.bottom = geometry.y() + geometry.height()
        else:
            self.app_bar_data.rc.left = geometry.x() + screen_width - bar_size
            self.app_bar_data.rc.right = geometry.x() + screen_width
            self.app_bar_data.rc.top = geometry.y()
            self.app_bar_data.rc.bottom = geometry.y() + geometry.height()
        bar_info = f"Bar {bar_name}" if bar_name else "Bar"
        logging.debug(
            "%s Created on Screen: %s [Bar Size: %spx, DPI Scale: %s]",
            bar_info,
            screen.name(),
            app_bar_size,
            screen.devicePixelRatio(),
        )

    def register_new(self):
        self.app_bar_data.uCallbackMessage = self.callback_message
        shell32.SHAppBarMessage(AppBarMessage.New, P_APPBAR_DATA(self.app_bar_data))

    def window_pos_changed(self):
        shell32.SHAppBarMessage(AppBarMessage.WindowPosChanged, P_APPBAR_DATA(self.app_bar_data))

    def query_appbar_position(self):
        shell32.SHAppBarMessage(AppBarMessage.QueryPos, P_APPBAR_DATA(self.app_bar_data))

    def set_position(self):
        shell32.SHAppBarMessage(AppBarMessage.SetPos, P_APPBAR_DATA(self.app_bar_data))

    def remove_appbar(self):
        shell32.SHAppBarMessage(AppBarMessage.Remove, P_APPBAR_DATA(self.app_bar_data))

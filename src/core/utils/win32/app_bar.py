import ctypes
import logging
from ctypes import POINTER, Structure, c_ulong, sizeof, windll, wintypes

import win32con
from PyQt6.QtGui import QScreen

from core.utils.win32.bindings.user32 import GetWindowLongPtr, SetWindowLongPtr

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
        self.app_bar_data: AppBarData | None = None
        self.callback_message = APPBAR_CALLBACK_MESSAGE

    def create_appbar(
        self,
        hwnd: int,
        edge: int,
        app_bar_height: int,
        screen: QScreen,
        scale_screen: bool = False,
        bar_name: str | None = None,
        reserve_space: bool = True,
        always_on_top: bool = False,
    ):
        self.app_bar_data = AppBarData()
        self.app_bar_data.cbSize = wintypes.DWORD(sizeof(self.app_bar_data))
        self.app_bar_data.uEdge = edge
        self.app_bar_data.hWnd = hwnd
        self.register_new()

        current_ex_style = GetWindowLongPtr(hwnd, win32con.GWL_EXSTYLE)
        updated_ex_style = current_ex_style | win32con.WS_EX_NOACTIVATE
        if always_on_top:
            updated_ex_style |= win32con.WS_EX_TOPMOST
        SetWindowLongPtr(hwnd, win32con.GWL_EXSTYLE, updated_ex_style)

        self.position_bar(app_bar_height, screen, scale_screen, bar_name)
        # Only reserve screen space if requested windows_app_bar: true
        if reserve_space:
            self.set_position()

    def position_bar(
        self, app_bar_height: int, screen: QScreen, scale_screen: bool = False, bar_name: str | None = None
    ) -> None:
        data = self.app_bar_data
        if data is None:
            return
        geometry = screen.geometry()
        bar_height = int(app_bar_height * screen.devicePixelRatio())
        screen_height = int(geometry.height() * screen.devicePixelRatio() if scale_screen else geometry.height())

        data.rc.left = geometry.x()
        data.rc.right = geometry.x() + geometry.width()

        if data.uEdge == AppBarEdge.Top:
            data.rc.top = screen.geometry().y()
            data.rc.bottom = screen.geometry().y() + bar_height
        else:
            data.rc.top = screen.geometry().y() + screen_height - bar_height
            data.rc.bottom = screen.geometry().y() + screen_height
        bar_info = f"Bar {bar_name}" if bar_name else "Bar"
        logging.debug(
            "%s Created on Screen: %s [Bar Height: %spx, DPI Scale: %s]",
            bar_info,
            screen.name(),
            app_bar_height,
            screen.devicePixelRatio(),
        )

    def _send(self, message: int) -> None:
        if self.app_bar_data is None:
            return
        shell32.SHAppBarMessage(message, P_APPBAR_DATA(self.app_bar_data))

    def register_new(self):
        if self.app_bar_data is not None:
            self.app_bar_data.uCallbackMessage = self.callback_message
        self._send(AppBarMessage.New)

    def window_pos_changed(self):
        self._send(AppBarMessage.WindowPosChanged)

    def query_appbar_position(self):
        self._send(AppBarMessage.QueryPos)

    def set_position(self):
        self._send(AppBarMessage.SetPos)

    def remove_appbar(self):
        self._send(AppBarMessage.Remove)

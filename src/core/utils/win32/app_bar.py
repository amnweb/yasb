import logging
from ctypes import sizeof

from PyQt6.QtGui import QScreen

from core.utils.win32.bindings.shell32 import SHAppBarMessage
from core.utils.win32.bindings.user32 import GetWindowLongPtr, SetWindowLongPtr
from core.utils.win32.constants import GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOPMOST
from core.utils.win32.structs import APPBARDATA

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


class Win32AppBar:
    def __init__(
        self,
    ):
        self.app_bar_data: APPBARDATA | None = None
        self.callback_message = APPBAR_CALLBACK_MESSAGE

    def create_appbar(
        self,
        hwnd: int,
        edge: int,
        thickness: int,
        screen: QScreen,
        scale_screen: bool = False,
        bar_name: str | None = None,
        reserve_space: bool = True,
        always_on_top: bool = False,
    ):
        self.app_bar_data = APPBARDATA()
        self.app_bar_data.cbSize = sizeof(self.app_bar_data)
        self.app_bar_data.uEdge = edge
        self.app_bar_data.hWnd = hwnd
        self.register_new()

        current_ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
        updated_ex_style = current_ex_style | WS_EX_NOACTIVATE
        if always_on_top:
            updated_ex_style |= WS_EX_TOPMOST
        SetWindowLongPtr(hwnd, GWL_EXSTYLE, updated_ex_style)

        self.position_bar(thickness, screen, scale_screen, bar_name)
        # Only reserve screen space if requested windows_app_bar: true
        if reserve_space:
            self.set_position()

    def position_bar(
        self, thickness: int, screen: QScreen, scale_screen: bool = False, bar_name: str | None = None
    ) -> None:
        data = self.app_bar_data
        if data is None:
            return
        geometry = screen.geometry()
        ratio = screen.devicePixelRatio()
        size = int(thickness * ratio)
        screen_width = int(geometry.width() * ratio if scale_screen else geometry.width())
        screen_height = int(geometry.height() * ratio if scale_screen else geometry.height())

        data.rc.left = geometry.x()
        data.rc.top = geometry.y()
        data.rc.right = geometry.x() + screen_width
        data.rc.bottom = geometry.y() + screen_height
        if data.uEdge == AppBarEdge.Top:
            data.rc.bottom = geometry.y() + size
        elif data.uEdge == AppBarEdge.Bottom:
            data.rc.top = geometry.y() + screen_height - size
        elif data.uEdge == AppBarEdge.Left:
            data.rc.right = geometry.x() + size
        else:
            data.rc.left = geometry.x() + screen_width - size
        bar_info = f"Bar {bar_name}" if bar_name else "Bar"
        logging.debug(
            "%s Created on Screen: %s [Bar Thickness: %spx, DPI Scale: %s]",
            bar_info,
            screen.name(),
            thickness,
            ratio,
        )

    def _send(self, message: int) -> None:
        if self.app_bar_data is None:
            return
        SHAppBarMessage(message, self.app_bar_data)

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

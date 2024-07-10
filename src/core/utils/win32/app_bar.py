import ctypes
from ctypes import wintypes, Structure, POINTER, sizeof, windll, c_ulong
from PyQt6.QtGui import QScreen

shell32 = windll.shell32
user32 = windll.user32

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
    def __init__(self, ):
        self.app_bar_data = None

    def create_appbar(
            self,
            hwnd: int,
            edge: AppBarEdge,
            app_bar_height: int,
            screen: QScreen,
            scale_screen: bool = False
    ):
        self.app_bar_data = AppBarData()
        self.app_bar_data.cbSize = wintypes.DWORD(sizeof(self.app_bar_data))
        self.app_bar_data.uEdge = edge
        self.app_bar_data.hWnd = hwnd
        self.register_new()
        self.position_bar(app_bar_height, screen, scale_screen)
        self.set_position()

    def position_bar(self, app_bar_height: int, screen: QScreen, scale_screen: bool = False) -> None:
        geometry = screen.geometry()
        bar_height = int(app_bar_height * screen.devicePixelRatio())
        screen_height = int(geometry.height() * screen.devicePixelRatio() if scale_screen else geometry.y())

        self.app_bar_data.rc.left = geometry.x()
        self.app_bar_data.rc.right = geometry.x() + bar_height

        if self.app_bar_data.uEdge == AppBarEdge.Top:
            self.app_bar_data.rc.top = screen.geometry().y()
            self.app_bar_data.rc.bottom = screen.geometry().y() + bar_height
        else:
            self.app_bar_data.rc.top = screen.geometry().y() + screen_height - bar_height
            self.app_bar_data.rc.bottom = screen.geometry().y() + screen_height

    def register_new(self):
        shell32.SHAppBarMessage(AppBarMessage.New, P_APPBAR_DATA(self.app_bar_data))

    def window_pos_changed(self):
        shell32.SHAppBarMessage(AppBarMessage.WindowPosChanged, P_APPBAR_DATA(self.app_bar_data))

    def query_appbar_position(self):
        shell32.SHAppBarMessage(AppBarMessage.QueryPos, P_APPBAR_DATA(self.app_bar_data))

    def set_position(self):
        shell32.SHAppBarMessage(AppBarMessage.SetPos, P_APPBAR_DATA(self.app_bar_data))

    def remove_appbar(self):
        shell32.SHAppBarMessage(AppBarMessage.Remove, P_APPBAR_DATA(self.app_bar_data))

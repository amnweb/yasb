"""Wrappers for user32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    c_int,
    c_long,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HDC,
    HICON,
    HMENU,
    HWND,
    INT,
    LPARAM,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    UINT,
    WPARAM,
)

from core.utils.win32.structs import (
    ICONINFO,
)
from core.utils.win32.typecheck import CArgObject

user32 = windll.user32

user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = c_long

user32.CreateWindowExW.argtypes = [
    DWORD,
    LPCWSTR,
    LPCWSTR,
    DWORD,
    INT,
    INT,
    INT,
    INT,
    HWND,
    HMENU,
    WPARAM,
    LPVOID,
]
user32.CreateWindowExW.restype = HWND

user32.SetWindowPos.argtypes = [
    HWND,
    HWND,
    INT,
    INT,
    INT,
    INT,
    UINT,
]
user32.SetWindowPos.restype = c_int

user32.DestroyWindow.argtypes = [HWND]
user32.DestroyWindow.restype = c_int

user32.RegisterWindowMessageW.argtypes = [LPCWSTR]
user32.RegisterWindowMessageW.restype = UINT

user32.RegisterShellHookWindow.argtypes = [HWND]
user32.RegisterShellHookWindow.restype = BOOL

user32.DeregisterShellHookWindow.argtypes = [HWND]
user32.DeregisterShellHookWindow.restype = BOOL

user32.SetPropW.argtypes = [HWND, LPCWSTR, HANDLE]
user32.SetPropW.restype = BOOL

user32.RemovePropW.argtypes = [HWND, LPCWSTR]
user32.RemovePropW.restype = BOOL

user32.SetTaskmanWindow.argtypes = [HWND]
user32.SetTaskmanWindow.restype = BOOL

user32.SendNotifyMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendNotifyMessageW.restype = c_int

user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = c_int

user32.SetTimer.argtypes = [HWND, UINT, UINT, LPVOID]
user32.SetTimer.restype = c_int

user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
user32.FindWindowW.restype = HWND

user32.FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]
user32.FindWindowExW.restype = HWND

user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = c_int

user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = BOOL

user32.GetWindowThreadProcessId.argtypes = [HWND, LPDWORD]
user32.GetWindowThreadProcessId.restype = DWORD

user32.AllowSetForegroundWindow.argtypes = [DWORD]
user32.AllowSetForegroundWindow.restype = BOOL

user32.GetIconInfo.argtypes = [HICON, POINTER(ICONINFO)]
user32.GetIconInfo.restype = BOOL

user32.GetDC.argtypes = [HANDLE]
user32.GetDC.restype = HDC

user32.ReleaseDC.argtypes = [HANDLE, HDC]
user32.ReleaseDC.restype = c_int


def DefWindowProc(hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
    return user32.DefWindowProcW(hwnd, uMsg, wParam, lParam)


def CreateWindowEx(
    dwExStyle: int,
    lpClassName: str | None,
    lpWindowName: str | None,
    dwStyle: int,
    x: int,
    y: int,
    nWidth: int,
    nHeight: int,
    hWndParent: int | None,
    hMenu: int | None,
    hInstance: int | None,
    lpParam: int | None,
):
    return user32.CreateWindowExW(
        dwExStyle,
        lpClassName,
        lpWindowName,
        dwStyle,
        x,
        y,
        nWidth,
        nHeight,
        hWndParent,
        hMenu,
        hInstance,
        lpParam,
    )


def SetWindowPos(
    hwnd: int,
    hWndInsertAfter: int,
    x: int,
    y: int,
    cx: int,
    cy: int,
    uFlags: int,
):
    return user32.SetWindowPos(hwnd, hWndInsertAfter, x, y, cx, cy, uFlags)


def DestroyWindow(hwnd: int):
    return user32.DestroyWindow(hwnd)


def RegisterWindowMessage(lpString: str):
    return user32.RegisterWindowMessageW(lpString)


def RegisterShellHookWindow(hwnd: int) -> bool:
    return user32.RegisterShellHookWindow(hwnd)


def DeregisterShellHookWindow(hwnd: int) -> bool:
    return user32.DeregisterShellHookWindow(hwnd)


def SetProp(hwnd: int, lpString: str, hData: int) -> bool:
    return user32.SetPropW(hwnd, lpString, hData)


def RemoveProp(hwnd: int, lpString: str) -> bool:
    return user32.RemovePropW(hwnd, lpString)


def SetTaskmanWindow(hwnd: int) -> bool:
    return user32.SetTaskmanWindow(hwnd)


def SendNotifyMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    return user32.SendNotifyMessageW(hwnd, msg, wParam, lParam)


def PostMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    return user32.PostMessageW(hwnd, msg, wParam, lParam)


def SetTimer(hwnd: int, nIDEvent: int, uElapse: int, lpTimerFunc: LPVOID | None):
    return user32.SetTimer(hwnd, nIDEvent, uElapse, lpTimerFunc)


def FindWindow(lpClassName: str | None, lpWindowName: str | None):
    return user32.FindWindowW(lpClassName, lpWindowName)


def FindWindowEx(
    hwndParent: int,
    hwndChildAfter: int,
    lpszClass: str | None,
    lpszWindow: str | None,
):
    return user32.FindWindowExW(hwndParent, hwndChildAfter, lpszClass, lpszWindow)


def SendMessage(
    hwnd: int,
    msg: int,
    wParam: int,
    lParam: int,
) -> int:
    return user32.SendMessageW(hwnd, msg, wParam, lParam)


def IsWindow(hwnd: int) -> bool:
    return user32.IsWindow(hwnd)


def GetWindowThreadProcessId(hwnd: int, lpdwProcessId: CArgObject) -> int:
    return user32.GetWindowThreadProcessId(hwnd, lpdwProcessId)


def AllowSetForegroundWindow(dwProcessId: int) -> int:
    return user32.AllowSetForegroundWindow(dwProcessId)


def GetIconInfo(hIcon: int, piconinfo: CArgObject) -> bool:
    return user32.GetIconInfo(hIcon, piconinfo)


def GetDC(hwnd: int | None) -> int:
    return user32.GetDC(hwnd)


def ReleaseDC(hwnd: int | None, hdc: int) -> int:
    return user32.ReleaseDC(hwnd, hdc)

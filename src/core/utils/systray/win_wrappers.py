"""Wrappers for windows API functions to make them easier to use and have proper types"""

import ctypes as ct
from ctypes import (
    Array,
    c_int,
    c_long,
    c_wchar,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HMENU,
    HWND,
    INT,
    LPARAM,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    LPWSTR,
    UINT,
    WPARAM,
)

# Load necessary Windows functions
user32 = windll.user32
gdi32 = windll.gdi32
kernel32 = windll.kernel32


def DefWindowProc(hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
    user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = c_long
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
    user32.SetWindowPos.restype = c_int
    user32.SetWindowPos.argtypes = [
        HWND,
        HWND,
        INT,
        INT,
        INT,
        INT,
        UINT,
    ]
    return user32.SetWindowPos(hwnd, hWndInsertAfter, x, y, cx, cy, uFlags)


def DestroyWindow(hwnd: int):
    user32.DestroyWindow.restype = c_int
    user32.DestroyWindow.argtypes = [HWND]
    return user32.DestroyWindow(hwnd)


def RegisterWindowMessage(lpString: str):
    user32.RegisterWindowMessageW.restype = UINT
    user32.RegisterWindowMessageW.argtypes = [LPCWSTR]
    return user32.RegisterWindowMessageW(lpString)


def SendNotifyMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    user32.SendNotifyMessageW.restype = c_int
    user32.SendNotifyMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    return user32.SendNotifyMessageW(hwnd, msg, wParam, lParam)


def PostMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    user32.PostMessageW.restype = c_int
    user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    return user32.PostMessageW(hwnd, msg, wParam, lParam)


def SetTimer(hwnd: int, nIDEvent: int, uElapse: int, lpTimerFunc: LPVOID | None):
    user32.SetTimer.restype = c_int
    user32.SetTimer.argtypes = [HWND, UINT, UINT, LPVOID]
    return user32.SetTimer(hwnd, nIDEvent, uElapse, lpTimerFunc)


def FindWindow(lpClassName: str | None, lpWindowName: str | None):
    user32.FindWindowW.restype = HWND
    user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
    return user32.FindWindowW(lpClassName, lpWindowName)


def FindWindowEx(
    hwndParent: int,
    hwndChildAfter: int,
    lpszClass: str | None,
    lpszWindow: str | None,
):
    user32.FindWindowExW.restype = HWND
    user32.FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]
    return user32.FindWindowExW(hwndParent, hwndChildAfter, lpszClass, lpszWindow)


def SendMessage(
    hwnd: int,
    msg: int,
    wParam: int,
    lParam: int,
) -> int:
    user32.SendMessageW.restype = c_int
    user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    return user32.SendMessageW(hwnd, msg, wParam, lParam)


def IsWindow(hwnd: int) -> BOOL:
    user32.IsWindow.restype = BOOL
    user32.IsWindow.argtypes = [HWND]
    return user32.IsWindow(hwnd)


def GetWindowThreadProcessId(hwnd: int, lpdwProcessId: "ct._CArgObject") -> int:  # pyright: ignore [reportPrivateUsage]
    user32.GetWindowThreadProcessId.restype = DWORD
    user32.GetWindowThreadProcessId.argtypes = [HWND, LPDWORD]
    return user32.GetWindowThreadProcessId(hwnd, lpdwProcessId)


def AllowSetForegroundWindow(dwProcessId: int) -> int:
    user32.AllowSetForegroundWindow.restype = BOOL
    user32.AllowSetForegroundWindow.argtypes = [DWORD]
    return user32.AllowSetForegroundWindow(dwProcessId)


def OpenProcess(dwDesiredAccess: int, bInheritHandle: bool, dwProcessId: int) -> int:
    kernel32.OpenProcess.restype = HANDLE
    kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
    return kernel32.OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId)


def QueryFullProcessImageNameW(
    hProcess: int,
    dwFlags: int,
    lpExeName: Array[c_wchar],
    lpdwSize: "ct._CArgObject",  # pyright: ignore [reportPrivateUsage]
) -> int:
    kernel32.QueryFullProcessImageNameW.restype = BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, LPDWORD]
    return kernel32.QueryFullProcessImageNameW(hProcess, dwFlags, lpExeName, lpdwSize)


def CloseHandle(hObject: int):
    kernel32.CloseHandle.restype = BOOL
    kernel32.CloseHandle.argtypes = [HANDLE]
    return kernel32.CloseHandle(hObject)

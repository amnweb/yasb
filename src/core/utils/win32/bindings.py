"""Wrappers for win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
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
    HDC,
    HICON,
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
from typing import TYPE_CHECKING, Any

from core.utils.win32.structs import (
    BITMAPINFO,
    HBITMAP,
    ICONINFO,
)

if TYPE_CHECKING:
    # NOTE: this is an internal ctypes type that does not exist during runtime
    from ctypes import _CArgObject as CArgObject  # type: ignore[reportPrivateUsage]
else:
    CArgObject = Any

user32 = windll.user32
gdi32 = windll.gdi32
kernel32 = windll.kernel32

# --- Function prototypes (argtypes/restype) ---
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

user32.DestroyWindow.restype = c_int
user32.DestroyWindow.argtypes = [HWND]

user32.RegisterWindowMessageW.restype = UINT
user32.RegisterWindowMessageW.argtypes = [LPCWSTR]

user32.SendNotifyMessageW.restype = c_int
user32.SendNotifyMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]

user32.PostMessageW.restype = c_int
user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]

user32.SetTimer.restype = c_int
user32.SetTimer.argtypes = [HWND, UINT, UINT, LPVOID]

user32.FindWindowW.restype = HWND
user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]

user32.FindWindowExW.restype = HWND
user32.FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]

user32.SendMessageW.restype = c_int
user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]

user32.IsWindow.restype = BOOL
user32.IsWindow.argtypes = [HWND]

user32.GetWindowThreadProcessId.restype = DWORD
user32.GetWindowThreadProcessId.argtypes = [HWND, LPDWORD]

user32.AllowSetForegroundWindow.restype = BOOL
user32.AllowSetForegroundWindow.argtypes = [DWORD]

user32.GetIconInfo.argtypes = [HICON, POINTER(ICONINFO)]
user32.GetIconInfo.restype = BOOL

user32.GetDC.argtypes = [HANDLE]
user32.GetDC.restype = HDC

user32.ReleaseDC.argtypes = [HANDLE, HDC]
user32.ReleaseDC.restype = c_int

kernel32.OpenProcess.restype = HANDLE
kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]

kernel32.QueryFullProcessImageNameW.restype = BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, LPDWORD]

kernel32.CloseHandle.restype = BOOL
kernel32.CloseHandle.argtypes = [HANDLE]

gdi32.GetObjectW.argtypes = [HANDLE, c_int, LPVOID]
gdi32.GetObjectW.restype = c_int

gdi32.GetDIBits.argtypes = [HDC, HBITMAP, DWORD, DWORD, LPVOID, POINTER(BITMAPINFO), DWORD]
gdi32.GetDIBits.restype = c_int

gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteObject.restype = BOOL


# --- Python-friendly typed wrapper functions ---
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


def OpenProcess(dwDesiredAccess: int, bInheritHandle: bool, dwProcessId: int) -> int:
    return kernel32.OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId)


def QueryFullProcessImageNameW(
    hProcess: int,
    dwFlags: int,
    lpExeName: Array[c_wchar],
    lpdwSize: CArgObject,
) -> int:
    return kernel32.QueryFullProcessImageNameW(hProcess, dwFlags, lpExeName, lpdwSize)


def CloseHandle(hObject: int):
    return kernel32.CloseHandle(hObject)


def GetIconInfo(hIcon: int, piconinfo: CArgObject) -> bool:
    return user32.GetIconInfo(hIcon, piconinfo)


def GetDC(hwnd: int | None) -> int:
    return user32.GetDC(hwnd)


def GetDIBits(
    hdc: int,
    hbmp: HBITMAP,
    uStartScan: int,
    cScanLines: int,
    lpvBits: CArgObject,
    lpbi: CArgObject,
    uUsage: int,
) -> int:
    return gdi32.GetDIBits(hdc, hbmp, uStartScan, cScanLines, lpvBits, lpbi, uUsage)


def ReleaseDC(hwnd: int | None, hdc: int) -> int:
    return user32.ReleaseDC(hwnd, hdc)


def DeleteObject(hObject: int) -> bool:
    return gdi32.DeleteObject(hObject)


def GetObject(hgdiobj: int, cbBuffer: int, lpvObject: CArgObject) -> int:
    return gdi32.GetObjectW(hgdiobj, cbBuffer, lpvObject)

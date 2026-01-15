"""Wrappers for user32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    WINFUNCTYPE,
    c_int,
    c_long,
    c_ulong,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HDC,
    HICON,
    HINSTANCE,
    HMENU,
    HMONITOR,
    HWND,
    INT,
    LPARAM,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    RECT,
    UINT,
    WPARAM,
)

from core.utils.win32.structs import (
    ICONINFO,
)
from core.utils.win32.typecheck import CArgObject

user32 = windll.user32
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND

# Monitor functions
MONITORENUMPROC = WINFUNCTYPE(BOOL, HMONITOR, HDC, POINTER(RECT), LPARAM)

user32.EnumDisplayMonitors.argtypes = [HDC, POINTER(RECT), MONITORENUMPROC, LPARAM]
user32.EnumDisplayMonitors.restype = BOOL

user32.MonitorFromWindow.argtypes = [HWND, DWORD]
user32.MonitorFromWindow.restype = HMONITOR

# Monitor flags
MONITOR_DEFAULTTONULL = 0
MONITOR_DEFAULTTOPRIMARY = 1
MONITOR_DEFAULTTONEAREST = 2

user32.SetWinEventHook.argtypes = [
    DWORD,  # eventMin
    DWORD,  # eventMax
    HINSTANCE,  # hmodWinEventProc (HMODULE/HINSTANCE)
    LPVOID,  # lpfnWinEventProc (callback)
    DWORD,  # idProcess
    DWORD,  # idThread
    DWORD,  # dwFlags
]
user32.SetWinEventHook.restype = HANDLE

user32.UnhookWinEvent.argtypes = [HANDLE]
user32.UnhookWinEvent.restype = BOOL


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

user32.IsWindowEnabled.argtypes = [HWND]
user32.IsWindowEnabled.restype = BOOL

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

user32.EnumWindows.argtypes = [LPVOID, LPARAM]
user32.EnumWindows.restype = BOOL

user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = BOOL

# Using LPVOID for the data pointer to avoid hard dependency on struct definition here
user32.SetWindowCompositionAttribute.argtypes = [HWND, LPVOID]
user32.SetWindowCompositionAttribute.restype = c_int

# Additional user32 APIs commonly used across the codebase
user32.GetAncestor.argtypes = [HWND, UINT]
user32.GetAncestor.restype = HWND

user32.GetLastActivePopup.argtypes = [HWND]
user32.GetLastActivePopup.restype = HWND

user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = BOOL

user32.GetWindowLongW.argtypes = [HWND, INT]
user32.GetWindowLongW.restype = c_long

user32.ShowWindowAsync.argtypes = [HWND, INT]
user32.ShowWindowAsync.restype = BOOL

user32.ShowWindow.argtypes = [HWND, INT]
user32.ShowWindow.restype = BOOL

user32.BringWindowToTop.argtypes = [HWND]
user32.BringWindowToTop.restype = BOOL

user32.SetActiveWindow.argtypes = [HWND]
user32.SetActiveWindow.restype = HWND

user32.AttachThreadInput.argtypes = [DWORD, DWORD, BOOL]
user32.AttachThreadInput.restype = BOOL

user32.SendMessageTimeoutW.argtypes = [HWND, UINT, WPARAM, LPARAM, UINT, UINT, LPVOID]
user32.SendMessageTimeoutW.restype = c_int

user32.EndTask.argtypes = [HWND, BOOL, BOOL]
user32.EndTask.restype = BOOL


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


def SetProp(hwnd: int, lpString: str, hData: int | None = None) -> bool:
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


def IsWindowEnabled(hwnd: int) -> bool:
    return user32.IsWindowEnabled(hwnd)


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


def GetForegroundWindow() -> int:
    return user32.GetForegroundWindow()


def SetWinEventHook(
    eventMin: int,
    eventMax: int,
    hmodWinEventProc: int | None,
    lpfnWinEventProc: LPVOID,
    idProcess: int,
    idThread: int,
    dwFlags: int,
) -> int:
    return user32.SetWinEventHook(eventMin, eventMax, hmodWinEventProc, lpfnWinEventProc, idProcess, idThread, dwFlags)


def UnhookWinEvent(hWinEventHook: int) -> bool:
    return bool(user32.UnhookWinEvent(hWinEventHook))


def EnumWindows(lpEnumFunc: LPVOID, lParam: int) -> bool:
    return bool(user32.EnumWindows(lpEnumFunc, lParam))


def SetForegroundWindow(hwnd: int) -> bool:
    return bool(user32.SetForegroundWindow(hwnd))


def SetWindowCompositionAttribute(hwnd: int, data: LPVOID) -> int:
    return user32.SetWindowCompositionAttribute(hwnd, data)


def GetAncestor(hwnd: int, ga_flags: int) -> int:
    return user32.GetAncestor(hwnd, ga_flags)


def GetLastActivePopup(hwnd: int) -> int:
    return user32.GetLastActivePopup(hwnd)


def IsWindowVisible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def GetWindowLong(hwnd: int, index: int) -> int:
    return int(user32.GetWindowLongW(hwnd, index))


def ShowWindowAsync(hwnd: int, cmd_show: int) -> bool:
    return bool(user32.ShowWindowAsync(hwnd, cmd_show))


def ShowWindow(hwnd: int, cmd_show: int) -> bool:
    return bool(user32.ShowWindow(hwnd, cmd_show))


def BringWindowToTop(hwnd: int) -> bool:
    return bool(user32.BringWindowToTop(hwnd))


def SetActiveWindow(hwnd: int) -> int:
    return user32.SetActiveWindow(hwnd)


def AttachThreadInput(id_attach: int, id_attach_to: int, attach: bool) -> bool:
    return bool(user32.AttachThreadInput(id_attach, id_attach_to, attach))


def SendMessageTimeout(
    hwnd: int,
    msg: int,
    wParam: int,
    lParam: int,
    fuFlags: int,
    uTimeout: int,
    lpdwResult: int | None,
) -> int:
    # Accept None for lpdwResult and provide a dummy buffer
    if lpdwResult is None:
        tmp = c_ulong()
        from ctypes import byref as _byref  # local import to avoid polluting namespace

        return user32.SendMessageTimeoutW(hwnd, msg, wParam, lParam, fuFlags, uTimeout, _byref(tmp))
    return user32.SendMessageTimeoutW(hwnd, msg, wParam, lParam, fuFlags, uTimeout, lpdwResult)


def EndTask(hwnd: int, fShutDown: bool, fForce: bool) -> bool:
    return bool(user32.EndTask(hwnd, fShutDown, fForce))


def SendMessageTimeoutW(
    hwnd: int,
    msg: int,
    wParam: int,
    lParam: int,
    fuFlags: int,
    uTimeout: int,
    lpdwResult,
) -> int:
    """Direct wrapper with the wide-character entrypoint name for robustness."""
    return user32.SendMessageTimeoutW(hwnd, msg, wParam, lParam, fuFlags, uTimeout, lpdwResult)

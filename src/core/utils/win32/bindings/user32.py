"""Wrappers for user32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    WINFUNCTYPE,
    Array,
    WinDLL,
    byref,
    c_int,
    c_long,
    c_size_t,
    c_ssize_t,
    create_unicode_buffer,
    sizeof,
)
from ctypes.wintypes import (
    ATOM,
    BOOL,
    BYTE,
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
    LPWSTR,
    MSG,
    POINT,
    RECT,
    SHORT,
    UINT,
    WPARAM,
)

from core.utils.win32.structs import (
    GUID,
    ICONINFO,
    INPUT,
    WINDOWPLACEMENT,
    WNDCLASS,
    WNDENUMPROC,
)
from core.utils.win32.typecheck import CArgObject, CFunctionType

user32 = WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND

# Monitor functions
MONITORENUMPROC = WINFUNCTYPE(BOOL, HMONITOR, HDC, POINTER(RECT), LPARAM)

user32.EnumDisplayMonitors.argtypes = [HDC, POINTER(RECT), MONITORENUMPROC, LPARAM]
user32.EnumDisplayMonitors.restype = BOOL

user32.MonitorFromWindow.argtypes = [HWND, DWORD]
user32.MonitorFromWindow.restype = HMONITOR


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

user32.GetMessageW.argtypes = [POINTER(MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = INT

user32.PeekMessageW.argtypes = [POINTER(MSG), HWND, UINT, UINT, UINT]
user32.PeekMessageW.restype = BOOL

user32.TranslateMessage.argtypes = [POINTER(MSG)]
user32.TranslateMessage.restype = BOOL

user32.DispatchMessageW.argtypes = [POINTER(MSG)]
user32.DispatchMessageW.restype = LPARAM

user32.PostQuitMessage.argtypes = [INT]
user32.PostQuitMessage.restype = None

user32.PostThreadMessageW.argtypes = [DWORD, UINT, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = BOOL

user32.RegisterClassW.argtypes = [POINTER(WNDCLASS)]
user32.RegisterClassW.restype = ATOM

user32.RegisterPowerSettingNotification.argtypes = [HANDLE, POINTER(GUID), DWORD]
user32.RegisterPowerSettingNotification.restype = HANDLE

user32.UnregisterPowerSettingNotification.argtypes = [HANDLE]
user32.UnregisterPowerSettingNotification.restype = BOOL

# Global hotkey functions
user32.RegisterHotKey.argtypes = [HWND, INT, UINT, UINT]
user32.RegisterHotKey.restype = BOOL

user32.UnregisterHotKey.argtypes = [HWND, INT]
user32.UnregisterHotKey.restype = BOOL

user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LPARAM

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


user32.GetPropW.argtypes = [HWND, LPCWSTR]
user32.GetPropW.restype = HANDLE

user32.SetTaskmanWindow.argtypes = [HWND]
user32.SetTaskmanWindow.restype = BOOL

user32.SendNotifyMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendNotifyMessageW.restype = c_int

user32.GetDesktopWindow.argtypes = []
user32.GetDesktopWindow.restype = HWND

user32.WaitForInputIdle.argtypes = [HANDLE, DWORD]
user32.WaitForInputIdle.restype = DWORD

user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = c_int

user32.SetTimer.argtypes = [HWND, c_size_t, UINT, LPVOID]
user32.SetTimer.restype = c_size_t

user32.KillTimer.argtypes = [HWND, c_size_t]
user32.KillTimer.restype = BOOL

user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
user32.FindWindowW.restype = HWND

user32.SetWindowsHookExW.argtypes = [c_int, LPVOID, HINSTANCE, DWORD]
user32.SetWindowsHookExW.restype = HANDLE

user32.UnhookWindowsHookEx.argtypes = [HANDLE]
user32.UnhookWindowsHookEx.restype = BOOL

user32.FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]
user32.FindWindowExW.restype = HWND

user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LPARAM

user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = BOOL

user32.IsWindowEnabled.argtypes = [HWND]
user32.IsWindowEnabled.restype = BOOL

user32.IsHungAppWindow.argtypes = [HWND]
user32.IsHungAppWindow.restype = BOOL

user32.GetWindowThreadProcessId.argtypes = [HWND, LPDWORD]
user32.GetWindowThreadProcessId.restype = DWORD

user32.AllowSetForegroundWindow.argtypes = [DWORD]
user32.AllowSetForegroundWindow.restype = BOOL

user32.GetIconInfo.argtypes = [HICON, POINTER(ICONINFO)]
user32.GetIconInfo.restype = BOOL

# https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-loadimagew
user32.LoadImageW.argtypes = [HINSTANCE, LPCWSTR, UINT, INT, INT, UINT]
user32.LoadImageW.restype = HANDLE

user32.DestroyIcon.argtypes = [HICON]
user32.DestroyIcon.restype = BOOL

user32.GetDC.argtypes = [HANDLE]
user32.GetDC.restype = HDC

user32.ReleaseDC.argtypes = [HANDLE, HDC]
user32.ReleaseDC.restype = c_int

user32.EnumWindows.argtypes = [LPVOID, LPARAM]
user32.EnumWindows.restype = BOOL

user32.EnumChildWindows.argtypes = [HWND, LPVOID, LPARAM]
user32.EnumChildWindows.restype = BOOL

user32.SetParent.argtypes = [HWND, HWND]
user32.SetParent.restype = HWND

user32.GetWindowRect.argtypes = [HWND, POINTER(RECT)]
user32.GetWindowRect.restype = BOOL

user32.GetClassNameW.argtypes = [HWND, LPCWSTR, INT]
user32.GetClassNameW.restype = INT

user32.InternalGetWindowText.argtypes = [HWND, LPCWSTR, INT]
user32.InternalGetWindowText.restype = INT

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

user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = BOOL

user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowTextLengthW.restype = c_int

user32.GetWindowTextW.argtypes = [HWND, LPWSTR, INT]
user32.GetWindowTextW.restype = INT

user32.GetClassLongPtrW.argtypes = [HWND, INT]
user32.GetClassLongPtrW.restype = c_size_t

user32.GetParent.argtypes = [HWND]
user32.GetParent.restype = HWND

user32.GetWindow.argtypes = [HWND, UINT]
user32.GetWindow.restype = HWND

user32.GetWindowPlacement.argtypes = [HWND, POINTER(WINDOWPLACEMENT)]
user32.GetWindowPlacement.restype = BOOL

user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = HMENU

user32.AppendMenuW.argtypes = [HMENU, UINT, c_size_t, LPCWSTR]
user32.AppendMenuW.restype = BOOL

user32.TrackPopupMenu.argtypes = [HMENU, UINT, INT, INT, INT, HWND, POINTER(RECT)]
user32.TrackPopupMenu.restype = BOOL

user32.DestroyMenu.argtypes = [HMENU]
user32.DestroyMenu.restype = BOOL

user32.GetKeyState.argtypes = [INT]
user32.GetKeyState.restype = SHORT

user32.GetWindowLongW.argtypes = [HWND, INT]
user32.GetWindowLongW.restype = c_long

user32.GetWindowLongPtrW.argtypes = [HWND, INT]
user32.GetWindowLongPtrW.restype = c_ssize_t

user32.SetWindowLongPtrW.argtypes = [HWND, INT, c_ssize_t]
user32.SetWindowLongPtrW.restype = c_ssize_t

user32.GetShellWindow.argtypes = []
user32.GetShellWindow.restype = HWND

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

user32.SendMessageTimeoutW.argtypes = [HWND, UINT, WPARAM, LPARAM, UINT, UINT, POINTER(c_size_t)]
user32.SendMessageTimeoutW.restype = LPARAM

user32.EndTask.argtypes = [HWND, BOOL, BOOL]
user32.EndTask.restype = BOOL

# Keyboard layout functions - HKL is a HANDLE (c_void_p)
user32.GetKeyboardLayout.argtypes = [DWORD]
user32.GetKeyboardLayout.restype = HANDLE

user32.GetKeyboardLayoutList.argtypes = [c_int, HANDLE]
user32.GetKeyboardLayoutList.restype = c_int

user32.ActivateKeyboardLayout.argtypes = [HANDLE, UINT]
user32.ActivateKeyboardLayout.restype = HANDLE

user32.LoadKeyboardLayoutW.argtypes = [LPCWSTR, UINT]
user32.LoadKeyboardLayoutW.restype = HANDLE

user32.GetKeyboardLayoutNameW.argtypes = [LPCWSTR]
user32.GetKeyboardLayoutNameW.restype = BOOL

user32.keybd_event.argtypes = [BYTE, BYTE, DWORD, c_size_t]
user32.keybd_event.restype = None

user32.SendInput.argtypes = [UINT, POINTER(INPUT), c_int]
user32.SendInput.restype = UINT

user32.GetCursorPos.argtypes = [POINTER(POINT)]
user32.GetCursorPos.restype = BOOL

user32.GetAsyncKeyState.argtypes = [c_int]
user32.GetAsyncKeyState.restype = SHORT

user32.MessageBeep.argtypes = [UINT]
user32.MessageBeep.restype = BOOL

user32.SetFocus.argtypes = [HWND]
user32.SetFocus.restype = HWND

user32.OpenClipboard.argtypes = [HWND]
user32.OpenClipboard.restype = BOOL

user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = BOOL

user32.SetClipboardData.argtypes = [UINT, HANDLE]
user32.SetClipboardData.restype = HANDLE

user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = BOOL


def DefWindowProc(hwnd: int, uMsg: int, wParam: int, lParam: int) -> int:
    return user32.DefWindowProcW(hwnd, uMsg, wParam, lParam)


def PostQuitMessage(nExitCode: int) -> None:
    user32.PostQuitMessage(nExitCode)


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


def GetProp(hwnd: int, lpString: str) -> int | None:
    return user32.GetPropW(hwnd, lpString)


def SetTaskmanWindow(hwnd: int) -> bool:
    return user32.SetTaskmanWindow(hwnd)


def SendNotifyMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    return user32.SendNotifyMessageW(hwnd, msg, wParam, lParam)


def GetDesktopWindow() -> int:
    return user32.GetDesktopWindow()


def WaitForInputIdle(hProcess: int, dwMilliseconds: int) -> int:
    return user32.WaitForInputIdle(hProcess, dwMilliseconds)


def PostMessage(hwnd: int, msg: int, wParam: int, lParam: int) -> int:
    return user32.PostMessageW(hwnd, msg, wParam, lParam)


def SetTimer(hwnd: int, nIDEvent: int, uElapse: int, lpTimerFunc: LPVOID | None):
    return user32.SetTimer(hwnd, nIDEvent, uElapse, lpTimerFunc)


def KillTimer(hwnd: int, uIDEvent: int):
    return user32.KillTimer(hwnd, uIDEvent)


def FindWindow(lpClassName: str | None, lpWindowName: str | None):
    return user32.FindWindowW(lpClassName, lpWindowName)


def SetWindowsHookEx(idHook: int, lpfn: int, hmod: int, dwThreadId: int) -> int:
    return int(user32.SetWindowsHookExW(idHook, lpfn, hmod, dwThreadId))


def UnhookWindowsHookEx(hhk: int) -> bool:
    return bool(user32.UnhookWindowsHookEx(hhk))


def PostThreadMessage(idThread: int, Msg: int, wParam: int, lParam: int) -> bool:
    return bool(user32.PostThreadMessageW(idThread, Msg, wParam, lParam))


def FindWindowEx(
    hwndParent: int,
    hwndChildAfter: int,
    lpszClass: str | None,
    lpszWindow: str | None,
) -> int:
    return user32.FindWindowExW(hwndParent, hwndChildAfter, lpszClass, lpszWindow) or 0


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


def IsHungAppWindow(hwnd: int) -> bool:
    return bool(user32.IsHungAppWindow(hwnd))


def GetWindowThreadProcessId(hwnd: int, lpdwProcessId: CArgObject | None) -> int:
    return user32.GetWindowThreadProcessId(hwnd, lpdwProcessId)


def get_window_thread_process_id(hwnd: int) -> tuple[int, int]:
    pid = DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, byref(pid))
    return tid, pid.value


def AllowSetForegroundWindow(dwProcessId: int) -> int:
    return user32.AllowSetForegroundWindow(dwProcessId)


def GetIconInfo(hIcon: int, piconinfo: CArgObject) -> bool:
    return user32.GetIconInfo(hIcon, piconinfo)


def LoadImage(hInst: int, name: LPCWSTR | str, type: int, cx: int, cy: int, fuLoad: int) -> int:
    return int(user32.LoadImageW(hInst, name, type, cx, cy, fuLoad) or 0)


def DestroyIcon(hIcon: int) -> bool:
    return bool(user32.DestroyIcon(hIcon))


def GetDC(hwnd: int | None) -> int:
    return user32.GetDC(hwnd)


def ReleaseDC(hwnd: int | None, hdc: int) -> int:
    return user32.ReleaseDC(hwnd, hdc)


def GetForegroundWindow() -> int:
    return user32.GetForegroundWindow() or 0


def SetWinEventHook(
    eventMin: int,
    eventMax: int,
    hmodWinEventProc: int | None,
    lpfnWinEventProc: CFunctionType | LPVOID,
    idProcess: int,
    idThread: int,
    dwFlags: int,
) -> int:
    return user32.SetWinEventHook(eventMin, eventMax, hmodWinEventProc, lpfnWinEventProc, idProcess, idThread, dwFlags)


def UnhookWinEvent(hWinEventHook: int) -> bool:
    return bool(user32.UnhookWinEvent(hWinEventHook))


def EnumWindows(lpEnumFunc: CFunctionType | LPVOID, lParam: int) -> bool:
    return bool(user32.EnumWindows(lpEnumFunc, lParam))


def EnumChildWindows(hWndParent: int, lpEnumFunc: CFunctionType, lParam: int) -> bool:
    return bool(user32.EnumChildWindows(hWndParent, lpEnumFunc, lParam))


def enum_windows() -> list[int]:
    hwnds: list[int] = []

    def collect(hwnd: int, _: int) -> bool:
        hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(collect), 0)
    return hwnds


def enum_child_windows(parent: int) -> list[int]:
    hwnds: list[int] = []

    def collect(hwnd: int, _: int) -> bool:
        hwnds.append(hwnd)
        return True

    user32.EnumChildWindows(parent, WNDENUMPROC(collect), 0)
    return hwnds


def SetParent(hWndChild: int, hWndNewParent: int) -> int | None:
    return user32.SetParent(hWndChild, hWndNewParent)


def GetWindowRect(hwnd: int, lpRect: CArgObject) -> bool:
    return bool(user32.GetWindowRect(hwnd, lpRect))


def GetClassName(hwnd: int, buf_size: int = 256) -> str:
    from ctypes import create_unicode_buffer

    buf = create_unicode_buffer(buf_size)
    user32.GetClassNameW(hwnd, buf, buf_size)
    return buf.value


def InternalGetWindowText(hwnd: int, buf_size: int = 512) -> str:
    """Window title without sending WM_GETTEXT, so it cannot wait on a hung window."""
    from ctypes import create_unicode_buffer

    buf = create_unicode_buffer(buf_size)
    user32.InternalGetWindowText(hwnd, buf, buf_size)
    return buf.value


def SetForegroundWindow(hwnd: int) -> bool:
    return bool(user32.SetForegroundWindow(hwnd))


def SetWindowCompositionAttribute(hwnd: int, data: CArgObject) -> int:
    return user32.SetWindowCompositionAttribute(hwnd, data)


def GetAncestor(hwnd: int, ga_flags: int) -> int:
    return user32.GetAncestor(hwnd, ga_flags)


def GetLastActivePopup(hwnd: int) -> int:
    return user32.GetLastActivePopup(hwnd)


def IsWindowVisible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def IsIconic(hwnd: int) -> bool:
    return bool(user32.IsIconic(hwnd))


def GetWindowTextLength(hwnd: int) -> int:
    return user32.GetWindowTextLengthW(hwnd)


def GetWindowText(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def GetClassLongPtr(hwnd: int, index: int) -> int:
    return user32.GetClassLongPtrW(hwnd, index)


def GetParent(hwnd: int) -> int:
    return user32.GetParent(hwnd) or 0


def GetWindow(hwnd: int, cmd: int) -> int:
    return user32.GetWindow(hwnd, cmd) or 0


def GetWindowPlacement(hwnd: int, lpwndpl: CArgObject) -> bool:
    return bool(user32.GetWindowPlacement(hwnd, lpwndpl))


def GetWindowLong(hwnd: int, index: int) -> int:
    return int(user32.GetWindowLongW(hwnd, index))


def GetWindowLongPtr(hwnd: int, index: int) -> int:
    return user32.GetWindowLongPtrW(hwnd, index)


def SetWindowLongPtr(hwnd: int, index: int, value: int) -> int:
    return user32.SetWindowLongPtrW(hwnd, index, value)


def GetShellWindow() -> int:
    return user32.GetShellWindow()


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
        tmp = c_size_t()
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
    lpdwResult: CArgObject,
) -> int:
    """Direct wrapper with the wide-character entrypoint name for robustness."""
    return user32.SendMessageTimeoutW(hwnd, msg, wParam, lParam, fuFlags, uTimeout, lpdwResult)


def keybd_event(bVk: int, bScan: int, dwFlags: int, dwExtraInfo: int = 0) -> None:
    user32.keybd_event(bVk, bScan, dwFlags, dwExtraInfo)


def SendInput(inputs: Array[INPUT]) -> int:
    return user32.SendInput(len(inputs), inputs, sizeof(INPUT))


def GetCursorPos() -> tuple[int, int]:
    point = POINT()
    user32.GetCursorPos(byref(point))
    return point.x, point.y


def GetAsyncKeyState(vKey: int) -> int:
    return user32.GetAsyncKeyState(vKey)


def OpenClipboard(hWndNewOwner: int | None) -> bool:
    return bool(user32.OpenClipboard(hWndNewOwner))


def EmptyClipboard() -> bool:
    return bool(user32.EmptyClipboard())


def SetClipboardData(uFormat: int, hMem: int) -> int | None:
    return user32.SetClipboardData(uFormat, hMem)


def CloseClipboard() -> bool:
    return bool(user32.CloseClipboard())


def CreatePopupMenu() -> int:
    return user32.CreatePopupMenu() or 0


def AppendMenu(hMenu: int, uFlags: int, uIDNewItem: int, lpNewItem: str | None) -> bool:
    return bool(user32.AppendMenuW(hMenu, uFlags, uIDNewItem, lpNewItem))


def TrackPopupMenu(hMenu: int, uFlags: int, x: int, y: int, hWnd: int) -> int:
    return user32.TrackPopupMenu(hMenu, uFlags, x, y, 0, hWnd, None)


def DestroyMenu(hMenu: int) -> bool:
    return bool(user32.DestroyMenu(hMenu))

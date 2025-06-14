"""Wrappers for win32 API functions to make them easier to use and have proper types"""

from ctypes import POINTER, Array, byref, c_int, c_long, c_wchar, create_string_buffer, windll, wintypes
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
    LPCVOID,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    LPWSTR,
    UINT,
    WPARAM,
)
from typing import TYPE_CHECKING, Any

from core.utils.win32.structs import BITMAPINFO, GUID, HBITMAP, ICONINFO

if TYPE_CHECKING:
    # NOTE: this is an internal ctypes type that does not exist during runtime
    from ctypes import _CArgObject as CArgObject  # type: ignore[reportPrivateUsage]
else:
    CArgObject = Any

user32 = windll.user32
gdi32 = windll.gdi32
kernel32 = windll.kernel32
powrprof = windll.powrprof

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

kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
kernel32.OpenProcess.restype = HANDLE

kernel32.QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, LPDWORD]
kernel32.QueryFullProcessImageNameW.restype = BOOL

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.CreateNamedPipeW.argtypes = [
    LPCWSTR,
    DWORD,
    DWORD,
    DWORD,
    DWORD,
    DWORD,
    DWORD,
    LPVOID,
]
kernel32.CreateNamedPipeW.restype = HANDLE

kernel32.ConnectNamedPipe.argtypes = [HANDLE, LPVOID]
kernel32.ConnectNamedPipe.restype = BOOL

kernel32.DisconnectNamedPipe.argtypes = [HANDLE]
kernel32.DisconnectNamedPipe.restype = BOOL

kernel32.WaitNamedPipeW.argtypes = [LPCWSTR, DWORD]
kernel32.WaitNamedPipeW.restype = BOOL

kernel32.CreateEventW.argtypes = [
    LPVOID,
    BOOL,
    BOOL,
    LPCWSTR,
]
kernel32.CreateEventW.restype = HANDLE

kernel32.SetEvent.argtypes = [HANDLE]
kernel32.SetEvent.restype = BOOL

kernel32.OpenEventW.argtypes = [DWORD, BOOL, LPCWSTR]
kernel32.OpenEventW.restype = HANDLE

kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
kernel32.WaitForSingleObject.restype = DWORD

kernel32.ReadFile.argtypes = [
    HANDLE,
    LPVOID,
    DWORD,
    POINTER(DWORD),
    LPVOID,
]
kernel32.ReadFile.restype = BOOL

kernel32.WriteFile.argtypes = [
    HANDLE,
    LPCVOID,
    DWORD,
    POINTER(DWORD),
    LPVOID,
]
kernel32.WriteFile.restype = BOOL

kernel32.CreateFileW.argtypes = [
    LPCWSTR,
    DWORD,
    DWORD,
    LPVOID,
    DWORD,
    DWORD,
    HANDLE,
]
kernel32.CreateFileW.restype = HANDLE

kernel32.CloseHandle.argtypes = [
    HANDLE,
]
kernel32.CloseHandle.restype = BOOL

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


def CreateNamedPipe(
    lpName: str,
    dwOpenMode: int,
    dePipeMode: int,
    nMaxInstances: int,
    nOutBufferSize: int,
    nInBufferSize: int,
    nDefaultTimeOut: int,
    lpSecurityAttributes: int | None,
) -> int:
    return kernel32.CreateNamedPipeW(
        lpName,
        dwOpenMode,
        dePipeMode,
        nMaxInstances,
        nOutBufferSize,
        nInBufferSize,
        nDefaultTimeOut,
        lpSecurityAttributes,
    )


def ConnectNamedPipe(hNamedPipe: int, lpOverlapped: int | None = None) -> bool:
    return bool(kernel32.ConnectNamedPipe(hNamedPipe, lpOverlapped))


def DisconnectNamedPipe(hNamedPipe: int) -> bool:
    return bool(kernel32.DisconnectNamedPipe(hNamedPipe))


def WaitNamedPipe(hNamedPipe: str, nTimeOut: int) -> bool:
    return bool(kernel32.WaitNamedPipeW(hNamedPipe, nTimeOut))


def CreateEvent(
    lpEventAttributes: int | None,
    bManualReset: bool,
    bInitialState: bool,
    lpName: str | None,
) -> int:
    return kernel32.CreateEventW(lpEventAttributes, bManualReset, bInitialState, lpName)


def SetEvent(hEvent: int) -> bool:
    return bool(kernel32.SetEvent(hEvent))


def OpenEvent(dwDesiredAccess: int, bInheritHandle: bool, lpName: str) -> int:
    return kernel32.OpenEventW(dwDesiredAccess, bInheritHandle, lpName)


def WaitForSingleObject(hHandle: int, dwMilliseconds: int) -> int:
    return kernel32.WaitForSingleObject(hHandle, dwMilliseconds)


def ReadFile(hFile: int, nNumberOfBytesToRead: int) -> tuple[bool, bytes]:
    """Reads data from a file handle.
    - Returns a tuple of (success, data).
    - If success is False, data will be an empty bytes object.
    """
    buffer = create_string_buffer(nNumberOfBytesToRead)
    bytes_read = DWORD()
    success = bool(kernel32.ReadFile(hFile, buffer, nNumberOfBytesToRead, byref(bytes_read), None))
    return success, buffer.raw[: bytes_read.value]


def WriteFile(hFile: int, data: bytes) -> bool:
    buffer = create_string_buffer(data)
    bytes_written = DWORD()
    success = kernel32.WriteFile(hFile, buffer, len(data), byref(bytes_written), None)
    return bool(success)


def CreateFile(
    lpFileName: str,
    dwDesiredAccess: int,
    dwShareMode: int,
    lpSecurityAttributes: int | None,
    dwCreationDisposition: int,
    dwFlagsAndAttributes: int,
    hTemplateFile: int | None = None,
) -> int:
    return kernel32.CreateFileW(
        lpFileName,
        dwDesiredAccess,
        dwShareMode,
        lpSecurityAttributes,
        dwCreationDisposition,
        dwFlagsAndAttributes,
        hTemplateFile,
    )


# -- Power management function prototypes -- #
powrprof.PowerEnumerate.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    wintypes.DWORD,
    wintypes.ULONG,
    wintypes.LPBYTE,
    POINTER(wintypes.DWORD),
]
powrprof.PowerEnumerate.restype = wintypes.DWORD

powrprof.PowerReadFriendlyName.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(wintypes.DWORD),
    wintypes.LPBYTE,
    POINTER(wintypes.DWORD),
]
powrprof.PowerReadFriendlyName.restype = wintypes.DWORD

powrprof.PowerGetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(POINTER(GUID))]
powrprof.PowerGetActiveScheme.restype = wintypes.DWORD

powrprof.PowerSetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(GUID)]
powrprof.PowerSetActiveScheme.restype = wintypes.DWORD


# -- Power management function wrappers -- #
def PowerEnumerate(
    RootPowerKey,
    SchemeGuid,
    SubGroupOfPowerSettingsGuid,
    AccessFlags,
    Index,
    Buffer,
    BufferSize,
):
    return powrprof.PowerEnumerate(
        RootPowerKey, SchemeGuid, SubGroupOfPowerSettingsGuid, AccessFlags, Index, Buffer, BufferSize
    )


def PowerReadFriendlyName(
    RootPowerKey,
    SchemeGuid,
    SubGroupOfPowerSettingsGuid,
    PowerSettingGuid,
    Buffer,
    BufferSize,
):
    return powrprof.PowerReadFriendlyName(
        RootPowerKey, SchemeGuid, SubGroupOfPowerSettingsGuid, PowerSettingGuid, Buffer, BufferSize
    )


def PowerGetActiveScheme(
    UserRootPowerKey,
    ActivePolicyGuid,
):
    return powrprof.PowerGetActiveScheme(UserRootPowerKey, ActivePolicyGuid)


def PowerSetActiveScheme(
    UserRootPowerKey,
    SchemeGuid,
):
    return powrprof.PowerSetActiveScheme(UserRootPowerKey, SchemeGuid)

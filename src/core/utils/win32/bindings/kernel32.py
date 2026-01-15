"""Wrappers for kernel32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    Array,
    byref,
    c_wchar,
    create_string_buffer,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    LPCVOID,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    LPWSTR,
)

from core.utils.win32.typecheck import CArgObject

kernel32 = windll.kernel32

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

kernel32.DeviceIoControl.argtypes = [
    HANDLE,
    DWORD,
    LPVOID,
    DWORD,
    LPVOID,
    DWORD,
    LPDWORD,
    LPVOID,
]
kernel32.DeviceIoControl.restype = BOOL

kernel32.CloseHandle.argtypes = [
    HANDLE,
]
kernel32.CloseHandle.restype = BOOL


kernel32.FormatMessageW.argtypes = [
    DWORD,
    LPCVOID,
    DWORD,
    DWORD,
    LPWSTR,
    DWORD,
    POINTER(DWORD),
]
kernel32.FormatMessageW.restype = DWORD

# Additional kernel32 APIs
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = DWORD


# --- Python-friendly typed wrapper functions ---


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


def FormatMessage(
    dwFlags: int,
    lpSource: int | None,
    dwMessageId: int,
    dwLanguageId: int,
    lpBuffer: Array[c_wchar],
    nSize: int,
    Arguments: int | None,
) -> int:
    return kernel32.FormatMessageW(
        dwFlags,
        lpSource,
        dwMessageId,
        dwLanguageId,
        lpBuffer,
        nSize,
        Arguments,
    )


def GetCurrentThreadId() -> int:
    return int(kernel32.GetCurrentThreadId())

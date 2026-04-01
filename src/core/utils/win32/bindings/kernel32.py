"""Wrappers for kernel32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    Array,
    byref,
    c_char,
    c_size_t,
    c_wchar,
    create_string_buffer,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    LPCSTR,
    LPCVOID,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    LPWSTR,
    ULONG,
    USHORT,
)

from core.utils.win32.structs import SYSTEM_POWER_STATUS
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

kernel32.PeekNamedPipe.argtypes = [
    HANDLE,
    LPVOID,
    DWORD,
    LPDWORD,
    LPDWORD,
    LPDWORD,
]
kernel32.PeekNamedPipe.restype = BOOL

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

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.CreateMutexW.argtypes = [LPVOID, BOOL, LPCWSTR]
kernel32.CreateMutexW.restype = HANDLE

kernel32.OpenMutexW.argtypes = [DWORD, BOOL, LPCWSTR]
kernel32.OpenMutexW.restype = HANDLE

kernel32.VirtualAllocEx.restype = LPVOID
kernel32.VirtualAllocEx.argtypes = [HANDLE, LPVOID, c_size_t, DWORD, DWORD]

kernel32.WriteProcessMemory.restype = BOOL
kernel32.WriteProcessMemory.argtypes = [
    HANDLE,
    LPVOID,
    LPCSTR,
    c_size_t,
    POINTER(c_size_t),
]

kernel32.GetProcAddress.restype = LPVOID
kernel32.GetProcAddress.argtypes = [HANDLE, LPCSTR]

kernel32.CreateRemoteThread.restype = HANDLE
kernel32.CreateRemoteThread.argtypes = [
    HANDLE,
    LPVOID,
    c_size_t,
    LPVOID,
    LPVOID,
    DWORD,
    POINTER(DWORD),
]


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

kernel32.GetModuleHandleW.argtypes = [LPCWSTR]
kernel32.GetModuleHandleW.restype = HANDLE

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = DWORD

# GetSystemPowerStatus - Battery/power status
kernel32.GetSystemPowerStatus.argtypes = [POINTER(SYSTEM_POWER_STATUS)]
kernel32.GetSystemPowerStatus.restype = BOOL

# GetSystemInfo - System information
kernel32.GetSystemInfo.argtypes = [LPVOID]
kernel32.GetSystemInfo.restype = None

kernel32.IsWow64Process2.argtypes = [HANDLE, POINTER(USHORT), POINTER(USHORT)]
kernel32.IsWow64Process2.restype = BOOL

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = HANDLE

# Process enumeration and termination
kernel32.CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
kernel32.CreateToolhelp32Snapshot.restype = HANDLE

kernel32.Process32FirstW.argtypes = [HANDLE, LPVOID]
kernel32.Process32FirstW.restype = BOOL

kernel32.Process32NextW.argtypes = [HANDLE, LPVOID]
kernel32.Process32NextW.restype = BOOL

kernel32.TerminateProcess.argtypes = [HANDLE, DWORD]
kernel32.TerminateProcess.restype = BOOL

# GetLogicalProcessorInformationEx - Processor topology
kernel32.GetLogicalProcessorInformationEx.argtypes = [ULONG, LPVOID, POINTER(DWORD)]
kernel32.GetLogicalProcessorInformationEx.restype = BOOL

# PE resource loading
kernel32.LoadLibraryExW.argtypes = [LPCWSTR, HANDLE, DWORD]
kernel32.LoadLibraryExW.restype = HANDLE

kernel32.FindResourceW.argtypes = [HANDLE, LPCWSTR, LPCWSTR]
kernel32.FindResourceW.restype = HANDLE

kernel32.SizeofResource.argtypes = [HANDLE, HANDLE]
kernel32.SizeofResource.restype = DWORD

kernel32.LoadResource.argtypes = [HANDLE, HANDLE]
kernel32.LoadResource.restype = HANDLE

kernel32.LockResource.argtypes = [HANDLE]
kernel32.LockResource.restype = LPVOID

kernel32.FreeLibrary.argtypes = [HANDLE]
kernel32.FreeLibrary.restype = BOOL


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


def PeekNamedPipe(hNamedPipe: int) -> tuple[bool, int, int]:
    """Peeks at a named pipe. Returns (success, bytes_read, total_bytes_avail)."""
    bytes_read = DWORD()
    total_bytes_avail = DWORD()
    bytes_left_this_message = DWORD()
    success = kernel32.PeekNamedPipe(
        hNamedPipe,
        None,
        0,
        byref(bytes_read),
        byref(total_bytes_avail),
        byref(bytes_left_this_message),
    )
    return bool(success), bytes_read.value, total_bytes_avail.value


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


def CreateMutex(lpMutexAttributes: int | None, bInitialOwner: bool, lpName: str) -> int:
    return kernel32.CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)


def OpenMutex(dwDesiredAccess: int, bInheritHandle: bool, lpName: str) -> int:
    return kernel32.OpenMutexW(dwDesiredAccess, bInheritHandle, lpName)


def VirtualAllocEx(hProcess: int, lpAddress: int | None, dwSize: int, flAllocationType: int, flProtect: int) -> int:
    return kernel32.VirtualAllocEx(hProcess, lpAddress, dwSize, flAllocationType, flProtect)


def WriteProcessMemory(
    hProcess: int,
    lpBaseAddress: int,
    lpBuffer: Array[c_char],
    nSize: int,
    lpNumberOfBytesWritten: CArgObject,
) -> bool:
    return bool(kernel32.WriteProcessMemory(hProcess, lpBaseAddress, lpBuffer, nSize, lpNumberOfBytesWritten))


def GetProcAddress(hModule: int, lpProcName: bytes) -> int:
    return kernel32.GetProcAddress(hModule, lpProcName)


def CreateRemoteThread(
    hProcess: int,
    lpThreadAttributes: int | None,
    dwStackSize: int,
    lpStartAddress: int,
    lpParameter: int,
    dwCreationFlags: int,
    lpThreadId: CArgObject | None,
) -> int:
    return kernel32.CreateRemoteThread(
        hProcess,
        lpThreadAttributes,
        dwStackSize,
        lpStartAddress,
        lpParameter,
        dwCreationFlags,
        lpThreadId,
    )


def CreateToolhelp32Snapshot(dwFlags: int, th32ProcessID: int) -> int:
    return kernel32.CreateToolhelp32Snapshot(dwFlags, th32ProcessID)


def Process32FirstW(hSnapshot: int, lppe: CArgObject) -> bool:
    return bool(kernel32.Process32FirstW(hSnapshot, lppe))


def Process32NextW(hSnapshot: int, lppe: CArgObject) -> bool:
    return bool(kernel32.Process32NextW(hSnapshot, lppe))


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


def GetModuleHandle(lpModuleName: str | None) -> int:
    return kernel32.GetModuleHandleW(lpModuleName)


def GetLastError() -> int:
    return int(kernel32.GetLastError())


def IsWow64Process2(hProcess: int, lpProcessMachine: CArgObject, lpNativeMachine: CArgObject | None) -> bool:
    return bool(kernel32.IsWow64Process2(hProcess, lpProcessMachine, lpNativeMachine))


def GetCurrentProcess() -> int:
    return int(kernel32.GetCurrentProcess())

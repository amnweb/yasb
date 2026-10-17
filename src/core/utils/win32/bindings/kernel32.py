"""Wrappers for kernel32 win32 API functions to make them easier to use and have proper types"""

from collections.abc import Callable
from ctypes import (
    POINTER,
    WINFUNCTYPE,
    Array,
    WinDLL,
    byref,
    c_char,
    c_int,
    c_long,
    c_size_t,
    c_ulonglong,
    c_void_p,
    c_wchar,
    cast,
    create_string_buffer,
    create_unicode_buffer,
    get_last_error,
    sizeof,
    string_at,
    wstring_at,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HMODULE,
    LONG,
    LPCSTR,
    LPCVOID,
    LPCWSTR,
    LPDWORD,
    LPVOID,
    LPWSTR,
    UINT,
    ULONG,
    USHORT,
    WORD,
)
from typing import NamedTuple

from core.utils.win32.constants import ERROR_INSUFFICIENT_BUFFER, INVALID_HANDLE_VALUE, TH32CS_SNAPPROCESS
from core.utils.win32.structs import (
    COORD,
    MEMORYSTATUSEX,
    OVERLAPPED,
    PROCESS_INFORMATION,
    PROCESSENTRY32,
    SYSTEM_POWER_STATUS,
    WIN32_FIND_DATAW,
)
from core.utils.win32.typecheck import CArgObject

kernel32 = WinDLL("kernel32", use_last_error=True)

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

kernel32.ResetEvent.argtypes = [HANDLE]
kernel32.ResetEvent.restype = BOOL


kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
kernel32.WaitForSingleObject.restype = DWORD

kernel32.WaitForMultipleObjects.argtypes = [DWORD, POINTER(HANDLE), BOOL, DWORD]
kernel32.WaitForMultipleObjects.restype = DWORD

kernel32.ReadFile.argtypes = [
    HANDLE,
    LPVOID,
    DWORD,
    POINTER(DWORD),
    LPVOID,
]
kernel32.ReadFile.restype = BOOL

kernel32.GetOverlappedResult.argtypes = [HANDLE, POINTER(OVERLAPPED), LPDWORD, BOOL]
kernel32.GetOverlappedResult.restype = BOOL

kernel32.CancelIoEx.argtypes = [HANDLE, POINTER(OVERLAPPED)]
kernel32.CancelIoEx.restype = BOOL

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

kernel32.FindFirstChangeNotificationW.argtypes = [LPCWSTR, BOOL, DWORD]
kernel32.FindFirstChangeNotificationW.restype = HANDLE

kernel32.FindNextChangeNotification.argtypes = [HANDLE]
kernel32.FindNextChangeNotification.restype = BOOL

kernel32.FindCloseChangeNotification.argtypes = [HANDLE]
kernel32.FindCloseChangeNotification.restype = BOOL

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
    LPVOID,  # va_list*, or a DWORD_PTR array with FORMAT_MESSAGE_ARGUMENT_ARRAY
]
kernel32.FormatMessageW.restype = DWORD

# Additional kernel32 APIs
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = DWORD

kernel32.GetTickCount64.argtypes = []
kernel32.GetTickCount64.restype = c_ulonglong

kernel32.GetModuleHandleW.argtypes = [LPCWSTR]
kernel32.GetModuleHandleW.restype = HANDLE

# GetSystemPowerStatus - Battery/power status
kernel32.GetSystemPowerStatus.argtypes = [POINTER(SYSTEM_POWER_STATUS)]
kernel32.GetSystemPowerStatus.restype = BOOL

kernel32.LocalFree.argtypes = [LPVOID]
kernel32.LocalFree.restype = LPVOID

# GetSystemInfo - System information
kernel32.GetSystemInfo.argtypes = [LPVOID]
kernel32.GetSystemInfo.restype = None

kernel32.IsWow64Process2.argtypes = [HANDLE, POINTER(USHORT), POINTER(USHORT)]
kernel32.IsWow64Process2.restype = BOOL

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = HANDLE

kernel32.GetSystemWindowsDirectoryW.argtypes = [LPWSTR, UINT]
kernel32.GetSystemWindowsDirectoryW.restype = UINT

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

# https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nc-libloaderapi-enumresnameprocw
ENUMRESNAMEPROCW = WINFUNCTYPE(BOOL, HMODULE, c_void_p, c_void_p, c_void_p)
kernel32.EnumResourceNamesW.argtypes = [HMODULE, c_void_p, ENUMRESNAMEPROCW, c_void_p]
kernel32.EnumResourceNamesW.restype = BOOL

kernel32.LoadLibraryW.argtypes = [LPCWSTR]
kernel32.LoadLibraryW.restype = HANDLE

kernel32.GetPackageFullName.argtypes = [HANDLE, POINTER(UINT), LPWSTR]
kernel32.GetPackageFullName.restype = LONG

kernel32.GetApplicationUserModelId.argtypes = [HANDLE, POINTER(UINT), LPWSTR]
kernel32.GetApplicationUserModelId.restype = LONG

kernel32.GetLogicalDrives.argtypes = []
kernel32.GetLogicalDrives.restype = DWORD

kernel32.GetDriveTypeW.argtypes = [LPCWSTR]
kernel32.GetDriveTypeW.restype = UINT

kernel32.GetDiskFreeSpaceExW.argtypes = [LPCWSTR, POINTER(c_ulonglong), POINTER(c_ulonglong), POINTER(c_ulonglong)]
kernel32.GetDiskFreeSpaceExW.restype = BOOL

kernel32.GetVolumeInformationW.argtypes = [LPCWSTR, LPWSTR, DWORD, LPDWORD, LPDWORD, LPDWORD, LPWSTR, DWORD]
kernel32.GetVolumeInformationW.restype = BOOL

kernel32.FindFirstFileExW.argtypes = [LPCWSTR, c_int, POINTER(WIN32_FIND_DATAW), c_int, LPVOID, DWORD]
kernel32.FindFirstFileExW.restype = HANDLE

kernel32.FindNextFileW.argtypes = [HANDLE, POINTER(WIN32_FIND_DATAW)]
kernel32.FindNextFileW.restype = BOOL

kernel32.FindClose.argtypes = [HANDLE]
kernel32.FindClose.restype = BOOL

kernel32.GetUserGeoID.argtypes = [DWORD]
kernel32.GetUserGeoID.restype = LONG

kernel32.GetGeoInfoW.argtypes = [LONG, DWORD, LPWSTR, c_int, WORD]
kernel32.GetGeoInfoW.restype = c_int

kernel32.GlobalAlloc.argtypes = [UINT, c_size_t]
kernel32.GlobalAlloc.restype = HANDLE

kernel32.GlobalLock.argtypes = [HANDLE]
kernel32.GlobalLock.restype = LPVOID

kernel32.GlobalUnlock.argtypes = [HANDLE]
kernel32.GlobalUnlock.restype = BOOL

kernel32.GlobalFree.argtypes = [HANDLE]
kernel32.GlobalFree.restype = HANDLE

kernel32.GlobalMemoryStatusEx.argtypes = [POINTER(MEMORYSTATUSEX)]
kernel32.GlobalMemoryStatusEx.restype = BOOL

kernel32.GetLocaleInfoW.argtypes = [DWORD, DWORD, LPWSTR, c_int]
kernel32.GetLocaleInfoW.restype = c_int

kernel32.CreatePipe.argtypes = [POINTER(HANDLE), POINTER(HANDLE), LPVOID, DWORD]
kernel32.CreatePipe.restype = BOOL

kernel32.InitializeProcThreadAttributeList.argtypes = [LPVOID, DWORD, DWORD, POINTER(c_size_t)]
kernel32.InitializeProcThreadAttributeList.restype = BOOL

kernel32.UpdateProcThreadAttribute.argtypes = [LPVOID, DWORD, c_size_t, LPVOID, c_size_t, LPVOID, POINTER(c_size_t)]
kernel32.UpdateProcThreadAttribute.restype = BOOL

kernel32.DeleteProcThreadAttributeList.argtypes = [LPVOID]
kernel32.DeleteProcThreadAttributeList.restype = None

# lpStartupInfo is LPVOID: with EXTENDED_STARTUPINFO_PRESENT it points to a STARTUPINFOEXW
kernel32.CreateProcessW.argtypes = [
    LPCWSTR,
    LPWSTR,
    LPVOID,
    LPVOID,
    BOOL,
    DWORD,
    LPVOID,
    LPCWSTR,
    LPVOID,
    POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = BOOL

# ConPTY, Windows 10 1809 and later
try:
    kernel32.CreatePseudoConsole.argtypes = [COORD, HANDLE, HANDLE, DWORD, POINTER(HANDLE)]
    kernel32.CreatePseudoConsole.restype = c_long
    kernel32.ClosePseudoConsole.argtypes = [HANDLE]
    kernel32.ClosePseudoConsole.restype = None
except AttributeError:
    pass


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


def ConnectNamedPipe(hNamedPipe: int, lpOverlapped: CArgObject | int | None = None) -> bool:
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


def ResetEvent(hEvent: int) -> bool:
    return bool(kernel32.ResetEvent(hEvent))


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


def ReadFileOverlapped(hFile: int, lpBuffer: Array[c_char], lpOverlapped: CArgObject) -> bool:
    """Start a read; the caller must keep the buffer and OVERLAPPED alive until completion."""
    return bool(kernel32.ReadFile(hFile, lpBuffer, len(lpBuffer), None, lpOverlapped))


def GetOverlappedResult(hFile: int, lpOverlapped: CArgObject, bWait: bool) -> tuple[bool, int]:
    """Return (success, bytes_transferred), including partial reads on ERROR_MORE_DATA."""
    bytes_transferred = DWORD()
    success = bool(kernel32.GetOverlappedResult(hFile, lpOverlapped, byref(bytes_transferred), bWait))
    return success, bytes_transferred.value


def CancelIoEx(hFile: int, lpOverlapped: CArgObject | None = None) -> bool:
    return bool(kernel32.CancelIoEx(hFile, lpOverlapped))


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


class ProcessEntry(NamedTuple):
    pid: int
    parent_pid: int
    exe: str


def snapshot_processes() -> list[ProcessEntry]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, INVALID_HANDLE_VALUE):
        return []
    try:
        entry = PROCESSENTRY32(dwSize=sizeof(PROCESSENTRY32))
        found: list[ProcessEntry] = []
        more = kernel32.Process32FirstW(snapshot, byref(entry))
        while more:
            found.append(ProcessEntry(entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
            more = kernel32.Process32NextW(snapshot, byref(entry))
        return found
    finally:
        kernel32.CloseHandle(snapshot)


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


def GetTickCount64() -> int:
    return kernel32.GetTickCount64()


def GetModuleHandle(lpModuleName: str | None) -> int:
    return kernel32.GetModuleHandleW(lpModuleName)


def GetLastError() -> int:
    return get_last_error()


def LoadLibraryW(lpLibFileName: str) -> int:
    return int(kernel32.LoadLibraryW(lpLibFileName))


def FreeLibrary(hLibModule: int) -> bool:
    return bool(kernel32.FreeLibrary(hLibModule))


def LoadLibraryEx(lpLibFileName: str, dwFlags: int) -> int:
    return int(kernel32.LoadLibraryExW(lpLibFileName, None, dwFlags) or 0)


def MAKEINTRESOURCE(name: int | str) -> LPCWSTR | str:
    """A resource name or type for the resource functions: an ID number goes as a pointer value."""
    return cast(c_void_p(name), LPCWSTR) if isinstance(name, int) else name


def EnumResourceNames(hModule: int, resource_type: int) -> list[int | str]:
    """The names of a module's resources of one type, in Windows' order: ID numbers or strings."""
    names: list[int | str] = []

    def collect(_module: int, _type: int, name: int | None, _param: int) -> bool:
        # IDs are <= 0xFFFF and ctypes passes ID 0 as None, anything else is a string pointer
        name = name or 0
        names.append(name if name <= 0xFFFF else wstring_at(name))
        return True

    kernel32.EnumResourceNamesW(hModule, resource_type, ENUMRESNAMEPROCW(collect), None)
    return names


def LoadResourceData(hModule: int, name: int | str, resource_type: int) -> bytes | None:
    """The bytes of one of a module's resources, or None."""
    resource = kernel32.FindResourceW(hModule, MAKEINTRESOURCE(name), MAKEINTRESOURCE(resource_type))
    if not resource:
        return None
    data = kernel32.LockResource(kernel32.LoadResource(hModule, resource))
    return string_at(data, kernel32.SizeofResource(hModule, resource)) if data else None


def IsWow64Process2(hProcess: int, lpProcessMachine: CArgObject, lpNativeMachine: CArgObject | None) -> bool:
    return bool(kernel32.IsWow64Process2(hProcess, lpProcessMachine, lpNativeMachine))


def GetCurrentProcess() -> int:
    return int(kernel32.GetCurrentProcess())


def GetSystemWindowsDirectoryW(lpBuffer: Array[c_wchar], uSize: int) -> int:
    return kernel32.GetSystemWindowsDirectoryW(lpBuffer, uSize)


def LocalFree(hMem: object) -> None:
    kernel32.LocalFree(hMem)


def WaitForMultipleObjects(nCount: int, lpHandles: Array[HANDLE], bWaitAll: bool, dwMilliseconds: int) -> int:
    return kernel32.WaitForMultipleObjects(nCount, lpHandles, bWaitAll, dwMilliseconds)


def _query_process_string(query: Callable[..., int], hProcess: int) -> str | None:
    length = UINT(0)
    if query(hProcess, byref(length), None) != ERROR_INSUFFICIENT_BUFFER or not length.value:
        return None
    buf = create_unicode_buffer(length.value)
    if query(hProcess, byref(length), buf) != 0:
        return None
    return buf.value or None


def GetPackageFullName(hProcess: int) -> str | None:
    return _query_process_string(kernel32.GetPackageFullName, hProcess)


def GetApplicationUserModelId(hProcess: int) -> str | None:
    return _query_process_string(kernel32.GetApplicationUserModelId, hProcess)


def GetLogicalDrives() -> int:
    return kernel32.GetLogicalDrives()


def GetDriveType(lpRootPathName: str) -> int:
    return kernel32.GetDriveTypeW(lpRootPathName)


def GetDiskFreeSpaceEx(lpDirectoryName: str) -> tuple[int, int, int] | None:
    """(free bytes for the caller, total bytes, free bytes), or None."""
    free_to_caller, total, free = c_ulonglong(), c_ulonglong(), c_ulonglong()
    if not kernel32.GetDiskFreeSpaceExW(lpDirectoryName, byref(free_to_caller), byref(total), byref(free)):
        return None
    return free_to_caller.value, total.value, free.value


def get_volume_label(root_path: str) -> str | None:
    label = create_unicode_buffer(261)
    if not kernel32.GetVolumeInformationW(root_path, label, len(label), None, None, None, None, 0):
        return None
    return label.value


def FindFirstFileEx(
    lpFileName: str, fInfoLevelId: int, lpFindFileData: CArgObject, fSearchOp: int, dwAdditionalFlags: int
) -> int | None:
    handle = kernel32.FindFirstFileExW(lpFileName, fInfoLevelId, lpFindFileData, fSearchOp, None, dwAdditionalFlags)
    return None if handle in (None, INVALID_HANDLE_VALUE) else handle


def FindNextFile(hFindFile: int, lpFindFileData: CArgObject) -> bool:
    return bool(kernel32.FindNextFileW(hFindFile, lpFindFileData))


def FindClose(hFindFile: int) -> bool:
    return bool(kernel32.FindClose(hFindFile))


def GetUserGeoID(GeoClass: int) -> int:
    return kernel32.GetUserGeoID(GeoClass)


def GetGeoInfo(Location: int, GeoType: int, lpGeoData: Array[c_wchar], LangId: int = 0) -> int:
    return kernel32.GetGeoInfoW(Location, GeoType, lpGeoData, len(lpGeoData), LangId)


def GlobalAlloc(uFlags: int, dwBytes: int) -> int | None:
    return kernel32.GlobalAlloc(uFlags, dwBytes)


def GlobalLock(hMem: int) -> int | None:
    return kernel32.GlobalLock(hMem)


def GlobalUnlock(hMem: int) -> bool:
    return bool(kernel32.GlobalUnlock(hMem))


def GlobalFree(hMem: int) -> int | None:
    return kernel32.GlobalFree(hMem)

"""Wrappers for psapi (Process Status API) win32 API functions"""

from ctypes import POINTER, Array, c_void_p, c_wchar, c_wchar_p, windll
from ctypes.wintypes import BOOL, DWORD, HANDLE, HMODULE

from core.utils.win32.structs import PROCESS_MEMORY_COUNTERS
from core.utils.win32.typecheck import CArgObject

psapi = windll.psapi

# Function signatures
psapi.GetPerformanceInfo.argtypes = [c_void_p, DWORD]
psapi.GetPerformanceInfo.restype = BOOL

psapi.GetProcessMemoryInfo.argtypes = [HANDLE, POINTER(PROCESS_MEMORY_COUNTERS), DWORD]
psapi.GetProcessMemoryInfo.restype = BOOL


psapi.EnumProcessModulesEx.argtypes = [
    HANDLE,
    POINTER(HANDLE),
    DWORD,
    POINTER(DWORD),
    DWORD,
]
psapi.EnumProcessModulesEx.restype = BOOL

psapi.GetModuleBaseNameW.argtypes = [
    HANDLE,
    HANDLE,
    c_wchar_p,
    DWORD,
]
psapi.GetModuleBaseNameW.restype = DWORD


def EnumProcessModulesEx(
    hProcess: int,
    lphModule: Array[HMODULE],
    cb: int,
    lpcbNeeded: CArgObject,
    dwFilterFlag: int,
) -> bool:
    return psapi.EnumProcessModulesEx(hProcess, lphModule, cb, lpcbNeeded, dwFilterFlag)


def GetModuleBaseNameW(
    hProcess: int,
    hModule: int,
    lpBaseName: Array[c_wchar],
    nSize: int,
) -> DWORD:
    return psapi.GetModuleBaseNameW(hProcess, hModule, lpBaseName, nSize)

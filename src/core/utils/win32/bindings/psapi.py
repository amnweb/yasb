"""Wrappers for psapi (Process Status API) win32 API functions"""

from ctypes import POINTER, c_void_p, windll
from ctypes.wintypes import BOOL, DWORD, HANDLE

from core.utils.win32.structs import PROCESS_MEMORY_COUNTERS

psapi = windll.psapi

# Function signatures
psapi.GetPerformanceInfo.argtypes = [c_void_p, DWORD]
psapi.GetPerformanceInfo.restype = BOOL

psapi.GetProcessMemoryInfo.argtypes = [HANDLE, POINTER(PROCESS_MEMORY_COUNTERS), DWORD]
psapi.GetProcessMemoryInfo.restype = BOOL

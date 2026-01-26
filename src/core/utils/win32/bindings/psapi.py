"""Wrappers for psapi (Process Status API) win32 API functions"""

from ctypes import c_void_p, windll
from ctypes.wintypes import BOOL, DWORD

psapi = windll.psapi

# Function signatures
psapi.GetPerformanceInfo.argtypes = [c_void_p, DWORD]
psapi.GetPerformanceInfo.restype = BOOL

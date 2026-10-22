"""Bindings for PDH (Performance Data Helper) API."""

from ctypes import POINTER, WinDLL, c_void_p
from ctypes.wintypes import DWORD, HANDLE, LONG, LPCWSTR

pdh = WinDLL("pdh", use_last_error=True)

pdh.PdhOpenQueryW.argtypes = [LPCWSTR, c_void_p, POINTER(HANDLE)]
pdh.PdhOpenQueryW.restype = LONG

pdh.PdhAddEnglishCounterW.argtypes = [HANDLE, LPCWSTR, c_void_p, POINTER(HANDLE)]
pdh.PdhAddEnglishCounterW.restype = LONG

pdh.PdhCollectQueryData.argtypes = [HANDLE]
pdh.PdhCollectQueryData.restype = LONG

pdh.PdhGetFormattedCounterValue.argtypes = [HANDLE, DWORD, POINTER(DWORD), c_void_p]
pdh.PdhGetFormattedCounterValue.restype = LONG

pdh.PdhGetFormattedCounterArrayW.argtypes = [HANDLE, DWORD, POINTER(DWORD), POINTER(DWORD), c_void_p]
pdh.PdhGetFormattedCounterArrayW.restype = LONG

pdh.PdhCloseQuery.argtypes = [HANDLE]
pdh.PdhCloseQuery.restype = LONG

"""Bindings for PDH (Performance Data Helper) API."""

from ctypes import POINTER, c_void_p, windll
from ctypes.wintypes import DWORD, HANDLE, LONG, LPCWSTR

pdh = windll.pdh

pdh.PdhOpenQueryW.argtypes = [LPCWSTR, c_void_p, POINTER(HANDLE)]
pdh.PdhOpenQueryW.restype = LONG

pdh.PdhAddEnglishCounterW.argtypes = [HANDLE, LPCWSTR, c_void_p, POINTER(HANDLE)]
pdh.PdhAddEnglishCounterW.restype = LONG

pdh.PdhCollectQueryData.argtypes = [HANDLE]
pdh.PdhCollectQueryData.restype = LONG

pdh.PdhGetFormattedCounterValue.argtypes = [HANDLE, DWORD, POINTER(DWORD), c_void_p]
pdh.PdhGetFormattedCounterValue.restype = LONG

pdh.PdhCloseQuery.argtypes = [HANDLE]
pdh.PdhCloseQuery.restype = LONG

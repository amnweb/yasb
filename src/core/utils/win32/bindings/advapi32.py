"""Wrappers for advapi32 win32 API functions"""

from ctypes import WinDLL
from ctypes.wintypes import BOOL, DWORD, HANDLE, HKEY, LONG

advapi32 = WinDLL("advapi32", use_last_error=True)

advapi32.RegNotifyChangeKeyValue.argtypes = [HKEY, BOOL, DWORD, HANDLE, BOOL]
advapi32.RegNotifyChangeKeyValue.restype = LONG


def RegNotifyChangeKeyValue(
    hKey: int, bWatchSubtree: bool, dwNotifyFilter: int, hEvent: int | None, fAsynchronous: bool
) -> int:
    return advapi32.RegNotifyChangeKeyValue(hKey, bWatchSubtree, dwNotifyFilter, hEvent, fAsynchronous)

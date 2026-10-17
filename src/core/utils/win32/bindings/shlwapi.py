"""Wrappers for shlwapi win32 API functions"""

from ctypes import WinDLL, c_int, c_long, create_unicode_buffer
from ctypes.wintypes import LPCWSTR, LPVOID, LPWSTR, UINT

shlwapi = WinDLL("shlwapi", use_last_error=True)

shlwapi.SHLoadIndirectString.argtypes = [LPCWSTR, LPWSTR, UINT, LPVOID]
shlwapi.SHLoadIndirectString.restype = c_long

shlwapi.StrCmpLogicalW.argtypes = [LPCWSTR, LPCWSTR]
shlwapi.StrCmpLogicalW.restype = c_int


def SHLoadIndirectString(source: str, max_chars: int = 1024) -> str | None:
    buf = create_unicode_buffer(max_chars)
    if shlwapi.SHLoadIndirectString(source, buf, max_chars, None) != 0:
        return None
    return buf.value


def StrCmpLogical(psz1: str, psz2: str) -> int:
    return shlwapi.StrCmpLogicalW(psz1, psz2)

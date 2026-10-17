"""Wrappers for version.dll (file version information) win32 API functions"""

from ctypes import POINTER, Array, WinDLL, byref, c_char, c_void_p, create_string_buffer
from ctypes.wintypes import BOOL, DWORD, LPCVOID, LPCWSTR, LPDWORD, LPVOID, UINT

version = WinDLL("version", use_last_error=True)

version.GetFileVersionInfoSizeW.argtypes = [LPCWSTR, LPDWORD]
version.GetFileVersionInfoSizeW.restype = DWORD

version.GetFileVersionInfoW.argtypes = [LPCWSTR, DWORD, DWORD, LPVOID]
version.GetFileVersionInfoW.restype = BOOL

version.VerQueryValueW.argtypes = [LPCVOID, LPCWSTR, POINTER(LPVOID), POINTER(UINT)]
version.VerQueryValueW.restype = BOOL


def GetFileVersionInfo(filename: str) -> Array[c_char] | None:
    size = version.GetFileVersionInfoSizeW(filename, None)
    if not size:
        return None
    block = create_string_buffer(size)
    if not version.GetFileVersionInfoW(filename, 0, size, block):
        return None
    return block


def VerQueryValue(block: Array[c_char], sub_block: str) -> tuple[int, int] | None:
    """(address, length) of the value; the address points into block, so keep block alive while using it."""
    address = c_void_p()
    length = UINT()
    if not version.VerQueryValueW(block, sub_block, byref(address), byref(length)):
        return None
    if not address.value or not length.value:
        return None
    return address.value, length.value

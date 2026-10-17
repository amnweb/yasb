"""Wrappers for secur32 win32 API functions"""

from ctypes import POINTER, WinDLL, byref, create_unicode_buffer
from ctypes.wintypes import BOOLEAN, INT, LPWSTR, ULONG

secur32 = WinDLL("secur32", use_last_error=True)

secur32.GetUserNameExW.argtypes = [INT, LPWSTR, POINTER(ULONG)]
secur32.GetUserNameExW.restype = BOOLEAN


def GetUserNameEx(name_format: int) -> str | None:
    size = ULONG()
    secur32.GetUserNameExW(name_format, None, byref(size))
    if not size.value:
        return None
    buffer = create_unicode_buffer(size.value)
    return buffer.value if secur32.GetUserNameExW(name_format, buffer, byref(size)) else None

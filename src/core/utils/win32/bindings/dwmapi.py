"""Wrappers for dwmapi Win32 API with typed signatures."""

from ctypes import windll
from ctypes.wintypes import DWORD, HWND, LPVOID

# Load dwmapi once
_dwmapi = windll.dwmapi

# Signatures
_dwmapi.DwmGetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
_dwmapi.DwmGetWindowAttribute.restype = DWORD  # HRESULT

_dwmapi.DwmSetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
_dwmapi.DwmSetWindowAttribute.restype = DWORD  # HRESULT


def DwmGetWindowAttribute(hwnd: int, attribute: int, out_ptr: LPVOID, size: int) -> int:
    return _dwmapi.DwmGetWindowAttribute(hwnd, attribute, out_ptr, size)


def DwmSetWindowAttribute(hwnd: int, attribute: int, in_ptr: LPVOID, size: int) -> int:
    return _dwmapi.DwmSetWindowAttribute(hwnd, attribute, in_ptr, size)

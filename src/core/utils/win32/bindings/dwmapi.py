"""Wrappers for dwmapi Win32 API with typed signatures."""

import ctypes
from ctypes import POINTER, windll
from ctypes.wintypes import DWORD, HANDLE, HWND, LPVOID

from core.utils.win32.structs import DWM_THUMBNAIL_PROPERTIES, SIZE

# Load dwmapi
_dwmapi = windll.dwmapi

# Window attribute signatures
_dwmapi.DwmGetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
_dwmapi.DwmGetWindowAttribute.restype = DWORD  # HRESULT

_dwmapi.DwmSetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
_dwmapi.DwmSetWindowAttribute.restype = DWORD  # HRESULT

# Thumbnail signatures
_dwmapi.DwmRegisterThumbnail.argtypes = [HWND, HWND, POINTER(HANDLE)]
_dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long

_dwmapi.DwmUnregisterThumbnail.argtypes = [HANDLE]
_dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long

_dwmapi.DwmUpdateThumbnailProperties.argtypes = [HANDLE, POINTER(DWM_THUMBNAIL_PROPERTIES)]
_dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long

_dwmapi.DwmQueryThumbnailSourceSize.argtypes = [HANDLE, POINTER(SIZE)]
_dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.c_long


def DwmGetWindowAttribute(hwnd: int, attribute: int, out_ptr: LPVOID, size: int) -> int:
    """Get the value of a specified attribute for a given window."""
    return _dwmapi.DwmGetWindowAttribute(hwnd, attribute, out_ptr, size)


def DwmSetWindowAttribute(hwnd: int, attribute: int, in_ptr: LPVOID, size: int) -> int:
    """Set the value of a specified attribute for a given window."""
    return _dwmapi.DwmSetWindowAttribute(hwnd, attribute, in_ptr, size)


def DwmRegisterThumbnail(hwnd_destination: int, hwnd_source: int, thumbnail_handle_ptr) -> int:
    """Register a thumbnail relationship between two windows."""
    return _dwmapi.DwmRegisterThumbnail(hwnd_destination, hwnd_source, thumbnail_handle_ptr)


def DwmUnregisterThumbnail(thumbnail_handle: HANDLE) -> int:
    """Unregister a thumbnail relationship."""
    return _dwmapi.DwmUnregisterThumbnail(thumbnail_handle)


def DwmUpdateThumbnailProperties(thumbnail_handle: HANDLE, properties_ptr) -> int:
    """Update thumbnail properties such as size, opacity, and visibility."""
    return _dwmapi.DwmUpdateThumbnailProperties(thumbnail_handle, properties_ptr)


def DwmQueryThumbnailSourceSize(thumbnail_handle: HANDLE, size_ptr) -> int:
    """Query the source size of a thumbnail."""
    return _dwmapi.DwmQueryThumbnailSourceSize(thumbnail_handle, size_ptr)

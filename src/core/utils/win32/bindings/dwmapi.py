"""Wrappers for dwmapi Win32 API with typed signatures."""

import ctypes
from ctypes import POINTER, WinDLL
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND, LPVOID, UINT

from core.utils.win32.structs import DWM_THUMBNAIL_PROPERTIES, MARGINS, RECT, SIZE
from core.utils.win32.typecheck import CArgObject

dwmapi = WinDLL("dwmapi", use_last_error=True)

# DwmExtendFrameIntoClientArea
dwmapi.DwmExtendFrameIntoClientArea.argtypes = [HWND, POINTER(MARGINS)]
dwmapi.DwmExtendFrameIntoClientArea.restype = ctypes.c_long

# Window attribute signatures
dwmapi.DwmGetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

dwmapi.DwmSetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

# Thumbnail signatures
dwmapi.DwmRegisterThumbnail.argtypes = [HWND, HWND, POINTER(HANDLE)]
dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long

dwmapi.DwmUnregisterThumbnail.argtypes = [HANDLE]
dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long

dwmapi.DwmUpdateThumbnailProperties.argtypes = [HANDLE, POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long

dwmapi.DwmQueryThumbnailSourceSize.argtypes = [HANDLE, POINTER(SIZE)]
dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.c_long

# DwmpActivateLivePreview: undocumented, exported by ordinal only, and absent from some builds
_activate_live_preview = None
try:
    _activate_live_preview = dwmapi[113]  # pyright: ignore[reportArgumentType]
    _activate_live_preview.argtypes = [BOOL, HWND, HWND, UINT, POINTER(RECT)]
    _activate_live_preview.restype = ctypes.c_long
except AttributeError:
    pass


def live_preview_exported() -> bool:
    return _activate_live_preview is not None


def DwmpActivateLivePreview(activate: bool, hwnd_peek: int, hwnd_caller: int, trigger: int) -> int:
    if _activate_live_preview is None:
        raise OSError("this Windows build does not export DwmpActivateLivePreview")
    return _activate_live_preview(activate, hwnd_peek, hwnd_caller, trigger, None)


def DwmGetWindowAttribute(hwnd: int, attribute: int, out_ptr: CArgObject, size: int) -> int:
    """Get the value of a specified attribute for a given window."""
    return dwmapi.DwmGetWindowAttribute(hwnd, attribute, out_ptr, size)


def DwmSetWindowAttribute(hwnd: int, attribute: int, in_ptr: CArgObject, size: int) -> int:
    """Set the value of a specified attribute for a given window."""
    return dwmapi.DwmSetWindowAttribute(hwnd, attribute, in_ptr, size)


def DwmExtendFrameIntoClientArea(hwnd: int, margins: MARGINS) -> int:
    """Extend the window frame into the client area."""
    return dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))


def DwmRegisterThumbnail(hwnd_destination: int, hwnd_source: int, thumbnail_handle_ptr: CArgObject) -> int:
    """Register a thumbnail relationship between two windows."""
    return dwmapi.DwmRegisterThumbnail(hwnd_destination, hwnd_source, thumbnail_handle_ptr)


def DwmUnregisterThumbnail(thumbnail_handle: HANDLE) -> int:
    """Unregister a thumbnail relationship."""
    return dwmapi.DwmUnregisterThumbnail(thumbnail_handle)


def DwmUpdateThumbnailProperties(thumbnail_handle: HANDLE, properties_ptr: CArgObject) -> int:
    """Update thumbnail properties such as size, opacity, and visibility."""
    return dwmapi.DwmUpdateThumbnailProperties(thumbnail_handle, properties_ptr)


def DwmQueryThumbnailSourceSize(thumbnail_handle: HANDLE, size_ptr: CArgObject) -> int:
    """Query the source size of a thumbnail."""
    return dwmapi.DwmQueryThumbnailSourceSize(thumbnail_handle, size_ptr)

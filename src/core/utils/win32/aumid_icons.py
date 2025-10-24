"""
Icon extraction utilities for App User Model IDs (AUMIDs).
Provides functions to extract icons from UWP apps based on their AUMID.
"""

import ctypes
import ctypes.wintypes as wt
from ctypes import POINTER, WINFUNCTYPE, byref, c_void_p

from PIL import Image

from core.utils.win32.aumid import GUID, _ensure_com_initialized
from core.utils.win32.bindings import (
    DeleteObject,
    GetDC,
    GetDIBits,
    GetObject,
    ReleaseDC,
)
from core.utils.win32.structs import BITMAP, BITMAPINFO, BITMAPINFOHEADER

# IShellItemImageFactory interface for icon extraction
IID_IShellItemImageFactory = GUID("BCC18B79-BA16-442F-80C4-8A59C30C463B")


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class IShellItemImageFactoryVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))),
        ("AddRef", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("Release", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("GetImage", WINFUNCTYPE(ctypes.c_long, c_void_p, SIZE, ctypes.c_int, POINTER(wt.HBITMAP))),
    ]


class IShellItemImageFactory(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(IShellItemImageFactoryVtbl))]


# Shell32 API
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

SHCreateItemFromParsingName = shell32.SHCreateItemFromParsingName
SHCreateItemFromParsingName.argtypes = [wt.LPCWSTR, c_void_p, POINTER(GUID), POINTER(c_void_p)]
SHCreateItemFromParsingName.restype = ctypes.c_long


# SIIGBF flags
# https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ishellitemimagefactory-getimage
SIIGBF_RESIZETOFIT = 0x00
SIIGBF_BIGGERSIZEOK = 0x01
SIIGBF_MEMORYONLY = 0x02
SIIGBF_ICONONLY = 0x04
SIIGBF_THUMBNAILONLY = 0x08
SIIGBF_INCACHEONLY = 0x10


def _hbitmap_to_image(hbitmap: int) -> Image.Image | None:
    """Convert a Windows HBITMAP to a PIL Image."""
    # Get bitmap info
    bmp = BITMAP()
    res = GetObject(wt.HBITMAP(hbitmap), ctypes.sizeof(BITMAP), ctypes.byref(bmp))
    if res == 0:
        return None

    width, height = bmp.bmWidth, bmp.bmHeight
    # Prepare BITMAPINFO
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -abs(height)
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32

    buf_size = width * height * 4
    pixel_buffer = (ctypes.c_byte * buf_size)()

    hdc = GetDC(None)
    try:
        n = GetDIBits(
            hdc,
            wt.HBITMAP(hbitmap),
            0,
            height,
            ctypes.byref(pixel_buffer),
            ctypes.byref(bi),
            0,
        )
        if n == 0:
            return None
        # Convert buffer to bytes and interpret as BGRA
        raw_bytes = ctypes.string_at(ctypes.addressof(pixel_buffer), buf_size)
        return Image.frombuffer("RGBA", (width, height), raw_bytes, "raw", "BGRA", 0, 1)
    finally:
        ReleaseDC(None, hdc)
        try:
            DeleteObject(wt.HBITMAP(hbitmap))
        except Exception:
            pass


def get_icon_for_aumid(aumid: str, size: int = 48) -> Image.Image | None:
    """
    Extract an icon for a UWP app by its AUMID.

    Args:
        aumid: The App User Model ID
        size: Desired icon size in pixels (default: 48)

    Returns:
        PIL Image object if successful, None otherwise
    """
    if not aumid:
        return None

    _ensure_com_initialized()
    path = f"shell:AppsFolder\\{aumid}"
    ppv = c_void_p()
    hr = SHCreateItemFromParsingName(path, None, byref(IID_IShellItemImageFactory), byref(ppv))
    if hr != 0 or not ppv.value:
        return None

    factory = ctypes.cast(ppv, POINTER(IShellItemImageFactory))
    hbmp = wt.HBITMAP()
    try:
        sz = SIZE(size, size)
        flags = SIIGBF_ICONONLY | SIIGBF_BIGGERSIZEOK
        hr = factory.contents.lpVtbl.contents.GetImage(factory, sz, flags, byref(hbmp))
        if hr != 0 or not hbmp.value:
            return None
        return _hbitmap_to_image(hbmp.value)
    finally:
        try:
            factory.contents.lpVtbl.contents.Release(factory)
        except Exception:
            pass

"""
Icon extraction utilities for App User Model IDs (AUMIDs).
Provides functions to extract icons from UWP apps based on their AUMID.
"""

import ctypes
import ctypes.wintypes as wt
import os
import winreg
from ctypes import POINTER, WINFUNCTYPE, byref, c_void_p
from pathlib import Path

from PIL import Image, ImageOps

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


# Where an app installed outside the Store registers the icon its notifications show with
APP_MODEL_KEY = r"Software\Classes\AppUserModelId"


def _registered_icon(aumid: str, size: int) -> Image.Image | None:
    """The icon an app registered for its AUMID, for senders the Apps folder does not know.

    Apps installed outside the Store are not in the Apps folder, so the shell cannot draw
    them an icon. Windows itself falls back to this registration, which is how a toast from
    a browser or a packaged-less app still shows a picture in the Notification Center.
    """
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, f"{APP_MODEL_KEY}\\{aumid}") as key:
                uri, _ = winreg.QueryValueEx(key, "IconUri")
        except OSError:
            continue
        # Package resources (ms-resource://) need the package that owns them to resolve
        if not uri or not isinstance(uri, str) or "://" in uri:
            continue
        # The value is written as REG_EXPAND_SZ, which winreg hands back unexpanded
        path = Path(os.path.expandvars(uri))
        try:
            if not path.is_file():
                continue
            with Image.open(path) as source:
                image = source.convert("RGBA")
            # What is registered here is often a tile asset with its own margin baked in,
            # so the drawing is cut out first. Otherwise it lands noticeably smaller than
            # the icons the shell hands out, which carry no margin
            drawing = image.getchannel("A").getbbox()
            if drawing is None:
                continue
            # Not always square once trimmed, so the shape is kept and centred rather than
            # stretched to fill the caller's box
            return ImageOps.pad(image.crop(drawing), (size, size), Image.LANCZOS, (0, 0, 0, 0))
        except OSError, ValueError:
            continue
    return None


def _apps_folder_icon(aumid: str, size: int) -> Image.Image | None:
    """The icon the shell draws for an app, which only works for apps it lists."""
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


def get_icon_for_aumid(aumid: str, size: int = 48) -> Image.Image | None:
    """
    Extract an icon for an app by its AUMID.

    Args:
        aumid: The App User Model ID
        size: Desired icon size in pixels (default: 48)

    Returns:
        PIL Image object if successful, None otherwise
    """
    if not aumid:
        return None

    return _apps_folder_icon(aumid, size) or _registered_icon(aumid, size)

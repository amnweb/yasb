import ctypes
import ctypes.wintypes as wt
import logging
import struct
from ctypes import POINTER, WINFUNCTYPE, byref, c_size_t, c_void_p
from typing import cast

import win32api
import win32con
import win32gui
from PIL import Image

from core.utils.icons.convert import hbitmap_to_image, hicon_to_image
from core.utils.win32.aumid import GUID, ensure_com_initialized
from core.utils.win32.bindings import (
    MAKEINTRESOURCE,
    DestroyIcon,
    EnumResourceNames,
    FreeLibrary,
    LoadImage,
    LoadLibraryEx,
    LoadResourceData,
    SendMessageTimeoutW,
    shell32,
)
from core.utils.win32.constants import (
    LOAD_LIBRARY_AS_DATAFILE,
    LOAD_LIBRARY_AS_IMAGE_RESOURCE,
    RT_GROUP_ICON,
    SHGSI_ICON,
    SHGSI_LARGEICON,
    SMTO_ABORTIFHUNG,
    SMTO_BLOCK,
)
from core.utils.win32.structs import SHSTOCKICONINFO, SIZE

IID_IShellItemImageFactory = GUID("BCC18B79-BA16-442F-80C4-8A59C30C463B")

# https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ishellitemimagefactory-getimage
SIIGBF_BIGGERSIZEOK = 0x01
SIIGBF_ICONONLY = 0x04

WM_GETICON_TIMEOUT_MS = 200


class IShellItemImageFactoryVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))),
        ("AddRef", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("Release", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("GetImage", WINFUNCTYPE(ctypes.c_long, c_void_p, SIZE, ctypes.c_int, POINTER(wt.HBITMAP))),
    ]


class IShellItemImageFactory(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(IShellItemImageFactoryVtbl))]


_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
SHCreateItemFromParsingName = _shell32.SHCreateItemFromParsingName
SHCreateItemFromParsingName.argtypes = [wt.LPCWSTR, c_void_p, POINTER(GUID), POINTER(c_void_p)]
SHCreateItemFromParsingName.restype = ctypes.c_long


def get_stock_icon(icon_id: int) -> Image.Image | None:
    """Large stock icon by SHSTOCKICONID, e.g. 31/32 for the empty/full Recycle Bin."""
    sii = SHSTOCKICONINFO()
    sii.cbSize = ctypes.sizeof(sii)
    if shell32.SHGetStockIconInfo(icon_id, SHGSI_ICON | SHGSI_LARGEICON, byref(sii)) != 0:
        return None
    return _icon_image(sii.hIcon)


def get_default_app_icon() -> Image.Image | None:
    """The generic app icon (IDI_APPLICATION)."""
    try:
        size = win32api.GetSystemMetrics(win32con.SM_CXICON)
        default_hicon = cast(
            int,
            win32gui.LoadImage(
                0,
                win32con.IDI_APPLICATION,  # pyright: ignore[reportArgumentType]
                win32con.IMAGE_ICON,
                size,
                size,
                win32con.LR_SHARED,
            ),
        )
    except Exception as e:
        logging.debug("Failed to get default icon: %s", e)
        return None
    return hicon_to_image(default_hicon) if default_hicon else None


def get_resource_icon(path: str, index: int, size: int) -> Image.Image | None:
    """Icon number index of an exe, dll or cpl, picked for size px; the caller scales it.

    Picked like LoadIconWithScaleDown: exact size, else the next bigger, else the biggest. A negative index is a
    resource ID.
    """
    module = LoadLibraryEx(path, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)
    if not module:
        return None
    try:
        names = EnumResourceNames(module, RT_GROUP_ICON)
        if index < 0:
            name: int | str = -index
        elif index < len(names):
            name = names[index]
        else:
            return None
        group = LoadResourceData(module, name, RT_GROUP_ICON)
        sizes = _stored_sizes(group, 14) if group else []
        if not sizes:
            return None
        chosen = next((s for s in sizes if s >= size), sizes[-1])
        # own copy, shared icons are cached by module handle and the next file can get the same handle
        hicon = LoadImage(module, MAKEINTRESOURCE(name), win32con.IMAGE_ICON, chosen, chosen, 0)
    finally:
        FreeLibrary(module)
    return _icon_image(hicon)


def get_ico_icon(path: str, size: int) -> Image.Image | None:
    """An .ico file's picture for size px, picked like get_resource_icon."""
    try:
        with open(path, "rb") as file:
            sizes = _stored_sizes(file.read(), 16)
    except OSError, IndexError, struct.error:
        return None
    if not sizes:
        return None
    chosen = next((s for s in sizes if s >= size), sizes[-1])
    return _icon_image(LoadImage(0, path, win32con.IMAGE_ICON, chosen, chosen, win32con.LR_LOADFROMFILE))


def _icon_image(hicon: int) -> Image.Image | None:
    if not hicon:
        return None
    try:
        return hicon_to_image(hicon)
    finally:
        DestroyIcon(hicon)


def _stored_sizes(directory: bytes, entry_size: int) -> list[int]:
    # GRPICONDIR (14-byte entries) or ICONDIR (16-byte): count at offset 4, entries from 6, width first (0 = 256)
    count = struct.unpack_from("<H", directory, 4)[0]
    return sorted({directory[6 + entry_size * i] or 256 for i in range(count)})


def get_shell_icon(parsing_name: str, size: int) -> Image.Image | None:
    """The icon Explorer shows for a file, folder or app (shell:AppsFolder\\<AUMID>), drawn at size px.

    Above 48 px, exe/ico icons without a 256 px picture come back small inside a frame.
    """
    ensure_com_initialized()
    ppv = c_void_p()
    hr = SHCreateItemFromParsingName(parsing_name, None, byref(IID_IShellItemImageFactory), byref(ppv))
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
        return hbitmap_to_image(hbmp.value)
    finally:
        try:
            factory.contents.lpVtbl.contents.Release(factory)
        except Exception:
            pass


def get_own_icon(hwnd: int) -> tuple[Image.Image | None, bool]:
    """The window's own icon (WM_GETICON big, else small) and whether it answered in time."""
    # big icon first, Illustrator's small one is a document icon
    for which in (win32con.ICON_BIG, win32con.ICON_SMALL):
        hicon = c_size_t(0)
        # without SMTO_BLOCK every message we get while waiting restarts the timeout
        if not SendMessageTimeoutW(
            hwnd,
            win32con.WM_GETICON,
            which,
            0,
            SMTO_ABORTIFHUNG | SMTO_BLOCK,
            WM_GETICON_TIMEOUT_MS,
            byref(hicon),
        ):
            return None, False
        # owned by the window, don't destroy
        img = hicon_to_image(hicon.value)
        if img is not None and img.getchannel("A").getbbox() is not None:
            return img, True
    return None, True


def get_class_icons(hwnd: int) -> list[Image.Image]:
    """The window class's small and big icons."""
    images: list[Image.Image] = []
    for index in (win32con.GCL_HICONSM, win32con.GCL_HICON):
        try:
            hicon = cast(int, win32gui.GetClassLong(hwnd, index)) or 0  # pyright: ignore[reportUnknownMemberType]
        except Exception:
            continue
        img = hicon_to_image(hicon)
        if img is not None:
            images.append(img)
    return images

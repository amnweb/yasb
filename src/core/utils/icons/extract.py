import ctypes
import logging
import struct
from ctypes import byref, c_size_t

import win32api
from comtypes import COMError  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image

from core.utils.icons.convert import hbitmap_to_image, hicon_to_image
from core.utils.win32.bindings.kernel32 import (
    MAKEINTRESOURCE,
    EnumResourceNames,
    FreeLibrary,
    LoadLibraryEx,
    LoadResourceData,
)
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import SHCreateItemFromParsingName, shell32
from core.utils.win32.bindings.user32 import DestroyIcon, GetClassLongPtr, LoadImage, SendMessageTimeoutW
from core.utils.win32.constants import (
    GCLP_HICON,
    GCLP_HICONSM,
    ICON_BIG,
    ICON_SMALL,
    IDI_APPLICATION,
    IMAGE_ICON,
    LOAD_LIBRARY_AS_DATAFILE,
    LOAD_LIBRARY_AS_IMAGE_RESOURCE,
    LR_LOADFROMFILE,
    LR_SHARED,
    RT_GROUP_ICON,
    SHGSI_ICON,
    SHGSI_LARGEICON,
    SIIGBF_BIGGERSIZEOK,
    SIIGBF_ICONONLY,
    SM_CXICON,
    SMTO_ABORTIFHUNG,
    SMTO_BLOCK,
    WM_GETICON,
)
from core.utils.win32.structs import SHSTOCKICONINFO, SIZE

WM_GETICON_TIMEOUT_MS = 200


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
        size = win32api.GetSystemMetrics(SM_CXICON)
        default_hicon = LoadImage(0, MAKEINTRESOURCE(IDI_APPLICATION), IMAGE_ICON, size, size, LR_SHARED)
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
        hicon = LoadImage(module, MAKEINTRESOURCE(name), IMAGE_ICON, chosen, chosen, 0)
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
    return _icon_image(LoadImage(0, path, IMAGE_ICON, chosen, chosen, LR_LOADFROMFILE))


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
    CoInitialize()
    factory = SHCreateItemFromParsingName(parsing_name)
    if factory is None:
        return None
    try:
        hbmp = factory.GetImage(SIZE(size, size), SIIGBF_ICONONLY | SIIGBF_BIGGERSIZEOK)
    except COMError:
        return None
    return hbitmap_to_image(hbmp) if hbmp else None


def get_own_icon(hwnd: int) -> tuple[Image.Image | None, bool]:
    """The window's own icon (WM_GETICON big, else small) and whether it answered in time."""
    # big icon first, Illustrator's small one is a document icon
    for which in (ICON_BIG, ICON_SMALL):
        hicon = c_size_t(0)
        # without SMTO_BLOCK every message we get while waiting restarts the timeout
        if not SendMessageTimeoutW(
            hwnd,
            WM_GETICON,
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
    for index in (GCLP_HICONSM, GCLP_HICON):
        img = hicon_to_image(GetClassLongPtr(hwnd, index))
        if img is not None:
            images.append(img)
    return images

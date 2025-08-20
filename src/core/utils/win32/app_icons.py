import logging
import struct
from ctypes import byref, create_string_buffer, sizeof

import win32api
import win32con
import win32gui
import win32ui
from PIL import Image
from win32con import DIB_RGB_COLORS

from core.utils.win32.app_aumid import get_aumid_for_window, get_icon_for_aumid
from core.utils.win32.bindings import DeleteObject, GetDC, GetDIBits, GetIconInfo, GetObject, ReleaseDC
from core.utils.win32.structs import BITMAP, BITMAPINFO, BITMAPINFOHEADER, ICONINFO

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


def get_window_icon(hwnd: int):
    """Get the icon for a window handle (HWND).

    - WM_GETICON: ICON_BIG, ICON_SMALL, ICON_SMALL2
    - App User Model ID icon (UWP) via AUMID
    - Class icons: GCLP_HICONSM, GCLP_HICON
    - OS default application icon (IDI_APPLICATION)
    """
    try:

        def _image_from_hicon(hicon: int) -> Image.Image | None:
            if not hicon:
                return None
            img = hicon_to_image(hicon)
            if img is not None:
                return img

            # Fallback draw the icon into a compatible bitmap
            hdc_handle = win32gui.GetDC(0)
            if not hdc_handle:
                return None
            memdc = None
            hdc = None
            hbmp = None
            try:
                hdc = win32ui.CreateDCFromHandle(hdc_handle)
                hbmp = win32ui.CreateBitmap()
                system_icon_size = win32api.GetSystemMetrics(win32con.SM_CXICON)
                bitmap_size = int(system_icon_size)
                hbmp.CreateCompatibleBitmap(hdc, bitmap_size, bitmap_size)
                memdc = hdc.CreateCompatibleDC()
                memdc.SelectObject(hbmp)
                try:
                    memdc.DrawIcon((0, 0), hicon)
                except Exception:
                    return None

                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                raw_data = bytes(bmpstr)
                return Image.frombuffer(
                    "RGBA",
                    (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                    raw_data,
                    "raw",
                    "BGRA",
                    0,
                    1,
                ).convert("RGBA")
            finally:
                try:
                    if memdc is not None:
                        memdc.DeleteDC()
                except Exception:
                    pass
                try:
                    if hdc is not None:
                        hdc.DeleteDC()
                except Exception:
                    pass
                try:
                    if hbmp is not None:
                        win32gui.DeleteObject(hbmp.GetHandle())
                except Exception:
                    pass
                try:
                    win32gui.ReleaseDC(0, hdc_handle)
                except Exception:
                    pass

        def _is_fully_transparent(img: Image.Image) -> bool:
            try:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                alpha = img.getchannel("A")
                return alpha.getbbox() is None
            except Exception:
                return False

        # Ask the window for its icons
        for which in (win32con.ICON_BIG, win32con.ICON_SMALL, getattr(win32con, "ICON_SMALL2", 2)):
            try:
                hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, which, 0)
            except Exception:
                hicon = 0
            if hicon:
                img = _image_from_hicon(hicon)
                # WM_GETICON returns an icon handle we should destroy
                try:
                    win32gui.DestroyIcon(hicon)
                except Exception:
                    pass
                if img is not None and not _is_fully_transparent(img):
                    return img

        # AppUserModelID icon for UWP apps
        aumid = get_aumid_for_window(hwnd)
        if aumid:
            img = get_icon_for_aumid(aumid)
            if img is not None:
                return img

        # Fall back to class icons
        class_hicon = 0
        try:
            if hasattr(win32gui, "GetClassLongPtr"):
                # Try small icon first, then big
                class_hicon = win32gui.GetClassLongPtr(hwnd, getattr(win32con, "GCLP_HICONSM", 0)) or 0
                if not class_hicon:
                    class_hicon = win32gui.GetClassLongPtr(hwnd, win32con.GCLP_HICON) or 0
            else:
                class_hicon = win32gui.GetClassLong(hwnd, getattr(win32con, "GCL_HICONSM", -34)) or 0
                if not class_hicon:
                    class_hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON) or 0
        except Exception:
            class_hicon = 0

        if class_hicon:
            img = _image_from_hicon(class_hicon)
            if img is not None:
                return img

        # OS default application icon
        try:
            size = win32api.GetSystemMetrics(win32con.SM_CXICON)
            default_hicon = win32gui.LoadImage(
                0,
                win32con.IDI_APPLICATION,
                win32con.IMAGE_ICON,
                size,
                size,
                win32con.LR_SHARED,
            )
        except Exception:
            default_hicon = 0

        if default_hicon:
            return _image_from_hicon(default_hicon)

        return None
    except Exception as e:
        logging.error(f"Error fetching icon: {e}")
        return None


def hicon_to_image(hicon: int) -> Image.Image | None:
    """Converts an icon handle to an image"""
    # Get icon info
    icon_info = ICONINFO()
    if not GetIconInfo(hicon, byref(icon_info)):
        logging.error("GetIconInfo failed: %s", hicon)
        return None

    # Get bitmap info
    bitmap = BITMAP()
    result = GetObject(icon_info.hbmColor, sizeof(BITMAP), byref(bitmap))

    if result == 0:
        DeleteObject(icon_info.hbmMask)
        DeleteObject(icon_info.hbmColor)
        logging.error("GetObjectW failed")
        return None

    width, height = bitmap.bmWidth, bitmap.bmHeight
    buffer_size = width * height * 4

    # Create buffers for the bitmap data
    color_buffer = create_string_buffer(buffer_size)
    mask_buffer = create_string_buffer(buffer_size)

    # Get DC
    hdc = GetDC(None)
    if hdc == 0:
        DeleteObject(icon_info.hbmMask)
        DeleteObject(icon_info.hbmColor)
        logging.error("GetDC failed")
        return None

    # Create bitmap info
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -abs(height)
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32

    # Get color bitmap data
    color_result = GetDIBits(
        hdc,
        icon_info.hbmColor,
        0,
        height,
        byref(color_buffer),
        byref(bi),
        DIB_RGB_COLORS,
    )

    # Get mask bitmap data
    mask_result = GetDIBits(
        hdc,
        icon_info.hbmMask,
        0,
        height,
        byref(mask_buffer),
        byref(bi),
        DIB_RGB_COLORS,
    )

    # Release DC and delete objects
    ReleaseDC(None, hdc)
    DeleteObject(icon_info.hbmColor)
    DeleteObject(icon_info.hbmMask)

    if color_result == 0 or mask_result == 0:
        logging.error("GetDIBits failed")
        return None

    # Convert buffer to bytes
    color_bytes = color_buffer.raw
    mask_bytes = mask_buffer.raw

    # Check if icon is mask-based
    is_mask_based = all(b == 0 for _, _, _, b in struct.iter_unpack("BBBB", color_bytes))

    # Process pixel data
    img_data = bytearray(buffer_size)
    color_view = memoryview(color_bytes)
    mask_view = memoryview(mask_bytes)

    for i in range(0, buffer_size, 4):
        # Get mask alpha
        mask_alpha = mask_view[i]

        # Unpack pixel (BGR + A)
        b, g, r, a = color_view[i : i + 4]

        # Adjust alpha if mask-based
        if is_mask_based:
            a = 0 if mask_alpha == 255 else 255

        # Store as RGBA (BGR to RGB)
        img_data[i : i + 4] = bytes((r, g, b, a))

    # Create PIL Image
    return Image.frombuffer("RGBA", (width, height), bytes(img_data), "raw", "RGBA", 0, 1)

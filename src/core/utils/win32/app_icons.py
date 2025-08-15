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
    """Fetch the icon of the window."""
    try:
        hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
        if hicon == 0:
            # If big icon is not available, try to get the small icon
            hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
        if hicon == 0:
            # If both small and big icons are not available, get the class icon
            if hasattr(win32gui, "GetClassLongPtr"):
                hicon = win32gui.GetClassLongPtr(hwnd, win32con.GCLP_HICON)
            else:
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)

        if hicon:
            img = hicon_to_image(hicon)
            if img is not None:
                return img

            hdc_handle = win32gui.GetDC(0)
            if not hdc_handle:
                raise Exception("Failed to get DC handle")
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
                img = Image.frombuffer(
                    "RGBA", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), raw_data, "raw", "BGRA", 0, 1
                ).convert("RGBA")
                return img
            finally:
                # Cleaning up resources
                try:
                    win32gui.DestroyIcon(hicon)
                except Exception:
                    pass
                try:
                    memdc.DeleteDC()
                except Exception:
                    pass
                try:
                    hdc.DeleteDC()
                except Exception:
                    pass
                try:
                    win32gui.DeleteObject(hbmp.GetHandle())
                except Exception:
                    pass
                try:
                    win32gui.ReleaseDC(0, hdc_handle)
                except Exception:
                    pass
        else:
            aumid = get_aumid_for_window(hwnd)
            if aumid:
                img = get_icon_for_aumid(aumid)
                if img is not None:
                    return img

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

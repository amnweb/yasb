import logging
from ctypes import addressof, byref, c_byte, create_string_buffer, sizeof, string_at
from ctypes.wintypes import HBITMAP

from PIL import Image
from win32con import DIB_RGB_COLORS

from core.utils.win32.bindings import DeleteObject, GetDC, GetDIBits, GetIconInfo, GetObject, ReleaseDC
from core.utils.win32.structs import BITMAP, BITMAPINFO, BITMAPINFOHEADER, ICONINFO

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


def hicon_to_image(hicon: int) -> Image.Image | None:
    """Icon handle to an image; None for icons that only have a 2-color picture."""
    if not hicon:
        return None

    icon_info = ICONINFO()
    if not GetIconInfo(hicon, byref(icon_info)):
        logging.error("GetIconInfo failed: %s", hicon)
        return None
    try:
        bitmap = BITMAP()
        if GetObject(icon_info.hbmColor, sizeof(BITMAP), byref(bitmap)) == 0:
            logging.error("GetObjectW failed")
            return None
        width, height = bitmap.bmWidth, bitmap.bmHeight
        hdc = GetDC(None)
        if hdc == 0:
            logging.error("GetDC failed")
            return None
        try:
            bi = BITMAPINFO()
            bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
            bi.bmiHeader.biWidth = width
            bi.bmiHeader.biHeight = -abs(height)
            bi.bmiHeader.biPlanes = 1
            bi.bmiHeader.biBitCount = 32
            color_buffer = create_string_buffer(width * height * 4)
            if GetDIBits(hdc, icon_info.hbmColor, 0, height, byref(color_buffer), byref(bi), DIB_RGB_COLORS) == 0:
                logging.error("GetDIBits failed")
                return None
            img = Image.frombuffer(  # pyright: ignore[reportUnknownMemberType]
                "RGBA", (width, height), color_buffer.raw, "raw", "BGRA", 0, 1
            )

            # no alpha channel, use the AND mask (white = transparent)
            if img.getchannel("A").getextrema() == (0, 0):  # pyright: ignore[reportUnknownMemberType]
                mask_buffer = create_string_buffer(width * height * 4)
                if GetDIBits(hdc, icon_info.hbmMask, 0, height, byref(mask_buffer), byref(bi), DIB_RGB_COLORS) == 0:
                    logging.error("GetDIBits failed")
                    return None
                mask = Image.frombuffer(  # pyright: ignore[reportUnknownMemberType]
                    "RGBA", (width, height), mask_buffer.raw, "raw", "BGRA", 0, 1
                )
                img.putalpha(mask.getchannel("B").point([255] * 255 + [0]))  # pyright: ignore[reportUnknownMemberType]
            return img
        finally:
            ReleaseDC(None, hdc)
    finally:
        DeleteObject(icon_info.hbmColor)
        DeleteObject(icon_info.hbmMask)


def hbitmap_to_image(hbitmap: int) -> Image.Image | None:
    """Convert a Windows HBITMAP to a PIL Image. The bitmap is deleted afterwards."""
    bmp = BITMAP()
    res = GetObject(hbitmap, sizeof(BITMAP), byref(bmp))
    if res == 0:
        return None

    width, height = bmp.bmWidth, bmp.bmHeight
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -abs(height)
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32

    buf_size = width * height * 4
    pixel_buffer = (c_byte * buf_size)()

    hdc = GetDC(None)
    try:
        n = GetDIBits(
            hdc,
            HBITMAP(hbitmap),
            0,
            height,
            byref(pixel_buffer),
            byref(bi),
            0,
        )
        if n == 0:
            return None
        raw_bytes = string_at(addressof(pixel_buffer), buf_size)
        return Image.frombuffer(  # pyright: ignore[reportUnknownMemberType]
            "RGBA", (width, height), raw_bytes, "raw", "BGRA", 0, 1
        )
    finally:
        ReleaseDC(None, hdc)
        try:
            DeleteObject(hbitmap)
        except Exception:
            pass

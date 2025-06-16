import ctypes
import locale
import logging
import os
import re
import struct
import xml.etree.ElementTree as ET
from ctypes import byref, create_string_buffer, sizeof
from glob import glob
from pathlib import Path

import win32api
import win32con
import win32gui
import win32ui
from PIL import Image, ImageFilter
from win32con import DIB_RGB_COLORS

from core.utils.win32.app_uwp import get_package
from core.utils.win32.bindings import DeleteObject, GetDC, GetDIBits, GetIconInfo, GetObject, ReleaseDC
from core.utils.win32.structs import BITMAP, BITMAPINFO, BITMAPINFOHEADER, ICONINFO
from settings import DEBUG

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)

TARGETSIZE_REGEX = re.compile(r"targetsize-([0-9]+)")


def get_window_icon(hwnd: int, smooth_level: int = 0):
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
                # Select the bitmap into the memory device context
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
                # target_size = 48  # target size (48x48) wihout DPI, most of uwps are also 48x48
                # img = img.resize((target_size, target_size), Image.LANCZOS)
                if smooth_level == 1:
                    img = img.filter(ImageFilter.SMOOTH)
                elif smooth_level == 2:
                    img = img.filter(ImageFilter.SMOOTH_MORE)
                return img
            finally:
                # Cleaning up resources
                # logging.debug("Cleaning up")
                try:
                    win32gui.DestroyIcon(hicon)
                    # logging.debug("Destroyed hicon")
                except Exception:
                    # logging.debug(f"Error destroying hicon: {e}")
                    pass
                try:
                    memdc.DeleteDC()
                    # logging.debug("Deleted memory device context.")
                except Exception:
                    # logging.debug(f"Error deleting memory device context: {e}")
                    pass
                try:
                    hdc.DeleteDC()
                    # logging.debug("Deleted device context.")
                except Exception:
                    # logging.debug(f"Error deleting device context: {e}")
                    pass
                try:
                    win32gui.DeleteObject(hbmp.GetHandle())
                    # logging.debug("Deleted bitmap object.")
                except Exception:
                    # logging.debug(f"Error deleting bitmap object: {e}")
                    pass
                try:
                    win32gui.ReleaseDC(0, hdc_handle)
                    # logging.debug("Released device context handle.")
                except Exception:
                    # logging.debug(f"Error releasing device context handle: {e}")
                    pass
        else:
            try:
                class_name = win32gui.GetClassName(hwnd)
            except:
                return None
            actual_hwnd = 1

            def cb(hwnd, b):
                nonlocal actual_hwnd
                try:
                    class_name = win32gui.GetClassName(hwnd)
                except:
                    class_name = ""
                if "ApplicationFrame" in class_name:
                    return True
                actual_hwnd = hwnd
                return False

            if class_name == "ApplicationFrameWindow":
                win32gui.EnumChildWindows(hwnd, cb, False)
            else:
                actual_hwnd = hwnd

            package = get_package(actual_hwnd)
            if package is None:
                return None
            if package.package_path is None:
                return None
            manifest_path = os.path.join(package.package_path, "AppXManifest.xml")
            if not os.path.exists(manifest_path):
                if DEBUG:
                    logging.error(f"manifest not found {manifest_path}")
                return None
            root = ET.parse(manifest_path)
            velement = root.find(".//VisualElements")
            if velement is None:
                velement = root.find(".//{http://schemas.microsoft.com/appx/manifest/uap/windows10}VisualElements")
            if not velement:
                return None
            if "Square44x44Logo" not in velement.attrib:
                return None
            package_path = Path(package.package_path)
            # logopath = Path(package.package_path) / (velement.attrib["Square44x44Logo"])
            logofile = Path(velement.attrib["Square44x44Logo"])
            logopattern = str(logofile.parent / "**") + "\\" + str(logofile.stem) + "*" + str(logofile.suffix)
            logofiles = glob(logopattern, recursive=True, root_dir=package_path)
            logofiles = [x.lower() for x in logofiles]
            if len(logofiles) == 0:
                return None

            def filter_logos(logofiles, qualifiers, values):
                for qualifier in qualifiers:
                    for value in values:
                        filtered_files = list(filter(lambda x: (qualifier + "-" + value in x), logofiles))
                        if len(filtered_files) > 0:
                            return filtered_files
                return logofiles

            langs = []
            current_lang_code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if current_lang_code in locale.windows_locale:
                current_lang = locale.windows_locale[current_lang_code].lower().replace("_", "-")
                current_lang_short = current_lang.split("-", 1)[0]
                langs += [current_lang, current_lang_short]
            if "en" not in langs:
                langs += ["en", "en-us"]

            # filter_logos will try to select only the files matching the qualifier values
            # if nothing matches, the list is unchanged
            if langs:
                logofiles = filter_logos(logofiles, ["lang", "language"], langs)
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["alternateform", "altform"], ["unplated"])
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["scale"], ["100", "150", "200"])

            # find the one closest to 48, but bigger
            def target_size_sort(s):
                m = TARGETSIZE_REGEX.search(s)
                if m:
                    size = int(m.group(1))
                    if size < 48:
                        return 5000 - size
                    return size - 48
                return 10000

            logofiles.sort(key=target_size_sort)

            img = Image.open(package_path / logofiles[0])
            if not img:
                return None
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

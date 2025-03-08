import os
import locale
import re
import logging
import win32ui
import win32con
import ctypes
import ctypes.wintypes
from core.utils.win32.app_uwp import get_package
import xml.etree.ElementTree as ET
from pathlib import Path
import win32gui
from glob import glob
from PIL import Image, ImageFilter 
from settings import DEBUG

pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.INFO)

TARGETSIZE_REGEX = re.compile(r'targetsize-([0-9]+)')

def get_window_icon(hwnd, smooth_level=0):
    """Fetch the icon of the window at higher quality if possible."""
    try:
        hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
        if hicon == 0:
            hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
        if hicon == 0:
            if hasattr(win32gui, 'GetClassLongPtr'):
                hicon = win32gui.GetClassLongPtr(hwnd, win32con.GCLP_HICON)
            else:
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
        
        if hicon:
            desired_size = 48 # Most of UWPs also return 48x48 icons
            hdc_handle = win32gui.GetDC(0)
            if not hdc_handle:
                raise Exception("Failed to get DC handle")
            try:
                hdc = win32ui.CreateDCFromHandle(hdc_handle)
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, desired_size, desired_size)
                memdc = hdc.CreateCompatibleDC()
                memdc.SelectObject(hbmp)
                
                # Call DrawIconEx via ctypes
                DrawIconEx = ctypes.windll.user32.DrawIconEx
                DrawIconEx.argtypes = [
                    ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int,
                    ctypes.wintypes.HICON, ctypes.c_int, ctypes.c_int,
                    ctypes.c_uint, ctypes.wintypes.HBRUSH, ctypes.c_uint
                ]
                DI_NORMAL = 0x0003
                result = DrawIconEx(memdc.GetSafeHdc(), 0, 0, hicon,
                                      desired_size, desired_size, 0, 0, DI_NORMAL)
                if result == 0:
                    return None
                
                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                raw_data = bytes(bmpstr)
                img = Image.frombuffer(
                    'RGBA',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    raw_data, 'raw', 'BGRA', 0, 1
                ).convert('RGBA')
                if smooth_level == 1:
                    img = img.filter(ImageFilter.SMOOTH)
                elif smooth_level == 2:
                    img = img.filter(ImageFilter.SMOOTH_MORE)
                return img
            finally:
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
            logopattern = str(logofile.parent / '**') + '\\' + str(logofile.stem) + '*' + str(logofile.suffix)
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
                current_lang = locale.windows_locale[current_lang_code].lower().replace('_', '-')
                current_lang_short = current_lang.split('-', 1)[0]
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
                        return 5000-size
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
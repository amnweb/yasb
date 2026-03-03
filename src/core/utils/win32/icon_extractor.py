import configparser
import ctypes
import ctypes.wintypes
import hashlib
import json
import logging
import os
import re
import tempfile
import time
import urllib.request
import winreg
from urllib.parse import urljoin, urlparse

import win32com.client
import win32gui
from icoextract import IconExtractor
from PIL import Image

from core.utils.win32.app_icons import hicon_to_image
from core.utils.win32.aumid_icons import get_icon_for_aumid

logging.getLogger("icoextract").setLevel(logging.ERROR)


def parse_icon_location(value: str) -> tuple[str, int]:
    """Split an icon location string like ``'file.dll,-3'`` into *(file, index)*.

    The file portion is expanded via :func:`os.path.expandvars`.
    """
    parts = value.rsplit(",", 1)
    icon_file = os.path.expandvars(parts[0].strip())
    icon_index = 0
    if len(parts) > 1:
        try:
            icon_index = int(parts[1].strip())
        except ValueError:
            pass
    return icon_file, icon_index


class IconExtractorUtil:
    """
    Extract the icon from a file (ico, exe, dll) and save as PNG in the icons dir.
    Falls back to extracting from a mun file if available.
    For UWP/packaged apps, uses IShellItemImageFactory via extract_shell_appid_icon.
    Returns the PNG path or None.
    """

    @staticmethod
    def extract_icon_from_path(file_path, icons_dir, size=48):
        ext = os.path.splitext(file_path)[1].lower()
        base = os.path.splitext(os.path.basename(file_path))[0]
        temp_png = os.path.join(icons_dir, f"{base}_{int(time.time() * 1000)}.png")

        if ext == ".ico":
            try:
                im = Image.open(file_path)
                largest = im
                max_area = im.width * im.height
                for frame in range(getattr(im, "n_frames", 1)):
                    im.seek(frame)
                    area = im.width * im.height
                    if area > max_area:
                        largest = im.copy()
                        max_area = area
                largest.save(temp_png, format="PNG")
                return temp_png
            except Exception:
                return None

        if ext == ".lnk":
            return IconExtractorUtil.extract_lnk_icon(file_path, icons_dir, size=size)

        mun_candidate = None
        system32 = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
        sysres = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SystemResources")
        basename = os.path.basename(file_path)
        if file_path.lower().startswith(system32.lower()) and basename.lower().endswith(".exe"):
            mun_candidate = os.path.join(sysres, f"{basename}.mun")

        try:
            extractor = IconExtractor(file_path)
            data = extractor.get_icon(num=0)
            img = Image.open(data)
            img.save(temp_png, format="PNG")
            return temp_png
        except Exception:
            if mun_candidate and os.path.exists(mun_candidate):
                try:
                    extractor = IconExtractor(mun_candidate)
                    data = extractor.get_icon(num=0)
                    img = Image.open(data)
                    img.save(temp_png, format="PNG")
                    return temp_png
                except Exception:
                    pass
            # Fallback: win32 API extraction (handles more exe/dll edge cases)
            return IconExtractorUtil.extract_icon_with_index(file_path, 0, icons_dir, size=size)

    @staticmethod
    def extract_lnk_icon(lnk_path, icons_dir, size=48):
        """Extract icon from a .lnk shortcut by resolving its IconLocation or target.

        *size* controls the requested icon dimensions when using win32 APIs.
        When *size* > 48, icoextract is tried first for a full-resolution
        (256x256) PE icon.
        """
        use_icoextract = size > 48

        try:
            shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)
            target_path = shortcut.TargetPath or ""
            icon_location = shortcut.IconLocation or ""
        except Exception:
            return None

        # Try the explicit IconLocation first (e.g. "explorer.exe,0")
        if icon_location:
            icon_file, icon_index = parse_icon_location(icon_location)
            if icon_file and os.path.isfile(icon_file):
                if use_icoextract:
                    # Try icoextract first for high-res (256x256) icons
                    try:
                        extractor = IconExtractor(icon_file)
                        data = extractor.get_icon(num=max(icon_index, 0))
                        img = Image.open(data)
                        base = os.path.splitext(os.path.basename(icon_file))[0]
                        temp_png = os.path.join(icons_dir, f"{base}_{int(time.time() * 1000)}.png")
                        img.save(temp_png, format="PNG")
                        return temp_png
                    except Exception:
                        pass
                # win32 API path
                result = IconExtractorUtil.extract_icon_with_index(icon_file, icon_index, icons_dir, size=size)
                if result:
                    return result

        # Fall back to extracting from the target executable
        target = os.path.expandvars(target_path)
        if target and os.path.isfile(target):
            if use_icoextract:
                return IconExtractorUtil.extract_icon_from_path(target, icons_dir, size=size)
            return IconExtractorUtil.extract_icon_with_index(target, 0, icons_dir, size=size)
        return None

    @staticmethod
    def extract_icon_with_index(file_path, icon_index, icons_dir, size=48):
        """Extract an icon at a specific index using win32 APIs.

        Uses PrivateExtractIconsW (supports any index and a custom *size*)
        with a fallback to ExtractIconEx for edge cases.
        """
        path_hash = hashlib.md5(file_path.lower().encode()).hexdigest()[:10]
        base = os.path.splitext(os.path.basename(file_path))[0]
        temp_png = os.path.join(icons_dir, f"{base}_{path_hash}_{abs(icon_index)}_{size}.png")
        if os.path.isfile(temp_png):
            return temp_png

        hicon = None
        cleanup_handles = []
        try:
            h = ctypes.wintypes.HICON()
            icon_id = ctypes.c_uint()
            count = ctypes.windll.user32.PrivateExtractIconsW(
                file_path,
                icon_index,
                size,
                size,
                ctypes.byref(h),
                ctypes.byref(icon_id),
                1,
                0,
            )
            if count >= 1 and h.value:
                hicon = h.value
                cleanup_handles.append(hicon)

            # Fallback to ExtractIconEx (returns 32x32 but handles some edge cases)
            if not hicon:
                result = win32gui.ExtractIconEx(file_path, icon_index, 1)
                if not isinstance(result, tuple) or len(result) != 2:
                    return None
                large, small = result
                if not large and icon_index != 0:
                    for handle in (large or []) + (small or []):
                        win32gui.DestroyIcon(handle)
                    result = win32gui.ExtractIconEx(file_path, 0, 1)
                    if not isinstance(result, tuple) or len(result) != 2:
                        return None
                    large, small = result
                if not large:
                    for handle in (large or []) + (small or []):
                        win32gui.DestroyIcon(handle)
                    return None
                hicon = large[0]
                cleanup_handles.extend(large)
                cleanup_handles.extend(small)

            if not hicon:
                return None

            img = hicon_to_image(hicon)
            if img is None:
                return None
            img.save(temp_png, format="PNG")
            return temp_png
        except Exception as e:
            logging.debug(f"Icon extraction failed for {file_path}: {e}")
            return None
        finally:
            for h in cleanup_handles:
                win32gui.DestroyIcon(h)

    @staticmethod
    def extract_cpl_icon(path, icons_dir, size=48):
        """Extract icon for a Control Panel item.

        Path format: CPL::{clsid}::CanonicalName
        Icon is read from HKCR\\CLSID\\{clsid}\\DefaultIcon.
        """
        clsid = path[5:].split("::", 1)[0]
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\DefaultIcon") as icon_key:
                icon_val, _ = winreg.QueryValueEx(icon_key, "")
            if not icon_val:
                return None
            icon_file, icon_index = parse_icon_location(icon_val.lstrip("@"))
            if icon_file and os.path.isfile(icon_file):
                return IconExtractorUtil.extract_icon_with_index(icon_file, icon_index, icons_dir, size=size)
        except Exception as e:
            logging.debug(f"CPL icon resolve failed for {clsid}: {e}")
        return None

    @staticmethod
    def extract_default_icon(icons_dir, size=48):
        """Generate a generic Windows application icon as a cached PNG.

        Uses shell32.dll index 2 (the standard executable icon) at the
        requested *size*.
        """
        default_png = os.path.join(icons_dir, f"_default_app_{size}.png")
        if os.path.isfile(default_png):
            return default_png
        try:
            h = ctypes.wintypes.HICON()
            icon_id = ctypes.c_uint()
            count = ctypes.windll.user32.PrivateExtractIconsW(
                r"C:\Windows\System32\shell32.dll",
                2,
                size,
                size,
                ctypes.byref(h),
                ctypes.byref(icon_id),
                1,
                0,
            )
            if count >= 1 and h.value:
                img = hicon_to_image(h.value)
                ctypes.windll.user32.DestroyIcon(h.value)
                if img:
                    img.save(default_png, format="PNG")
                    return default_png
        except Exception:
            pass
        return None

    @staticmethod
    def extract_ico_to_png(ico_path, icons_dir, size=48):
        """Convert a .ico file to a cached PNG, resized to *size* x *size*."""
        try:
            path_hash = hashlib.md5(ico_path.lower().encode()).hexdigest()[:10]
            base = os.path.splitext(os.path.basename(ico_path))[0]
            temp_png = os.path.join(icons_dir, f"{base}_{path_hash}.png")
            if os.path.isfile(temp_png):
                return temp_png
            with Image.open(ico_path) as img:
                best_frame = None
                best_area = 0
                try:
                    for frame_idx in range(img.n_frames):
                        img.seek(frame_idx)
                        w, h = img.size
                        if w * h > best_area:
                            best_area = w * h
                            best_frame = frame_idx
                except EOFError, AttributeError:
                    pass
                if best_frame is not None:
                    img.seek(best_frame)
                img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                img.save(temp_png, format="PNG")
            return temp_png
        except Exception as e:
            logging.debug(f"ICO to PNG conversion failed for {ico_path}: {e}")
            return None

    @staticmethod
    def extract_url_icon(url_path, icons_dir, size=48):
        """Parse a .url (Internet Shortcut) file and extract its icon."""
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(url_path, encoding="utf-8")
            section = "InternetShortcut"
            if not cfg.has_section(section):
                return None
            icon_file = cfg.get(section, "IconFile", fallback="").strip()
            icon_index = 0
            try:
                icon_index = int(cfg.get(section, "IconIndex", fallback="0"))
            except ValueError:
                pass
            if icon_file and os.path.isfile(icon_file):
                if icon_file.lower().endswith(".ico"):
                    return IconExtractorUtil.extract_ico_to_png(icon_file, icons_dir, size=size)
                return IconExtractorUtil.extract_icon_with_index(icon_file, icon_index, icons_dir, size=size)
        except Exception as e:
            logging.debug(f"URL icon resolve failed for {url_path}: {e}")
        return None

    @staticmethod
    def extract_shell_appid_icon(appid, icons_dir, size=48):
        """Extract icon for any AppID via the shell:AppsFolder virtual namespace.

        Delegates to :func:`get_icon_for_aumid` from ``aumid_icons`` which uses
        ``IShellItemImageFactory`` for a bitmap of the requested *size*, and
        saves the result as PNG.  Always re-extracts so icon updates are picked up.
        """
        safe_name = hashlib.md5(appid.lower().encode()).hexdigest()[:12]
        cached_png = os.path.join(icons_dir, f"shell_{safe_name}_{size}.png")
        try:
            img = get_icon_for_aumid(appid, size=size)
            if img is None:
                return None
            img.save(cached_png, format="PNG")
            return cached_png
        except Exception as e:
            logging.debug(f"Shell AppID icon resolve failed for {appid}: {e}")
        return None


class UrlExtractorUtil:
    """
    Extract the icon and title from URL and save as PNG in the icons dir.
    Falls back to extracting from the manifest.json or manifest.webmanifest.
    Returns the PNG path and page title or None if not found.
    """

    @staticmethod
    def extract_from_url(url, icons_dir):
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            manifest_url = None
            page_title = None
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                title_match = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)

                if title_match:
                    page_title = title_match.group(1).strip()
                    if len(page_title) > 30:
                        page_title = page_title[:30] + "..."
                match = re.search(r'<link[^>]+rel=["\']manifest["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if match:
                    manifest_url = urljoin(base_url, match.group(1))
            except Exception:
                manifest_url = None

            # Fallback to default manifest locations if not found in HTML
            # This is useful for sites that don't explicitly link to a manifest
            manifest_urls = []
            if manifest_url:
                manifest_urls.append(manifest_url)
            manifest_urls += [
                urljoin(base_url, "manifest.webmanifest"),
                urljoin(base_url, "manifest.json"),
            ]

            manifest = None
            manifest_base_url = None
            for m_url in manifest_urls:
                try:
                    with urllib.request.urlopen(m_url, timeout=2) as resp:
                        if resp.status == 200:
                            manifest = json.loads(resp.read().decode("utf-8"))
                            manifest_base_url = m_url
                            break
                except Exception:
                    continue
            if not manifest or "icons" not in manifest:
                return None, page_title

            # Find the largest icon >=192x192
            icons = manifest["icons"]
            best_icon = None
            best_size = 0
            for icon in icons:
                purpose = icon.get("purpose", "").strip().lower()
                if purpose == "monochrome":
                    continue
                sizes = icon.get("sizes", "")
                if not sizes:
                    continue
                for size in sizes.split():
                    try:
                        w, h = map(int, size.lower().split("x"))
                        if w >= 192 and h >= 192:
                            best_icon = icon
                            break
                        if w * h > best_size:
                            fallback_icon = icon
                            best_size = w * h
                    except Exception:
                        continue
                if best_icon:
                    break

            if not best_icon and "fallback_icon" in locals():
                best_icon = fallback_icon
            if not best_icon:
                return None, page_title

            icon_src = best_icon.get("src")
            if not icon_src:
                return None, page_title

            # Use the manifest's URL as the base for relative icon URLs
            icon_url = urljoin(manifest_base_url, icon_src) if manifest_base_url else urljoin(base_url, icon_src)
            try:
                with urllib.request.urlopen(icon_url, timeout=5) as icon_resp:
                    if icon_resp.status != 200:
                        return None, page_title
                    icon_data = icon_resp.read()
            except Exception:
                return None, page_title

            temp_dir = tempfile.gettempdir()
            temp_png = os.path.join(temp_dir, f"{int(time.time() * 1000)}.png")
            with open(temp_png, "wb") as f:
                f.write(icon_data)
            return temp_png, page_title
        except Exception as e:
            logging.error(f"Failed to extract icon from url {url}: {e}")
            return None, None

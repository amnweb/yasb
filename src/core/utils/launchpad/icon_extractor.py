import json
import logging
import os
import re
import tempfile
import time
import urllib.request
from urllib.parse import urljoin, urlparse

from icoextract import IconExtractor
from PIL import Image

logging.getLogger("icoextract").setLevel(logging.ERROR)


class IconExtractorUtil:
    """
    Extract the icon from a file (ico, exe, dll) and save as PNG in the icons dir.
    Falls back to extracting from a mun file if available.
    For UWP apps, it tries to extract the icon from the AppxManifest.xml.
    Returns the PNG path or None.
    """

    @staticmethod
    def extract_icon_from_path(file_path, icons_dir):
        ext = os.path.splitext(file_path)[1].lower()
        base = os.path.splitext(os.path.basename(file_path))[0]
        temp_png = os.path.join(icons_dir, f"{base}_{int(time.time() * 1000)}.png")

        if ext == ".ico":
            try:
                im = Image.open(file_path)
                largest = im
                max_size = im.width * im.height
                for frame in range(getattr(im, "n_frames", 1)):
                    im.seek(frame)
                    size = im.width * im.height
                    if size > max_size:
                        largest = im.copy()
                        max_size = size
                largest.save(temp_png, format="PNG")
                return temp_png
            except Exception:
                return None

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
                    return None
            return None

    def extract_uwp_icon(appid, install_location=None):
        import ctypes
        import locale
        import os
        import xml.etree.ElementTree as ET
        from glob import glob
        from pathlib import Path

        if not install_location or not os.path.isdir(install_location):
            return None

        manifest_path = os.path.join(install_location, "AppxManifest.xml")
        if not os.path.isfile(manifest_path):
            return None

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            velement = root.find(".//VisualElements")
            if velement is None:
                velement = root.find(".//{http://schemas.microsoft.com/appx/manifest/uap/windows10}VisualElements")
            if velement is None or "Square44x44Logo" not in velement.attrib:
                return None

            logofile = Path(velement.attrib["Square44x44Logo"])
            logopattern = str(logofile.parent / "**") + "\\" + str(logofile.stem) + "*" + str(logofile.suffix)
            package_path = Path(install_location)
            logofiles = glob(logopattern, recursive=True, root_dir=package_path)
            logofiles = [x.lower() for x in logofiles]
            if not logofiles:
                return None

            def filter_logos(logofiles, qualifiers, values):
                for qualifier in qualifiers:
                    for value in values:
                        filtered_files = list(filter(lambda x: (qualifier + "-" + value in x), logofiles))
                        if filtered_files:
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

            if langs:
                logofiles = filter_logos(logofiles, ["lang", "language"], langs)
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["alternateform", "altform"], ["unplated"])
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["scale"], ["100", "150", "200"])

            def get_size(p):
                try:
                    with Image.open(package_path / p) as img:
                        return img.width * img.height
                except Exception:
                    return 0

            logofiles.sort(key=get_size, reverse=True)
            if not logofiles:
                return None
            return str(package_path / logofiles[0])
        except Exception as e:
            logging.error(f"Failed to parse manifest or find logo: {e}")
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

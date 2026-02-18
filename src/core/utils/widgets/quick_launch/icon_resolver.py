import configparser
import hashlib
import logging
import os

import win32api
import win32com.client
import win32con
import win32gui
from PyQt6.QtCore import QThread, pyqtSignal
from winrt.windows.management.deployment import PackageManager

from core.utils.widgets.launchpad.icon_extractor import IconExtractorUtil
from core.utils.win32.app_icons import hicon_to_image


class IconResolverWorker(QThread):
    """Background thread that resolves icons for discovered apps."""

    icon_ready = pyqtSignal(str, str)

    def __init__(self, apps: list[tuple[str, str, object]], icons_dir: str):
        super().__init__()
        self._apps = apps
        self._icons_dir = icons_dir
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        self._uwp_locations = self._batch_resolve_uwp_locations()
        self._default_icon = self._get_default_icon()
        for name, path, _ in self._apps:
            if self._should_stop:
                break
            app_key = f"{name}::{path}"
            try:
                icon_path = self._resolve_icon(name, path)
                if not icon_path or not os.path.isfile(icon_path):
                    icon_path = self._default_icon
                if icon_path and os.path.isfile(icon_path):
                    self.icon_ready.emit(app_key, icon_path)
            except Exception as e:
                logging.debug(f"Icon resolve failed for {name}: {e}")
                if self._default_icon:
                    self.icon_ready.emit(app_key, self._default_icon)

    def _get_default_icon(self) -> str | None:
        """Generate the default Windows app icon as a cached PNG."""
        default_png = os.path.join(self._icons_dir, "_default_app.png")
        if os.path.isfile(default_png):
            return default_png
        try:
            size = win32api.GetSystemMetrics(win32con.SM_CXICON)
            hicon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, size, size, win32con.LR_SHARED)
            if hicon:
                img = hicon_to_image(hicon)
                if img:
                    img.save(default_png, format="PNG")
                    return default_png
        except Exception:
            pass
        return None

    def _batch_resolve_uwp_locations(self) -> dict[str, str]:
        if not any(p.startswith("UWP::") for _, p, _ in self._apps):
            return {}
        try:
            pm = PackageManager()
            locations = {}
            for pkg in pm.find_packages_by_user_security_id(""):
                try:
                    family = pkg.id.family_name
                    path = pkg.installed_path
                    if family and path:
                        locations[family] = path
                except Exception:
                    continue
            return locations
        except Exception as e:
            logging.debug(f"WinRT UWP location resolve failed: {e}")
        return {}

    def _resolve_icon(self, name: str, path: str) -> str | None:
        if path.startswith("UWP::"):
            return self._resolve_uwp_icon(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".lnk":
            return self._resolve_lnk_icon(path)
        if ext == ".url":
            return self._resolve_url_icon(path)
        if os.path.isfile(path):
            return self._extract_icon_with_index(path, 0)
        return None

    def _resolve_url_icon(self, url_path: str) -> str | None:
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
                # .ico files can be extracted directly
                if icon_file.lower().endswith(".ico"):
                    return self._cache_ico_file(icon_file)
                return self._extract_icon_with_index(icon_file, icon_index)
        except Exception as e:
            logging.debug(f"URL icon resolve failed for {url_path}: {e}")
        return None

    def _cache_ico_file(self, ico_path: str) -> str | None:
        """Convert a .ico file to a cached PNG."""
        try:
            path_hash = hashlib.md5(ico_path.lower().encode()).hexdigest()[:10]
            base = os.path.splitext(os.path.basename(ico_path))[0]
            temp_png = os.path.join(self._icons_dir, f"{base}_{path_hash}.png")
            if os.path.isfile(temp_png):
                return temp_png
            from PIL import Image

            with Image.open(ico_path) as img:
                # Select the largest frame in the ICO file
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
                img = img.convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
                img.save(temp_png, format="PNG")
            return temp_png
        except Exception as e:
            logging.debug(f"ICO to PNG conversion failed for {ico_path}: {e}")
            return None

    def _resolve_lnk_icon(self, lnk_path: str) -> str | None:
        try:
            shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)
            target_path = shortcut.TargetPath or ""
            icon_location = shortcut.IconLocation or ""
        except Exception:
            return None

        if icon_location:
            parts = icon_location.rsplit(",", 1)
            icon_file = os.path.expandvars(parts[0].strip()) if parts[0].strip() else ""
            icon_index = 0
            if len(parts) > 1:
                try:
                    icon_index = int(parts[1].strip())
                except ValueError:
                    icon_index = 0
            if icon_file and os.path.isfile(icon_file):
                result = self._extract_icon_with_index(icon_file, icon_index)
                if result:
                    return result

        target = os.path.expandvars(target_path)
        if target and os.path.isfile(target):
            return self._extract_icon_with_index(target, 0)
        return None

    def _extract_icon_with_index(self, file_path: str, icon_index: int = 0) -> str | None:
        try:
            path_hash = hashlib.md5(file_path.lower().encode()).hexdigest()[:10]
            base = os.path.splitext(os.path.basename(file_path))[0]
            temp_png = os.path.join(self._icons_dir, f"{base}_{path_hash}_{abs(icon_index)}.png")
            if os.path.isfile(temp_png):
                return temp_png

            result = win32gui.ExtractIconEx(file_path, icon_index, 1)
            if not isinstance(result, tuple) or len(result) != 2:
                return None
            large, small = result
            if not large and icon_index != 0:
                # Destroy handles from the failed first attempt before retrying
                self._destroy_icon_handles(large, small)
                result = win32gui.ExtractIconEx(file_path, 0, 1)
                if not isinstance(result, tuple) or len(result) != 2:
                    return None
                large, small = result
            if not large:
                # Destroy any remaining small handles before returning
                self._destroy_icon_handles(large, small)
                return None

            hicon = large[0]
            try:
                img = hicon_to_image(hicon)
                if img is None:
                    return None
                img.save(temp_png, format="PNG")
                return temp_png
            finally:
                win32gui.DestroyIcon(hicon)
                for h in small:
                    win32gui.DestroyIcon(h)
                for h in large[1:]:
                    win32gui.DestroyIcon(h)
        except Exception as e:
            logging.debug(f"Icon extraction failed for {file_path}: {e}")
            return None

    @staticmethod
    def _destroy_icon_handles(large, small):
        """Destroy all icon handles returned by ExtractIconEx."""
        if large:
            for h in large:
                win32gui.DestroyIcon(h)
        if small:
            for h in small:
                win32gui.DestroyIcon(h)

    def _resolve_uwp_icon(self, path: str) -> str | None:
        appid = path.replace("UWP::", "")
        family_name = appid.split("!")[0]
        safe_name = family_name.replace("\\", "_").replace("/", "_").replace(":", "_")
        cached_png = os.path.join(self._icons_dir, f"uwp_{safe_name}.png")
        if os.path.isfile(cached_png):
            return cached_png

        install_location = getattr(self, "_uwp_locations", {}).get(family_name)
        if not install_location:
            return None
        try:
            icon = IconExtractorUtil.extract_uwp_icon(appid, install_location=install_location)
            if icon and os.path.isfile(icon):
                from PIL import Image

                with Image.open(icon) as img:
                    img = img.convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
                    img.save(cached_png, format="PNG")
                return cached_png
        except Exception:
            pass
        return None

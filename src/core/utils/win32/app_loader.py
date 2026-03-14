import ctypes
import glob
import os
import re
import subprocess
import winreg

from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
)

_APPS_CACHE = None

_CPL_NS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ControlPanel\NameSpace"


def _load_indirect_string(resource: str) -> str | None:
    """Resolve a @resource.dll,-123 string to its localized value via SHLoadIndirectString."""
    buf = ctypes.create_unicode_buffer(1024)
    hr = ctypes.windll.shlwapi.SHLoadIndirectString(resource, buf, len(buf), None)
    return buf.value if hr == 0 else None


def _reg_value(key, name: str, default=None):
    """Read a single registry value, returning *default* on failure."""
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return val
    except OSError:
        return default


def _resolve_reg_string(key, value_name: str) -> str | None:
    """Read a registry string and resolve it if it is a @resource reference."""
    raw = _reg_value(key, value_name)
    if not raw:
        return None
    if raw.startswith("@"):
        return _load_indirect_string(raw)
    return raw


def _enumerate_control_panel_items():
    """Yield (name, clsid, canonical_name, description) for each Control Panel item."""
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _CPL_NS_KEY) as ns:
        i = 0
        while True:
            try:
                clsid = winreg.EnumKey(ns, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}") as ck:
                    canonical = _reg_value(ck, "System.ApplicationName")
                    if not canonical:
                        continue
                    name = _resolve_reg_string(ck, "LocalizedString") or _reg_value(ck, "")
                    if not name or name.startswith("@"):
                        continue
                    desc = _resolve_reg_string(ck, "InfoTip")
                    yield name, clsid, canonical, desc
            except OSError:
                continue


class AppListLoader(QThread):
    """
    Thread to load the list of applications from the Windows Start Menu and UWP apps.
    This class caches the results to avoid reloading on subsequent calls.
    """

    apps_loaded = pyqtSignal(list)

    @staticmethod
    def clear_cache():
        global _APPS_CACHE
        _APPS_CACHE = None

    def run(self):
        global _APPS_CACHE
        if _APPS_CACHE is not None:
            self.apps_loaded.emit(_APPS_CACHE)
            return

        filter_keywords = {
            "readme",
            "documentation",
            "license",
            "setup",
            "administrative tools",
        }

        strict_filter_keywords = {
            "uninstall",
            "installer",
            "help",
        }

        # Pre-compile regex for strict keywords
        strict_pattern = re.compile(r"\b(" + "|".join(map(re.escape, strict_filter_keywords)) + r")\b")

        start_menu_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu"),
        ]
        apps = []
        seen_names = set()

        def should_filter_app(name):
            """Check if app name contains any filter keywords"""
            name_lower = name.lower()

            # Check loose keywords (substring match)
            if any(keyword in name_lower for keyword in filter_keywords):
                return True

            # Check strict keywords (whole word match)
            if strict_pattern.search(name_lower):
                return True

            return False

        def is_duplicate(name):
            """Check if name (or its space-stripped form) was already seen.

            Some shortcuts use CamelCase without spaces (e.g. "LiveCaptions")
            while Get-StartApps returns the spaced form ("Live captions").
            Checking both forms prevents duplicates.
            """
            lower = name.lower()
            stripped = lower.replace(" ", "")
            return lower in seen_names or stripped in seen_names

        def mark_seen(name):
            lower = name.lower()
            seen_names.add(lower)
            seen_names.add(lower.replace(" ", ""))

        for dir in start_menu_dirs:
            for lnk in glob.glob(os.path.join(dir, "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(lnk))[0]
                if should_filter_app(name):
                    continue
                if not is_duplicate(name):
                    apps.append((name, lnk, None))
                    mark_seen(name)

            # Also scan .url files (e.g. Steam games)
            for url_file in glob.glob(os.path.join(dir, "**", "*.url"), recursive=True):
                name = os.path.splitext(os.path.basename(url_file))[0]
                if should_filter_app(name):
                    continue
                if not is_duplicate(name):
                    apps.append((name, url_file, None))
                    mark_seen(name)

        try:
            ps_script = "Get-StartApps | ForEach-Object { [PSCustomObject]@{Name=$_.Name;AppID=$_.AppID} } | ConvertTo-Json -Compress"
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-NoLogo",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                import json as _json

                uwp_list = _json.loads(result.stdout)
                if isinstance(uwp_list, dict):
                    uwp_list = [uwp_list]
                for entry in uwp_list:
                    name = entry.get("Name")
                    appid = entry.get("AppID")
                    if name and appid and not is_duplicate(name) and not should_filter_app(name):
                        apps.append((name, f"UWP::{appid}", None))
                        mark_seen(name)
        except Exception:
            pass

        # Source 3: Control Panel items from registry (Device Manager, Programs and Features, etc.)
        try:
            for name, clsid, canonical, desc in _enumerate_control_panel_items():
                if not is_duplicate(name):
                    apps.append((name, f"CPL::{clsid}::{canonical}", desc))
                    mark_seen(name)
        except Exception:
            pass

        _APPS_CACHE = apps
        self.apps_loaded.emit(apps)


class ShortcutResolver:
    @staticmethod
    def resolve_lnk_target(lnk_path, warning_callback=None):
        """
        Resolve the target path, icon location, and display name from a .lnk file.
        If warning_callback is provided, it will be called with an error message on failure.
        Returns (full_command, icon_path, app_name) or (None, None, None) on error.
        """
        try:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(lnk_path)
            target_path = shortcut.TargetPath
            arguments = shortcut.Arguments
            icon_path = shortcut.IconLocation
            app_name = os.path.splitext(os.path.basename(lnk_path))[0]
            # Combine target and arguments for the real launch command
            if arguments:
                full_command = f'"{target_path}" {arguments}'
            else:
                full_command = target_path
            if icon_path:
                icon_path = icon_path.split(",")[0]
            if icon_path and os.path.isfile(icon_path):
                return full_command, icon_path, app_name
            elif target_path and os.path.isfile(target_path):
                return full_command, target_path, app_name
            else:
                return full_command, None, app_name
        except Exception:
            if warning_callback:
                warning_callback("Failed to resolve shortcut: {lnk_path}")
            return None, None, None

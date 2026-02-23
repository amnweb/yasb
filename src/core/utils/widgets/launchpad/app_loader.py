import glob
import os
import re
import subprocess

from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
)

_APPS_CACHE = None


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
            "help",
            "documentation",
            "license",
            "setup",
            "administrative tools",
        }

        strict_filter_keywords = {
            "uninstall",
            "installer",
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

        for dir in start_menu_dirs:
            for lnk in glob.glob(os.path.join(dir, "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(lnk))[0]
                if should_filter_app(name):
                    continue
                if name.lower() not in seen_names:
                    apps.append((name, lnk, None))
                    seen_names.add(name.lower())

            # Also scan .url files (e.g. Steam games)
            for url_file in glob.glob(os.path.join(dir, "**", "*.url"), recursive=True):
                name = os.path.splitext(os.path.basename(url_file))[0]
                if should_filter_app(name):
                    continue
                if name.lower() not in seen_names:
                    apps.append((name, url_file, None))
                    seen_names.add(name.lower())

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
                    if name and appid and name.lower() not in seen_names and not should_filter_app(name):
                        apps.append((name, f"UWP::{appid}", None))
                        seen_names.add(name.lower())
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

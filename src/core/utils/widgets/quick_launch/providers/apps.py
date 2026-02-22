import ctypes
import ctypes.wintypes
import json
import logging
import os
import time

import pythoncom
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication
from win32comext.shell import shell

from core.utils.shell_utils import shell_open
from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.fuzzy import _split_camel, fuzzy_score
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_APPS


class LaunchHistory:
    """Manages launch history and frecency scoring for apps."""

    def __init__(self):
        self._recent_file = str(app_data_path("quick_launch_recent.json"))
        self._history: dict[str, dict] = self._load()

    @property
    def data(self) -> dict[str, dict]:
        return self._history

    def record(self, name: str, path: str):
        key = f"{name}::{path}"
        now = time.time()
        entry = self._history.get(key)
        if entry:
            entry["count"] += 1
            entry["last_used"] = now
        else:
            self._history[key] = {
                "name": name,
                "path": path,
                "count": 1,
                "last_used": now,
            }
        self.save()

    def remove(self, key: str):
        self._history.pop(key, None)
        self.save()

    def get_frecency_score(self, app_key: str) -> float:
        """Return a frecency boost in range [0.0, 3.0].

        Can promote an app by up to ~2 tiers so frequently/recently used
        apps outrank apps with a slightly better match quality but no usage
        history.
        """
        entry = self._history.get(app_key)
        if not entry:
            return 0.0
        count = entry.get("count", 0)
        hours_ago = (time.time() - entry.get("last_used", 0)) / 3600
        if hours_ago < 4:
            recency = 1.0
        elif hours_ago < 24:
            recency = 0.8
        elif hours_ago < 168:
            recency = 0.6
        else:
            recency = 0.4
        return min(count * recency * 1.5, 3.0)

    def save(self):
        try:
            os.makedirs(os.path.dirname(self._recent_file), exist_ok=True)
            with open(self._recent_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2)
        except Exception:
            pass

    def _load(self) -> dict[str, dict]:
        try:
            if os.path.isfile(self._recent_file):
                with open(self._recent_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Migrate legacy list format
                if isinstance(data, list):
                    history: dict[str, dict] = {}
                    for r in reversed(data):
                        key = r.get("key", "")
                        if key:
                            history[key] = {
                                "name": r.get("name", ""),
                                "path": r.get("path", ""),
                                "count": 1,
                                "last_used": r.get("timestamp", time.time()),
                            }
                    return history
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}


def _get_exe_description(exe_path: str) -> str | None:
    """Extract FileDescription + CompanyName from an exe's version info."""
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, size, buf):
            return None
        lp_translate = ctypes.c_void_p()
        u_len = ctypes.c_uint()
        ctypes.windll.version.VerQueryValueW(
            buf, r"\VarFileInfo\Translation", ctypes.byref(lp_translate), ctypes.byref(u_len)
        )
        if not u_len.value:
            return None
        lang, codepage = ctypes.cast(lp_translate, ctypes.POINTER(ctypes.wintypes.WORD * 2)).contents
        prefix = rf"\StringFileInfo\{lang:04x}{codepage:04x}"
        parts = []
        for field in ("FileDescription", "CompanyName"):
            lp_buf = ctypes.c_wchar_p()
            u_len2 = ctypes.c_uint()
            if ctypes.windll.version.VerQueryValueW(
                buf, f"{prefix}\\{field}", ctypes.byref(lp_buf), ctypes.byref(u_len2)
            ):
                val = lp_buf.value
                if val:
                    parts.append(val.strip())
        return " - ".join(parts) if parts else None
    except Exception:
        return None


def _resolve_squirrel_target(target: str, args: str) -> str | None:
    """For Squirrel/Electron apps (Discord, Slack, etc.) the shortcut points to
    Update.exe --processStart RealApp.exe. Resolve the real exe from app-* dirs."""
    if not target or not args:
        return None
    if os.path.basename(target).lower() != "update.exe" or "--processstart" not in args.lower():
        return None
    parts = args.split()
    try:
        idx = [p.lower() for p in parts].index("--processstart")
        exe_name = parts[idx + 1].strip('"')
    except ValueError, IndexError:
        return None
    parent = os.path.dirname(target)
    # Pick the highest-versioned app-* directory
    app_dirs = sorted(
        (d for d in os.listdir(parent) if d.startswith("app-") and os.path.isdir(os.path.join(parent, d))),
        reverse=True,
    )
    for d in app_dirs:
        candidate = os.path.join(parent, d, exe_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _get_lnk_description(lnk_path: str) -> str | None:
    """Resolve a .lnk shortcut and return description from its target exe,
    falling back to the shortcut's own Description property, then target path."""
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        link.QueryInterface(pythoncom.IID_IPersistFile).Load(lnk_path)
        target = link.GetPath(0)[0]
        args = link.GetArguments()
        # Squirrel/Electron apps point to Update.exe --processStart RealApp.exe
        resolved = _resolve_squirrel_target(target, args)
        if resolved and os.path.isfile(resolved):
            desc = _get_exe_description(resolved)
            if desc:
                return desc
        elif target and os.path.isfile(target):
            desc = _get_exe_description(target)
            if desc:
                return desc
        shortcut_desc = link.GetDescription()
        if shortcut_desc and shortcut_desc.strip():
            return shortcut_desc.strip()
        if resolved and os.path.isfile(resolved):
            return resolved
        if target and os.path.isfile(target):
            return target
    except Exception:
        pass
    # Fallback: use subfolder name under Start Menu\Programs (e.g. "System Tools")
    lnk_lower = lnk_path.lower()
    marker = r"\start menu\programs" + "\\"
    idx = lnk_lower.find(marker)
    if idx != -1:
        relative = lnk_path[idx + len(marker) :]
        folder = os.path.dirname(relative)
        if folder:
            return folder
    return None


class DescriptionResolverWorker(QThread):
    """Background thread to resolve app descriptions."""

    finished = pyqtSignal(dict)

    def __init__(self, apps: list):
        super().__init__()
        self._apps = apps

    def run(self):
        cache: dict[str, str] = {}
        # Build UWP package lookup
        uwp_lookup = {}
        try:
            from winrt.windows.management.deployment import PackageManager

            pm = PackageManager()
            for pkg in pm.find_packages_by_user_security_id(""):
                fn = pkg.id.family_name
                if fn:
                    dn = pkg.display_name or ""
                    pub = pkg.publisher_display_name or ""
                    if dn and pub:
                        uwp_lookup[fn] = f"{dn} - {pub}"
                    elif dn:
                        uwp_lookup[fn] = dn
        except Exception:
            pass
        for _name, path, _ in self._apps:
            if path.startswith("UWP::"):
                aumid = path[5:]
                family = aumid.split("!")[0] if "!" in aumid else aumid
                cache[path] = uwp_lookup.get(family, "Windows App")
            elif path.lower().endswith(".lnk") and os.path.isfile(path):
                cache[path] = _get_lnk_description(path) or path
            elif os.path.isfile(path):
                cache[path] = _get_exe_description(path) or path
        self.finished.emit(cache)


def _is_subfolder_app(path: str) -> bool:
    """Return True if the shortcut is inside a subfolder of Start Menu\\Programs."""
    marker = r"\start menu\programs"
    idx = path.lower().find(marker)
    if idx == -1:
        return False
    relative = path[idx + len(marker) + 1 :]
    return "\\" in relative or "/" in relative


class AppsProvider(BaseProvider):
    """Search and launch installed applications."""

    name = "apps"
    display_name = "Applications"
    input_placeholder = "Search applications..."
    icon = ICON_APPS

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._service = None
        self._history = LaunchHistory()
        self._desc_cache: dict[str, str] = {}
        self._desc_worker: DescriptionResolverWorker | None = None

    @property
    def service(self):
        if self._service is None:
            from core.utils.widgets.quick_launch.service import QuickLaunchService

            self._service = QuickLaunchService.instance()
        return self._service

    def match(self, text: str) -> bool:
        return True

    def start_description_resolution(self, apps: list):
        """Start background thread to resolve app descriptions."""
        if self._desc_worker and self._desc_worker.isRunning():
            self._desc_worker.finished.disconnect()
            self._desc_worker.wait()
        self._desc_worker = DescriptionResolverWorker(apps)
        self._desc_worker.finished.connect(self._on_descriptions_ready)
        self._desc_worker.start()

    def _on_descriptions_ready(self, cache: dict):
        self._desc_cache = cache

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        svc = self.service
        show_recent = self.config.get("show_recent", True)
        max_recent = self.config.get("max_recent", 10)

        query_text = self.get_query_text(text) if self.prefix and text.startswith(self.prefix) else text
        text_stripped = query_text.strip()
        text_lower = text_stripped.lower()

        if not text_stripped:
            if show_recent:
                # Recent apps first (by last_used timestamp) then the rest
                # Non-recent apps: root-level first, subfolder apps after
                recent = []
                rest = []
                for name, path, _ in svc.apps:
                    key = f"{name}::{path}"
                    entry = self._history.data.get(key)
                    if entry:
                        recent.append((entry.get("last_used", 0), name, path))
                    else:
                        rest.append((name, path))
                recent.sort(key=lambda x: x[0], reverse=True)
                rest.sort(key=lambda a: (_is_subfolder_app(a[1]), a[0].lower()))
                apps = [(n, p) for _, n, p in recent[:max_recent]] + rest
            else:
                apps = [(n, p) for n, p, _ in sorted(svc.apps, key=lambda a: (_is_subfolder_app(a[1]), a[0].lower()))]
        else:
            # Search query fuzzy match by name, fallback to app id
            scored_apps: list[tuple[float, str, str]] = []
            for n, p, _ in svc.apps:
                fs = fuzzy_score(text_lower, n)
                if fs is None and p.startswith("UWP::"):
                    appid = p[5:].split("!")[0].split("_")[0]
                    pkg_name = appid.rsplit(".", 1)[-1] if "." in appid else appid
                    # Split CamelCase (WindowsTerminal -> Windows Terminal)
                    # and match against the human-readable form.
                    pkg_words = _split_camel(pkg_name)
                    pkg_fs = fuzzy_score(text_lower, pkg_words)
                    if pkg_fs is not None:
                        # Cap package-name matches between word-prefix (3)
                        # and prefix (4). Frecency can bridge the gap to
                        # higher tiers for frequently used apps.
                        fs = min(pkg_fs, 3.5)
                if fs is not None:
                    # Demote apps with default icon (system shortcuts,
                    # not real apps) so they sink below real app matches.
                    icon = svc.icon_paths.get(f"{n}::{p}", "")
                    if icon.endswith("_default_app.png"):
                        fs = min(fs, 0.5)
                    scored_apps.append((float(fs), n, p))

            if show_recent:
                for i, (fs, n, p) in enumerate(scored_apps):
                    # Only boost apps with a reasonable match quality
                    # (tier >= 3: word-prefix or better).  Weak matches
                    # like subsequence shouldn't be promoted by history.
                    if fs >= 3.0:
                        key = f"{n}::{p}"
                        frecency = self._history.get_frecency_score(key)
                        scored_apps[i] = (fs + frecency, n, p)

            scored_apps.sort(key=lambda x: x[0], reverse=True)

            apps = [(n, p) for _, n, p in scored_apps]

        show_description = self.config.get("show_description", False)
        results = []
        for name, path in apps:
            app_key = f"{name}::{path}"
            icon_path = svc.icon_paths.get(app_key, "")
            if show_description:
                desc = self._desc_cache.get(path, "")
            else:
                desc = ""
            results.append(
                ProviderResult(
                    title=name,
                    description=desc,
                    icon_path=icon_path,
                    provider=self.name,
                    id=app_key,
                    action_data={"name": name, "path": path},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        name = result.action_data.get("name", "")
        path = result.action_data.get("path", "")
        try:
            if path.startswith("UWP::"):
                aumid = path.replace("UWP::", "")
                shell_open(f"shell:AppsFolder\\{aumid}")
            elif path.startswith(("http://", "https://")):
                shell_open(path)
            elif os.path.isfile(path):
                shell_open(path)
            else:
                logging.warning("Quick Launch: path not found: %s", path)
        except Exception as e:
            logging.error("Failed to launch %s: %s", name, e)
        self._history.record(name, path)
        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        path = result.action_data.get("path", "")
        if not path:
            return []

        is_uwp = path.startswith("UWP::")
        is_url = path.startswith(("http://", "https://"))
        actions: list[ProviderMenuAction] = []

        if not is_url:
            actions.append(ProviderMenuAction(id="run_as_admin", label="Run as administrator"))

        if not is_uwp and not is_url and os.path.isfile(path):
            actions.append(ProviderMenuAction(id="open_file_location", label="Open file location"))

        if is_uwp:
            actions.append(ProviderMenuAction(id="copy_app_id", label="Copy App ID"))
        elif not is_url:
            actions.append(ProviderMenuAction(id="copy_path", label="Copy path"))

        app_key = result.id or f"{result.action_data.get('name', '')}::{path}"
        if app_key in self._history.data:
            actions.append(
                ProviderMenuAction(id="remove_from_recent", label="Remove from recent", separator_before=True)
            )

        if not is_url:
            actions.append(ProviderMenuAction(id="uninstall", label="Uninstall", separator_before=True))

        return actions

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        name = result.action_data.get("name", "")
        path = result.action_data.get("path", "")
        if not path:
            return ProviderMenuActionResult()

        if action_id == "run_as_admin":
            try:
                if path.startswith("UWP::"):
                    aumid = path.replace("UWP::", "")
                    shell_open(f"shell:AppsFolder\\{aumid}", verb="runas")
                elif os.path.isfile(path):
                    shell_open(path, verb="runas")
                self._history.record(name, path)
            except Exception as e:
                logging.debug(f"Failed to run as admin: {e}")
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "open_file_location":
            try:
                target = self._resolve_app_target(path)
                shell_open("explorer.exe", parameters=f'/select, "{target}"')
            except Exception as e:
                logging.debug(f"Failed to open file location: {e}")
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "copy_path":
            target = self._resolve_app_target(path)
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(target)
            return ProviderMenuActionResult()

        if action_id == "copy_app_id":
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(path[5:] if path.startswith("UWP::") else path)
            return ProviderMenuActionResult()

        if action_id == "remove_from_recent":
            app_key = result.id or f"{name}::{path}"
            self._history.remove(app_key)
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "uninstall":
            try:
                shell_open("ms-settings:appsfeatures")
            except Exception as e:
                logging.debug("Failed to open uninstall settings: %s", e)
            return ProviderMenuActionResult(close_popup=True)

        return ProviderMenuActionResult()

    @staticmethod
    def _resolve_app_target(path: str) -> str:
        """Resolve .lnk shortcut to its target executable path."""
        if path.lower().endswith(".lnk") and os.path.isfile(path):
            try:
                link = pythoncom.CoCreateInstance(
                    shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
                )
                link.QueryInterface(pythoncom.IID_IPersistFile).Load(path)
                target = link.GetPath(0)[0]
                args = link.GetArguments()
                resolved = _resolve_squirrel_target(target, args)
                if resolved and os.path.isfile(resolved):
                    return resolved
                if target and os.path.isfile(target):
                    return target
            except Exception:
                pass
        return path

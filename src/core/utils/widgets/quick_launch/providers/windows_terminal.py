"""Windows Terminal Quick Launch Provider

Lists profiles from Windows Terminal (stable and preview).
Supports launching profiles normally or as administrator via context menu.
"""

import json
import logging
import os

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_WINDOWS_TERMINAL,
    ICON_WINDOWS_TERMINAL_CANARY,
    ICON_WINDOWS_TERMINAL_PREVIEW,
)

_TERMINAL_VARIANTS = [
    {
        "id": "stable",
        "label": "Windows Terminal",
        "package": "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
        "icon": ICON_WINDOWS_TERMINAL,
    },
    {
        "id": "preview",
        "label": "Windows Terminal Preview",
        "package": "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe",
        "icon": ICON_WINDOWS_TERMINAL_PREVIEW,
    },
    {
        "id": "canary",
        "label": "Windows Terminal Canary",
        "package": "Microsoft.WindowsTerminalCanary_8wekyb3d8bbwe",
        "icon": ICON_WINDOWS_TERMINAL_CANARY,
    },
]


def _find_settings_path(package_family: str) -> str | None:
    """Return the settings.json path for a terminal package, or None if not found."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None
    path = os.path.join(local_app_data, "Packages", package_family, "LocalState", "settings.json")
    return path if os.path.isfile(path) else None


def _find_wt_executable(package_family: str) -> str | None:
    """Return the wt.exe path for a terminal package, or None if not found."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None
    # UWP apps register their executables here
    exe_path = os.path.join(local_app_data, "Microsoft", "WindowsApps", package_family, "wt.exe")
    if os.path.isfile(exe_path):
        return exe_path
    # Fallback: generic wt.exe on PATH (works when only stable is installed)
    generic = os.path.join(local_app_data, "Microsoft", "WindowsApps", "wt.exe")
    return generic if os.path.isfile(generic) else None


def _load_profiles(settings_path: str) -> tuple[list[dict], str]:
    """Load profiles from a settings.json file.

    Returns (profiles_list, default_profile_guid).
    """
    try:
        with open(settings_path, encoding="utf-8") as f:
            raw = f.read()
        # Strip single-line comments (// ...) that WT settings may contain
        lines = []
        for line in raw.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            lines.append(line)
        data = json.loads("\n".join(lines))
        profiles = data.get("profiles", {})
        profile_list = profiles.get("list", []) if isinstance(profiles, dict) else []
        default_guid = data.get("defaultProfile", "")
        return profile_list, default_guid
    except Exception as e:
        logging.error(f"Windows Terminal provider: failed to load settings: {e}")
        return [], ""


class WindowsTerminalProvider(BaseProvider):
    """Browse and launch Windows Terminal profiles.

    Supports both stable and preview installations.
    """

    name = "windows_terminal"
    display_name = "Terminal"
    icon = ICON_WINDOWS_TERMINAL
    input_placeholder = "Search terminal profiles..."

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._terminals: list[dict] = []
        self._loaded = False

    def _discover_terminals(self) -> None:
        """Discover installed terminal variants and load their profiles."""
        self._terminals = []
        for variant in _TERMINAL_VARIANTS:
            settings_path = _find_settings_path(variant["package"])
            if not settings_path:
                continue
            wt_exe = _find_wt_executable(variant["package"])
            if not wt_exe:
                continue
            profiles, default_guid = _load_profiles(settings_path)
            for profile in profiles:
                if profile.get("hidden", False):
                    continue
                name = profile.get("name", "")
                if not name:
                    continue
                guid = profile.get("guid", "")
                commandline = profile.get("commandline", "")
                self._terminals.append(
                    {
                        "name": name,
                        "guid": guid,
                        "commandline": commandline or "",
                        "variant_id": variant["id"],
                        "variant_label": variant["label"],
                        "icon": variant["icon"],
                        "wt_exe": wt_exe,
                        "is_default": guid == default_guid,
                    }
                )
        self._loaded = True

    def on_deactivate(self) -> None:
        """Clear cached profiles so the next popup open re-discovers installations."""
        self._loaded = False
        self._terminals = []

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        if not self._loaded:
            self._discover_terminals()

        if not self._terminals:
            return [
                ProviderResult(
                    title="No Windows Terminal installation found",
                    description="Install Windows Terminal from the Microsoft Store",
                    icon_char=ICON_WINDOWS_TERMINAL,
                    provider=self.name,
                )
            ]

        query = self.get_query_text(text).strip().lower()
        results: list[ProviderResult] = []

        # Group by terminal variant
        variants_seen: list[str] = []
        for terminal in self._terminals:
            vid = terminal["variant_id"]
            if vid not in variants_seen:
                variants_seen.append(vid)

        for vid in variants_seen:
            variant_profiles = [t for t in self._terminals if t["variant_id"] == vid]
            if query:
                variant_profiles = [
                    t
                    for t in variant_profiles
                    if query in t["name"].lower()
                    or query in t.get("commandline", "").lower()
                    or query in t["variant_label"].lower()
                ]
            if not variant_profiles:
                continue

            # Only show separator when multiple terminal variants are installed
            if len(variants_seen) > 1:
                variant_label = variant_profiles[0]["variant_label"]
                results.append(
                    ProviderResult(
                        title=variant_label,
                        provider=self.name,
                        is_separator=True,
                    )
                )

            for t in variant_profiles:
                desc_parts = []
                if t["commandline"]:
                    desc_parts.append(t["commandline"])
                desc = " · ".join(desc_parts)

                results.append(
                    ProviderResult(
                        title=t["name"],
                        description=desc,
                        icon_char=t["icon"],
                        provider=self.name,
                        action_data={
                            "guid": t["guid"],
                            "wt_exe": t["wt_exe"],
                            "name": t["name"],
                        },
                    )
                )

        if not results:
            return [
                ProviderResult(
                    title="No matching profiles",
                    description="Try a different search term",
                    icon_char=ICON_WINDOWS_TERMINAL,
                    provider=self.name,
                )
            ]

        return results

    def execute(self, result: ProviderResult) -> bool | None:
        data = result.action_data
        wt_exe = data.get("wt_exe", "")
        guid = data.get("guid", "")
        if wt_exe and guid:
            shell_open(wt_exe, parameters=f"-p {guid}")
            return True
        return None

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        data = result.action_data
        if not data.get("guid"):
            return []
        return [
            ProviderMenuAction(id="open", label="Open"),
            ProviderMenuAction(id="open_admin", label="Open as Administrator"),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        data = result.action_data
        wt_exe = data.get("wt_exe", "")
        guid = data.get("guid", "")

        if action_id == "open" and wt_exe and guid:
            shell_open(wt_exe, parameters=f"-p {guid}")
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "open_admin" and wt_exe and guid:
            shell_open(wt_exe, verb="runas", parameters=f"-p {guid}")
            return ProviderMenuActionResult(close_popup=True)

        return ProviderMenuActionResult()

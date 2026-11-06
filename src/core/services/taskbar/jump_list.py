"""The extra items a taskbar button's menu offers for some apps, as Windows' jump lists do: new and private browser
windows, VS Code windows, Windows Terminal profiles, File Explorer's pinned folders and emptying the Recycle Bin."""

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QUrl

from core.services.recycle_bin.recycle_bin_monitor import RecycleBinMonitor
from core.utils.icons.image_provider import icon_url
from core.utils.icons.service import IconService
from core.utils.icons.sources import FileIcon
from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_dispatch
from core.utils.win32.constants import KnownCLSID

# This PC, which File Explorer opens on
THIS_PC = "explorer:::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"
MAX_FOLDERS = 10
MAX_PROFILES = 20
_JSON_STRING = r'"(?:\\.|[^"\\])*"'


def is_recycle_bin(app_id: str) -> bool:
    upper = app_id.upper()
    return KnownCLSID.RECYCLE_BIN in upper or "RECYCLEBINFOLDER" in upper


def _item(kind: str, text: str, target: str, arguments: str = "") -> dict[str, Any]:
    return {"kind": kind, "text": text, "target": target, "arguments": arguments}


def jump_list(app_id: str) -> list[dict[str, Any]]:
    """The extra items for an app, each {kind, text, target, arguments} and optionally icon or iconText.

    kind is window (a new window), private (a new private window), profile (a Windows Terminal profile), folder (a
    folder pinned in File Explorer) or explorer (File Explorer itself); target is the app id to launch and arguments
    go after the app's own. The Recycle Bin has one item of kind recycleBin, with items and bytes, what it holds.
    """
    check = app_id.lower()
    if is_recycle_bin(app_id):
        info = RecycleBinMonitor.last_info()
        return [{"kind": "recycleBin", "items": int(info["num_items"]), "bytes": int(info["size_bytes"])}]
    if "explorer.exe" in check or check.startswith("explorer:"):
        # Each folder's own icon from the icon service, such as Downloads' or one the user set, and File Explorer's
        revision = IconService.instance().revision
        folders = [
            {**_item("folder", name, f"explorer:{path}"), "icon": icon_url(FileIcon(path), revision)}
            for name, path in explorer_pinned_folders()
        ]
        explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
        return [
            *folders,
            {**_item("explorer", "File Explorer", THIS_PC), "icon": icon_url(FileIcon(explorer), revision)},
        ]
    if "msedge" in check or "chrome" in check:
        chrome = "chrome" in check
        return [
            _item("window", "New window", app_id),
            _item(
                "private",
                "New Incognito window" if chrome else "New InPrivate window",
                app_id,
                "--incognito" if chrome else "--inprivate",
            ),
        ]
    if any(name in check for name in ("firefox.exe", "308046b0af4a39cb", "zen.exe", "f0dc299d809b9700")):
        if app_id.startswith("aumid:"):
            # Store installs open a private window from their private browsing app id
            return [
                _item("window", "New window", app_id),
                _item("private", "New private window", f"{app_id};PrivateBrowsingAUMID"),
            ]
        return [
            _item("window", "New window", app_id, "-new-window"),
            _item("private", "New private window", app_id, "-private-window"),
        ]
    if "code.exe" in check or "code - insiders.exe" in check:
        return [_item("window", "New window", app_id, "-n")]
    if "windowsterminal" in check:
        return _terminal_items(app_id)
    return []


def explorer_pinned_folders() -> list[tuple[str, str]]:
    """The folders pinned to Quick Access, each (name, path), with the Recycle Bin when it is pinned there."""
    result = CoInitialize()
    folders: list[tuple[str, str]] = []
    try:
        quick_access = create_dispatch("Shell.Application").NameSpace(f"shell:::{{{KnownCLSID.QUICK_ACCESS}}}")
        for item in quick_access.Items():
            try:
                path: str = item.Path
                if not path or not item.IsFolder:
                    continue
                if (item.IsFileSystem and os.path.isdir(path)) or KnownCLSID.RECYCLE_BIN in path.upper():
                    folders.append((item.Name or os.path.basename(path) or path, path))
            except Exception:
                logging.debug("Could not read a Quick Access item", exc_info=True)
    except Exception:
        logging.debug("Could not read Quick Access", exc_info=True)
    finally:
        if result >= 0:
            CoUninitialize()
    return folders[:MAX_FOLDERS]


def _terminal_items(app_id: str) -> list[dict[str, Any]]:
    check = app_id.lower()
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if app_id.startswith("path:") and "windowsterminal.exe" in check:
        # A portable install keeps its settings here too
        settings_path = local / "Microsoft" / "Windows Terminal" / "settings.json"
    else:
        package = (
            "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"
            if "windowsterminalpre" in check
            else "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
        )
        settings_path = local / "Packages" / package / "LocalState" / "settings.json"
    try:
        source = settings_path.read_text(encoding="utf-8-sig")
        # Terminal allows comments and trailing commas. Quoted strings can contain either.
        source = re.sub(rf"({_JSON_STRING})|//[^\r\n]*|/\*.*?\*/", lambda match: match[1] or " ", source, flags=re.S)
        source = re.sub(rf"({_JSON_STRING})|,(?=\s*[\]}}])", r"\1", source, flags=re.S)
        section = cast(dict[str, Any], json.loads(source)["profiles"])
        profiles = cast(list[Any], section["list"])
    except OSError, ValueError, KeyError, TypeError:
        logging.debug("Could not read Windows Terminal profiles from %s", settings_path, exc_info=True)
        return []
    defaults = section.get("defaults")
    default_icon = cast(dict[str, object], defaults).get("icon") if isinstance(defaults, dict) else None
    found: list[dict[str, Any]] = []
    for profile in profiles:
        if isinstance(profile, dict):
            profile = cast(dict[str, Any], profile)
            if profile.get("guid") and not profile.get("hidden", False):
                item = _item("profile", str(profile.get("name", "")), app_id, f"-p {profile['guid']}")
                item.update(_terminal_icon(profile.get("icon", default_icon), settings_path.parent))
                found.append(item)
                if len(found) == MAX_PROFILES:
                    break
    return found


def _terminal_icon(value: object, settings_dir: Path) -> dict[str, str]:
    if not isinstance(value, str) or not value.strip():
        return {}

    value = os.path.expandvars(value.strip())
    path = Path(value)
    if path.is_absolute():
        return {"icon": QUrl.fromLocalFile(str(path)).toString()}

    url = QUrl(value)
    if url.isLocalFile():
        return {"icon": url.toString()}
    if url.scheme() == "ms-appdata":
        location, _, filename = url.path().lstrip("/").partition("/")
        if location.lower() == "local" and filename:
            path = settings_dir / filename
        elif location.lower() == "roaming" and settings_dir.name == "LocalState" and filename:
            path = settings_dir.with_name("RoamingState") / filename
        else:
            return {}
    elif url.scheme():
        # Bundled ms-appx assets belong to Terminal. Use the menu's generic glyph for those.
        return {}
    elif path.suffix:
        path = settings_dir / path
    elif any(unicodedata.category(character) == "So" or character == "\u20e3" for character in value):
        return {"iconText": value}
    else:
        return {}

    return {"icon": QUrl.fromLocalFile(str(path)).toString()}

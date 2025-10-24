"""Shortcut discovery helpers for the taskbar pin manager."""

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import win32com.client

from core.utils.win32.aumid import get_aumid_from_shortcut


@lru_cache(maxsize=1)
def get_wscript_shell():
    """Get a cached WScript.Shell COM object for reading shortcut metadata."""
    return win32com.client.Dispatch("WScript.Shell")


@lru_cache(maxsize=1)
def _start_menu_search_roots() -> tuple[Path, ...]:
    """Locate the Start Menu program directories we should scan."""

    roots: list[Path] = []
    for env_var in ("APPDATA", "PROGRAMDATA"):
        base_dir = os.environ.get(env_var)
        if not base_dir:
            continue
        base_path = Path(base_dir) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if base_path.exists():
            roots.append(base_path)
    return tuple(roots)


def normalize_path(path_str: str) -> str:
    """Return a case-insensitive path suitable for cache keys."""

    try:
        return os.path.normcase(str(Path(path_str).resolve()))
    except Exception:
        return os.path.normcase(os.path.abspath(path_str))


def normalized_targets(exe_path: str | None) -> list[str]:
    """
    Produce path variants for versioned apps (Electron, Scoop, etc).
    """

    if not exe_path:
        return []

    try:
        path_obj = Path(exe_path)
        parent = path_obj.parent
        normalized = normalize_path(exe_path)

        # Electron apps: ...\\app-1.2.3\\app.exe -> ...\\appname\\app.exe
        if parent.name.lower().startswith("app-"):
            grandparent = parent.parent
            stable_path = grandparent / path_obj.name
            normalized_stable = os.path.normcase(str(stable_path))
            return [normalized, normalized_stable]

        # Scoop apps: ...\\scoop\\apps\\appname\\1.2.3.4\\app.exe -> ...\\appname\\app.exe
        grandparent = parent.parent
        if grandparent and re.match(r"^\d+[\d.]*$", parent.name):
            path_str_lower = str(path_obj).lower()
            if "\\scoop\\apps\\" in path_str_lower or "/scoop/apps/" in path_str_lower:
                stable_path = grandparent / path_obj.name
                normalized_stable = os.path.normcase(str(stable_path))
                return [normalized, normalized_stable]

        return [normalized]

    except Exception:
        return [normalize_path(exe_path)]


def canonical_display_key(name: str | None) -> str | None:
    """Canonicalise a display string for reliable comparison."""

    if not name:
        return None
    value = name.strip().lower()
    if not value:
        return None
    value = value.replace("-", " ").replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def extract_appname_from_cmdline(command_line: str | None) -> str | None:
    """Extract an AppName token from a command line if present."""

    if not command_line:
        return None

    match = re.search(r"AppName=(?:\"([^\"]+)\"|([^\s].*?))(?=\s[-/]|$)", command_line)
    if not match:
        return None

    value = match.group(1) or match.group(2)
    if not value:
        return None
    return value.strip()


def extract_title_from_cmdline(command_line: str | None) -> str | None:
    """Extract a title hint from command line arguments."""

    if not command_line:
        return None

    patterns = [
        r"(?:--title\s+|--title=)(?:\"([^\"]+)\"|([^\s].*?))(?:\s[-/]|$)",
        r"(?:-title\s+)(?:\"([^\"]+)\"|([^\s].*?))(?:\s[-/]|$)",
        r"Title=(?:\"([^\"]+)\"|([^\s].*?))(?:\s[-/]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, command_line, re.IGNORECASE)
        if match:
            value = match.group(1) or match.group(2)
            if value:
                return value.strip()
    return None


def find_shortcut_by_name(
    candidate_names: Iterable[str | None],
    *,
    shortcut_name_cache: dict[str, str],
) -> tuple[str, str] | None:
    """Find a Start Menu shortcut whose filename matches any candidate name."""

    normalized = []
    for name in candidate_names:
        canonical = canonical_display_key(name)
        if canonical:
            normalized.append(canonical)

    if not normalized:
        return None

    # Check cached entries first
    for name in normalized:
        cached_path = shortcut_name_cache.get(name)
        if cached_path and os.path.exists(cached_path):
            return cached_path, Path(cached_path).stem
        if cached_path and not os.path.exists(cached_path):
            shortcut_name_cache.pop(name, None)

    for base_path in _start_menu_search_roots():
        if not base_path.exists():
            continue
        try:
            for shortcut_file in base_path.rglob("*.lnk"):
                stem = canonical_display_key(shortcut_file.stem)
                if not stem:
                    continue
                if stem in normalized:
                    shortcut_str = str(shortcut_file)
                    shortcut_name_cache[stem] = shortcut_str
                    return shortcut_str, shortcut_file.stem
        except Exception:
            continue

    return None


def find_shortcut_by_aumid(aumid: str) -> tuple[str, str] | None:
    """
    Find a shortcut in Start Menu that has the specified AUMID embedded.
    This is the same method Windows uses for taskbar pinning.

    Args:
        aumid: The AppUserModelID to search for

    Returns:
        Tuple of (shortcut_path, shortcut_name) if found, None otherwise
    """
    if not aumid:
        return None

    for base_path in _start_menu_search_roots():
        if not base_path.exists():
            continue

        try:
            for lnk_file in base_path.rglob("*.lnk"):
                try:
                    shortcut_aumid = get_aumid_from_shortcut(str(lnk_file))
                    if shortcut_aumid == aumid:
                        return str(lnk_file), lnk_file.stem
                except Exception:
                    # Skip shortcuts we can't read
                    continue
        except Exception:
            continue

    return None


def find_app_shortcut(
    exe_path: str,
    *,
    candidate_names: Iterable[str | None],
    shortcut_cache: dict[str, str],
) -> tuple[str, str] | None:
    """Find a shortcut that targets the provided executable."""

    if not exe_path:
        return None

    try:
        if Path(exe_path).name.lower() == "explorer.exe":
            return None
    except Exception:
        if os.path.basename(exe_path).lower() == "explorer.exe":
            return None

    target_variants = normalized_targets(exe_path)
    if not target_variants:
        return None

    # Check cache first to avoid repeated filesystem scans
    for key in target_variants:
        cached_shortcut_path = shortcut_cache.get(key)
        if cached_shortcut_path and isinstance(cached_shortcut_path, str):
            if os.path.exists(cached_shortcut_path):
                return cached_shortcut_path, Path(cached_shortcut_path).stem
            shortcut_cache.pop(key, None)

    try:
        wsh = get_wscript_shell()
    except Exception as exc:
        logging.debug("Could not get WScript.Shell to inspect shortcuts: %s", exc)
        return None

    best_match_path: str | None = None
    best_match_name: str | None = None
    best_score = -1
    candidate_terms = [c.lower() for c in candidate_names if c]
    checked_shortcuts = 0

    exe_name = Path(exe_path).stem.lower()

    for base_path in _start_menu_search_roots():
        if not base_path.exists():
            continue

        try:
            for lnk_file in base_path.rglob("*.lnk"):
                try:
                    shortcut = wsh.CreateShortcut(str(lnk_file))
                    target = shortcut.Targetpath or ""
                    if not target:
                        continue

                    normalized_shortcut_target = normalize_path(target)
                    shortcut_name = lnk_file.stem
                    lower_name = shortcut_name.lower()
                    checked_shortcuts += 1

                    is_match = False
                    if normalized_shortcut_target in target_variants:
                        is_match = True
                    elif exe_name == lower_name:
                        is_match = True

                    if not is_match:
                        continue

                    score = 0
                    for idx, term in enumerate(candidate_terms):
                        if lower_name == term:
                            score = max(score, 100 - idx * 10)
                        elif term and term in lower_name:
                            score = max(score, 70 - idx * 10)

                    if best_match_path is None or score > best_score:
                        best_match_path = str(lnk_file)
                        best_match_name = shortcut_name
                        best_score = score
                    if best_score >= 100:
                        break
                except Exception:
                    continue
        except Exception:
            continue

        if best_score >= 100:
            break

    if best_match_path is not None:
        for key in target_variants:
            shortcut_cache[key] = best_match_path
        return best_match_path, best_match_name

    logging.debug("No shortcut found for %s after scanning %s shortcuts", exe_path, checked_shortcuts)
    return None

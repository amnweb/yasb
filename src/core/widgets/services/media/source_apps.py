"""
Resolve SMTC SourceAppUserModelId to a display name for the media widget.
"""

import os
from pathlib import Path

import win32gui
import win32process
from winrt.windows.applicationmodel import AppInfo

from core.utils.win32.aumid import get_aumid_for_window, get_aumid_from_shortcut
from core.utils.win32.utils import get_app_name_from_aumid, get_app_name_from_pid
from core.widgets.services.media.aumid_process import _enum_processes, get_process_name_for_aumid

_PWA_KNOWN_FOLDERS = ("Chrome Apps", "Brave Apps", "Edge Apps", "Firefox Web Apps")

_name_cache: dict[str, str] = {}
_pwa_shortcuts: dict[str, str] | None = None


def _humanize(aumid: str) -> str:
    if aumid.lower().endswith(".exe"):
        return os.path.splitext(os.path.basename(aumid))[0]
    if "!" in aumid:
        return aumid.split("!")[-1]
    last = aumid.split(".")[-1] if "." in aumid else aumid
    return last.replace("-", " ").replace("_", " ")


def _appinfo_name(aumid: str) -> str | None:
    try:
        name = AppInfo.get_from_app_user_model_id(aumid).display_info.display_name
        return name.strip() if name else None
    except Exception:
        return None


def _load_pwa_shortcuts() -> dict[str, str]:
    """Start Menu PWA .lnk files: aumid -> shortcut name."""
    global _pwa_shortcuts
    if _pwa_shortcuts is not None:
        return _pwa_shortcuts

    mapping: dict[str, str] = {}
    programs = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
    for folder in _PWA_KNOWN_FOLDERS:
        path = programs / folder
        if not path.is_dir():
            continue
        try:
            for lnk in path.glob("*.lnk"):
                aumid = get_aumid_from_shortcut(str(lnk))
                if aumid:
                    mapping[aumid] = lnk.stem
        except OSError:
            continue
    _pwa_shortcuts = mapping
    return mapping


def _find_pwa(aumid: str, title: str | None = None) -> tuple[str, str] | None:
    """
    Find an installed browser PWA for this SMTC session.

    Returns (pwa_aumid, display_name) or None.

    Chromium reports the PWA AUMID on the session (matches the .lnk).
    Firefox reports the browser AUMID, then match media title to an open
    window that carries the PWA AUMID.
    """
    shortcuts = _load_pwa_shortcuts()
    if not shortcuts:
        return None

    if aumid in shortcuts:
        return aumid, shortcuts[aumid]

    needle = (title or "").strip().lower()
    if not needle:
        return None

    prefix = needle[:32] if len(needle) >= 8 else None
    found: list[tuple[str, str]] = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        wa = get_aumid_for_window(hwnd)
        if not wa or wa not in shortcuts:
            return True
        wt = win32gui.GetWindowText(hwnd)
        if not wt:
            return True
        wtl = wt.lower()
        if needle in wtl or (prefix and prefix in wtl):
            found.append((wa, shortcuts[wa]))
            return False
        return True

    win32gui.EnumWindows(_enum, None)
    return found[0] if found else None


def _pwa_name(aumid: str, title: str | None = None) -> str | None:
    match = _find_pwa(aumid, title)
    return match[1] if match else None


def resolve_activate_aumid(aumid: str, *, title: str | None = None) -> str:
    """AUMID to focus for open_media_source (PWA window when applicable)."""
    match = _find_pwa(aumid, title)
    return match[0] if match else aumid


def _pid_for_exe(exe_name: str) -> int | None:
    target = exe_name.lower()
    for pid, exe in _enum_processes():
        if exe and os.path.basename(str(exe)).lower() == target:
            return pid
    return None


def _name_from_process(aumid: str) -> str | None:
    """Process AUMID / Electron heuristics -> FileDescription."""
    proc = get_process_name_for_aumid(aumid)
    if not proc:
        return None
    pid = _pid_for_exe(proc)
    if pid:
        name = get_app_name_from_pid(pid)
        if name:
            return name
    return os.path.splitext(proc)[0]


def _name_from_window(aumid: str) -> str | None:
    """Window AppUserModelID (Firefox/Zen hashes) -> FileDescription."""
    result: list[int] = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if get_aumid_for_window(hwnd) != aumid:
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid:
            result.append(pid)
            return False
        return True

    win32gui.EnumWindows(_enum, None)
    return get_app_name_from_pid(result[0]) if result else None


def resolve_source_app_name(aumid: str, *, title: str | None = None) -> str | None:
    """Resolve AUMID to display name. Cached per AUMID (PWA title matches are not cached)."""
    if not aumid:
        return None

    name = _pwa_name(aumid, title)
    if name:
        return name

    cached = _name_cache.get(aumid)
    if cached is not None:
        return cached

    name = _appinfo_name(aumid)
    if not name and "!" in aumid:
        name = get_app_name_from_aumid(aumid)
    if not name:
        name = _name_from_process(aumid)
    if not name:
        name = _name_from_window(aumid)
    if not name:
        name = _humanize(aumid)

    _name_cache[aumid] = name
    return name


def get_source_app_class_name(display_name: str) -> str | None:
    if display_name:
        return display_name.lower().replace(" ", "-")
    return None

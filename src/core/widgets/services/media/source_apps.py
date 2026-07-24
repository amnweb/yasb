"""
Resolve SMTC SourceAppUserModelId to a display name for the media widget.
"""

import os

from winrt.windows.applicationmodel import AppInfo

from core.utils.win32.utils import get_app_name_from_aumid, get_app_name_from_pid
from core.widgets.services.media.aumid_process import (
    _enum_processes,
    get_pid_for_window_aumid,
    get_process_name_for_aumid,
    resolve_shell_app,
)

_name_cache: dict[str, str] = {}


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


def _pid_for_exe(exe_name: str) -> int | None:
    target = exe_name.lower()
    for pid, exe in _enum_processes():
        if exe and os.path.basename(str(exe)).lower() == target:
            return pid
    return None


def _name_from_process(aumid: str) -> str | None:
    """Process / shell exe -> FileDescription."""
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
    pid = get_pid_for_window_aumid(aumid)
    return get_app_name_from_pid(pid) if pid else None


def resolve_source_app_name(aumid: str) -> str | None:
    """Resolve AUMID to display name. Cached per AUMID."""
    if not aumid:
        return None

    cached = _name_cache.get(aumid)
    if cached is not None:
        return cached

    name = _appinfo_name(aumid)
    if not name and "!" in aumid:
        name = get_app_name_from_aumid(aumid)
    # Shell app name before process lookup so PWAs are not labeled as the browser.
    # Skip .exe SMTC ids process path is enough.
    if not name and not aumid.lower().endswith(".exe"):
        name, _ = resolve_shell_app(aumid)
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

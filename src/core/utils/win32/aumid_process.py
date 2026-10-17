"""
Lookup process executable name from an AppUserModelID (AUMID).
"""

import os

from win32com.client import Dispatch

from core.utils.win32.aumid import get_aumid_for_process, get_pid_for_window_aumid
from core.utils.win32.bindings.kernel32 import snapshot_processes
from core.utils.win32.utils import get_process_path

# AUMID -> (app_display_name, process_exe); negative results cached too.
_shell_app_cache: dict[str, tuple[str | None, str | None]] = {}


def resolve_shell_app(aumid: str) -> tuple[str | None, str | None]:
    """Resolve AUMID via shell:AppsFolder to (app display name, process exe).

    One ParseName: item.Name + System.Link.TargetParsingPath. Cached.
    """
    if not aumid:
        return None, None

    cached = _shell_app_cache.get(aumid)
    if cached is not None:
        return cached

    display_name: str | None = None
    process_exe: str | None = None
    try:
        folder = Dispatch("Shell.Application").NameSpace("shell:AppsFolder")
        item = folder.ParseName(aumid) if folder else None
        if item:
            raw_name = item.Name
            if raw_name:
                display_name = str(raw_name).strip() or None
            target = item.ExtendedProperty("System.Link.TargetParsingPath")
            if target:
                process_exe = os.path.basename(str(target)) or None
    except Exception:
        pass

    _shell_app_cache[aumid] = (display_name, process_exe)
    return display_name, process_exe


def get_process_name_for_aumid(aumid: str) -> str | None:
    """Resolve AUMID -> exe name the way Windows associates apps with processes.

    1. SMTC sometimes uses the exe name as the AUMID
    2. GetApplicationUserModelId(process) == aumid
    3. Window PKEY_AppUserModel_ID == aumid -> that window's process
    4. shell AppsFolder TargetParsingPath (when process/window AUMID missing)
    """
    if not aumid:
        return None

    if aumid.lower().endswith(".exe"):
        return os.path.basename(aumid)

    for process in snapshot_processes():
        if get_aumid_for_process(process.pid) == aumid:
            name = os.path.basename(process.exe)
            # Edge PWA host process
            if name.lower() == "pwahelper.exe":
                return "msedge.exe"
            return name

    pid = get_pid_for_window_aumid(aumid)
    if pid:
        path = get_process_path(pid)
        if path:
            return os.path.basename(path)
        for process in snapshot_processes():
            if process.pid == pid and process.exe:
                return os.path.basename(process.exe)

    _, process_exe = resolve_shell_app(aumid)
    return process_exe

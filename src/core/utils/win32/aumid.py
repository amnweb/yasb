"""
This module provides utilities for working with App User Model IDs (AUMIDs).
It includes functions to retrieve the AUMID for a given window handle or shortcut file.
It uses the Windows Shell API to access properties of application windows.
"""

import os
from ctypes import byref
from ctypes.wintypes import DWORD

from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    GetApplicationUserModelId,
    OpenProcess,
    snapshot_processes,
)
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import (
    SHGetPropertyStoreForWindow,
    SHGetPropertyStoreFromParsingName,
    get_string_property,
)
from core.utils.win32.bindings.user32 import (
    EnumWindows,
    GetClassName,
    GetWindowTextLength,
    GetWindowThreadProcessId,
    IsIconic,
    IsWindowVisible,
)
from core.utils.win32.constants import PROCESS_QUERY_LIMITED_INFORMATION, PKEY_AppUserModel_ID
from core.utils.win32.structs import WNDENUMPROC


def get_aumid_for_window(hwnd: int) -> str | None:
    """Return the AUMID for a window.
    1. Try PKEY_AppUserModel_ID from the window's IPropertyStore.
    2. Fallback: Query the process AUMID using GetApplicationUserModelId for the window's PID.
    """
    CoInitialize()

    store = SHGetPropertyStoreForWindow(hwnd)
    if store is not None:
        aumid = get_string_property(store, PKEY_AppUserModel_ID)
        if aumid is not None:
            return aumid

    return get_aumid_for_process(_window_pid(hwnd))


def get_aumid_for_process(pid: int) -> str | None:
    """The AUMID a process runs under (Store apps, and apps that set their own), or None."""
    if not pid:
        return None
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        return None
    try:
        return GetApplicationUserModelId(process)
    finally:
        CloseHandle(process)


def get_aumid_from_shortcut(shortcut_path: str) -> str | None:
    """
    Read AUMID from a .lnk file using IPropertyStore.

    Args:
        shortcut_path: Full path to a .lnk file

    Returns:
        AUMID string if the shortcut has one embedded, None otherwise
    """
    CoInitialize()

    if not os.path.exists(shortcut_path):
        return None

    store = SHGetPropertyStoreFromParsingName(shortcut_path)
    if store is None:
        return None
    return get_string_property(store, PKEY_AppUserModel_ID)


def _pids_for_exe_tree(process_name: str) -> set[int]:
    """PIDs whose exe basename matches process_name, plus all descendants.

    Covers portable/Squirrel apps where the launcher holds the AUMID but the
    UI window lives on a child process with a different exe name.
    """
    target = process_name.lower()
    children: dict[int, list[int]] = {}
    roots: set[int] = set()

    for entry in snapshot_processes():
        children.setdefault(entry.parent_pid, []).append(entry.pid)
        if entry.exe and entry.exe.lower() == target:
            roots.add(entry.pid)

    result: set[int] = set()
    stack = list(roots)
    while stack:
        pid = stack.pop()
        if pid in result:
            continue
        result.add(pid)
        stack.extend(children.get(pid, []))
    return result


def activate_app_by_aumid(aumid: str, fallback_process_name: str | None = None) -> bool:
    """
    Find and activate a window for the given AUMID.

    Args:
        aumid: The App User Model ID to find.
        fallback_process_name: Optional process name (e.g. "firefox.exe") to match if AUMID fails.
            Also matches descendant processes (portable Electron launchers).

    Returns:
        True if a window was found and activation was attempted, False otherwise.
    """
    from core.utils.win32.window_actions import restore_window, set_foreground

    hwnd = _find_window_by_aumid(aumid, fallback_process_name)
    if hwnd is None:
        return False

    if IsIconic(hwnd):
        restore_window(hwnd)
    set_foreground(hwnd)
    return True


def _find_window_by_aumid(aumid: str, fallback_process_name: str | None) -> int | None:
    windows = _visible_top_level_windows()
    for hwnd in windows:
        if get_aumid_for_window(hwnd) == aumid:
            return hwnd

    if fallback_process_name:
        fallback_pids = _pids_for_exe_tree(fallback_process_name)
        for hwnd in windows:
            # Skip untitled helper windows of the same process
            if _window_pid(hwnd) in fallback_pids and GetWindowTextLength(hwnd) > 0:
                return hwnd

    return None


def get_pid_for_window_aumid(aumid: str) -> int | None:
    """PID of a visible window whose AppUserModelID matches, ignoring case (shell property store)."""
    if not aumid:
        return None

    target = aumid.lower()
    for hwnd in _top_level_windows():
        if not IsWindowVisible(hwnd):
            continue
        window_aumid = get_aumid_for_window(hwnd)
        if window_aumid and window_aumid.lower() == target:
            pid = _window_pid(hwnd)
            if pid:
                return pid
    return None


def _top_level_windows() -> list[int]:
    hwnds: list[int] = []

    def collect(hwnd: int, _: int) -> bool:
        hwnds.append(hwnd)
        return True

    EnumWindows(WNDENUMPROC(collect), 0)
    return hwnds


def _visible_top_level_windows() -> list[int]:
    # minimized Store apps leave their CoreWindow as a cloaked top-level window, restore the frame instead
    return [
        hwnd
        for hwnd in _top_level_windows()
        if IsWindowVisible(hwnd) and GetClassName(hwnd) != "Windows.UI.Core.CoreWindow"
    ]


def _window_pid(hwnd: int) -> int:
    pid = DWORD(0)
    GetWindowThreadProcessId(hwnd, byref(pid))
    return pid.value

"""
Lookup process executable name from an AppUserModelID (AUMID).
"""

import ctypes
import ctypes.wintypes as wt
import os
from ctypes import POINTER, byref, c_void_p

import win32gui
import win32process
from win32com.client import Dispatch

from core.utils.win32.aumid import get_aumid_for_window
from core.utils.win32.constants import PROCESS_QUERY_LIMITED_INFORMATION, TH32CS_SNAPPROCESS
from core.utils.win32.structs import PROCESSENTRY32

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
CreateToolhelp32Snapshot.restype = wt.HANDLE

Process32First = kernel32.Process32FirstW
Process32First.argtypes = [wt.HANDLE, c_void_p]
Process32First.restype = wt.BOOL

Process32Next = kernel32.Process32NextW
Process32Next.argtypes = [wt.HANDLE, c_void_p]
Process32Next.restype = wt.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wt.HANDLE]
CloseHandle.restype = wt.BOOL

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE

ERROR_INSUFFICIENT_BUFFER = 0x7A

GetApplicationUserModelId = None
for dll_name in ("kernel32", "shell32"):
    try:
        dll = ctypes.WinDLL(dll_name, use_last_error=True)
        fn = getattr(dll, "GetApplicationUserModelId")
        fn.argtypes = [wt.HANDLE, POINTER(ctypes.c_uint32), wt.LPWSTR]
        fn.restype = ctypes.c_long
        GetApplicationUserModelId = fn
        break
    except OSError:
        continue

# AUMID -> (app_display_name, process_exe); negative results cached too.
_shell_app_cache: dict[str, tuple[str | None, str | None]] = {}


def _enum_processes():
    """Yield (pid, exe_name) for running processes."""
    hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnap == wt.HANDLE(-1).value:
        return
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not Process32First(hSnap, ctypes.byref(pe)):
            return
        while True:
            yield pe.th32ProcessID, pe.szExeFile
            if not Process32Next(hSnap, ctypes.byref(pe)):
                break
    finally:
        CloseHandle(hSnap)


def get_process_image_path(pid: int) -> str | None:
    """Return full image path for a PID using QueryFullProcessImageNameW."""
    try:
        hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not hProc:
            return None
        try:
            QueryFullProcessImageName = kernel32.QueryFullProcessImageNameW
            QueryFullProcessImageName.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
            QueryFullProcessImageName.restype = wt.BOOL
            size = wt.DWORD(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if QueryFullProcessImageName(hProc, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            try:
                CloseHandle(hProc)
            except Exception:
                pass
    except OSError:
        pass
    return None


def get_pid_for_window_aumid(aumid: str) -> int | None:
    """PID of a visible window whose AppUserModelID matches (shell property store)."""
    if not aumid:
        return None

    target = aumid.lower()
    found: list[int] = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        wa = get_aumid_for_window(hwnd)
        if not wa or wa.lower() != target:
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid:
            found.append(pid)
            return False
        return True

    win32gui.EnumWindows(_enum, None)
    return found[0] if found else None


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

    if GetApplicationUserModelId is not None:
        for pid, exe in _enum_processes():
            hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not hProc:
                continue
            try:
                length = ctypes.c_uint32(0)
                res = GetApplicationUserModelId(hProc, byref(length), None)
                if res == ERROR_INSUFFICIENT_BUFFER and length.value:
                    buf = ctypes.create_unicode_buffer(length.value)
                    res = GetApplicationUserModelId(hProc, byref(length), buf)
                    if res == 0 and buf.value == aumid:
                        name = os.path.basename(exe)
                        # Edge PWA host process
                        if name.lower() == "pwahelper.exe":
                            return "msedge.exe"
                        return name
            except OSError:
                pass
            finally:
                try:
                    CloseHandle(hProc)
                except OSError:
                    pass

    pid = get_pid_for_window_aumid(aumid)
    if pid:
        path = get_process_image_path(pid)
        if path:
            return os.path.basename(path)
        for p, exe in _enum_processes():
            if p == pid and exe:
                return os.path.basename(str(exe))

    _, process_exe = resolve_shell_app(aumid)
    return process_exe

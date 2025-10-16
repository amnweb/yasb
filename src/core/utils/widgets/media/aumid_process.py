"""
Lookup process executable name from an AppUserModelID (AUMID).
"""

import ctypes
import ctypes.wintypes as wt
import os
import re
from ctypes import POINTER, byref, c_void_p

# Constants and API bindings
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Toolhelp snapshot
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

# Constants
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_INSUFFICIENT_BUFFER = 0x7A


# PROCESSENTRY32 structure
class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wt.ULONG)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


# GetApplicationUserModelId may be in kernel32 or shell32
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
            pid = pe.th32ProcessID
            exe = pe.szExeFile
            yield pid, exe
            if not Process32Next(hSnap, ctypes.byref(pe)):
                break
    finally:
        CloseHandle(hSnap)


def get_process_name_for_aumid(aumid: str) -> str | None:
    """Return process executable base name for the first process whose
    GetApplicationUserModelId() matches the provided `aumid`.

    Returns None if not found.
    """
    if not aumid:
        return None

    if GetApplicationUserModelId is None:
        return None

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
                if res == 0 and buf.value:
                    if buf.value == aumid:
                        name = os.path.basename(exe)
                        # PWAHelper.exe is used for PWAs hosted in Edge
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

    try:
        res = _aumid_heuristic_fallback(aumid)
        if res:
            return res
    except Exception:
        pass

    return None


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


def _search_processes_by_vendor_name(vendor: str) -> str | None:
    vendor_l = vendor.lower()
    for pid, exe in _enum_processes():
        try:
            # check snapshot exe name
            if exe and vendor_l in str(exe).lower():
                return os.path.basename(str(exe))
            # check image path
            path = get_process_image_path(pid)
            if path and vendor_l in path.lower():
                return os.path.basename(path)
        except OSError:
            continue
    return None


def _aumid_heuristic_fallback(aumid: str) -> str | None:
    """Heuristics for non-standard AUMIDs (Brave PWAs, Electron apps, etc.)."""
    if not aumid:
        return None

    if re.match(r"^Brave\._crx_[A-Za-z0-9_-]+$", aumid, re.IGNORECASE):
        return "brave.exe"

    if re.match(r"^Chrome\._crx_[A-Za-z0-9_-]+$", aumid, re.IGNORECASE):
        return "chrome.exe"

    # Electron packaged apps often use reverse domain AUMIDs like com.github.*
    if aumid.startswith("com.") or aumid.count(".") >= 2:
        # try to match by exe basename containing last segment
        last = aumid.split(".")[-1]
        res = _search_processes_by_vendor_name(last)
        if res:
            return res

    return None

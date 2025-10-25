"""
This module provides utilities for working with App User Model IDs (AUMIDs).
It includes functions to retrieve the AUMID for a given window handle or shortcut file.
It uses the Windows Shell API to access properties of application windows.
"""

import ctypes
import ctypes.wintypes as wt
from ctypes import POINTER, WINFUNCTYPE, byref, c_void_p


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, guid_str: str):
        super().__init__()
        import uuid

        u = uuid.UUID(guid_str)
        self.Data1 = u.time_low
        self.Data2 = u.time_mid
        self.Data3 = u.time_hi_version
        d4 = u.bytes[8:]
        for i in range(8):
            self.Data4[i] = d4[i]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


class PROPVARIANT_UNION(ctypes.Union):
    _fields_ = [
        ("pwszVal", wt.LPWSTR),
        ("pszVal", wt.LPSTR),
        ("ulVal", ctypes.c_uint32),
        ("uhVal", ctypes.c_uint64),
        ("boolVal", wt.VARIANT_BOOL),
    ]


class PROPVARIANT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ubyte),
        ("wReserved2", ctypes.c_ubyte),
        ("wReserved3", ctypes.c_ubyte),
        ("data", PROPVARIANT_UNION),
    ]


VT_LPWSTR = 31


IID_IPropertyStore = GUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
PKEY_AppUserModel_ID = PROPERTYKEY(GUID("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)


class IPropertyStoreVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))),
        ("AddRef", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("Release", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("GetCount", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(ctypes.c_uint))),
        ("GetAt", WINFUNCTYPE(ctypes.c_long, c_void_p, ctypes.c_uint, POINTER(PROPERTYKEY))),
        ("GetValue", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))),
        ("SetValue", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))),
        ("Commit", WINFUNCTYPE(ctypes.c_long, c_void_p)),
    ]


class IPropertyStore(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(IPropertyStoreVtbl))]


shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SHGetPropertyStoreForWindow = shell32.SHGetPropertyStoreForWindow
SHGetPropertyStoreForWindow.argtypes = [wt.HWND, POINTER(GUID), POINTER(c_void_p)]
SHGetPropertyStoreForWindow.restype = ctypes.c_long

# SHGetPropertyStoreFromParsingName - to read properties from files (shortcuts)
SHGetPropertyStoreFromParsingName = shell32.SHGetPropertyStoreFromParsingName
SHGetPropertyStoreFromParsingName.argtypes = [wt.LPCWSTR, c_void_p, ctypes.c_uint32, POINTER(GUID), POINTER(c_void_p)]
SHGetPropertyStoreFromParsingName.restype = ctypes.c_long

# PropVariantClear is exported by Ole32.dll
PropVariantClear = ole32.PropVariantClear
PropVariantClear.argtypes = [POINTER(PROPVARIANT)]
PropVariantClear.restype = ctypes.c_long

CoInitialize = ole32.CoInitialize
CoInitialize.argtypes = [c_void_p]
CoInitialize.restype = ctypes.c_long

# Additional APIs for process-based fallback
# Get PID for a HWND
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wt.HWND, POINTER(wt.DWORD)]
GetWindowThreadProcessId.restype = wt.DWORD

# Open/close process
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wt.HANDLE]
CloseHandle.restype = wt.BOOL

# GetApplicationUserModelId(HANDLE, PUINT32, PWSTR)
GetApplicationUserModelId = None  # type: ignore
for dll in (kernel32, shell32):
    if GetApplicationUserModelId is not None:
        break
    try:
        fn = getattr(dll, "GetApplicationUserModelId")
        fn.argtypes = [wt.HANDLE, POINTER(ctypes.c_uint32), wt.LPWSTR]
        fn.restype = ctypes.c_long
        GetApplicationUserModelId = fn  # type: ignore
    except AttributeError:
        continue

# Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_INSUFFICIENT_BUFFER = 0x7A
GPS_DEFAULT = 0  # Default flags for SHGetPropertyStoreFromParsingName


def _ensure_com_initialized():
    try:
        # COINIT_APARTMENTTHREADED is default for CoInitialize
        hr = CoInitialize(None)
        # Ignore S_OK (0), S_FALSE (1) and RPC_E_CHANGED_MODE (0x80010106)
        return hr
    except Exception:
        return 0


def get_aumid_for_window(hwnd: int) -> str | None:
    """Return the AUMID for a window.
    1. Try PKEY_AppUserModel_ID from the window's IPropertyStore.
    2. Fallback: Query the process AUMID using GetApplicationUserModelId for the window's PID.
    """
    _ensure_com_initialized()

    # 1) Window property store
    store_ptr = c_void_p()
    hr = SHGetPropertyStoreForWindow(wt.HWND(hwnd), byref(IID_IPropertyStore), byref(store_ptr))
    if hr == 0 and store_ptr.value:
        store = ctypes.cast(store_ptr, POINTER(IPropertyStore))
        pv = PROPVARIANT()
        try:
            hr = store.contents.lpVtbl.contents.GetValue(store, byref(PKEY_AppUserModel_ID), byref(pv))
            if hr == 0 and pv.vt == VT_LPWSTR and pv.pwszVal:
                return ctypes.wstring_at(pv.pwszVal)
        finally:
            PropVariantClear(byref(pv))
            # Release IPropertyStore
            try:
                store.contents.lpVtbl.contents.Release(store)
            except Exception:
                pass

    # Process-based fallback (if API available)
    pid = wt.DWORD(0)
    GetWindowThreadProcessId(wt.HWND(hwnd), byref(pid))
    if pid.value != 0 and GetApplicationUserModelId is not None:
        hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if hProcess:
            try:
                length = ctypes.c_uint32(0)
                res = GetApplicationUserModelId(hProcess, byref(length), None)
                if res == ERROR_INSUFFICIENT_BUFFER and length.value:
                    buf = ctypes.create_unicode_buffer(length.value)
                    res = GetApplicationUserModelId(hProcess, byref(length), buf)
                    if res == 0 and buf.value:
                        return buf.value
            finally:
                try:
                    CloseHandle(hProcess)
                except Exception:
                    pass

    return None


def get_aumid_from_shortcut(shortcut_path: str) -> str | None:
    """
    Read AUMID from a .lnk file using IPropertyStore.

    Args:
        shortcut_path: Full path to a .lnk file

    Returns:
        AUMID string if the shortcut has one embedded, None otherwise
    """
    import os

    _ensure_com_initialized()

    if not os.path.exists(shortcut_path):
        return None

    store_ptr = c_void_p()
    hr = SHGetPropertyStoreFromParsingName(
        shortcut_path, None, GPS_DEFAULT, byref(IID_IPropertyStore), byref(store_ptr)
    )

    if hr != 0 or not store_ptr.value:
        return None

    store = ctypes.cast(store_ptr, POINTER(IPropertyStore))
    pv = PROPVARIANT()
    aumid = None

    try:
        hr = store.contents.lpVtbl.contents.GetValue(store, byref(PKEY_AppUserModel_ID), byref(pv))
        if hr == 0 and pv.vt == VT_LPWSTR and pv.pwszVal:
            aumid = ctypes.wstring_at(pv.pwszVal)
    finally:
        PropVariantClear(byref(pv))
        try:
            store.contents.lpVtbl.contents.Release(store)
        except Exception:
            pass

    return aumid

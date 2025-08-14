"""
This module provides utilities for working with App User Model IDs (AUMIDs).
It includes functions to retrieve the AUMID for a given window handle and to extract icons for UWP apps based on their AUMID.
It uses the Windows Shell API to access properties of application windows and extract icons.
"""

import ctypes
import ctypes.wintypes as wt
from ctypes import POINTER, WINFUNCTYPE, byref, c_void_p

from PIL import Image

from core.utils.win32.bindings import DeleteObject, GetDC, GetDIBits, GetObject, ReleaseDC
from core.utils.win32.structs import BITMAP, BITMAPINFO, BITMAPINFOHEADER


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


# IShellItemImageFactory based icon extraction from AppsFolder\\<AUMID>
IID_IShellItemImageFactory = GUID("BCC18B79-BA16-442F-80C4-8A59C30C463B")


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class IShellItemImageFactoryVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))),
        ("AddRef", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("Release", WINFUNCTYPE(ctypes.c_ulong, c_void_p)),
        ("GetImage", WINFUNCTYPE(ctypes.c_long, c_void_p, SIZE, ctypes.c_int, POINTER(wt.HBITMAP))),
    ]


class IShellItemImageFactory(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(IShellItemImageFactoryVtbl))]


SHCreateItemFromParsingName = shell32.SHCreateItemFromParsingName
SHCreateItemFromParsingName.argtypes = [wt.LPCWSTR, c_void_p, POINTER(GUID), POINTER(c_void_p)]
SHCreateItemFromParsingName.restype = ctypes.c_long


# SIIGBF flags
# https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ishellitemimagefactory-getimage
SIIGBF_RESIZETOFIT = 0x00
SIIGBF_BIGGERSIZEOK = 0x01
SIIGBF_MEMORYONLY = 0x02
SIIGBF_ICONONLY = 0x04
SIIGBF_THUMBNAILONLY = 0x08
SIIGBF_INCACHEONLY = 0x10


def _hbitmap_to_image(hbitmap: int) -> Image.Image | None:
    # Get bitmap info
    bmp = BITMAP()
    res = GetObject(wt.HBITMAP(hbitmap), ctypes.sizeof(BITMAP), ctypes.byref(bmp))
    if res == 0:
        return None

    width, height = bmp.bmWidth, bmp.bmHeight
    # Prepare BITMAPINFO
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -abs(height)
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32

    buf_size = width * height * 4
    pixel_buffer = (ctypes.c_byte * buf_size)()

    hdc = GetDC(None)
    try:
        n = GetDIBits(
            hdc,
            wt.HBITMAP(hbitmap),
            0,
            height,
            ctypes.byref(pixel_buffer),
            ctypes.byref(bi),
            0,
        )
        if n == 0:
            return None
        # Convert buffer to bytes and interpret as BGRA
        raw_bytes = ctypes.string_at(ctypes.addressof(pixel_buffer), buf_size)
        return Image.frombuffer("RGBA", (width, height), raw_bytes, "raw", "BGRA", 0, 1)
    finally:
        ReleaseDC(None, hdc)
        try:
            DeleteObject(wt.HBITMAP(hbitmap))
        except Exception:
            pass


def get_icon_for_aumid(aumid: str, size: int = 48) -> Image.Image | None:
    if not aumid:
        return None

    _ensure_com_initialized()
    path = f"shell:AppsFolder\\{aumid}"
    ppv = c_void_p()
    hr = SHCreateItemFromParsingName(path, None, byref(IID_IShellItemImageFactory), byref(ppv))
    if hr != 0 or not ppv.value:
        return None

    factory = ctypes.cast(ppv, POINTER(IShellItemImageFactory))
    hbmp = wt.HBITMAP()
    try:
        sz = SIZE(size, size)
        flags = SIIGBF_ICONONLY | SIIGBF_BIGGERSIZEOK
        hr = factory.contents.lpVtbl.contents.GetImage(factory, sz, flags, byref(hbmp))
        if hr != 0 or not hbmp.value:
            return None
        return _hbitmap_to_image(hbmp.value)
    finally:
        try:
            factory.contents.lpVtbl.contents.Release(factory)
        except Exception:
            pass

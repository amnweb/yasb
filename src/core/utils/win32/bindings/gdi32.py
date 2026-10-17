"""Wrappers for gdi32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    WinDLL,
    c_int,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HDC,
    LPCWSTR,
    LPVOID,
)

from core.utils.win32.structs import (
    BITMAPINFO,
    HBITMAP,
)
from core.utils.win32.typecheck import CArgObject

gdi32 = WinDLL("gdi32", use_last_error=True)

gdi32.GetObjectW.argtypes = [HANDLE, c_int, LPVOID]
gdi32.GetObjectW.restype = c_int

gdi32.GetDIBits.argtypes = [HDC, HBITMAP, DWORD, DWORD, LPVOID, POINTER(BITMAPINFO), DWORD]
gdi32.GetDIBits.restype = c_int

gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteObject.restype = BOOL

gdi32.AddFontResourceExW.argtypes = [LPCWSTR, DWORD, LPVOID]
gdi32.AddFontResourceExW.restype = c_int


def GetDIBits(
    hdc: int,
    hbmp: HBITMAP,
    uStartScan: int,
    cScanLines: int,
    lpvBits: CArgObject,
    lpbi: CArgObject,
    uUsage: int,
) -> int:
    return gdi32.GetDIBits(hdc, hbmp, uStartScan, cScanLines, lpvBits, lpbi, uUsage)


def DeleteObject(hObject: int) -> bool:
    return gdi32.DeleteObject(hObject)


def GetObject(hgdiobj: int, cbBuffer: int, lpvObject: CArgObject) -> int:
    return gdi32.GetObjectW(hgdiobj, cbBuffer, lpvObject)


def AddFontResourceEx(name: str, fl: int = 0) -> int:
    return gdi32.AddFontResourceExW(name, fl, None)

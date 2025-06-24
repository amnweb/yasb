"""Wrappers for gdi32 win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    c_int,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    HDC,
    LPVOID,
)

from core.utils.win32.structs import (
    BITMAPINFO,
    HBITMAP,
)
from core.utils.win32.typecheck import CArgObject

gdi32 = windll.gdi32

gdi32.GetObjectW.argtypes = [HANDLE, c_int, LPVOID]
gdi32.GetObjectW.restype = c_int

gdi32.GetDIBits.argtypes = [HDC, HBITMAP, DWORD, DWORD, LPVOID, POINTER(BITMAPINFO), DWORD]
gdi32.GetDIBits.restype = c_int

gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteObject.restype = BOOL


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

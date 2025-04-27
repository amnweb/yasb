"""win32 types and structs"""

import ctypes as ct
import uuid
from ctypes import WINFUNCTYPE
from ctypes.wintypes import (
    BOOL,
    BYTE,
    DWORD,
    HANDLE,
    HBITMAP,
    HBRUSH,
    HICON,
    HINSTANCE,
    HWND,
    INT,
    LONG,
    LPARAM,
    LPCWSTR,
    LPVOID,
    UINT,
    ULONG,
    USHORT,
    WORD,
    WPARAM,
)

WNDPROC = WINFUNCTYPE(LPARAM, HWND, UINT, WPARAM, LPARAM)


class WNDCLASS(ct.Structure):
    _fields_ = [
        ("style", UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", INT),
        ("cbWndExtra", INT),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HANDLE),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
    ]


class COPYDATASTRUCT(ct.Structure):
    _fields_ = [
        ("dwData", ct.c_uint64),
        ("cbData", ct.c_uint64),
        ("lpData", ct.c_void_p),
    ]


class GUID(ct.Structure):
    _fields_ = [
        ("Data1", ULONG),
        ("Data2", USHORT),
        ("Data3", USHORT),
        ("Data4", ct.c_ubyte * 8),
    ]

    def to_uuid(self):
        # fmt: off
        return uuid.UUID(
            bytes=(
                self.Data1.to_bytes(4) +
                self.Data2.to_bytes(2) +
                self.Data3.to_bytes(2) +
                bytes(self.Data4)
            )
        )
        # fmt: on

    def __str__(self):
        return (
            f"{self.Data1:08X}-{self.Data2:04X}-{self.Data3:04X}-"
            + f"{''.join(f'{b:02X}' for b in self.Data4[:2])}-"
            + f"{''.join(f'{b:02X}' for b in self.Data4[2:])}"
        ).lower()


class NOFITYICONDATA_0(ct.Union):
    _fields_ = [
        ("uTimeout", ct.c_uint32),
        ("uVersion", ct.c_uint32),
    ]


class NOTIFYICONDATA(ct.Structure):
    _fields_ = [
        ("cbSize", ct.c_uint32),
        ("hWnd", ct.c_uint32),
        ("uID", ct.c_uint32),
        ("uFlags", ct.c_uint32),
        ("uCallbackMessage", ct.c_uint32),
        ("hIcon", ct.c_uint32),
        ("szTip", ct.c_uint16 * 128),
        ("dwState", ct.c_uint32),
        ("dwStateMask", ct.c_uint32),
        ("szInfo", ct.c_uint16 * 256),
        ("anonymous", NOFITYICONDATA_0),
        ("szInfoTitle", ct.c_uint16 * 64),
        ("dwInfoFlags", ct.c_uint32),
        ("guidItem", GUID),
        ("hBalloonIcon", ct.c_uint32),
    ]


class SHELLTRAYDATA(ct.Structure):
    _fields_ = [
        ("magic_number", ct.c_int32),
        ("message_type", ct.c_uint32),
        ("icon_data", NOTIFYICONDATA),
    ]


class WINNOTIFYICONIDENTIFIER(ct.Structure):
    _fields_ = [
        ("magic_number", ct.c_int32),
        ("message", ct.c_int32),
        ("callback_size", ct.c_int32),
        ("padding", ct.c_int32),
        ("window_handle", ct.c_uint32),
        ("uid", ct.c_uint32),
        ("guid_item", GUID),
    ]


class ICONINFO(ct.Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class BITMAP(ct.Structure):
    _fields_ = [
        ("bmType", LONG),
        ("bmWidth", LONG),
        ("bmHeight", LONG),
        ("bmWidthBytes", LONG),
        ("bmPlanes", WORD),
        ("bmBitsPixel", WORD),
        ("bmBits", LPVOID),
    ]


class BITMAPINFOHEADER(ct.Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class RGBQUAD(ct.Structure):
    _fields_ = [
        ("rgbBlue", BYTE),
        ("rgbGreen", BYTE),
        ("rgbRed", BYTE),
        ("rgbReserved", BYTE),
    ]


class BITMAPINFO(ct.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]

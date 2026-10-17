"""Wrappers for combase win32 API functions and the WinRT HSTRING type

https://learn.microsoft.com/en-us/windows/win32/winrt/hstring
"""

import ctypes
import weakref
from ctypes import POINTER, WinDLL, c_long, c_uint32, c_void_p
from ctypes.wintypes import WCHAR

from comtypes import GUID  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.constants import E_BOUNDS, E_NOINTERFACE, E_NOTIMPL
from core.utils.win32.typecheck import CArgObject

combase = WinDLL("combase", use_last_error=True)

combase.WindowsCreateString.argtypes = [c_void_p, c_uint32, POINTER(c_void_p)]
combase.WindowsCreateString.restype = c_long

combase.WindowsDeleteString.argtypes = [c_void_p]
combase.WindowsDeleteString.restype = c_long

combase.WindowsGetStringRawBuffer.argtypes = [c_void_p, POINTER(c_uint32)]
combase.WindowsGetStringRawBuffer.restype = c_void_p

PWSTR = POINTER(WCHAR)
REFGUID = POINTER(GUID)
REFIID = POINTER(GUID)


def WindowsCreateString(sourceString: bytes, length: int, string: CArgObject) -> int:
    return combase.WindowsCreateString(sourceString, length, string)


def WindowsDeleteString(string: int | None) -> int:
    return combase.WindowsDeleteString(string)


def WindowsGetStringRawBuffer(string: c_void_p, length: CArgObject) -> int | None:
    return combase.WindowsGetStringRawBuffer(string, length)


def check_hresult(hr: int) -> int:
    if (hr & 0x80000000) == 0:
        return hr
    if hr == E_NOTIMPL:
        raise NotImplementedError
    if hr == E_NOINTERFACE:
        raise TypeError("E_NOINTERFACE")
    if hr == E_BOUNDS:
        raise IndexError
    error = OSError(f"[HRESULT 0x{hr & 0xFFFFFFFF:08X}] {ctypes.FormatError(hr)}")
    error.winerror = hr & 0xFFFFFFFF
    raise error


def _delete_hstring(value: int | None) -> None:
    check_hresult(WindowsDeleteString(value))


# HSTRING is adapted from https://github.com/ninthDevilHAUNSTER/ArknightsAutoHelper (MIT).
class HSTRING(c_void_p):
    """A WinRT string.

    Constructing one from a Python string allocates a WinRT string, freed when
    this object is collected. Instances received from COM calls are not owned by
    us, so no finalizer is attached to those.
    """

    def __init__(self, value: str | None = None):
        super().__init__()
        if not value:
            self.value = None
            return
        encoded = value.encode("utf-16-le") + b"\x00\x00"
        length = (len(encoded) // 2) - 1
        check_hresult(WindowsCreateString(encoded, length, ctypes.byref(self)))
        self._finalizer = weakref.finalize(self, _delete_hstring, self.value)

    def __str__(self) -> str:
        if self.value is None:
            return ""
        length = c_uint32()
        buffer = WindowsGetStringRawBuffer(self, ctypes.byref(length))
        return ctypes.wstring_at(buffer, length.value) if buffer else ""

    def __repr__(self) -> str:
        return f"HSTRING({str(self)!r})"

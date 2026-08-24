"""Generic COM and WinRT primitives shared by the win32 binding modules.

The service provider used to reach shell singletons, the object array those
singletons return, and the WinRT string type used by newer shell interfaces.

https://learn.microsoft.com/en-us/windows/win32/api/objectarray/nn-objectarray-iobjectarray
https://learn.microsoft.com/en-us/windows/win32/winrt/hstring
"""

import ctypes
import weakref
from collections.abc import Iterator
from ctypes import HRESULT, POINTER
from ctypes.wintypes import LPVOID, UINT, WCHAR
from typing import Any

from comtypes import COMMETHOD, GUID, STDMETHOD, IUnknown

PWSTR = POINTER(WCHAR)
REFGUID = POINTER(GUID)
REFIID = POINTER(GUID)


class IServiceProvider(IUnknown):
    """Used to query the Immersive Shell for its internal service singletons."""

    _iid_ = GUID("{6D5140C1-7436-11CE-8034-00AA006009FA}")
    _methods_ = [
        STDMETHOD(HRESULT, "QueryService", (REFGUID, REFIID, POINTER(LPVOID))),
    ]


class IObjectArray(IUnknown):
    """A homogeneous array of COM objects, returned by several shell interfaces."""

    _iid_ = GUID("{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "pcObjects")),
        STDMETHOD(HRESULT, "GetAt", (UINT, REFIID, POINTER(LPVOID))),
    ]

    def get_at(self, index: int, cls: Any) -> Any:
        """Return the item at index, cast to interface cls."""
        item = POINTER(cls)()
        self.GetAt(index, cls._iid_, item)  # type: ignore[attr-defined]
        return item

    def iter(self, cls: Any) -> Iterator[Any]:
        """Iterate the array as instances of cls."""
        for i in range(self.GetCount()):  # type: ignore[attr-defined]
            yield self.get_at(i, cls)


# WinRT string support.
#
# Adapted from https://github.com/ninthDevilHAUNSTER/ArknightsAutoHelper (MIT).
# The newer virtual desktop interfaces take and return desktop names and
# wallpaper paths as HSTRINGs rather than plain wide strings.

E_NOTIMPL = -2147467263  # 0x80004001
E_NOINTERFACE = -2147467262  # 0x80004002
E_BOUNDS = -2147483637  # 0x8000000B


def check_hresult(hr: int) -> int:
    """Raise an appropriate exception when hr is a failure code.

    Used as a ctypes restype so failures raise at the call site rather than
    returning silently as negative integers.
    """
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


_combase = ctypes.windll.LoadLibrary("combase.dll")

_WindowsCreateString = _combase.WindowsCreateString
_WindowsCreateString.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p))
_WindowsCreateString.restype = check_hresult

_WindowsDeleteString = _combase.WindowsDeleteString
_WindowsDeleteString.argtypes = (ctypes.c_void_p,)
_WindowsDeleteString.restype = check_hresult

_WindowsGetStringRawBuffer = _combase.WindowsGetStringRawBuffer
_WindowsGetStringRawBuffer.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
_WindowsGetStringRawBuffer.restype = ctypes.c_void_p


class HSTRING(ctypes.c_void_p):
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
        _WindowsCreateString(encoded, ctypes.c_uint32(length), ctypes.byref(self))
        # Only registered when we allocated the string ourselves.
        self._finalizer = weakref.finalize(self, _WindowsDeleteString, self.value)

    def __str__(self) -> str:
        if self.value is None:
            return ""
        length = ctypes.c_uint32()
        buffer = _WindowsGetStringRawBuffer(self, ctypes.byref(length))
        return ctypes.wstring_at(buffer, length.value)

    def __repr__(self) -> str:
        return f"HSTRING({str(self)!r})"

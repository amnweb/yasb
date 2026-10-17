"""Wrappers for ole32 win32 API functions to make them easier to use and have proper types"""

from ctypes import POINTER, WinDLL, byref, c_long, c_ulong, c_void_p
from typing import Any

import comtypes  # pyright: ignore[reportMissingTypeStubs]
import comtypes.client  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.structs import GUID, PROPVARIANT
from core.utils.win32.typecheck import CArgObject

ole32 = WinDLL("ole32", use_last_error=True)

ole32.CoInitialize.argtypes = [c_void_p]
ole32.CoInitialize.restype = c_long

ole32.CoInitializeEx.argtypes = [c_void_p, c_ulong]
ole32.CoInitializeEx.restype = c_long

ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None

ole32.CoTaskMemFree.argtypes = [c_void_p]
ole32.CoTaskMemFree.restype = None

ole32.CoCreateInstance.argtypes = [POINTER(GUID), c_void_p, c_ulong, POINTER(GUID), POINTER(c_void_p)]
ole32.CoCreateInstance.restype = c_long

ole32.PropVariantClear.argtypes = [POINTER(PROPVARIANT)]
ole32.PropVariantClear.restype = c_long


def CoInitialize(pvReserved: None = None) -> int:
    return ole32.CoInitialize(pvReserved)


def CoUninitialize() -> None:
    ole32.CoUninitialize()


def CoCreateInstance(
    rclsid: CArgObject,
    pUnkOuter: int | None,
    dwClsContext: int,
    riid: CArgObject,
    ppv: CArgObject,
) -> int:
    return ole32.CoCreateInstance(rclsid, pUnkOuter, dwClsContext, riid, ppv)


def CoTaskMemFree(pv: c_void_p | int | None) -> None:
    ole32.CoTaskMemFree(pv)


def PropVariantClear(pvar: PROPVARIANT) -> int:
    return ole32.PropVariantClear(byref(pvar))


def create_com_object[T: comtypes.IUnknown](clsid: comtypes.GUID, interface: type[T], clsctx: int) -> T | None:
    try:
        return comtypes.CoCreateInstance(clsid, interface, clsctx)
    except comtypes.COMError, OSError:
        return None


def create_dispatch(progid: str) -> Any:
    """A late-bound automation object, the way script hosts create one (Shell.Application, ADODB.Connection)."""
    return comtypes.client.CreateObject(progid, dynamic=True)


def get_dispatch(display_name: str) -> Any:
    """The late-bound object a moniker display name names, such as "winmgmts:"."""
    return comtypes.client.CoGetObject(display_name, dynamic=True)

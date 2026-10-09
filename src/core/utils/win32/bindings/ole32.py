"""Wrappers for ole32 win32 API functions to make them easier to use and have proper types"""

from ctypes import POINTER, c_long, c_ulong, c_void_p, windll

from core.utils.win32.structs import GUID
from core.utils.win32.typecheck import CArgObject

ole32 = windll.ole32

COINIT_MULTITHREADED = 0x0

# COM was already initialised on this thread with a different apartment model.
RPC_E_CHANGED_MODE = -2147417850

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

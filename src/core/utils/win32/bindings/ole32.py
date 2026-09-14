"""Wrappers for ole32 win32 API functions to make them easier to use and have proper types"""

from ctypes import c_long, c_ulong, c_void_p, windll

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

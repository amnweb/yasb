"""Wrappers for ole32 win32 API functions to make them easier to use and have proper types"""

from ctypes import c_long, c_void_p, windll

ole32 = windll.ole32

ole32.CoInitialize.argtypes = [c_void_p]
ole32.CoInitialize.restype = c_long

ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None

"""Bindings for SetupAPI functions (device enumeration)."""

from ctypes import POINTER, c_void_p, windll
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND, LPCWSTR

from core.utils.win32.structs import GUID, SP_DEVICE_INTERFACE_DATA

setupapi = windll.setupapi

# SetupDiGetClassDevsW - Get device information set
setupapi.SetupDiGetClassDevsW.argtypes = [POINTER(GUID), LPCWSTR, HWND, DWORD]
setupapi.SetupDiGetClassDevsW.restype = HANDLE

# SetupDiEnumDeviceInterfaces - Enumerate device interfaces
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    HANDLE,
    c_void_p,
    POINTER(GUID),
    DWORD,
    POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = BOOL

# SetupDiGetDeviceInterfaceDetailW - Get device interface details
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    HANDLE,
    POINTER(SP_DEVICE_INTERFACE_DATA),
    c_void_p,
    DWORD,
    POINTER(DWORD),
    c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = BOOL

# SetupDiDestroyDeviceInfoList - Destroy device info list
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = BOOL

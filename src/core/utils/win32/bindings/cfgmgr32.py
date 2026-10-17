"""Wrappers for cfgmgr32 (PnP configuration manager) win32 API functions"""

from ctypes import POINTER, WinDLL, c_void_p
from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, ULONG

from core.utils.win32.structs import DEVPROPKEY

cfgmgr32 = WinDLL("cfgmgr32", use_last_error=True)

cfgmgr32.CM_Get_Device_ID_List_SizeW.argtypes = [POINTER(ULONG), LPCWSTR, ULONG]
cfgmgr32.CM_Get_Device_ID_List_SizeW.restype = DWORD

cfgmgr32.CM_Get_Device_ID_ListW.argtypes = [LPCWSTR, LPWSTR, ULONG, ULONG]
cfgmgr32.CM_Get_Device_ID_ListW.restype = DWORD

cfgmgr32.CM_Locate_DevNodeW.argtypes = [POINTER(DWORD), LPCWSTR, ULONG]
cfgmgr32.CM_Locate_DevNodeW.restype = DWORD

cfgmgr32.CM_Get_DevNode_PropertyW.argtypes = [
    DWORD,
    POINTER(DEVPROPKEY),
    POINTER(ULONG),
    c_void_p,
    POINTER(ULONG),
    ULONG,
]
cfgmgr32.CM_Get_DevNode_PropertyW.restype = DWORD

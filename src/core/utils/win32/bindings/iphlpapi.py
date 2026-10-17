"""Wrappers for iphlpapi (IP Helper API) win32 API functions"""

from ctypes import WinDLL, c_void_p
from ctypes.wintypes import DWORD, PULONG, ULONG

iphlpapi = WinDLL("iphlpapi", use_last_error=True)

# GetIfEntry2 - Get interface statistics
iphlpapi.GetIfEntry2.argtypes = [c_void_p]  # Pointer to MIB_IF_ROW2
iphlpapi.GetIfEntry2.restype = DWORD

# GetAdaptersAddresses - Get adapter addresses
iphlpapi.GetAdaptersAddresses.argtypes = [ULONG, ULONG, c_void_p, c_void_p, PULONG]
iphlpapi.GetAdaptersAddresses.restype = ULONG

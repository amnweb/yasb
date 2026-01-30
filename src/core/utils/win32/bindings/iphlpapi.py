"""Wrappers for iphlpapi (IP Helper API) win32 API functions"""

from ctypes import c_void_p, windll
from ctypes.wintypes import DWORD, PULONG, ULONG

iphlpapi = windll.iphlpapi

# GetIfEntry2 - Get interface statistics
iphlpapi.GetIfEntry2.argtypes = [c_void_p]  # Pointer to MIB_IF_ROW2
iphlpapi.GetIfEntry2.restype = DWORD

# GetAdaptersAddresses - Get adapter addresses
iphlpapi.GetAdaptersAddresses.argtypes = [ULONG, ULONG, c_void_p, c_void_p, PULONG]
iphlpapi.GetAdaptersAddresses.restype = ULONG

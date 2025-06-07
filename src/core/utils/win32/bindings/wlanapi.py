"""Wrappers for wlanapi win32 API functions to make them easier to use and have proper types"""

from ctypes import (
    POINTER,
    Array,
    c_void_p,
    c_wchar,
    c_wchar_p,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    DWORD,
    HANDLE,
    ULONG,
)
from typing import Any

from core.utils.win32.typecheck import CArgObject, CPointer
from core.utils.win32.structs import (
    DOT11_SSID,
    GUID,
    IP_ADAPTER_ADDRESSES,
    WLAN_AVAILABLE_NETWORK_LIST,
    WLAN_BSS_LIST,
    WLAN_CONNECTION_PARAMETERS,
    WLAN_INTERFACE_INFO_LIST,
    WLAN_PROFILE_INFO_LIST,
)

wlanapi = windll.wlanapi
iphlpapi = windll.iphlpapi

wlanapi.WlanOpenHandle.argtypes = [
    DWORD,
    c_void_p,
    POINTER(DWORD),
    POINTER(HANDLE),
]
wlanapi.WlanOpenHandle.restype = DWORD

wlanapi.WlanEnumInterfaces.argtypes = [
    HANDLE,
    c_void_p,
    POINTER(POINTER(WLAN_INTERFACE_INFO_LIST)),
]
wlanapi.WlanEnumInterfaces.restype = DWORD

wlanapi.WlanScan.argtypes = [
    HANDLE,
    POINTER(GUID),
    POINTER(DOT11_SSID),
    c_void_p,
    c_void_p,
]
wlanapi.WlanScan.restype = DWORD

wlanapi.WlanGetAvailableNetworkList.argtypes = [
    HANDLE,
    POINTER(GUID),
    DWORD,
    c_void_p,
    POINTER(POINTER(WLAN_AVAILABLE_NETWORK_LIST)),
]
wlanapi.WlanGetAvailableNetworkList.restype = DWORD

wlanapi.WlanQueryInterface.argtypes = [
    HANDLE,
    POINTER(GUID),
    DWORD,
    c_void_p,
    POINTER(DWORD),
    POINTER(c_void_p),
    POINTER(DWORD),
]
wlanapi.WlanQueryInterface.restype = DWORD

wlanapi.WlanGetProfileList.argtypes = [
    HANDLE,
    POINTER(GUID),
    c_void_p,
    POINTER(POINTER(WLAN_PROFILE_INFO_LIST)),
]
wlanapi.WlanGetProfileList.restype = DWORD

wlanapi.WlanSetProfile.argtypes = [
    HANDLE,
    POINTER(GUID),
    DWORD,
    c_wchar_p,
    c_wchar_p,
    BOOL,
    c_void_p,
    POINTER(DWORD),
]
wlanapi.WlanSetProfile.restype = DWORD

wlanapi.WlanReasonCodeToString.argtypes = [
    DWORD,
    DWORD,
    c_wchar_p,
    c_void_p,
]
wlanapi.WlanReasonCodeToString.restype = c_wchar_p

wlanapi.WlanConnect.argtypes = [
    HANDLE,
    POINTER(GUID),
    POINTER(WLAN_CONNECTION_PARAMETERS),
    c_void_p,
]
wlanapi.WlanConnect.restype = DWORD

wlanapi.WlanDisconnect.argtypes = [
    HANDLE,
    POINTER(GUID),
    c_void_p,
]
wlanapi.WlanDisconnect.restype = DWORD

wlanapi.WlanGetNetworkBssList.argtypes = [
    HANDLE,
    POINTER(GUID),
    POINTER(DOT11_SSID),
    DWORD,
    BOOL,
    c_void_p,
    POINTER(POINTER(WLAN_BSS_LIST)),
]
wlanapi.WlanGetNetworkBssList.restype = DWORD

wlanapi.WlanFreeMemory.argtypes = [c_void_p]

wlanapi.WlanCloseHandle.argtypes = [HANDLE, c_void_p]
wlanapi.WlanCloseHandle.restype = DWORD

iphlpapi.GetAdaptersAddresses.argtypes = [
    ULONG,
    ULONG,
    c_void_p,
    POINTER(IP_ADAPTER_ADDRESSES),
    POINTER(ULONG),
]
iphlpapi.GetAdaptersAddresses.restype = ULONG


def WlanOpenHandle(
    desiredAccess: int,
    clientHandle: int | None,
    pNetInfGuid: CArgObject | None,
    pClientHandle: CArgObject | None,
) -> int:
    return wlanapi.WlanOpenHandle(
        desiredAccess,
        clientHandle,
        pNetInfGuid,
        pClientHandle,
    )


def WlanEnumInterfaces(
    clientHandle: HANDLE,
    pReserved: int | None,
    ppInterfaceList: CArgObject | None,
) -> int:
    return wlanapi.WlanEnumInterfaces(
        clientHandle,
        pReserved,
        ppInterfaceList,
    )


def WlanScan(
    pClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pDot11Ssid: CArgObject | None,
    pIeData: int | None,
    pReserved: int | None,
) -> int:
    return wlanapi.WlanScan(
        pClientHandle,
        pInterfaceGuid,
        pDot11Ssid,
        pIeData,
        pReserved,
    )


def WlanGetAvailableNetworkList(
    clientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    dwFlags: int,
    pReserved: CArgObject | None,
    ppAvailableNetworkList: CArgObject | None,
) -> int:
    return wlanapi.WlanGetAvailableNetworkList(
        clientHandle,
        pInterfaceGuid,
        dwFlags,
        pReserved,
        ppAvailableNetworkList,
    )


def WlanQueryInterface(
    WlanQueryInterface: HANDLE,
    pInterfaceGuid: CArgObject | None,
    OpCode: int,
    pReserved: int | None,
    pdwDataSize: CArgObject | None,
    ppData: CArgObject | None,
    pWlanOpcodeValueType: CArgObject | None,
) -> int:
    return wlanapi.WlanQueryInterface(
        WlanQueryInterface,
        pInterfaceGuid,
        OpCode,
        pReserved,
        pdwDataSize,
        ppData,
        pWlanOpcodeValueType,
    )


def WlanGetProfileList(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pReserved: int | None,
    ppProfileList: CArgObject | None,
) -> int:
    return wlanapi.WlanGetProfileList(
        hClientHandle,
        pInterfaceGuid,
        pReserved,
        ppProfileList,
    )


def WlanGetNetworkBssList(
    clientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pDot11Ssid: CArgObject | None,
    dot11BssType: int,
    bSecurityEnabled: bool,
    pReserved: c_void_p | None,
    ppWlanBssList: CArgObject | None,
):
    return wlanapi.WlanGetNetworkBssList(
        clientHandle,
        pInterfaceGuid,
        pDot11Ssid,
        dot11BssType,
        bSecurityEnabled,
        pReserved,
        ppWlanBssList,
    )


def WlanReasonCodeToString(
    dwReasonCode: int,
    dwBufferSize: int,
    pStringBuffer: Array[c_wchar],
    pReserved: c_void_p | None,
) -> int:
    return wlanapi.WlanReasonCodeToString(
        dwReasonCode,
        dwBufferSize,
        pStringBuffer,
        pReserved,
    )


def WlanSetProfile(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    dwFlags: int,
    strProfileXml: str,
    strAllUserProfileSecurity: c_wchar_p | None,
    bOverwrite: bool,
    pReserved: c_void_p | None,
    pdwReasonCode: CArgObject | None,
) -> int:
    return wlanapi.WlanSetProfile(
        hClientHandle,
        pInterfaceGuid,
        dwFlags,
        strProfileXml,
        strAllUserProfileSecurity,
        bOverwrite,
        pReserved,
        pdwReasonCode,
    )


def GetAdaptersAddresses(
    Family: int,
    Flags: int,
    Reserved: int | None,
    AdapterAddresses: CPointer[Any] | c_void_p | None,
    SizePointer: CArgObject | None,
) -> int:
    return iphlpapi.GetAdaptersAddresses(
        Family,
        Flags,
        Reserved,
        AdapterAddresses,
        SizePointer,
    )


def WlanConnect(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pConnectionParameters: CArgObject | None,
    pReserved: c_void_p | None = None,
) -> int:
    return wlanapi.WlanConnect(
        hClientHandle,
        pInterfaceGuid,
        pConnectionParameters,
        pReserved,
    )


def WlanDisconnect(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pReserved: c_void_p | None = None,
) -> int:
    return wlanapi.WlanDisconnect(
        hClientHandle,
        pInterfaceGuid,
        pReserved,
    )


def WlanFreeMemory(pMemory: CPointer[Any] | c_void_p) -> None:
    return wlanapi.WlanFreeMemory(pMemory)


def WlanCloseHandle(clientHandle: HANDLE, pReserved: None = None) -> int:
    return wlanapi.WlanCloseHandle(clientHandle, pReserved)

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
    LPCWSTR,
    LPWSTR,
)
from typing import Any

from core.utils.win32.structs import (
    DOT11_SSID,
    GUID,
    WLAN_AVAILABLE_NETWORK_LIST,
    WLAN_INTERFACE_INFO_LIST,
)
from core.utils.win32.typecheck import CArgObject, CFunctionType, CPointer

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

wlanapi.WlanGetProfile.argtypes = [
    HANDLE,
    POINTER(GUID),
    LPCWSTR,
    c_void_p,
    POINTER(LPWSTR),
    POINTER(DWORD),
    POINTER(DWORD),
]
wlanapi.WlanGetProfile.restype = DWORD

wlanapi.WlanSetProfile.argtypes = [
    HANDLE,
    POINTER(GUID),
    DWORD,
    LPCWSTR,
    LPCWSTR,
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


wlanapi.WlanDeleteProfile.restype = DWORD

wlanapi.WlanFreeMemory.argtypes = [c_void_p]

wlanapi.WlanCloseHandle.argtypes = [HANDLE, c_void_p]
wlanapi.WlanCloseHandle.restype = DWORD

wlanapi.WlanRegisterNotification.argtypes = [
    HANDLE,
    DWORD,
    BOOL,
    c_void_p,
    c_void_p,
    c_void_p,
    POINTER(DWORD),
]
wlanapi.WlanRegisterNotification.restype = DWORD


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


def WlanGetProfile(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    strProfileName: str,
    pReserved: c_void_p | None,
    ppProfileXml: CArgObject | None,
    pdwFlags: CArgObject | None,
    pdwGrantedAccess: CArgObject | None,
) -> int:
    return wlanapi.WlanGetProfile(
        hClientHandle,
        pInterfaceGuid,
        strProfileName,
        pReserved,
        ppProfileXml,
        pdwFlags,
        pdwGrantedAccess,
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


def WlanDeleteProfile(
    hClientHandle: HANDLE,
    pInterfaceGuid: CArgObject | None,
    pProfileName: str,
    pReserved: c_void_p | None = None,
) -> int:
    return wlanapi.WlanDeleteProfile(
        hClientHandle,
        pInterfaceGuid,
        pProfileName,
        pReserved,
    )


def WlanFreeMemory(pMemory: CPointer[Any] | c_void_p) -> None:
    return wlanapi.WlanFreeMemory(pMemory)


def WlanCloseHandle(clientHandle: HANDLE, pReserved: None = None) -> int:
    return wlanapi.WlanCloseHandle(clientHandle, pReserved)


def WlanRegisterNotification(
    hClientHandle: HANDLE,
    dwNotifSource: int,
    bIgnoreDuplicate: bool,
    pNotifCallback: CFunctionType | None,
    pCallbackContext: c_void_p | None,
    pReserved: CArgObject | None,
    pdwPrevNotifSource: CArgObject | None,
) -> int:
    return wlanapi.WlanRegisterNotification(
        hClientHandle,
        dwNotifSource,
        bIgnoreDuplicate,
        pNotifCallback,
        pCallbackContext,
        pReserved,
        pdwPrevNotifSource,
    )

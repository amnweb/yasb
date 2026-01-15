"""win32 types and structs"""

import ctypes as ct
import uuid
from ctypes import (
    POINTER,
    WINFUNCTYPE,
    c_char_p,
    c_ubyte,
    c_ulonglong,
    c_void_p,
    c_wchar_p,
    wintypes,
)
from ctypes.wintypes import (
    BOOL,
    BOOLEAN,
    BYTE,
    DWORD,
    HANDLE,
    HBITMAP,
    HBRUSH,
    HICON,
    HINSTANCE,
    HWND,
    INT,
    LONG,
    LPARAM,
    LPCWSTR,
    LPVOID,
    MAX_PATH,
    UINT,
    ULONG,
    USHORT,
    WCHAR,
    WORD,
    WPARAM,
)

WNDPROC = WINFUNCTYPE(LPARAM, HWND, UINT, WPARAM, LPARAM)


class WNDCLASS(ct.Structure):
    _fields_ = [
        ("style", UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", INT),
        ("cbWndExtra", INT),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HANDLE),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
    ]


class COPYDATASTRUCT(ct.Structure):
    _fields_ = [
        ("dwData", ct.c_uint64),
        ("cbData", ct.c_uint64),
        ("lpData", ct.c_void_p),
    ]


class GUID(ct.Structure):
    _fields_ = [
        ("Data1", ULONG),
        ("Data2", USHORT),
        ("Data3", USHORT),
        ("Data4", ct.c_ubyte * 8),
    ]

    def to_uuid(self):
        # fmt: off
        return uuid.UUID(
            bytes=(
                self.Data1.to_bytes(4) +
                self.Data2.to_bytes(2) +
                self.Data3.to_bytes(2) +
                bytes(self.Data4)
            )
        )
        # fmt: on

    def __str__(self):
        return (
            f"{self.Data1:08X}-{self.Data2:04X}-{self.Data3:04X}-"
            + f"{''.join(f'{b:02X}' for b in self.Data4[:2])}-"
            + f"{''.join(f'{b:02X}' for b in self.Data4[2:])}"
        ).lower()


class NOFITYICONDATA_0(ct.Union):
    _fields_ = [
        ("uTimeout", ct.c_uint32),
        ("uVersion", ct.c_uint32),
    ]


class NOTIFYICONDATA(ct.Structure):
    _fields_ = [
        ("cbSize", ct.c_uint32),
        ("hWnd", ct.c_uint32),
        ("uID", ct.c_uint32),
        ("uFlags", ct.c_uint32),
        ("uCallbackMessage", ct.c_uint32),
        ("hIcon", ct.c_uint32),
        ("szTip", ct.c_uint16 * 128),
        ("dwState", ct.c_uint32),
        ("dwStateMask", ct.c_uint32),
        ("szInfo", ct.c_uint16 * 256),
        ("anonymous", NOFITYICONDATA_0),
        ("szInfoTitle", ct.c_uint16 * 64),
        ("dwInfoFlags", ct.c_uint32),
        ("guidItem", GUID),
        ("hBalloonIcon", ct.c_uint32),
    ]


class SHELLTRAYDATA(ct.Structure):
    _fields_ = [
        ("magic_number", ct.c_int32),
        ("message_type", ct.c_uint32),
        ("icon_data", NOTIFYICONDATA),
    ]


class WINNOTIFYICONIDENTIFIER(ct.Structure):
    _fields_ = [
        ("magic_number", ct.c_int32),
        ("message", ct.c_int32),
        ("callback_size", ct.c_int32),
        ("padding", ct.c_int32),
        ("window_handle", ct.c_uint32),
        ("uid", ct.c_uint32),
        ("guid_item", GUID),
    ]


class ICONINFO(ct.Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class BITMAP(ct.Structure):
    _fields_ = [
        ("bmType", LONG),
        ("bmWidth", LONG),
        ("bmHeight", LONG),
        ("bmWidthBytes", LONG),
        ("bmPlanes", WORD),
        ("bmBitsPixel", WORD),
        ("bmBits", LPVOID),
    ]


class BITMAPINFOHEADER(ct.Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class RGBQUAD(ct.Structure):
    _fields_ = [
        ("rgbBlue", BYTE),
        ("rgbGreen", BYTE),
        ("rgbRed", BYTE),
        ("rgbReserved", BYTE),
    ]


class BITMAPINFO(ct.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class WLAN_INTERFACE_INFO(ct.Structure):
    _fields_ = [
        ("InterfaceGuid", GUID),
        ("strInterfaceDescription", WCHAR * 256),
        ("isState", DWORD),
    ]


class WLAN_INTERFACE_INFO_LIST(ct.Structure):
    _fields_ = [
        ("dwNumberOfItems", DWORD),
        ("dwIndex", DWORD),
        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1),
    ]


class WLAN_NOTIFICATION_DATA(ct.Structure):
    _fields_ = [
        ("NotificationSource", DWORD),
        ("NotificationCode", DWORD),
        ("InterfaceGuid", GUID),
        ("dwDataSize", DWORD),
        ("pData", c_void_p),
    ]


WLAN_NOTIFICATION_CALLBACK = WINFUNCTYPE(
    None,
    POINTER(WLAN_NOTIFICATION_DATA),
    c_void_p,
)


class DOT11_SSID(ct.Structure):
    _fields_ = [
        ("uSSIDLength", ULONG),
        ("ucSSID", BYTE * 32),
    ]

    def __str__(self) -> str:
        # Slice the byte array to the length specified and decode
        return bytes(self.ucSSID[: self.uSSIDLength]).decode("utf-8", errors="replace")

    def set_ssid(self, ssid: bytes) -> None:
        if len(ssid) > 32:
            raise ValueError("SSID too long (max 32 bytes)")
        self.uSSIDLength = len(ssid)
        ct.memmove(self.ucSSID, ssid, self.uSSIDLength)


class WLAN_AVAILABLE_NETWORK(ct.Structure):
    _fields_ = [
        ("strProfileName", WCHAR * 256),
        ("dot11Ssid", DOT11_SSID),
        ("dot11BssType", DWORD),
        ("uNumberOfBssids", ULONG),
        ("bNetworkConnectable", BOOL),
        ("wlanNotConnectableReason", DWORD),
        ("uNumberOfPhyTypes", ULONG),
        ("dot11PhyTypes", DWORD * 8),
        ("bMorePhyTypes", BOOL),
        ("wlanSignalQuality", ULONG),
        ("bSecurityEnabled", BOOL),
        ("dot11DefaultAuthAlgorithm", DWORD),
        ("dot11DefaultCipherAlgorithm", DWORD),
        ("dwFlags", DWORD),
        ("dwReserved", DWORD),
    ]


class WLAN_AVAILABLE_NETWORK_LIST(ct.Structure):
    _fields_ = [
        ("dwNumberOfItems", DWORD),
        ("dwIndex", DWORD),
        ("Network", WLAN_AVAILABLE_NETWORK * 1),
    ]


# Function prototypes for IP Helper API
# We define it beforehand to use it in the 'Next' field later (linked list)
class IP_ADAPTER_ADDRESSES(ct.Structure):
    pass


IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", ULONG),
    ("IfIndex", DWORD),
    ("Next", POINTER(IP_ADAPTER_ADDRESSES)),
    ("AdapterName", c_char_p),
    ("FirstUnicastAddress", c_void_p),
    ("FirstAnycastAddress", c_void_p),
    ("FirstMulticastAddress", c_void_p),
    ("FirstDnsServerAddress", c_void_p),
    ("DnsSuffix", c_wchar_p),
    ("Description", c_wchar_p),
    ("FriendlyName", c_wchar_p),
    # There are more fields, but we don't need them for our purpose
]


class WLAN_PROFILE_INFO(ct.Structure):
    _fields_ = [
        ("strProfileName", WCHAR * 256),
        ("dwFlags", DWORD),
    ]


class WLAN_PROFILE_INFO_LIST(ct.Structure):
    _fields_ = [
        ("dwNumberOfItems", DWORD),
        ("dwIndex", DWORD),
        # ("ProfileInfo", WLAN_PROFILE_INFO * 10), # Dynamically allocated later
    ]


class WLAN_RATE_SET(ct.Structure):
    _fields_ = [
        ("uRateSetLength", ULONG),
        ("usRateSet", USHORT * 126),
    ]


class WLAN_BSS_ENTRY(ct.Structure):
    _fields_ = [
        ("dot11Ssid", DOT11_SSID),
        ("uPhyId", ULONG),
        ("dot11Bssid", c_ubyte * 6),
        ("dot11BssType", DWORD),
        ("dot11BssPhyType", DWORD),
        ("lRssi", LONG),
        ("uLinkQuality", ULONG),
        ("bInRegDomain", BOOLEAN),
        ("usBeaconPeriod", USHORT),
        ("ullTimestamp", c_ulonglong),
        ("ullHostTimestamp", c_ulonglong),
        ("usCapabilityInformation", USHORT),
        ("ulChCenterFrequency", ULONG),
        ("wlanRateSet", WLAN_RATE_SET),
        ("ulIeOffset", ULONG),
        ("ulIeSize", ULONG),
    ]


class WLAN_BSS_LIST(ct.Structure):
    _fields_ = [
        ("dwTotalSize", DWORD),
        ("dwNumberOfItems", DWORD),
        ("wlanBssEntries", WLAN_BSS_ENTRY * 1),  # temporary, will cast later
    ]


class NDIS_OBJECT_HEADER(ct.Structure):
    _fields_ = [
        ("Type", ct.c_ubyte),
        ("Revision", ct.c_ubyte),
        ("Size", ct.c_ushort),
    ]


class WLAN_CONNECTION_NOTIFICATION_DATA(ct.Structure):
    _fields_ = [
        ("wlanConnectionMode", DWORD),
        ("strProfileName", WCHAR * 256),
        ("dot11Ssid", DOT11_SSID),
        ("dot11BssType", DWORD),
        ("bSecurityEnabled", BOOL),
        ("wlanReasonCode", DWORD),
        ("dwFlags", DWORD),
        ("strProfileXml", WCHAR * 1),
    ]


# Structs for DWM (Desktop Window Manager) API
class RECT(ct.Structure):
    _fields_ = [
        ("left", LONG),
        ("top", LONG),
        ("right", LONG),
        ("bottom", LONG),
    ]


class SIZE(ct.Structure):
    _fields_ = [("cx", LONG), ("cy", LONG)]


class DWM_THUMBNAIL_PROPERTIES(ct.Structure):
    _fields_ = [
        ("dwFlags", UINT),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", BYTE),
        ("fVisible", BOOL),
        ("fSourceClientAreaOnly", BOOL),
    ]


# Win32 message structure used by Qt native event filter and other components
class MSG(ct.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", DWORD),
        ("pt_x", LONG),
        ("pt_y", LONG),
    ]


# Define SHQUERYRBINFO struct for Recycle Bin info
class SHQUERYRBINFO(ct.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ct.c_longlong), ("i64NumItems", ct.c_longlong)]


class SHSTOCKICONINFO(ct.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hIcon", wintypes.HICON),
        ("iSysImageIndex", ct.c_int),
        ("iIcon", ct.c_int),
        ("szPath", wintypes.WCHAR * MAX_PATH),
    ]


class DISPLAY_BRIGHTNESS(ct.Structure):
    """LCD brightness structure for DeviceIoControl."""

    _fields_ = [("ucDisplayPolicy", BYTE), ("ucACBrightness", BYTE), ("ucDCBrightness", BYTE)]

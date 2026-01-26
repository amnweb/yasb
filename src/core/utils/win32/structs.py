"""win32 types and structs"""

import ctypes as ct
import uuid
from ctypes import (
    POINTER,
    WINFUNCTYPE,
    c_size_t,
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


class SYSTEM_INFO(ct.Structure):
    """Windows SYSTEM_INFO structure for processor information."""

    _fields_ = [
        ("wProcessorArchitecture", WORD),
        ("wReserved", WORD),
        ("dwPageSize", DWORD),
        ("lpMinimumApplicationAddress", LPVOID),
        ("lpMaximumApplicationAddress", LPVOID),
        ("dwActiveProcessorMask", c_size_t),
        ("dwNumberOfProcessors", DWORD),
        ("dwProcessorType", DWORD),
        ("dwAllocationGranularity", DWORD),
        ("wProcessorLevel", WORD),
        ("wProcessorRevision", WORD),
    ]


class MEMORYSTATUSEX(ct.Structure):
    """Windows MEMORYSTATUSEX structure for memory information."""

    _fields_ = [
        ("dwLength", DWORD),
        ("dwMemoryLoad", DWORD),
        ("ullTotalPhys", ct.c_uint64),
        ("ullAvailPhys", ct.c_uint64),
        ("ullTotalPageFile", ct.c_uint64),
        ("ullAvailPageFile", ct.c_uint64),
        ("ullTotalVirtual", ct.c_uint64),
        ("ullAvailVirtual", ct.c_uint64),
        ("ullAvailExtendedVirtual", ct.c_uint64),
    ]


class PERFORMANCE_INFORMATION(ct.Structure):
    """Windows PERFORMANCE_INFORMATION structure for system performance."""

    _fields_ = [
        ("cb", DWORD),
        ("CommitTotal", c_size_t),
        ("CommitLimit", c_size_t),
        ("CommitPeak", c_size_t),
        ("PhysicalTotal", c_size_t),
        ("PhysicalAvailable", c_size_t),
        ("SystemCache", c_size_t),
        ("KernelTotal", c_size_t),
        ("KernelPaged", c_size_t),
        ("KernelNonpaged", c_size_t),
        ("PageSize", c_size_t),
        ("HandleCount", DWORD),
        ("ProcessCount", DWORD),
        ("ThreadCount", DWORD),
    ]


class UNICODE_STRING(ct.Structure):
    """Windows UNICODE_STRING structure used by NT APIs."""

    _fields_ = [
        ("Length", USHORT),
        ("MaximumLength", USHORT),
        ("Buffer", c_wchar_p),
    ]


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


class PROCESSENTRY32(ct.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", LPVOID),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", LONG),
        ("dwFlags", DWORD),
        ("szExeFile", WCHAR * MAX_PATH),
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


class MIB_IF_ROW2(ct.Structure):
    """Structure for network interface statistics"""

    _fields_ = [
        ("InterfaceLuid", ct.c_uint64),
        ("InterfaceIndex", DWORD),
        ("InterfaceGuid", BYTE * 16),
        ("Alias", WCHAR * 257),
        ("Description", WCHAR * 257),
        ("PhysicalAddressLength", DWORD),
        ("PhysicalAddress", BYTE * 32),
        ("PermanentPhysicalAddress", BYTE * 32),
        ("Mtu", DWORD),
        ("Type", DWORD),
        ("TunnelType", DWORD),
        ("MediaType", DWORD),
        ("PhysicalMediumType", DWORD),
        ("AccessType", DWORD),
        ("DirectionType", DWORD),
        ("InterfaceAndOperStatusFlags", BYTE),
        ("OperStatus", DWORD),
        ("AdminStatus", DWORD),
        ("MediaConnectState", DWORD),
        ("NetworkGuid", BYTE * 16),
        ("ConnectionType", DWORD),
        ("TransmitLinkSpeed", ct.c_uint64),
        ("ReceiveLinkSpeed", ct.c_uint64),
        ("InOctets", ct.c_uint64),
        ("InUcastPkts", ct.c_uint64),
        ("InNUcastPkts", ct.c_uint64),
        ("InDiscards", ct.c_uint64),
        ("InErrors", ct.c_uint64),
        ("InUnknownProtos", ct.c_uint64),
        ("InUcastOctets", ct.c_uint64),
        ("InMulticastOctets", ct.c_uint64),
        ("InBroadcastOctets", ct.c_uint64),
        ("OutOctets", ct.c_uint64),
        ("OutUcastPkts", ct.c_uint64),
        ("OutNUcastPkts", ct.c_uint64),
        ("OutDiscards", ct.c_uint64),
        ("OutErrors", ct.c_uint64),
        ("OutUcastOctets", ct.c_uint64),
        ("OutMulticastOctets", ct.c_uint64),
        ("OutBroadcastOctets", ct.c_uint64),
    ]


class SOCKADDR(ct.Structure):
    """Socket address structure"""

    _fields_ = [
        ("sa_family", USHORT),
        ("sa_data", ct.c_char * 14),
    ]


class SOCKADDR_IN(ct.Structure):
    """IPv4 socket address"""

    _fields_ = [
        ("sin_family", USHORT),
        ("sin_port", USHORT),
        ("sin_addr", BYTE * 4),
        ("sin_zero", ct.c_char * 8),
    ]


class SOCKET_ADDRESS(ct.Structure):
    """Socket address with length"""

    _fields_ = [
        ("lpSockaddr", ct.POINTER(SOCKADDR)),
        ("iSockaddrLength", INT),
    ]


class IP_ADAPTER_UNICAST_ADDRESS(ct.Structure):
    """Unicast address for an adapter"""

    pass


IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
    ("Length", ULONG),
    ("Flags", DWORD),
    ("Next", ct.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
    ("Address", SOCKET_ADDRESS),
    ("PrefixOrigin", INT),
    ("SuffixOrigin", INT),
    ("DadState", INT),
    ("ValidLifetime", ULONG),
    ("PreferredLifetime", ULONG),
    ("LeaseLifetime", ULONG),
    ("OnLinkPrefixLength", BYTE),
]


class IP_ADAPTER_ADDRESSES(ct.Structure):
    """Adapter addresses structure"""

    pass


IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", ULONG),
    ("IfIndex", DWORD),
    ("Next", ct.POINTER(IP_ADAPTER_ADDRESSES)),
    ("AdapterName", ct.c_char_p),
    ("FirstUnicastAddress", ct.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
    ("FirstAnycastAddress", ct.c_void_p),
    ("FirstMulticastAddress", ct.c_void_p),
    ("FirstDnsServerAddress", ct.c_void_p),
    ("DnsSuffix", ct.c_wchar_p),
    ("Description", ct.c_wchar_p),
    ("FriendlyName", ct.c_wchar_p),
    ("PhysicalAddress", BYTE * 8),  # MAX_ADAPTER_ADDRESS_LENGTH
    ("PhysicalAddressLength", DWORD),
    ("Flags", DWORD),
    ("Mtu", DWORD),
    ("IfType", DWORD),
    ("OperStatus", DWORD),
]


class SYSTEM_POWER_STATUS(ct.Structure):
    """Basic battery info from GetSystemPowerStatus."""

    _fields_ = [
        ("ACLineStatus", ct.c_byte),
        ("BatteryFlag", ct.c_byte),
        ("BatteryLifePercent", ct.c_byte),
        ("SystemStatusFlag", ct.c_byte),
        ("BatteryLifeTime", DWORD),
        ("BatteryFullLifeTime", DWORD),
    ]


class BATTERY_QUERY_INFORMATION(ct.Structure):
    """Query structure for battery information IOCTL."""

    _fields_ = [
        ("BatteryTag", ULONG),
        ("InformationLevel", ct.c_int),
        ("AtRate", LONG),
    ]


class BATTERY_INFORMATION(ct.Structure):
    """Battery information structure returned by IOCTL."""

    _fields_ = [
        ("Capabilities", ULONG),
        ("Technology", ct.c_ubyte),
        ("Reserved", ct.c_ubyte * 3),
        ("Chemistry", ct.c_char * 4),
        ("DesignedCapacity", ULONG),
        ("FullChargedCapacity", ULONG),
        ("DefaultAlert1", ULONG),
        ("DefaultAlert2", ULONG),
        ("CriticalBias", ULONG),
        ("CycleCount", ULONG),
    ]


class BATTERY_WAIT_STATUS(ct.Structure):
    """Wait status structure for battery status IOCTL."""

    _fields_ = [
        ("BatteryTag", ULONG),
        ("Timeout", ULONG),
        ("PowerState", ULONG),
        ("LowCapacity", ULONG),
        ("HighCapacity", ULONG),
    ]


class BATTERY_STATUS(ct.Structure):
    """Battery status structure returned by IOCTL."""

    _fields_ = [
        ("PowerState", ULONG),
        ("Capacity", ULONG),
        ("Voltage", ULONG),
        ("Rate", LONG),  # Signed! Negative = discharging
    ]


class SP_DEVICE_INTERFACE_DATA(ct.Structure):
    """SetupAPI device interface data structure."""

    _fields_ = [
        ("cbSize", DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", DWORD),
        ("Reserved", ct.POINTER(ULONG)),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ct.Structure):
    """SetupAPI device interface detail data (variable length)."""

    _fields_ = [
        ("cbSize", DWORD),
        ("DevicePath", WCHAR * 1),  # Variable length
    ]


class PDH_FMT_COUNTERVALUE_LARGE(ct.Structure):
    """PDH counter value for large integer format."""

    _fields_ = [
        ("CStatus", DWORD),
        ("padding", DWORD),
        ("largeValue", ct.c_longlong),
    ]


class PDH_FMT_COUNTERVALUE_DOUBLE(ct.Structure):
    """PDH counter value for double format."""

    _fields_ = [
        ("CStatus", DWORD),
        ("padding", DWORD),
        ("doubleValue", ct.c_double),
    ]

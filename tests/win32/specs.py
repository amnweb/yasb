"""How the ctypes definitions in src/ map onto the Windows SDK.

A ctypes Structure or Union named after its SDK type, with the SDK's member names, needs no entry
here: it is matched by name. Add an entry only when that is not true. Functions and COM interfaces
follow the same rule.
"""

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from types import MappingProxyType


@dataclass(frozen=True)
class Offset:
    """A field standing in for a C anonymous union: only its offset can be compared, via one member."""

    member: str


FieldMap = MappingProxyType[str, str | Offset | None]


@dataclass(frozen=True)
class Sdk:
    """A type declared by the SDK headers in tests/win32/probe.py:HEADERS."""

    c_type: str | None = None
    # Python field name -> C member designator ("pt.x"), Offset, or None for Python-only padding.
    fields: FieldMap = field(default_factory=lambda: FieldMap({}))
    # Python declares only the leading members; the API owns the allocation, so a smaller size is fine.
    prefix: bool = False


@dataclass(frozen=True)
class Vendored:
    """A type the SDK does not declare. Its C declaration lives in VENDORED_DECLARATIONS."""

    c_type: str
    fields: FieldMap = field(default_factory=lambda: FieldMap({}))


def _map(**fields: str | Offset | None) -> FieldMap:
    return MappingProxyType(fields)


STRUCTS: dict[str, Sdk | Vendored] = {
    "core.utils.win32.structs.MSG": Sdk(fields=_map(pt_x="pt.x", pt_y="pt.y")),
    "core.utils.win32.structs.WNDCLASS": Sdk("WNDCLASSW"),
    "core.utils.win32.structs.PROCESSENTRY32": Sdk("PROCESSENTRY32W"),
    "core.utils.win32.structs.PDH_FMT_COUNTERVALUE_DOUBLE": Sdk("PDH_FMT_COUNTERVALUE", _map(padding=None)),
    "core.utils.win32.structs.PDH_FMT_COUNTERVALUE_LARGE": Sdk("PDH_FMT_COUNTERVALUE", _map(padding=None)),
    "core.utils.win32.structs.IP_ADAPTER_ADDRESSES": Sdk("IP_ADAPTER_ADDRESSES_LH", prefix=True),
    "core.utils.win32.structs.IP_ADAPTER_UNICAST_ADDRESS": Sdk("IP_ADAPTER_UNICAST_ADDRESS_LH"),
    "core.utils.win32.structs.WLAN_PROFILE_INFO_LIST": Sdk(prefix=True),
    "core.utils.win32.structs.ACCENTPOLICY": Vendored("ACCENTPOLICY"),
    "core.utils.win32.structs.WINDOWCOMPOSITIONATTRIBDATA": Vendored("WINDOWCOMPOSITIONATTRIBDATA"),
    "core.utils.win32.structs.SYSTEM_MEMORY_LIST_INFORMATION": Vendored("SYSTEM_MEMORY_LIST_INFORMATION"),
    "core.utils.win32.structs.NOTIFYICONDATA": Vendored("NOTIFYICONDATA32"),
    "core.utils.win32.structs.NOFITYICONDATA_0": Vendored("NOTIFYICONDATA32_0"),
    "core.utils.win32.structs.SHELLTRAYDATA": Vendored("SHELLTRAYDATA"),
    "core.utils.win32.structs.WINNOTIFYICONIDENTIFIER": Vendored("WINNOTIFYICONIDENTIFIER"),
    "core.utils.win32.structs.SHELLEXECUTEINFO": Sdk("SHELLEXECUTEINFOW", _map(hIconOrMonitor="hIcon")),
    "core.utils.win32.app_bar.AppBarData": Sdk("APPBARDATA"),
    "core.utils.win32.aumid.PROPVARIANT": Sdk(fields=_map(data=Offset("pwszVal"))),
    "core.utils.win32.aumid.PROPVARIANT_UNION": Vendored("PROPVARIANT_UNION"),
    "core.widgets.services.audio_visualizer.loopback._WAVEFORMATEX": Sdk("WAVEFORMATEX"),
    "core.widgets.services.audio_visualizer.loopback._WAVEFORMATEXTENSIBLE": Sdk(
        "WAVEFORMATEXTENSIBLE", _map(wValidBitsPerSample="Samples.wValidBitsPerSample")
    ),
    "core.widgets.services.gpu.gpu_api._AdlTemperature": Vendored("ADLTemperature"),
    "core.widgets.services.gpu.gpu_api._AdlFanSpeedValue": Vendored("ADLFanSpeedValue"),
    "core.widgets.services.gpu.gpu_api._AdlODNFanControl": Vendored("ADLODNFanControl"),
    "core.widgets.services.gpu.gpu_api._NvmlMemory": Vendored("nvmlMemory_t"),
    "core.widgets.services.gpu.gpu_api._DxgiAdapterDesc": Sdk("DXGI_ADAPTER_DESC"),
    "core.widgets.services.gpu.gpu_api._DxgiLuid": Sdk("LUID"),
    "core.widgets.services.gpu.gpu_api._PdhItemW": Sdk(
        "PDH_FMT_COUNTERVALUE_ITEM_W", _map(CStatus="FmtValue.CStatus", _pad=None, doubleValue="FmtValue.doubleValue")
    ),
    "core.widgets.services.quick_launch.providers.snippets._INPUT": Sdk("INPUT", _map(_input=Offset("mi"))),
    "core.widgets.services.quick_launch.providers.snippets._INPUT_UNION": Vendored("INPUT_UNION"),
    "core.widgets.services.quick_launch.providers.snippets._MOUSEINPUT": Sdk("MOUSEINPUT"),
    "core.widgets.services.quick_launch.providers.snippets._KEYBDINPUT": Sdk("KEYBDINPUT"),
    "core.widgets.services.quick_launch.providers.snippets._HARDWAREINPUT": Sdk("HARDWAREINPUT"),
}

# C declarations for the types above that no SDK header declares. Copy them from the header that
# defines them where one exists, so the test compares the ctypes code against the vendor and not
# against a second hand-written guess.
VENDORED_DECLARATIONS = r"""
// Undocumented user32 SetWindowCompositionAttribute payload.
struct ACCENTPOLICY { DWORD AccentState; DWORD AccentFlags; DWORD GradientColor; DWORD AnimationId; };
struct WINDOWCOMPOSITIONATTRIBDATA { int Attribute; PVOID Data; SIZE_T SizeOfData; };

// ntexapi.h from phnt (System Informer), SystemMemoryListInformation.
struct SYSTEM_MEMORY_LIST_INFORMATION {
    ULONG_PTR ZeroPageCount;
    ULONG_PTR FreePageCount;
    ULONG_PTR ModifiedPageCount;
    ULONG_PTR ModifiedNoWritePageCount;
    ULONG_PTR BadPageCount;
    ULONG_PTR PageCountByPriority[8];
    ULONG_PTR RepurposedPageCountByPriority[8];
    ULONG_PTR ModifiedPageCountPageFile;
};

// NOTIFYICONDATAW as Explorer receives it from Shell_NotifyIcon over WM_COPYDATA: handles travel
// as 32-bit values in every process, so this is not the x64 SDK layout.
union NOTIFYICONDATA32_0 { UINT uTimeout; UINT uVersion; };
struct NOTIFYICONDATA32 {
    DWORD cbSize;
    DWORD hWnd;
    UINT uID;
    UINT uFlags;
    UINT uCallbackMessage;
    DWORD hIcon;
    WCHAR szTip[128];
    DWORD dwState;
    DWORD dwStateMask;
    WCHAR szInfo[256];
    NOTIFYICONDATA32_0 anonymous;
    WCHAR szInfoTitle[64];
    DWORD dwInfoFlags;
    GUID guidItem;
    DWORD hBalloonIcon;
};
struct SHELLTRAYDATA { DWORD magic_number; DWORD message_type; NOTIFYICONDATA32 icon_data; };
struct WINNOTIFYICONIDENTIFIER {
    DWORD magic_number;
    DWORD message;
    DWORD callback_size;
    DWORD padding;
    DWORD window_handle;
    UINT uid;
    GUID guid_item;
};

// The members of the anonymous unions inside PROPVARIANT (propidlbase.h) and INPUT (winuser.h)
// that the Python code uses.
union PROPVARIANT_UNION { LPWSTR pwszVal; LPSTR pszVal; ULONG ulVal; ULARGE_INTEGER uhVal; VARIANT_BOOL boolVal; BLOB blob; };
union INPUT_UNION { MOUSEINPUT mi; KEYBDINPUT ki; HARDWAREINPUT hi; };

// adl_structures.h, AMD Display Library SDK.
typedef struct ADLTemperature { int iSize; int iTemperature; } ADLTemperature;
typedef struct ADLFanSpeedValue { int iSize; int iSpeedType; int iFanSpeed; int iFlags; } ADLFanSpeedValue;
typedef struct ADLODNFanControl {
    int iMode;
    int iFanControlMode;
    int iCurrentFanSpeedMode;
    int iCurrentFanSpeed;
    int iTargetFanSpeed;
    int iTargetTemperature;
    int iMinPerformanceClock;
    int iMinFanLimit;
} ADLODNFanControl;

// nvml.h, NVIDIA Management Library.
typedef struct nvmlMemory_st { unsigned long long total; unsigned long long free; unsigned long long used; } nvmlMemory_t;
"""


def struct_spec(key: str, class_name: str) -> Sdk | Vendored:
    spec = STRUCTS.get(key, Sdk())
    if isinstance(spec, Sdk) and spec.c_type is None:
        return Sdk(class_name, spec.fields, spec.prefix)
    return spec


# Exported functions the SDK headers do not declare, by name pattern.
NOT_IN_SDK: dict[str, str] = {
    "Everything_*": "voidtools Everything SDK",
    "nvml*": "NVIDIA Management Library",
    "ADL2_*": "AMD Display Library",
    "SetWindowCompositionAttribute": "undocumented user32 export",
    "SetTaskmanWindow": "undocumented user32 export",
    "Power?etUserConfigured?CPowerMode": "undocumented powrprof export",
    "Rtl*WnfStateChangeNotification": "undocumented ntdll export",
}


def not_in_sdk(name: str) -> str | None:
    for pattern, reason in NOT_IN_SDK.items():
        if fnmatchcase(name, pattern):
            return reason
    return None


# comtypes interface -> SDK interface name, when the Python class is named differently.
COM_INTERFACES: dict[str, str] = {}

# comtypes interfaces with no SDK declaration to check against.
UNDOCUMENTED_INTERFACES: dict[str, str] = {
    "core.widgets.services.windows_desktops.interfaces.IApplicationView": "undocumented shell interface",
    "core.widgets.services.windows_desktops.interfaces.IApplicationViewCollection": "undocumented shell interface",
    "core.widgets.services.windows_desktops.interfaces.IVirtualDesktop2": "undocumented shell interface",
    "core.widgets.services.windows_desktops.interfaces.IVirtualDesktopNotificationService": "undocumented shell interface",
    "core.widgets.services.windows_desktops.interfaces.IVirtualDesktopPinnedApps": "undocumented shell interface",
}

# Python constant -> SDK name, for constants the code names differently from the headers.
CONSTANT_ALIASES: dict[str, str] = {
    "ACCESS_DENIED": "ERROR_ACCESS_DENIED",
    "NIN_CONTEXTMENU": "WM_CONTEXTMENU",
    "DISPLAY_BRIGHTNESS_POLICY_BOTH": "DISPLAYPOLICY_BOTH",
    "DOT11_BSS_TYPE_INFRASTRUCTURE": "dot11_BSS_type_infrastructure",
    "IF_OPER_STATUS_UP": "IfOperStatusUp",
    "WLAN_INTERFACE_STATE_CONNECTED": "wlan_interface_state_connected",
    "WLAN_INTF_OPCODE_CURRENT_CONNECTION": "wlan_intf_opcode_current_connection",
    "BATTERY_INFO_LEVEL_INFORMATION": "BatteryInformation",
    "BATTERY_INFO_LEVEL_TEMPERATURE": "BatteryTemperature",
    "BATTERY_INFO_LEVEL_ESTIMATED_TIME": "BatteryEstimatedTime",
    "BATTERY_INFO_LEVEL_DEVICE_NAME": "BatteryDeviceName",
    "BATTERY_INFO_LEVEL_MANUFACTURE_DATE": "BatteryManufactureDate",
    "BATTERY_INFO_LEVEL_MANUFACTURER_NAME": "BatteryManufactureName",
    "BATTERY_INFO_LEVEL_UNIQUE_ID": "BatteryUniqueID",
    "BATTERY_INFO_LEVEL_SERIAL_NUMBER": "BatterySerialNumber",
}

"""How the ctypes definitions in src/ map onto the Windows SDK.

A ctypes Structure or Union named after its SDK type, with the SDK's member names, needs no entry
here: it is matched by name. Add an entry only when that is not true. Functions, COM interfaces and
constants follow the same rule.
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
    "core.utils.win32.structs.INPUT": Sdk(fields=_map(_input=Offset("mi"))),
    "core.utils.win32.structs.INPUT_UNION": Vendored("INPUT_UNION"),
    "core.utils.win32.structs.PROPVARIANT": Sdk(fields=_map(data=Offset("pwszVal"))),
    "core.utils.win32.structs.PROPVARIANT_UNION": Vendored("PROPVARIANT_UNION"),
    "core.utils.win32.structs.WAVEFORMATEXTENSIBLE": Sdk(
        fields=_map(wValidBitsPerSample="Samples.wValidBitsPerSample")
    ),
    "core.utils.win32.bindings.adl.ADLTemperature": Vendored("ADLTemperature"),
    "core.utils.win32.bindings.adl.ADLFanSpeedValue": Vendored("ADLFanSpeedValue"),
    "core.utils.win32.bindings.adl.ADLODNFanControl": Vendored("ADLODNFanControl"),
    "core.utils.win32.bindings.nvml.nvmlMemory_t": Vendored("nvmlMemory_t"),
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
// The WM_COPYDATA payloads of Shell_NotifyIcon (TRAYNOTIFYDATAW in ReactOS undocshell.h) and
// Shell_NotifyIconGetRect.
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

# Modules that keep their own ctypes code instead of using the bindings, structs.py and constants.py,
# by module name prefix.
OWN_CTYPES_MODULES: dict[str, str] = {
    "core.cloud": "YASB Cloud stays independent of the rest of YASB",
    "core.widgets.services.windows_desktops.interfaces": "undocumented interfaces, built per Windows build",
}


def keeps_own_ctypes(module: str) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in OWN_CTYPES_MODULES)


# comtypes interfaces with no SDK declaration to check against.
UNDOCUMENTED_INTERFACES: dict[str, str] = {
    "core.utils.win32.bindings.shell32.IQuietHoursSettings": "undocumented shell interface",
    "core.utils.win32.bindings.shell32.ITipInvocation": "undocumented shell interface",
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
    "WLAN_INTERFACE_STATE_CONNECTED": "wlan_interface_state_connected",
    "WLAN_INTF_OPCODE_CURRENT_CONNECTION": "wlan_intf_opcode_current_connection",
    "BATTERY_INFO_LEVEL_INFORMATION": "BatteryInformation",
    "BATTERY_INFO_LEVEL_TEMPERATURE": "BatteryTemperature",
    "FIND_EX_INFO_BASIC": "FindExInfoBasic",
    "MINIDUMP_WITH_DATA_SEGS": "MiniDumpWithDataSegs",
    "MINIDUMP_WITH_HANDLE_DATA": "MiniDumpWithHandleData",
    "MINIDUMP_WITH_UNLOADED_MODULES": "MiniDumpWithUnloadedModules",
    "MINIDUMP_WITH_INDIRECTLY_REFERENCED_MEMORY": "MiniDumpWithIndirectlyReferencedMemory",
    "MINIDUMP_WITH_PROCESS_THREAD_DATA": "MiniDumpWithProcessThreadData",
    "MINIDUMP_WITH_FULL_MEMORY_INFO": "MiniDumpWithFullMemoryInfo",
    "MINIDUMP_WITH_THREAD_INFO": "MiniDumpWithThreadInfo",
}

# Struct fields whose sign differs from the SDK header on purpose, as "<struct>.<field>": reason.
FIELD_SIGN_EXCEPTIONS: dict[str, str] = {
    "core.utils.win32.structs.BATTERY_QUERY_INFORMATION.AtRate": (
        "a negative mW discharge rate: Microsoft Learn and batclass.h use LONG, poclass.h declares ULONG"
    ),
}

# Constants from vendor SDKs in the bindings, by name pattern. constants.py gets no exceptions: an
# undocumented Windows value goes in core/utils/win32/undocumented.py.
CONSTANTS_NOT_IN_SDK: dict[str, str] = {
    "EVERYTHING_*": "voidtools Everything SDK",
    "NVML_*": "NVIDIA Management Library",
    "VCP_*": "VESA MCCS VCP code",
}


def constant_not_in_sdk(name: str) -> str | None:
    for pattern, reason in CONSTANTS_NOT_IN_SDK.items():
        if fnmatchcase(name, pattern):
            return reason
    return None

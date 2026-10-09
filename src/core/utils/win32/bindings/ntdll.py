"""Wrappers for ntdll win32 API functions"""

from ctypes import POINTER, WINFUNCTYPE, c_long, c_uint64, c_ulong, c_void_p, windll
from ctypes.wintypes import HANDLE, LONG, ULONG

from core.utils.win32.typecheck import CArgObject, CFunctionType

ntdll = windll.ntdll

# NtQueryInformationProcess - used to get process command line, etc.
ntdll.NtQueryInformationProcess.argtypes = [
    HANDLE,  # ProcessHandle
    ULONG,  # ProcessInformationClass
    c_void_p,  # ProcessInformation
    ULONG,  # ProcessInformationLength
    POINTER(ULONG),  # ReturnLength
]
ntdll.NtQueryInformationProcess.restype = LONG

# NtQuerySystemInformation - used for memory list information, etc.
ntdll.NtQuerySystemInformation.argtypes = [
    ULONG,  # SystemInformationClass
    c_void_p,  # SystemInformation
    ULONG,  # SystemInformationLength
    POINTER(ULONG),  # ReturnLength
]
ntdll.NtQuerySystemInformation.restype = LONG

# WNF (Windows Notification Facility) state change notifications. Undocumented, so check they exist.
WnfCallbackType = WINFUNCTYPE(
    c_long,  # NTSTATUS
    c_uint64,  # StateName
    c_ulong,  # ChangeStamp
    c_void_p,  # TypeId
    c_void_p,  # CallbackContext
    c_void_p,  # Buffer
    c_ulong,  # BufferSize
)

WNF_SUPPORTED = hasattr(ntdll, "RtlSubscribeWnfStateChangeNotification") and hasattr(
    ntdll, "RtlUnsubscribeWnfStateChangeNotification"
)

if WNF_SUPPORTED:
    ntdll.RtlSubscribeWnfStateChangeNotification.argtypes = [
        POINTER(c_void_p),  # Subscription
        c_uint64,  # StateName
        c_ulong,  # ChangeStamp
        WnfCallbackType,  # Callback
        c_void_p,  # CallbackContext
        c_void_p,  # TypeId
        c_ulong,  # SerializationGroup
        c_ulong,  # Unknown
    ]
    ntdll.RtlSubscribeWnfStateChangeNotification.restype = c_long

    ntdll.RtlUnsubscribeWnfStateChangeNotification.argtypes = [c_void_p]
    ntdll.RtlUnsubscribeWnfStateChangeNotification.restype = c_long


def RtlSubscribeWnfStateChangeNotification(
    subscription: CArgObject,
    state_name: int,
    change_stamp: int,
    callback: CFunctionType,
    callback_context: int | None,
    type_id: int | None,
    serialization_group: int,
    unknown: int,
) -> int:
    return ntdll.RtlSubscribeWnfStateChangeNotification(
        subscription, state_name, change_stamp, callback, callback_context, type_id, serialization_group, unknown
    )


def RtlUnsubscribeWnfStateChangeNotification(subscription: c_void_p) -> int:
    return ntdll.RtlUnsubscribeWnfStateChangeNotification(subscription)


# Process information class constants
ProcessCommandLineInformation = 60

# System information class constants
SystemMemoryListInformation = 80

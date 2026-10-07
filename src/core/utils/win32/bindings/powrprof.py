"""Wrappers for powerprof win32 API functions to make them easier to use and have proper types"""

from ctypes import POINTER, Array, c_ubyte, windll, wintypes

from core.utils.win32.structs import GUID
from core.utils.win32.typecheck import CArgObject

powrprof = windll.powrprof

# -- Power management function prototypes -- #
powrprof.PowerEnumerate.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    wintypes.DWORD,
    wintypes.ULONG,
    wintypes.LPBYTE,
    POINTER(wintypes.DWORD),
]
powrprof.PowerEnumerate.restype = wintypes.DWORD

powrprof.PowerReadFriendlyName.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(GUID),
    wintypes.LPBYTE,
    POINTER(wintypes.DWORD),
]
powrprof.PowerReadFriendlyName.restype = wintypes.DWORD

powrprof.PowerGetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(POINTER(GUID))]
powrprof.PowerGetActiveScheme.restype = wintypes.DWORD

powrprof.PowerSetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(GUID)]
powrprof.PowerSetActiveScheme.restype = wintypes.DWORD

powrprof.PowerReadACValueIndex.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(GUID),
    POINTER(wintypes.DWORD),
]
powrprof.PowerReadACValueIndex.restype = wintypes.DWORD

powrprof.PowerReadDCValueIndex.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(GUID),
    POINTER(wintypes.DWORD),
]
powrprof.PowerReadDCValueIndex.restype = wintypes.DWORD

powrprof.PowerWriteACValueIndex.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(GUID),
    wintypes.DWORD,
]
powrprof.PowerWriteACValueIndex.restype = wintypes.DWORD

powrprof.PowerWriteDCValueIndex.argtypes = [
    wintypes.HANDLE,
    POINTER(GUID),
    POINTER(GUID),
    POINTER(GUID),
    wintypes.DWORD,
]
powrprof.PowerWriteDCValueIndex.restype = wintypes.DWORD

powrprof.SetSuspendState.argtypes = [wintypes.BOOLEAN, wintypes.BOOLEAN, wintypes.BOOLEAN]
powrprof.SetSuspendState.restype = wintypes.BOOLEAN


# -- Power management function wrappers -- #
def PowerEnumerate(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupOfPowerSettingsGuid: CArgObject | None,
    AccessFlags: int,
    Index: int,
    Buffer: Array[c_ubyte],
    BufferSize: CArgObject,
) -> int:
    return powrprof.PowerEnumerate(
        RootPowerKey,
        SchemeGuid,
        SubGroupOfPowerSettingsGuid,
        AccessFlags,
        Index,
        Buffer,
        BufferSize,
    )


def PowerReadFriendlyName(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupOfPowerSettingsGuid: CArgObject | None,
    PowerSettingGuid: CArgObject | None,
    Buffer: Array[c_ubyte] | None,
    BufferSize: CArgObject,
) -> int:
    return powrprof.PowerReadFriendlyName(
        RootPowerKey,
        SchemeGuid,
        SubGroupOfPowerSettingsGuid,
        PowerSettingGuid,
        Buffer,
        BufferSize,
    )


def PowerGetActiveScheme(
    UserRootPowerKey: int | None,
    ActivePolicyGuid: CArgObject,
) -> int:
    return powrprof.PowerGetActiveScheme(UserRootPowerKey, ActivePolicyGuid)


def PowerSetActiveScheme(
    UserRootPowerKey: int | None,
    SchemeGuid: CArgObject,
) -> int:
    return powrprof.PowerSetActiveScheme(UserRootPowerKey, SchemeGuid)


def PowerReadACValueIndex(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupGuid: CArgObject | None,
    PowerSettingGuid: CArgObject | None,
    ValueIndex: CArgObject,
) -> int:
    return powrprof.PowerReadACValueIndex(RootPowerKey, SchemeGuid, SubGroupGuid, PowerSettingGuid, ValueIndex)


def PowerReadDCValueIndex(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupGuid: CArgObject | None,
    PowerSettingGuid: CArgObject | None,
    ValueIndex: CArgObject,
) -> int:
    return powrprof.PowerReadDCValueIndex(RootPowerKey, SchemeGuid, SubGroupGuid, PowerSettingGuid, ValueIndex)


def PowerWriteACValueIndex(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupGuid: CArgObject | None,
    PowerSettingGuid: CArgObject | None,
    ValueIndex: int,
) -> int:
    return powrprof.PowerWriteACValueIndex(RootPowerKey, SchemeGuid, SubGroupGuid, PowerSettingGuid, ValueIndex)


def PowerWriteDCValueIndex(
    RootPowerKey: int | None,
    SchemeGuid: CArgObject | None,
    SubGroupGuid: CArgObject | None,
    PowerSettingGuid: CArgObject | None,
    ValueIndex: int,
) -> int:
    return powrprof.PowerWriteDCValueIndex(RootPowerKey, SchemeGuid, SubGroupGuid, PowerSettingGuid, ValueIndex)


def SetSuspendState(bHibernate: bool, bForce: bool, bWakeupEventsDisabled: bool) -> int:
    return powrprof.SetSuspendState(bHibernate, bForce, bWakeupEventsDisabled)

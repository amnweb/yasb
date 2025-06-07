"""Wrappers for powerprof win32 API functions to make them easier to use and have proper types"""

from ctypes import POINTER, windll, wintypes

from core.utils.win32.structs import GUID

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
    POINTER(wintypes.DWORD),
    wintypes.LPBYTE,
    POINTER(wintypes.DWORD),
]
powrprof.PowerReadFriendlyName.restype = wintypes.DWORD

powrprof.PowerGetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(POINTER(GUID))]
powrprof.PowerGetActiveScheme.restype = wintypes.DWORD

powrprof.PowerSetActiveScheme.argtypes = [wintypes.HANDLE, POINTER(GUID)]
powrprof.PowerSetActiveScheme.restype = wintypes.DWORD


# -- Power management function wrappers -- #
def PowerEnumerate(
    RootPowerKey,
    SchemeGuid,
    SubGroupOfPowerSettingsGuid,
    AccessFlags,
    Index,
    Buffer,
    BufferSize,
):
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
    RootPowerKey,
    SchemeGuid,
    SubGroupOfPowerSettingsGuid,
    PowerSettingGuid,
    Buffer,
    BufferSize,
):
    return powrprof.PowerReadFriendlyName(
        RootPowerKey,
        SchemeGuid,
        SubGroupOfPowerSettingsGuid,
        PowerSettingGuid,
        Buffer,
        BufferSize,
    )


def PowerGetActiveScheme(
    UserRootPowerKey,
    ActivePolicyGuid,
):
    return powrprof.PowerGetActiveScheme(UserRootPowerKey, ActivePolicyGuid)


def PowerSetActiveScheme(
    UserRootPowerKey,
    SchemeGuid,
):
    return powrprof.PowerSetActiveScheme(UserRootPowerKey, SchemeGuid)

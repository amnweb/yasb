import logging
from ctypes import POINTER, byref, wintypes

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.powrprof import powrprof
from core.utils.win32.constants import (
    AC_LINE_OFFLINE,
    AC_LINE_ONLINE,
    ERROR_SUCCESS,
    GUID_DEVICE_POWER_POLICY_VIDEO_BRIGHTNESS,
    GUID_VIDEO_SUBGROUP,
)
from core.utils.win32.structs import GUID, SYSTEM_POWER_STATUS


def _is_online() -> bool | None:
    status = SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(byref(status)):
        return None
    if status.ACLineStatus == AC_LINE_ONLINE:
        return True
    if status.ACLineStatus == AC_LINE_OFFLINE:
        return False
    return None


def get_scheme_brightness() -> int | None:
    """Read preferred brightness (0-100) from the active power scheme."""
    online = _is_online()
    if online is None:
        return None
    scheme_ptr = POINTER(GUID)()
    if powrprof.PowerGetActiveScheme(None, byref(scheme_ptr)) != ERROR_SUCCESS:
        return None
    try:
        value = wintypes.DWORD()
        reader = powrprof.PowerReadACValueIndex if online else powrprof.PowerReadDCValueIndex
        if (
            reader(
                None,
                scheme_ptr,
                byref(GUID_VIDEO_SUBGROUP),
                byref(GUID_DEVICE_POWER_POLICY_VIDEO_BRIGHTNESS),
                byref(value),
            )
            != ERROR_SUCCESS
        ):
            return None
        return max(0, min(100, int(value.value)))
    finally:
        kernel32.LocalFree(scheme_ptr)


def set_scheme_brightness(value: int) -> bool:
    """Write preferred brightness (0-100) to AC and DC scheme indexes."""
    value = max(0, min(100, int(value)))
    scheme_ptr = POINTER(GUID)()
    if powrprof.PowerGetActiveScheme(None, byref(scheme_ptr)) != ERROR_SUCCESS:
        logging.debug("set_scheme_brightness: PowerGetActiveScheme failed")
        return False
    try:
        for writer in (powrprof.PowerWriteACValueIndex, powrprof.PowerWriteDCValueIndex):
            if (
                writer(
                    None,
                    scheme_ptr,
                    byref(GUID_VIDEO_SUBGROUP),
                    byref(GUID_DEVICE_POWER_POLICY_VIDEO_BRIGHTNESS),
                    value,
                )
                != ERROR_SUCCESS
            ):
                logging.debug("set_scheme_brightness: PowerWrite failed")
                return False
        if powrprof.PowerSetActiveScheme(None, scheme_ptr) != ERROR_SUCCESS:
            logging.debug("set_scheme_brightness: PowerSetActiveScheme failed")
            return False
        return True
    finally:
        kernel32.LocalFree(scheme_ptr)


def policy_brightness_guid() -> GUID:
    """GUID struct for RegisterPowerSettingNotification."""
    return GUID.from_buffer_copy(GUID_DEVICE_POWER_POLICY_VIDEO_BRIGHTNESS)

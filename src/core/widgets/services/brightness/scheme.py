import logging
import uuid
from ctypes import POINTER, byref, wintypes

from core.utils.win32.bindings import powrprof
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.constants import ERROR_SUCCESS
from core.utils.win32.structs import GUID, SYSTEM_POWER_STATUS

_VIDEO_SUBGROUP = GUID.from_buffer_copy(uuid.UUID("7516b95f-f776-4464-8c53-06167f40cc99").bytes_le)
_POLICY_BRIGHTNESS = GUID.from_buffer_copy(uuid.UUID("aded5e82-b909-4619-9949-f5d71dac0bcb").bytes_le)


def _is_online() -> bool | None:
    status = SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(byref(status)):
        return None
    if status.ACLineStatus == 1:
        return True
    if status.ACLineStatus == 0:
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
        if reader(None, scheme_ptr, byref(_VIDEO_SUBGROUP), byref(_POLICY_BRIGHTNESS), byref(value)) != ERROR_SUCCESS:
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
            if writer(None, scheme_ptr, byref(_VIDEO_SUBGROUP), byref(_POLICY_BRIGHTNESS), value) != ERROR_SUCCESS:
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
    return GUID.from_buffer_copy(_POLICY_BRIGHTNESS)

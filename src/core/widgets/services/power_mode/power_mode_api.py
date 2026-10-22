import ctypes
import uuid
import winreg
from ctypes import byref

from core.utils.win32.bindings.kernel32 import LocalFree
from core.utils.win32.bindings.powrprof import (
    PowerGetActiveScheme,
    PowerGetUserConfiguredACPowerMode,
    PowerSetUserConfiguredACPowerMode,
    PowerSetUserConfiguredDCPowerMode,
)
from core.utils.win32.constants import GUID_POWERSCHEME_PERSONALITY
from core.utils.win32.registry_keys import POWER_SCHEMES_KEY
from core.utils.win32.structs import GUID
from core.utils.win32.undocumented import POWER_MODE_BALANCED, POWER_MODE_BEST_EFFICIENCY, POWER_MODE_BEST_PERFORMANCE

_MODES: list[tuple[str, GUID]] = [
    ("Best power efficiency", POWER_MODE_BEST_EFFICIENCY),
    ("Balanced", POWER_MODE_BALANCED),
    ("Best performance", POWER_MODE_BEST_PERFORMANCE),
]


def get_modes() -> list[tuple[str, GUID]]:
    return list(_MODES)


def is_mode_supported() -> bool:
    """Return True if the active plan supports Power Mode overlays.

    Only Balanced plans (personality value: 2) support Windows 11 Power Mode overlays.
    This works for both built-in and custom power plans.
    """
    plan = _get_active_scheme_str()
    if plan is None:
        return False

    try:
        path = f"{POWER_SCHEMES_KEY}\\{plan}\\{GUID_POWERSCHEME_PERSONALITY.to_uuid()}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            personality, _ = winreg.QueryValueEx(key, "ACSettingIndex")
            return personality == 2
    except OSError:
        return False


def get_active_mode() -> tuple[str, GUID] | None:
    guid = GUID()
    if PowerGetUserConfiguredACPowerMode(guid) == 0:
        return _mode_name(guid)

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, POWER_SCHEMES_KEY) as key:
            guid_str = winreg.QueryValueEx(key, "ActiveOverlayAcPowerScheme")[0].strip("{}")
            return _mode_name(GUID.from_buffer_copy(uuid.UUID(guid_str).bytes_le))
    except Exception:
        return None


def set_mode(guid: GUID) -> bool:
    ok = True

    if PowerSetUserConfiguredACPowerMode(guid) != 0:
        ok = False
    if PowerSetUserConfiguredDCPowerMode(guid) != 0:
        ok = False

    return ok


def guids_equal(a: GUID, b: GUID) -> bool:
    return ctypes.string_at(byref(a), ctypes.sizeof(GUID)) == ctypes.string_at(byref(b), ctypes.sizeof(GUID))


def _get_active_scheme_str() -> str | None:
    """Return the active power scheme GUID as a lowercase string, or None on failure."""
    ptr = ctypes.POINTER(GUID)()
    if PowerGetActiveScheme(None, byref(ptr)) != 0 or not ptr:
        return None
    result = str(GUID.from_buffer_copy(ptr.contents))
    LocalFree(ptr)
    return result


def _mode_name(guid: GUID) -> tuple[str, GUID] | None:
    for name, g in _MODES:
        if guids_equal(guid, g):
            return (name, guid)
    return None

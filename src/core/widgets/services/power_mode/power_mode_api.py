import ctypes
import uuid
import winreg
from ctypes import byref, wintypes

from core.utils.win32.structs import GUID

_powrprof = ctypes.WinDLL("powrprof.dll")

_POWER_SCHEMES_KEY = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
_PERSONALITY_SETTING = "245d8541-3943-4422-b025-13a784f679b7"
_BALANCED = GUID.from_buffer_copy(uuid.UUID("00000000-0000-0000-0000-000000000000").bytes_le)
_BEST_EFFICIENCY = GUID.from_buffer_copy(uuid.UUID("961cc777-2547-4f9d-8174-7d86181b8a7a").bytes_le)
_BEST_PERFORMANCE = GUID.from_buffer_copy(uuid.UUID("ded574b5-45a0-4f42-8737-46345c09c238").bytes_le)

_MODES: list[tuple[str, GUID]] = [
    ("Best power efficiency", _BEST_EFFICIENCY),
    ("Balanced", _BALANCED),
    ("Best performance", _BEST_PERFORMANCE),
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
        path = f"{_POWER_SCHEMES_KEY}\\{plan}\\{_PERSONALITY_SETTING}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            personality, _ = winreg.QueryValueEx(key, "ACSettingIndex")
            return personality == 2
    except OSError:
        return False


def get_active_mode() -> tuple[str, GUID] | None:
    guid = GUID()
    fn = _powrprof.PowerGetUserConfiguredACPowerMode
    fn.argtypes = [ctypes.POINTER(GUID)]
    fn.restype = wintypes.DWORD
    if fn(byref(guid)) == 0:
        return _mode_name(guid)

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _POWER_SCHEMES_KEY) as key:
            guid_str = winreg.QueryValueEx(key, "ActiveOverlayAcPowerScheme")[0].strip("{}")
            return _mode_name(GUID.from_buffer_copy(uuid.UUID(guid_str).bytes_le))
    except Exception:
        return None


def set_mode(guid: GUID) -> bool:
    ok = True

    set_ac = _powrprof.PowerSetUserConfiguredACPowerMode
    set_ac.argtypes = [ctypes.POINTER(GUID)]
    set_ac.restype = wintypes.DWORD
    if set_ac(byref(guid)) != 0:
        ok = False

    set_dc = _powrprof.PowerSetUserConfiguredDCPowerMode
    set_dc.argtypes = [ctypes.POINTER(GUID)]
    set_dc.restype = wintypes.DWORD
    if set_dc(byref(guid)) != 0:
        ok = False

    return ok


def guids_equal(a: GUID, b: GUID) -> bool:
    return ctypes.string_at(byref(a), ctypes.sizeof(GUID)) == ctypes.string_at(byref(b), ctypes.sizeof(GUID))


def _get_active_scheme_str() -> str | None:
    """Return the active power scheme GUID as a lowercase string, or None on failure."""
    PowerGetActiveScheme = _powrprof.PowerGetActiveScheme
    PowerGetActiveScheme.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.POINTER(GUID))]
    PowerGetActiveScheme.restype = wintypes.DWORD
    ptr = ctypes.POINTER(GUID)()
    if PowerGetActiveScheme(None, byref(ptr)) != 0 or not ptr:
        return None
    result = str(GUID.from_buffer_copy(ptr.contents))
    ctypes.windll.kernel32.LocalFree(ptr)
    return result


def _mode_name(guid: GUID) -> tuple[str, GUID] | None:
    for name, g in _MODES:
        if guids_equal(guid, g):
            return (name, guid)
    return None

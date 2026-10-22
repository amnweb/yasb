"""Wrappers for advapi32 win32 API functions"""

from ctypes import (
    POINTER,
    Array,
    WinDLL,
    byref,
    c_char,
    c_void_p,
    create_string_buffer,
    create_unicode_buffer,
    wstring_at,
)
from ctypes.wintypes import BOOL, DWORD, HANDLE, HKEY, INT, LONG, LPCWSTR, LPDWORD, LPVOID, LPWSTR

from core.utils.win32.bindings.kernel32 import CloseHandle, GetCurrentProcess, LocalFree
from core.utils.win32.constants import (
    SE_PRIVILEGE_ENABLED,
    TOKEN_INFORMATION_GROUPS,
    TOKEN_INFORMATION_USER,
    TOKEN_QUERY,
)
from core.utils.win32.structs import (
    LUID,
    LUID_AND_ATTRIBUTES,
    SID_AND_ATTRIBUTES,
    TOKEN_GROUPS,
    TOKEN_PRIVILEGES,
    TOKEN_USER,
)

advapi32 = WinDLL("advapi32", use_last_error=True)

advapi32.RegNotifyChangeKeyValue.argtypes = [HKEY, BOOL, DWORD, HANDLE, BOOL]
advapi32.RegNotifyChangeKeyValue.restype = LONG

advapi32.OpenProcessToken.argtypes = [HANDLE, DWORD, POINTER(HANDLE)]
advapi32.OpenProcessToken.restype = BOOL

advapi32.GetTokenInformation.argtypes = [HANDLE, INT, LPVOID, DWORD, LPDWORD]
advapi32.GetTokenInformation.restype = BOOL

advapi32.ConvertSidToStringSidW.argtypes = [c_void_p, POINTER(c_void_p)]
advapi32.ConvertSidToStringSidW.restype = BOOL

advapi32.LookupPrivilegeValueW.argtypes = [LPCWSTR, LPCWSTR, POINTER(LUID)]
advapi32.LookupPrivilegeValueW.restype = BOOL

advapi32.AdjustTokenPrivileges.argtypes = [
    HANDLE,
    BOOL,
    POINTER(TOKEN_PRIVILEGES),
    DWORD,
    POINTER(TOKEN_PRIVILEGES),
    LPDWORD,
]
advapi32.AdjustTokenPrivileges.restype = BOOL

advapi32.GetUserNameW.argtypes = [LPWSTR, LPDWORD]
advapi32.GetUserNameW.restype = BOOL


def RegNotifyChangeKeyValue(
    hKey: int, bWatchSubtree: bool, dwNotifyFilter: int, hEvent: int | None, fAsynchronous: bool
) -> int:
    return advapi32.RegNotifyChangeKeyValue(hKey, bWatchSubtree, dwNotifyFilter, hEvent, fAsynchronous)


def OpenProcessToken(hProcess: int, dwDesiredAccess: int) -> int | None:
    token = HANDLE()
    return token.value if advapi32.OpenProcessToken(hProcess, dwDesiredAccess, byref(token)) else None


def _token_information(token: int, information_class: int) -> Array[c_char] | None:
    size = DWORD()
    advapi32.GetTokenInformation(token, information_class, None, 0, byref(size))
    if not size.value:
        return None
    buffer = create_string_buffer(size.value)
    if not advapi32.GetTokenInformation(token, information_class, buffer, size, byref(size)):
        return None
    return buffer


def sid_to_string(sid: int | None) -> str | None:
    text = c_void_p()
    if not advapi32.ConvertSidToStringSidW(sid, byref(text)):
        return None
    try:
        return wstring_at(text)
    finally:
        LocalFree(text)


def get_token_user_sid(token: int) -> str | None:
    buffer = _token_information(token, TOKEN_INFORMATION_USER)
    return sid_to_string(TOKEN_USER.from_buffer(buffer).User.Sid) if buffer is not None else None


def get_token_group_sids(token: int) -> list[str]:
    """String SIDs of every group in the token, including deny-only ones."""
    buffer = _token_information(token, TOKEN_INFORMATION_GROUPS)
    if buffer is None:
        return []
    count = TOKEN_GROUPS.from_buffer(buffer).GroupCount
    groups = (SID_AND_ATTRIBUTES * count).from_buffer(buffer, TOKEN_GROUPS.Groups.offset)
    return [sid for group in groups if (sid := sid_to_string(group.Sid))]


def enable_token_privilege(token: int, privilege: str) -> bool:
    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(None, privilege, byref(luid)):
        return False
    state = TOKEN_PRIVILEGES(PrivilegeCount=1)
    state.Privileges[0] = LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED)
    return bool(advapi32.AdjustTokenPrivileges(token, False, byref(state), 0, None, None))


def get_current_user_sid() -> str | None:
    token = OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY)
    if token is None:
        return None
    try:
        return get_token_user_sid(token)
    finally:
        CloseHandle(token)


def GetUserName() -> str | None:
    size = DWORD(257)
    buffer = create_unicode_buffer(size.value)
    return buffer.value if advapi32.GetUserNameW(buffer, byref(size)) else None

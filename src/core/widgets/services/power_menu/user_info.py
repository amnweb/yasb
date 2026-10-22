import os
import winreg
from functools import cache

from core.utils.win32.bindings.advapi32 import GetUserName, OpenProcessToken, get_current_user_sid, get_token_group_sids
from core.utils.win32.bindings.kernel32 import CloseHandle, GetCurrentProcess
from core.utils.win32.bindings.secur32 import GetUserNameEx
from core.utils.win32.constants import NAME_DISPLAY, NAME_USER_PRINCIPAL, TOKEN_QUERY
from core.utils.win32.registry_keys import ACCOUNT_PICTURE_USERS_KEY, IDENTITY_USER_PROPERTIES_KEY

ADMINISTRATORS_SID = "S-1-5-32-544"


@cache
def get_windows_username() -> str:
    """Get the Windows display name for the current user."""
    return GetUserNameEx(NAME_DISPLAY) or GetUserName() or ""


@cache
def get_account_type() -> str:
    """Get account type: Administrator or Standard User."""
    token = OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY)
    if token is None:
        return "Standard User"
    try:
        return "Administrator" if ADMINISTRATORS_SID in get_token_group_sids(token) else "Standard User"
    finally:
        CloseHandle(token)


@cache
def get_user_email() -> str | None:
    """Get the email address associated with the current Windows user account."""
    if email := GetUserNameEx(NAME_USER_PRINCIPAL):
        return email
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            IDENTITY_USER_PROPERTIES_KEY,
        ) as key:
            if winreg.QueryInfoKey(key)[0] > 0:
                return winreg.EnumKey(key, 0)
    except Exception:
        pass
    return None


@cache
def get_user_avatar_path() -> str | None:
    """Get the current user's account picture from registry using the process token SID."""
    sid = get_current_user_sid()
    if sid is not None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                f"{ACCOUNT_PICTURE_USERS_KEY}\\{sid}",
            ) as key:
                best_path, best_res = None, 0
                for i in range(winreg.QueryInfoKey(key)[1]):
                    name, value, _ = winreg.EnumValue(key, i)
                    if name.startswith("Image") and isinstance(value, str) and os.path.isfile(value):
                        try:
                            res = int(name.removeprefix("Image"))
                        except ValueError:
                            continue
                        if res > best_res:
                            best_res, best_path = res, value
                return best_path
        except Exception:
            pass
    fallback = os.path.join(
        os.environ.get("ProgramData", r"C:\ProgramData"), "Microsoft", "User Account Pictures", "user-192.png"
    )
    return fallback if os.path.isfile(fallback) else None

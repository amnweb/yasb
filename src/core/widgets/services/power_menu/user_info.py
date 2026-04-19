import os
import winreg
from functools import cache

import win32api
import win32con
import win32security


@cache
def get_windows_username() -> str:
    """Get the Windows display name for the current user."""
    try:
        return win32api.GetUserNameEx(3)  # NameDisplay
    except Exception:
        return win32api.GetUserName()


@cache
def get_account_type() -> str:
    """Get account type: Administrator or Standard User."""
    try:
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        admin_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")
        groups = win32security.GetTokenInformation(token, win32security.TokenGroups)
        for sid, _ in groups:
            if sid == admin_sid:
                return "Administrator"
        return "Standard User"
    except Exception:
        return "Standard User"


@cache
def get_user_email() -> str | None:
    """Get the email address associated with the current Windows user account."""
    try:
        return win32api.GetUserNameEx(8)  # NameUserPrincipal
    except Exception:
        pass
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\IdentityCRL\UserExtendedProperties",
        ) as key:
            if winreg.QueryInfoKey(key)[0] > 0:
                return winreg.EnumKey(key, 0)
    except Exception:
        pass
    return None


@cache
def get_user_avatar_path() -> str | None:
    """Get the current user's account picture from registry using the process token SID."""
    try:
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        sid = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AccountPicture\\Users\\{sid}",
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

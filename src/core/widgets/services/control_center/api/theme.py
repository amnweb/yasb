import ctypes
import ctypes.wintypes
import logging
import winreg
from typing import Literal

ThemeMode = Literal["light", "dark"]

_WM_SETTINGCHANGE = 0x001A
_HWND_BROADCAST = 0xFFFF

_user32_private = ctypes.WinDLL("user32")
_send_notify_msg = _user32_private.SendNotifyMessageW
_send_notify_msg.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.c_wchar_p,
]
_send_notify_msg.restype = ctypes.wintypes.BOOL


class ThemeService:
    """Helpers for reading and switching the Windows system theme."""

    _PERSONALIZE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"

    @classmethod
    def get_theme_mode(cls) -> ThemeMode:
        """Return the current Windows app theme mode."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls._PERSONALIZE_KEY) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if int(value) else "dark"
        except Exception as exc:
            logging.error("Failed to read Windows theme mode: %s", exc)
            return "dark"

    @staticmethod
    def _broadcast_setting_change() -> bool:
        """Broadcast WM_SETTINGCHANGE asynchronously to all top-level windows."""
        try:
            result = _send_notify_msg(_HWND_BROADCAST, _WM_SETTINGCHANGE, 0, "ImmersiveColorSet")
            return bool(result)
        except Exception as exc:
            logging.error("Failed to broadcast setting change: %s", exc)
            return False

    @classmethod
    def set_theme_mode(cls, mode: ThemeMode) -> bool:
        """Set Windows system theme mode."""
        value = 1 if mode == "light" else 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls._PERSONALIZE_KEY, access=winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)

            if not cls._broadcast_setting_change():
                logging.warning("Theme set to %s but broadcast notification failed.", mode)
            return True
        except Exception as exc:
            logging.error("Failed to set Windows theme mode to %s: %s", mode, exc)
            return False

    @classmethod
    def toggle_theme_mode(cls) -> ThemeMode | None:
        """Toggle between light and dark theme. Returns the new mode, or None on failure."""
        next_mode: ThemeMode = "light" if cls.get_theme_mode() == "dark" else "dark"
        if cls.set_theme_mode(next_mode):
            return next_mode
        return None

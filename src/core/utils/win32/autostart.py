"""Starting YASB with Windows, through the current user's Run key. Kept free of Qt, so yasbc can use it too."""

import logging
import winreg

from core.utils.win32.registry_keys import RUN_KEY


def _open_startup_registry(access_flag: int):
    """Helper function to open the startup registry key."""
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access_flag)


def enable_autostart(app_name: str, executable_path: str) -> bool:
    """Add application to Windows startup."""
    try:
        with _open_startup_registry(winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, executable_path)
        logging.info("%s added to startup", app_name)
        return True
    except Exception as e:
        logging.error("Failed to add %s to startup: %s", app_name, e)
        return False


def disable_autostart(app_name: str) -> bool:
    """Remove application from Windows startup."""
    try:
        # First check if the entry exists
        if is_autostart_enabled(app_name):
            with _open_startup_registry(winreg.KEY_ALL_ACCESS) as key:
                winreg.DeleteValue(key, app_name)
            logging.info("%s removed from startup", app_name)
        else:
            logging.info("Startup entry for %s not found", app_name)
        return True
    except Exception as e:
        logging.error("Failed to remove %s from startup: %s", app_name, e)
        return False


def is_autostart_enabled(app_name: str) -> bool:
    """Check if application is in Windows startup."""
    try:
        with _open_startup_registry(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, app_name)
        return True
    except OSError:
        return False
    except Exception as e:
        logging.error("Failed to check startup status for %s: %s", app_name, e)
        return False

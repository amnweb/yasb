import ctypes
import ctypes.wintypes
import logging
import winreg
from contextlib import suppress

import psutil
from win32api import GetMonitorInfo, MonitorFromWindow
from win32gui import GetClassName, GetWindowPlacement, GetWindowRect, GetWindowText
from win32process import GetWindowThreadProcessId

SW_MAXIMIZE = 3
DWMWA_EXTENDED_FRAME_BOUNDS = 9
dwmapi = ctypes.WinDLL("dwmapi")


def get_monitor_hwnd(window_hwnd: int) -> int:
    return int(MonitorFromWindow(window_hwnd))


def get_monitor_info(monitor_hwnd: int) -> dict:
    monitor_info = GetMonitorInfo(monitor_hwnd)
    return {
        "rect": {
            "x": monitor_info["Monitor"][0],
            "y": monitor_info["Monitor"][1],
            "width": monitor_info["Monitor"][2],
            "height": monitor_info["Monitor"][3],
        },
        "rect_work_area": {
            "x": monitor_info["Work"][0],
            "y": monitor_info["Work"][1],
            "width": monitor_info["Work"][2],
            "height": monitor_info["Work"][3],
        },
        "flags": monitor_info["Flags"],
        "device": monitor_info["Device"],
    }


def get_process_info(hwnd: int) -> dict:
    process_id = GetWindowThreadProcessId(hwnd)
    process = psutil.Process(process_id[-1])
    return {
        "name": process.name(),
        "pid": process.pid,
        "ppid": process.ppid(),
        "cpu_percent": process.cpu_percent(),
        "mem_percent": process.memory_percent(),
        "num_threads": process.num_threads(),
        "username": process.username(),
        "status": process.status(),
    }


def get_window_extended_frame_bounds(hwnd: int) -> dict:
    rect = ctypes.wintypes.RECT()

    dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(hwnd),
        ctypes.wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )

    return {"x": rect.left, "y": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}


def get_window_rect(hwnd: int) -> dict:
    window_rect = GetWindowRect(hwnd)
    return {
        "x": window_rect[0],
        "y": window_rect[1],
        "width": window_rect[2] - window_rect[0],
        "height": window_rect[3] - window_rect[1],
    }


def is_window_maximised(hwnd: int) -> bool:
    window_placement = GetWindowPlacement(hwnd)
    return window_placement[1] == SW_MAXIMIZE


def get_hwnd_info(hwnd: int) -> dict:
    with suppress(Exception):
        monitor_hwnd = get_monitor_hwnd(hwnd)
        monitor_info = get_monitor_info(monitor_hwnd)

        return {
            "hwnd": hwnd,
            "title": GetWindowText(hwnd),
            "class_name": GetClassName(hwnd),
            "process": get_process_info(hwnd),
            "monitor_hwnd": monitor_hwnd,
            "monitor_info": monitor_info,
            "rect": get_window_rect(hwnd),
        }


def _open_startup_registry(access_flag: int):
    """Helper function to open the startup registry key."""
    registry_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, access_flag)


def enable_autostart(app_name: str, executable_path: str) -> bool:
    """Add application to Windows startup."""
    try:
        with _open_startup_registry(winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, executable_path)
        logging.info(f"{app_name} added to startup")
        return True
    except Exception as e:
        logging.error(f"Failed to add {app_name} to startup: {e}")
        return False


def disable_autostart(app_name: str) -> bool:
    """Remove application from Windows startup."""
    try:
        # First check if the entry exists
        if is_autostart_enabled(app_name):
            with _open_startup_registry(winreg.KEY_ALL_ACCESS) as key:
                winreg.DeleteValue(key, app_name)
            logging.info(f"{app_name} removed from startup")
        else:
            logging.info(f"Startup entry for {app_name} not found")
        return True
    except Exception as e:
        logging.error(f"Failed to remove {app_name} from startup: {e}")
        return False


def is_autostart_enabled(app_name: str) -> bool:
    """Check if application is in Windows startup."""
    try:
        with _open_startup_registry(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, app_name)
        return True
    except WindowsError:
        return False
    except Exception as e:
        logging.error(f"Failed to check startup status for {app_name}: {e}")
        return False

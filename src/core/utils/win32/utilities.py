import ctypes
import ctypes.wintypes
import logging
import winreg
from contextlib import suppress
from ctypes import GetLastError
from functools import lru_cache

from win32api import GetMonitorInfo, MonitorFromWindow
from win32gui import GetClassName, GetWindowPlacement, GetWindowRect, GetWindowText

from core.utils.win32.bindings import (
    CloseHandle,
    DwmGetWindowAttribute,
    DwmSetWindowAttribute,
    GetForegroundWindow,
    GetWindowThreadProcessId,
    OpenProcess,
    QueryFullProcessImageNameW,
    SetForegroundWindow,
)
from core.utils.win32.constants import (
    ACCESS_DENIED,
    DWMWA_EXTENDED_FRAME_BOUNDS,
    ERROR_INVALID_HANDLE,
    ERROR_INVALID_PARAMETER,
    PROCESS_QUERY_LIMITED_INFORMATION,
    SW_MAXIMIZE,
)


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


@lru_cache(maxsize=4096)
def _pid_to_name(pid: int) -> str | None:
    """Return the executable file name for a PID or None on failure."""
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        return None
    try:
        size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            val = buf.value
            i = val.rfind("\\")
            return val[i + 1 :] if i != -1 else val
        return None
    finally:
        CloseHandle(h_process)


def get_process_info(hwnd: int) -> dict:
    """Get process info { name, pid }.

    - Returns pid=0 when no valid PID is associated or process is gone.
    - Returns name=None when access is denied or name can't be resolved.
    """
    try:
        pid_c = ctypes.c_ulong(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        pid = int(pid_c.value)
    except Exception:
        return {"name": None, "pid": 0}

    if pid <= 0:
        return {"name": None, "pid": 0}

    name = _pid_to_name(pid)
    if name is not None:
        return {"name": name, "pid": pid}

    # Disambiguate failure: try opening to check error cause
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        # Determine why it failed
        err = GetLastError()
        if err in (ERROR_INVALID_PARAMETER, ERROR_INVALID_HANDLE, 0):
            # Process likely no longer exists
            return {"name": None, "pid": 0}
        if err == ACCESS_DENIED:
            # Access denied: process exists but protected
            return {"name": None, "pid": pid}
        # Unknown: keep pid but no name
        return {"name": None, "pid": pid}
    else:
        CloseHandle(h_process)
        # Handle opened but name lookup failed: keep pid without name
        return {"name": None, "pid": pid}


def get_window_extended_frame_bounds(hwnd: int) -> dict:
    rect = ctypes.wintypes.RECT()

    DwmGetWindowAttribute(
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


def is_window_maximized(hwnd: int) -> bool:
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


def qmenu_rounded_corners(qwidget):
    """
    Set default Windows 11 rounded corners for a QMenu
    This function uses the DWM API to set the window corner preference for a QMenu.
    Windows 10 is not supported, as it does not have the DWM API for rounded corners.
    """
    try:
        hwnd = int(qwidget.winId())
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2

        preference = ctypes.wintypes.DWORD(DWMWCP_ROUND)
        DwmSetWindowAttribute(
            ctypes.wintypes.HWND(hwnd),
            ctypes.wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        # If we can't set the rounded corners, we just ignore the error
        # This can happen if the DWM API is not available
        pass


def get_foreground_hwnd():
    """Get HWND of the current foreground window"""
    return GetForegroundWindow()


def set_foreground_hwnd(hwnd):
    """Set focus to the given HWND"""
    if hwnd and hwnd != 0:
        SetForegroundWindow(int(hwnd))


def find_focused_screen(follow_mouse, follow_window, screens=None):
    """Find the screen that should be focused based on mouse position or active window."""
    import win32api
    import win32gui
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import QApplication

    qt_screens = QApplication.screens()
    primary_screen = QApplication.primaryScreen()

    def is_valid(name):
        return screens is None or any(name in s for s in screens)

    # Map device names to Qt screen names for window focus
    device_to_screen = {
        win32api.GetMonitorInfo(win32api.MonitorFromRect((geo.left(), geo.top(), geo.right(), geo.bottom()))).get(
            "Device"
        ): screen.name()
        for screen in qt_screens
        for geo in [screen.geometry()]
    }

    if follow_mouse:
        try:
            pos = QCursor.pos()
            for screen in qt_screens:
                if screen.geometry().contains(pos) and is_valid(screen.name()):
                    return screen.name()
        except Exception as e:
            logging.error(f"Exception in follow_mouse: {e}")

    if follow_window:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            monitor = get_monitor_hwnd(hwnd)
            device_name = win32api.GetMonitorInfo(monitor).get("Device")
            screen_name = device_to_screen.get(device_name)
            if screen_name and is_valid(screen_name):
                return screen_name

    # Fallback to primary screen
    if primary_screen is not None and is_valid(primary_screen.name()):
        return primary_screen.name()
    # Final fallback to first available screen from the list if no other screen is valid
    for screen in qt_screens:
        if is_valid(screen.name()):
            return screen.name()
    return None


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

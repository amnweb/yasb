import ctypes
import ctypes.wintypes
import logging
import winreg
from contextlib import suppress
from ctypes import GetLastError, byref, c_ulong, create_unicode_buffer

import win32api
import win32gui
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QWidget
from win32api import GetMonitorInfo, MonitorFromWindow
from win32gui import GetClassName, GetWindowPlacement, GetWindowRect, GetWindowText
from winrt.windows.management.deployment import PackageManager

from core.utils.utilities import is_windows_10
from core.utils.win32.bindings import (
    CloseHandle,
    DwmGetWindowAttribute,
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


def get_process_info(hwnd: int) -> dict:
    """Get process info { name, pid, path }.

    - Returns pid=0 when no valid PID is associated or process is gone.
    - Returns name=None when access is denied or name can't be resolved.
    - Returns path=None when access is denied or path can't be resolved.
    """
    try:
        pid_c = ctypes.c_ulong(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        pid = int(pid_c.value)
    except Exception:
        return {"name": None, "pid": 0, "path": None}

    if pid <= 0:
        return {"name": None, "pid": 0, "path": None}

    # Try to get the full path first (includes name extraction as bonus)
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        # Determine why it failed
        err = GetLastError()
        if err in (ERROR_INVALID_PARAMETER, ERROR_INVALID_HANDLE, 0):
            # Process likely no longer exists
            return {"name": None, "pid": 0, "path": None}
        if err == ACCESS_DENIED:
            # Access denied: process exists but protected
            return {"name": None, "pid": pid, "path": None}
        # Unknown: keep pid but no name/path
        return {"name": None, "pid": pid, "path": None}

    try:
        # Get full path
        size = c_ulong(1024)
        buf = create_unicode_buffer(size.value)
        path = None
        if QueryFullProcessImageNameW(h_process, 0, buf, byref(size)):
            path = buf.value

        # Extract name from path if we got it
        name = None
        if path:
            i = path.rfind("\\")
            name = path[i + 1 :] if i != -1 else path

        return {"name": name, "pid": pid, "path": path}
    finally:
        CloseHandle(h_process)


def get_app_name_from_pid(pid: int) -> str | None:
    """
    Get the actual application name - handles both UWP and Win32 apps properly.
    """
    try:
        h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return None

        try:
            # Check if this is a UWP app and get its proper display name
            length = c_ulong(0)
            kernel32 = ctypes.windll.kernel32
            ERROR_INSUFFICIENT_BUFFER = 0x7A

            res = kernel32.GetPackageFullName(h_process, byref(length), None)

            if res == ERROR_INSUFFICIENT_BUFFER and length.value > 0:
                # This is a UWP app - get its package display name
                buf = create_unicode_buffer(length.value)
                res = kernel32.GetPackageFullName(h_process, byref(length), buf)

                if res == 0 and buf.value:
                    package_full_name = buf.value
                    CloseHandle(h_process)

                    # Use WinRT API to get the SHORT name
                    try:
                        package_manager = PackageManager()

                        # Find the package by full name
                        for package in package_manager.find_packages_by_user_security_id(""):
                            if package.id.full_name == package_full_name:
                                # Try to get SHORT name from app list entries first
                                try:
                                    app_entries = package.get_app_list_entries()
                                    if app_entries and len(app_entries) > 0:
                                        # Use the first app entry's short name
                                        short_name = app_entries[0].display_info.display_name
                                        if short_name and short_name.strip():
                                            return short_name.strip()
                                except Exception:
                                    pass

                                # Fallback to package display name
                                display_name = package.display_name
                                if display_name and display_name.strip():
                                    return display_name.strip()
                                break
                    except Exception as e:
                        logging.debug(f"Failed to get UWP package display name for {package_full_name}: {e}")

                    # If WinRT fails, we already closed the handle, so return None
                    return None

            # This is a Win32 app - get FileDescription from executable
            size = c_ulong(1024)
            buf = create_unicode_buffer(size.value)
            if QueryFullProcessImageNameW(h_process, 0, buf, byref(size)):
                exe_path = buf.value

                # Get ProductName or FileDescription from executable version info
                try:
                    lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
                    string_file_info = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\"

                    try:
                        app_name = win32api.GetFileVersionInfo(exe_path, string_file_info + "FileDescription")
                        if app_name and app_name.strip():
                            return app_name.strip()
                    except:
                        pass
                    try:
                        app_name = win32api.GetFileVersionInfo(exe_path, string_file_info + "ProductName")
                        if app_name and app_name.strip():
                            return app_name.strip()
                    except:
                        pass
                except Exception as e:
                    logging.debug(f"Failed to get version info for {exe_path}: {e}")
        finally:
            CloseHandle(h_process)
    except Exception as e:
        logging.debug(f"Failed to get app name for PID {pid}: {e}")

    return None


def get_app_name_from_aumid(aumid: str) -> str | None:
    """
    Get the real app name from AUMID using Windows Package Manager API.
    Works for any UWP app (Edge PWAs, Microsoft Store apps, etc.).
    """
    try:
        if "!" in aumid:
            package_family = aumid.split("!")[0]
        else:
            package_family = aumid

        package_manager = PackageManager()
        for package in package_manager.find_packages_by_user_security_id(""):
            try:
                family_name = package.id.family_name
                if family_name and package_family == family_name:
                    # Try to get the SHORT name from app list entries
                    try:
                        app_entries = package.get_app_list_entries()
                        for app_entry in app_entries:
                            if app_entry.app_user_model_id == aumid:
                                short_name = app_entry.display_info.display_name
                                if short_name and short_name.strip():
                                    return short_name.strip()
                    except Exception:
                        pass

                    # Fallback to package display name if app list entry method fails
                    display_name = package.display_name
                    if display_name:
                        return display_name
            except Exception:
                continue

    except ImportError:
        logging.debug("winrt module not available, cannot resolve UWP app names")
    except Exception as e:
        logging.debug(f"Failed to get UWP app name from PackageManager: {e}")

    return None


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


def apply_qmenu_style(qwidget: QWidget):
    """
    Set blur and rounded corners for a QMenu on Windows 11.
    Fusion style is required for correct rendering and removing qmenu shadow.
    """
    if is_windows_10():
        return
    try:
        from PyQt6.QtWidgets import QStyleFactory

        from core.utils.win32.win32_accent import Blur

        # First we need to set Fusion style to remove shadow artifacts
        qwidget.setStyle(QStyleFactory.create("Fusion"))

        def apply_blur():
            try:
                hwnd = int(qwidget.winId())
                Blur(
                    hwnd, Acrylic=False, DarkMode=True, RoundCorners=True, RoundCornersType="normal", BorderColor="None"
                )
            except Exception:
                pass

        # When the menu is shown, apply blur and rounded corners
        qwidget.aboutToShow.connect(apply_blur)

    except Exception:
        # If anything goes wrong, just skip it.
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

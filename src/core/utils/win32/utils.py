import ctypes
import ctypes.wintypes
import logging
import platform
import winreg
from collections.abc import Collection
from contextlib import suppress
from ctypes import byref
from typing import NotRequired, TypedDict

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QMenu, QWidget
from winrt.windows.applicationmodel import Package
from winrt.windows.management.deployment import PackageManager

from core.utils.system import is_windows_10
from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    GetCurrentProcess,
    GetLastError,
    GetPackageFullName,
    IsWow64Process2,
    OpenProcess,
    QueryFullProcessImageName,
)
from core.utils.win32.bindings.user32 import (
    GetClassName,
    GetForegroundWindow,
    GetMonitorInfo,
    GetWindowPlacement,
    GetWindowRect,
    GetWindowText,
    IsWindowVisible,
    MonitorFromRect,
    MonitorFromWindow,
    enum_windows,
    get_window_thread_process_id,
)
from core.utils.win32.bindings.version import get_version_strings
from core.utils.win32.constants import (
    ERROR_INVALID_HANDLE,
    ERROR_INVALID_PARAMETER,
    IMAGE_FILE_MACHINE_AMD64,
    IMAGE_FILE_MACHINE_ARM64,
    IMAGE_FILE_MACHINE_I386,
    IMAGE_FILE_MACHINE_UNKNOWN,
    PROCESS_QUERY_LIMITED_INFORMATION,
    SW_MAXIMIZE,
)
from core.utils.win32.registry_keys import RUN_KEY
from core.utils.win32.structs import WINDOWPLACEMENT


def get_windows_host_arch():
    """Returns the actual host machine architecture on Windows,
    bypassing emulation layers like Prism."""

    arch_map = {
        IMAGE_FILE_MACHINE_AMD64: "AMD64",
        IMAGE_FILE_MACHINE_ARM64: "ARM64",
        IMAGE_FILE_MACHINE_I386: "x86",
        IMAGE_FILE_MACHINE_UNKNOWN: "Unknown",
    }

    process_machine = ctypes.c_ushort(0)
    native_machine = ctypes.c_ushort(0)

    if IsWow64Process2(GetCurrentProcess(), ctypes.byref(process_machine), ctypes.byref(native_machine)):
        return arch_map.get(native_machine.value, f"Unknown(0x{native_machine.value:04X})")
    return platform.machine()


def is_running_under_emulation():
    """Returns True if the current process is running under WOW64 emulation
    (e.g. x64 process on ARM64 host)."""

    process_machine = ctypes.c_ushort(0)
    native_machine = ctypes.c_ushort(0)

    if IsWow64Process2(GetCurrentProcess(), ctypes.byref(process_machine), ctypes.byref(native_machine)):
        # If process_machine is not 0, it's running under emulation
        return process_machine.value != 0
    return False


def get_widget_monitor_hwnd(widget: QWidget) -> int | None:
    # Don't use widget.winId() here, Qt would turn the widget and all its
    # siblings into native windows.
    top = widget.window()
    if top is None:
        return None
    return MonitorFromWindow(int(top.winId()))


class MonitorRect(TypedDict):
    x: int
    y: int
    width: int
    height: int


class MonitorInfo(TypedDict):
    rect: MonitorRect
    rect_work_area: MonitorRect
    flags: int
    device: str


def get_monitor_info(monitor_hwnd: int) -> MonitorInfo:
    info = GetMonitorInfo(monitor_hwnd)
    if info is None:
        raise ctypes.WinError(GetLastError())
    monitor, work = info.rcMonitor, info.rcWork
    return {
        "rect": {
            "x": monitor.left,
            "y": monitor.top,
            "width": monitor.right - monitor.left,
            "height": monitor.bottom - monitor.top,
        },
        "rect_work_area": {
            "x": work.left,
            "y": work.top,
            "width": work.right - work.left,
            "height": work.bottom - work.top,
        },
        "flags": info.dwFlags,
        "device": info.szDevice,
    }


class ProcessInfo(TypedDict):
    name: str | None
    pid: int
    path: str | None


def get_process_info(hwnd: int) -> ProcessInfo:
    """Get process info { name, pid, path }.

    - Returns pid=0 when no valid PID is associated or process is gone.
    - Returns name=None when access is denied or name can't be resolved.
    - Returns path=None when access is denied or path can't be resolved.
    """
    pid = get_window_thread_process_id(hwnd)[1]
    if not pid:
        return {"name": None, "pid": 0, "path": None}

    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        # These errors mean the process is gone; any other means it exists but cannot be opened
        gone = GetLastError() in (ERROR_INVALID_PARAMETER, ERROR_INVALID_HANDLE, 0)
        return {"name": None, "pid": 0 if gone else pid, "path": None}

    try:
        path = QueryFullProcessImageName(h_process)
    finally:
        CloseHandle(h_process)
    return {"name": path.rsplit("\\", 1)[-1] if path else None, "pid": pid, "path": path}


def get_process_path(pid: int) -> str | None:
    """The exe path of a process, or None when it is gone or YASB may not open it."""
    h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        return None
    try:
        return QueryFullProcessImageName(h_process)
    finally:
        CloseHandle(h_process)


def get_process_window(pid: int) -> int:
    """A visible, titled top-level window of a process, or 0."""
    for hwnd in enum_windows():
        if get_window_thread_process_id(hwnd)[1] == pid and IsWindowVisible(hwnd) and GetWindowText(hwnd):
            return hwnd
    return 0


def _find_package(full_name: str) -> Package | None:
    # The direct lookup is much faster; listing every package is the fallback when it fails
    try:
        package = PackageManager().find_package_by_user_security_id_package_full_name("", full_name)
        if package:
            return package
    except Exception as e:
        logging.debug("Direct UWP lookup failed for %s: %s", full_name, e)
    try:
        for package in PackageManager().find_packages_by_user_security_id(""):
            if package.id.full_name == full_name:
                return package
    except Exception as e:
        logging.debug("Fallback UWP lookup failed for %s: %s", full_name, e)
    return None


def _package_app_name(package: Package, aumid: str | None = None) -> str | None:
    """The app list name of aumid, or of the package's first app, else the package display name."""
    with suppress(Exception):
        for entry in package.get_app_list_entries():
            if aumid is None or entry.app_user_model_id == aumid:
                name = entry.display_info.display_name
                if name and name.strip():
                    return name.strip()
                if aumid is None:
                    break
    with suppress(Exception):
        name = package.display_name
        if name and name.strip():
            return name.strip()
    return None


def get_app_name_from_pid(pid: int) -> str | None:
    """The Store app name of a packaged process, else the FileDescription or ProductName of its exe."""
    try:
        h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return None
        try:
            package_full_name = GetPackageFullName(h_process)
            exe_path = None if package_full_name else QueryFullProcessImageName(h_process)
        finally:
            CloseHandle(h_process)

        if package_full_name:
            package = _find_package(package_full_name)
            return _package_app_name(package) if package else None
        if exe_path:
            names = get_version_strings(exe_path, ("FileDescription", "ProductName"))
            return names.get("FileDescription") or names.get("ProductName")
    except Exception as e:
        logging.debug("Failed to get app name for PID %s: %s", pid, e)
    return None


def get_app_name_from_aumid(aumid: str) -> str | None:
    """The Store app name of an AUMID, such as a Microsoft Store app or an Edge PWA."""
    family = aumid.split("!")[0]
    try:
        for package in PackageManager().find_packages_by_user_security_id(""):
            with suppress(Exception):
                if package.id.family_name == family and (name := _package_app_name(package, aumid)):
                    return name
    except Exception as e:
        logging.debug("Failed to get UWP app name from PackageManager: %s", e)
    return None


class WindowRect(TypedDict):
    x: int
    y: int
    width: int
    height: int


def get_window_rect(hwnd: int) -> WindowRect:
    rect = ctypes.wintypes.RECT()
    if not GetWindowRect(hwnd, byref(rect)):
        raise ctypes.WinError(GetLastError())
    return {"x": rect.left, "y": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}


def is_window_maximized(hwnd: int) -> bool:
    placement = WINDOWPLACEMENT(length=ctypes.sizeof(WINDOWPLACEMENT))
    if not GetWindowPlacement(hwnd, byref(placement)):
        raise ctypes.WinError(GetLastError())
    return placement.showCmd == SW_MAXIMIZE


class WindowInfo(TypedDict):
    hwnd: int
    title: str
    class_name: str | None
    process: ProcessInfo
    monitor_hwnd: int | None
    monitor_info: MonitorInfo
    rect: WindowRect
    app_name: NotRequired[str]


def get_hwnd_info(hwnd: int) -> WindowInfo | None:
    with suppress(Exception):
        monitor_hwnd = MonitorFromWindow(hwnd)
        if monitor_hwnd is None:
            return None
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


def apply_qmenu_style(qwidget: QMenu):
    """
    Set blur and rounded corners for a QMenu on Windows 11.
    Fusion style is required for correct rendering and removing qmenu shadow.
    """
    if is_windows_10():
        return
    try:
        from PyQt6.QtWidgets import QStyleFactory

        from core.utils.win32.backdrop import enable_blur

        # First we need to set Fusion style to remove shadow artifacts
        # Keep a reference so Python GC doesn't destroy the C++ QStyle
        # while Qt still holds a raw pointer to it (prevents DEP crash).
        style = QStyleFactory.create("Fusion")
        qwidget.setStyle(style)
        setattr(qwidget, "_fusion_style_ref", style)

        def apply_blur():
            try:
                hwnd = int(qwidget.winId())
                enable_blur(hwnd, DarkMode=False, RoundCorners=True, RoundCornersType="normal", BorderColor="None")
            except Exception:
                pass

        # When the menu is shown, apply blur and rounded corners
        qwidget.aboutToShow.connect(apply_blur)

    except Exception:
        # If anything goes wrong, just skip it.
        pass


def _monitor_device(monitor: int | None) -> str | None:
    info = GetMonitorInfo(monitor) if monitor else None
    return info.szDevice if info else None


def find_focused_screen(
    follow_mouse: bool, follow_window: bool, follow_primary: bool = False, screens: Collection[str] | None = None
) -> str | None:
    """Find the screen that should be focused based on mouse position, active window, or primary screen."""

    qt_screens = QApplication.screens()
    primary_screen = QApplication.primaryScreen()

    def is_valid(name: str) -> bool:
        return screens is None or any(name in s for s in screens)

    # Map device names to Qt screen names for window focus
    device_to_screen = {
        _monitor_device(MonitorFromRect((geo.left(), geo.top(), geo.right(), geo.bottom()))): screen.name()
        for screen in qt_screens
        for geo in [screen.geometry()]
    }

    if follow_primary:
        if primary_screen is not None and is_valid(primary_screen.name()):
            return primary_screen.name()

    if follow_mouse:
        try:
            pos = QCursor.pos()
            for screen in qt_screens:
                if screen.geometry().contains(pos) and is_valid(screen.name()):
                    return screen.name()
        except Exception as e:
            logging.error("Exception in follow_mouse: %s", e)

    if follow_window:
        hwnd = GetForegroundWindow()
        if hwnd:
            monitor = MonitorFromWindow(hwnd)
            if monitor is not None:
                device_name = _monitor_device(monitor)
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

"""Optional bridge to the already-installed Windhawk icon-size mod."""

import ctypes
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

MOD_KEY = r"SOFTWARE\Windhawk\Engine\Mods\taskbar-icon-size"
SIZE_NAMES = ("IconSize", "IconSizeSmall")
MIN_SIZE, MAX_SIZE = 16, 40


# Kept local so the portable Python 3.12 settings app does not import YASB's
# Python 3.14-only win32 module or require the rest of the YASB runtime.
class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def read_sizes() -> tuple[int, int]:
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MOD_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as mod:
        if winreg.QueryValueEx(mod, "Disabled")[0]:
            raise ValueError("Enable Taskbar height and icon size in Windhawk first.")
        with winreg.OpenKey(mod, "Settings") as settings:
            return tuple(int(winreg.QueryValueEx(settings, name)[0]) for name in SIZE_NAMES)


def write_sizes(size: int, expected: tuple[int, int]) -> None:
    """Elevated entry point: bounded writes to fixed registry values only."""
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError("Dock icon size must be between 16 and 40 pixels.")
    access = winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MOD_KEY, 0, access) as mod:
        with winreg.OpenKey(mod, "Settings", 0, access) as settings:
            if read_sizes() != expected:
                raise ValueError("Dock settings changed elsewhere. Reopen settings before saving.")
            previous_time = winreg.QueryValueEx(mod, "SettingsChangeTime")[0]
            try:
                for name in SIZE_NAMES:
                    winreg.SetValueEx(settings, name, 0, winreg.REG_DWORD, size)
                winreg.SetValueEx(
                    mod, "SettingsChangeTime", 0, winreg.REG_DWORD, max(int(time.time()), previous_time + 1)
                )
            except OSError:
                for name, value in zip(SIZE_NAMES, expected):
                    winreg.SetValueEx(settings, name, 0, winreg.REG_DWORD, value)
                winreg.SetValueEx(mod, "SettingsChangeTime", 0, winreg.REG_DWORD, previous_time)
                raise


def _run_elevated(size: int, expected: tuple[int, int]) -> None:
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve().parents[3] / "settings_launcher.py"))
    command += ["--apply-dock-size", str(size), *(str(value) for value in expected)]
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = command[0]
    info.lpParameters = subprocess.list2cmdline(command[1:])
    info.nShow = 0
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.get_last_error() == 1223:
            raise OSError("Administrator approval was cancelled. Dock size was not changed.")
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(info.hProcess, 30000) != 0:
            raise OSError("Dock update has not completed. Reopen settings to check the current size.")
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value == 2:
            raise ValueError("Dock settings changed or are unavailable. Reopen settings before saving.")
        if code.value:
            raise OSError("Windows could not save the dock size. Check Windhawk and try again.")
    finally:
        kernel.CloseHandle(info.hProcess)


class DockIconSettings:
    def __init__(self):
        self.original = read_sizes()

    def save(self, size: int) -> bool:
        if (size, size) == self.original:
            return False
        if not MIN_SIZE <= size <= MAX_SIZE:
            raise ValueError("Dock icon size must be between 16 and 40 pixels.")
        if read_sizes() != self.original:
            raise ValueError("Dock settings changed elsewhere. Reopen settings before saving.")
        _run_elevated(size, self.original)
        current = read_sizes()
        if current != (size, size):
            raise OSError("Dock size could not be confirmed. Reopen settings to check it.")
        self.original = current
        return True

import ctypes
import logging
from ctypes import wintypes

from core.utils.win32.structs import GUID

# Load isolated DLL instances to avoid mutating global bindings (see dnd_api.py)
_ole32 = ctypes.WinDLL("ole32")
_user32 = ctypes.WinDLL("user32")
_kernel32 = ctypes.WinDLL("kernel32")
_shell32 = ctypes.WinDLL("shell32")


_CLSID = GUID(0x4CE576FA, 0x83DC, 0x4F88, (0x95, 0x1C, 0x9D, 0x07, 0x82, 0xB4, 0xE3, 0x76))
_IID = GUID(0x37C994E7, 0x432B, 0x4834, (0xA2, 0xF7, 0xDC, 0xE1, 0xF1, 0x3B, 0x83, 0x4B))

_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_FLAG_NO_UI = 0x00000400


class _SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
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


def _try_toggle_via_com() -> bool:
    """Connect to the TabTip COM server and send the Toggle call. Returns True on success."""
    ppv = ctypes.c_void_p()
    hr = _ole32.CoCreateInstance(ctypes.byref(_CLSID), None, 2 | 4, ctypes.byref(_IID), ctypes.byref(ppv))
    if hr < 0:
        return False
    vtable = ctypes.cast(ppv, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    toggle_fn = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p)(vtable[0][3])
    toggle_fn(ppv, _user32.GetDesktopWindow())
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[0][2])(ppv)  # Release
    return True


def _tabtip_path() -> str:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    _shell32.SHGetFolderPathW(0, 0x002B, 0, 0, buf)  # 0x002B = CSIDL_PROGRAM_FILES_COMMON
    return buf.value + r"\microsoft shared\ink\TabTip.exe"


class TouchKeyboardService:
    """Toggle the Windows 11 touch / on-screen keyboard (TabTip)."""

    @staticmethod
    def toggle() -> None:
        """Show or hide the touch keyboard.

        Attempts a direct COM toggle first. If TabTip is not running, launches it,
        waits for its message pump to be ready, then toggles.
        """
        try:
            _ole32.CoInitialize(None)
            if not _try_toggle_via_com():
                sei = _SHELLEXECUTEINFO()
                sei.cbSize = ctypes.sizeof(_SHELLEXECUTEINFO)
                sei.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_FLAG_NO_UI
                sei.lpFile = _tabtip_path()
                sei.nShow = 1  # SW_SHOWNORMAL
                if _shell32.ShellExecuteExW(ctypes.byref(sei)) and sei.hProcess:
                    _user32.WaitForInputIdle(sei.hProcess, 5000)
                    _kernel32.CloseHandle(sei.hProcess)
                    _try_toggle_via_com()
        except Exception as exc:
            logging.error("Failed to toggle touch keyboard: %s", exc)

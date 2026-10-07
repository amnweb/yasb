import ctypes
import logging
from ctypes import wintypes

from core.utils.win32.bindings.kernel32 import CloseHandle
from core.utils.win32.bindings.ole32 import CoCreateInstance, CoInitialize
from core.utils.win32.bindings.shell32 import ShellExecuteEx, SHGetFolderPath
from core.utils.win32.bindings.user32 import GetDesktopWindow, WaitForInputIdle
from core.utils.win32.structs import GUID, SHELLEXECUTEINFO

_CLSID = GUID(0x4CE576FA, 0x83DC, 0x4F88, (0x95, 0x1C, 0x9D, 0x07, 0x82, 0xB4, 0xE3, 0x76))
_IID = GUID(0x37C994E7, 0x432B, 0x4834, (0xA2, 0xF7, 0xDC, 0xE1, 0xF1, 0x3B, 0x83, 0x4B))

_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_FLAG_NO_UI = 0x00000400


def _try_toggle_via_com() -> bool:
    """Connect to the TabTip COM server and send the Toggle call. Returns True on success."""
    ppv = ctypes.c_void_p()
    hr = CoCreateInstance(ctypes.byref(_CLSID), None, 2 | 4, ctypes.byref(_IID), ctypes.byref(ppv))
    if hr < 0:
        return False
    vtable = ctypes.cast(ppv, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    toggle_fn = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p)(vtable[0][3])
    toggle_fn(ppv, GetDesktopWindow())
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[0][2])(ppv)  # Release
    return True


def _tabtip_path() -> str:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    SHGetFolderPath(0x002B, buf)  # 0x002B = CSIDL_PROGRAM_FILES_COMMON
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
            CoInitialize()
            if not _try_toggle_via_com():
                sei = SHELLEXECUTEINFO()
                sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
                sei.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_FLAG_NO_UI
                sei.lpFile = _tabtip_path()
                sei.nShow = 1  # SW_SHOWNORMAL
                if ShellExecuteEx(ctypes.byref(sei)) and sei.hProcess:
                    WaitForInputIdle(sei.hProcess, 5000)
                    CloseHandle(sei.hProcess)
                    _try_toggle_via_com()
        except Exception as exc:
            logging.error("Failed to toggle touch keyboard: %s", exc)

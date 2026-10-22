import ctypes
import logging
from contextlib import suppress
from ctypes import wintypes

from comtypes import COMError  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.bindings.kernel32 import CloseHandle
from core.utils.win32.bindings.ole32 import CoInitialize, create_com_object
from core.utils.win32.bindings.shell32 import CLSID_UIHostNoLaunch, ITipInvocation, ShellExecuteEx, SHGetFolderPath
from core.utils.win32.bindings.user32 import GetDesktopWindow, WaitForInputIdle
from core.utils.win32.constants import (
    CLSCTX_INPROC_HANDLER,
    CLSCTX_LOCAL_SERVER,
    CSIDL_PROGRAM_FILES_COMMON,
    SEE_MASK_FLAG_NO_UI,
    SEE_MASK_NOCLOSEPROCESS,
    SW_SHOWNORMAL,
)
from core.utils.win32.structs import SHELLEXECUTEINFO


def _try_toggle_via_com() -> bool:
    """Connect to the TabTip COM server and send the Toggle call. Returns True on success."""
    tip = create_com_object(CLSID_UIHostNoLaunch, ITipInvocation, CLSCTX_INPROC_HANDLER | CLSCTX_LOCAL_SERVER)
    if tip is None:
        return False
    with suppress(COMError):
        tip.Toggle(GetDesktopWindow())
    return True


def _tabtip_path() -> str:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    SHGetFolderPath(CSIDL_PROGRAM_FILES_COMMON, buf)
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
                sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
                sei.lpFile = _tabtip_path()
                sei.nShow = SW_SHOWNORMAL
                if ShellExecuteEx(ctypes.byref(sei)) and sei.hProcess:
                    WaitForInputIdle(sei.hProcess, 5000)
                    CloseHandle(sei.hProcess)
                    _try_toggle_via_com()
        except Exception as exc:
            logging.error("Failed to toggle touch keyboard: %s", exc)

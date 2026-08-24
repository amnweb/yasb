import ctypes
import logging
from ctypes import POINTER, windll
from ctypes.wintypes import BOOL, HWND, UINT

from core.utils.win32.bindings.dwmapi import DwmSetWindowAttribute
from core.utils.win32.constants import DWMWA_EXCLUDED_FROM_PEEK, LPT_SUPERBAR
from core.utils.win32.structs import RECT

logger = logging.getLogger("taskbar_peek")

# DwmpActivateLivePreview is exported by ordinal only and has never been documented, so it is
# resolved here rather than in the dwmapi bindings: a build that stops exporting it leaves peek
# unavailable instead of breaking the import for everything else that uses dwmapi
try:
    _activate_live_preview = windll.dwmapi[113]
    _activate_live_preview.argtypes = [BOOL, HWND, HWND, UINT, POINTER(RECT)]
    _activate_live_preview.restype = ctypes.c_long
except Exception:
    _activate_live_preview = None


def is_live_preview_available() -> bool:
    """Whether this Windows build still exports the peek entry point."""
    return _activate_live_preview is not None


def activate_live_preview(activate: bool, hwnd_peek: int = 0, hwnd_caller: int = 0) -> bool:
    """Show one window on the faded desktop, or restore them all when activate is False.

    Returns whether DWM accepted the call, rather than merely whether it was made.
    """
    if _activate_live_preview is None:
        return False
    try:
        hresult = _activate_live_preview(bool(activate), hwnd_peek, hwnd_caller, LPT_SUPERBAR, None)
    except Exception:
        logger.exception("DwmpActivateLivePreview raised for activate=%s hwnd=%s", activate, hwnd_peek)
        return False
    if hresult != 0:
        logger.warning(
            "DwmpActivateLivePreview(activate=%s, hwnd=%s, caller=%s) failed with 0x%08X",
            activate,
            hwnd_peek,
            hwnd_caller,
            hresult & 0xFFFFFFFF,
        )
        return False
    return True


def exclude_from_peek(hwnd) -> bool:
    """Keep one of our own windows painted while peek fades every other one."""
    try:
        value = ctypes.c_int(1)
        hresult = DwmSetWindowAttribute(int(hwnd), DWMWA_EXCLUDED_FROM_PEEK, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        logger.exception("Could not exclude %s from peek, it will fade along with the desktop", hwnd)
        return False
    if hresult != 0:
        logger.warning(
            "Excluding %s from peek failed with 0x%08X, it will fade with the desktop", hwnd, hresult & 0xFFFFFFFF
        )
        return False
    return True

import ctypes
import logging

from core.utils.win32.bindings.dwmapi import DwmpActivateLivePreview, DwmSetWindowAttribute, live_preview_exported
from core.utils.win32.constants import DWMWA_EXCLUDED_FROM_PEEK
from core.utils.win32.undocumented import LPT_SUPERBAR

logger = logging.getLogger("taskbar_peek")


def is_live_preview_available() -> bool:
    """Whether this Windows build still exports the peek entry point."""
    return live_preview_exported()


def activate_live_preview(activate: bool, hwnd_peek: int = 0, hwnd_caller: int = 0) -> bool:
    """Show one window on the faded desktop, or restore them all when activate is False.

    Returns whether DWM accepted the call, rather than merely whether it was made.
    """
    if not live_preview_exported():
        return False
    try:
        hresult = DwmpActivateLivePreview(bool(activate), hwnd_peek, hwnd_caller, LPT_SUPERBAR)
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


def exclude_from_peek(hwnd: int) -> bool:
    """Keep one of our own windows painted while peek fades every other one."""
    try:
        value = ctypes.c_int(1)
        hresult = DwmSetWindowAttribute(hwnd, DWMWA_EXCLUDED_FROM_PEEK, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        logger.exception("Could not exclude %s from peek, it will fade along with the desktop", hwnd)
        return False
    if hresult != 0:
        logger.warning(
            "Excluding %s from peek failed with 0x%08X, it will fade with the desktop", hwnd, hresult & 0xFFFFFFFF
        )
        return False
    return True

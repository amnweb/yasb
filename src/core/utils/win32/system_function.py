import time

from core.utils.win32.bindings.user32 import (
    FindWindow,
    GetClassName,
    GetForegroundWindow,
    SetForegroundWindow,
    keybd_event,
)
from core.utils.win32.constants import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    VK_ESCAPE,
    VK_LMENU,
    VK_LWIN,
    VK_SPACE,
)

# Virtual Key Codes
VK_N = 0x4E
VK_A = 0x41
VK_S = 0x53
VK_W = 0x57


def ensure_non_elevated_foreground():
    """Temporarily shifts foreground focus to the desktop (Progman) before simulating
    keystrokes.
    This prevents User Interface Privilege Isolation (UIPI) from blocking
    low-level input injection (keybd_event) when an Administrator window has focus.
    """
    hwnd_desktop = FindWindow("Progman", None)
    if hwnd_desktop:
        SetForegroundWindow(hwnd_desktop)


def notification_center():
    ensure_non_elevated_foreground()
    # Hold down Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press N key
    keybd_event(VK_N, 0, KEYEVENTF_EXTENDEDKEY, 0)
    keybd_event(VK_N, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def quick_settings():
    ensure_non_elevated_foreground()
    # Hold down Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press A key
    keybd_event(VK_A, 0, KEYEVENTF_EXTENDEDKEY, 0)
    keybd_event(VK_A, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def close_quick_settings(timeout: float = 0.3) -> None:
    """Close the Windows Quick Settings flyout if it is open and wait until it is gone.

    While the flyout is open it keeps the foreground, so a popup shown on top of it
    loses focus straight away and Qt closes it again.
    """
    # The flyout always has the foreground while it is open, and Escape closes it.
    if GetClassName(GetForegroundWindow()) != "ControlCenterWindow":
        return
    keybd_event(VK_ESCAPE, 0, 0, 0)
    keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    deadline = time.monotonic() + timeout
    while GetClassName(GetForegroundWindow()) == "ControlCenterWindow" and time.monotonic() < deadline:
        time.sleep(0.01)


def search():
    ensure_non_elevated_foreground()
    # Hold down Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press S key
    keybd_event(VK_S, 0, KEYEVENTF_EXTENDEDKEY, 0)
    keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def widget():
    ensure_non_elevated_foreground()
    # Hold down Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press W key
    keybd_event(VK_W, 0, KEYEVENTF_EXTENDEDKEY, 0)
    keybd_event(VK_W, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def start_menu():
    ensure_non_elevated_foreground()
    # Hold down Win key
    keybd_event(VK_LWIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def launcher():
    ensure_non_elevated_foreground()
    # Press down ALT key
    keybd_event(VK_LMENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press down Space key
    keybd_event(VK_SPACE, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Release keys
    keybd_event(VK_LMENU, 0, KEYEVENTF_KEYUP, 0)
    keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)


function_map = {
    "quick_settings": quick_settings,
    "notification_center": notification_center,
    "search": search,
    "widget": widget,
    "start_menu": start_menu,
    "launcher": launcher,
}

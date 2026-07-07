import ctypes

# Constants for key events
KEYEVENTF_EXTENDEDKEY = 0x1
KEYEVENTF_KEYUP = 0x2

# Virtual Key Codes
VK_WIN = 0x5B
VK_LMENU = 0xA4  # Left Alt
VK_N = 0x4E
VK_A = 0x41
VK_S = 0x53
VK_W = 0x57
VK_SPACE = 0x20

VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
KEYEVENTF_KEYUP = 0x0002


def ensure_non_elevated_foreground():
    """Temporarily shifts foreground focus to the desktop (Progman) before simulating
    keystrokes.
    This prevents User Interface Privilege Isolation (UIPI) from blocking
    low-level input injection (keybd_event) when an Administrator window has focus.
    """
    hwnd_desktop = ctypes.windll.user32.FindWindowW("Progman", None)
    if hwnd_desktop:
        ctypes.windll.user32.SetForegroundWindow(hwnd_desktop)


def notification_center():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Hold down Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press N key
    user32.keybd_event(VK_N, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(VK_N, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_KEYUP, 0)


def quick_settings():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Hold down Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press A key
    user32.keybd_event(VK_A, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(VK_A, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_KEYUP, 0)


def search():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Hold down Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press S key
    user32.keybd_event(VK_S, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_KEYUP, 0)


def widget():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Hold down Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press W key
    user32.keybd_event(VK_W, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(VK_W, 0, KEYEVENTF_KEYUP, 0)
    # Release Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_KEYUP, 0)


def start_menu():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Hold down Win key
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(VK_WIN, 0, KEYEVENTF_KEYUP, 0)


def launcher():
    ensure_non_elevated_foreground()
    user32 = ctypes.windll.user32
    # Press down ALT key
    user32.keybd_event(VK_LMENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Press down Space key
    user32.keybd_event(VK_SPACE, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # Release keys
    user32.keybd_event(VK_LMENU, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)


function_map = {
    "quick_settings": quick_settings,
    "notification_center": notification_center,
    "search": search,
    "widget": widget,
    "start_menu": start_menu,
    "launcher": launcher,
}

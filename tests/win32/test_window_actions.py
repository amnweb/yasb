import pytest
import win32api
import win32con
import win32gui

from core.utils.win32.window_actions import can_minimize

WINDOWS = {
    "normal": (win32con.WS_OVERLAPPEDWINDOW, True),
    "popup with minimize box": (win32con.WS_POPUP | win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX, True),
    "no minimize box": (win32con.WS_OVERLAPPED | win32con.WS_CAPTION | win32con.WS_SYSMENU, False),
    "disabled": (win32con.WS_OVERLAPPEDWINDOW | win32con.WS_DISABLED, False),
}


@pytest.fixture(scope="module")
def window_class():
    instance = win32api.GetModuleHandle(None)
    wc = win32gui.WNDCLASS()
    wc.hInstance = instance
    wc.lpszClassName = "YasbTestWindow"
    wc.lpfnWndProc = {}
    atom = win32gui.RegisterClass(wc)
    yield atom
    win32gui.UnregisterClass(atom, instance)


@pytest.fixture
def make_window(window_class):
    created = []

    def make(style: int) -> int:
        hwnd = win32gui.CreateWindow(
            window_class, "YASB test window", style, 0, 0, 200, 100, 0, 0, win32api.GetModuleHandle(None), None
        )
        created.append(hwnd)
        return hwnd

    yield make
    for hwnd in created:
        if win32gui.IsWindow(hwnd):
            win32gui.DestroyWindow(hwnd)


@pytest.mark.parametrize(("style", "expected"), list(WINDOWS.values()), ids=list(WINDOWS))
def test_can_minimize(make_window, style: int, expected: bool):
    assert can_minimize(make_window(style)) is expected


def test_can_minimize_closed_window(make_window):
    hwnd = make_window(win32con.WS_OVERLAPPEDWINDOW)
    win32gui.DestroyWindow(hwnd)

    assert can_minimize(hwnd) is False

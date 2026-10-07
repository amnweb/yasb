from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import pytest
import win32api
import win32con
import win32gui

from core.utils.win32.window_actions import can_minimize

if TYPE_CHECKING:
    from _win32typing import PyResourceId  # pyright: ignore[reportMissingModuleSource]

WINDOWS = {
    "normal": (win32con.WS_OVERLAPPEDWINDOW, True),
    "popup with minimize box": (win32con.WS_POPUP | win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX, True),
    "no minimize box": (win32con.WS_OVERLAPPED | win32con.WS_CAPTION | win32con.WS_SYSMENU, False),
    "disabled": (win32con.WS_OVERLAPPEDWINDOW | win32con.WS_DISABLED, False),
}


@pytest.fixture(scope="module")
def window_class() -> Iterator[PyResourceId]:
    instance = win32api.GetModuleHandle(None)
    wc = win32gui.WNDCLASS()
    wc.hInstance = instance  # pyright: ignore[reportAttributeAccessIssue]
    wc.lpszClassName = "YasbTestWindow"  # pyright: ignore[reportAttributeAccessIssue]
    wc.lpfnWndProc = {}  # pyright: ignore[reportAttributeAccessIssue]
    atom = win32gui.RegisterClass(wc)
    yield atom
    win32gui.UnregisterClass(atom, instance)


@pytest.fixture
def make_window(window_class: PyResourceId) -> Iterator[Callable[[int], int]]:
    created: list[int] = []

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
def test_can_minimize(make_window: Callable[[int], int], style: int, expected: bool):
    assert can_minimize(make_window(style)) is expected


def test_can_minimize_closed_window(make_window: Callable[[int], int]):
    hwnd = make_window(win32con.WS_OVERLAPPEDWINDOW)
    win32gui.DestroyWindow(hwnd)

    assert can_minimize(hwnd) is False

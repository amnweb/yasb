# pyright: reportPrivateUsage=false

import pytest
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QGuiApplication

from core.bar import maximized
from core.bar.maximized import MaximizedWindows

FOCUSED, OTHER = 101, 202


class Desktop:
    """The windows the tracker reads in place of Windows: which are maximized, and on which monitor."""

    def __init__(self) -> None:
        self.zoomed: set[int] = set()
        self.monitors = {FOCUSED: 7, OTHER: 8}


@pytest.fixture
def desktop(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Desktop:
    desktop = Desktop()

    def is_zoomed(hwnd: int) -> bool:
        return hwnd in desktop.zoomed

    def monitor(hwnd: int) -> int:
        return desktop.monitors.get(hwnd, 0)

    monkeypatch.setattr(maximized, "_counts", is_zoomed)
    monkeypatch.setattr(maximized, "IsZoomed", is_zoomed)
    monkeypatch.setattr(maximized, "enum_windows", lambda: [FOCUSED, OTHER])
    monkeypatch.setattr(maximized, "GetForegroundWindow", lambda: FOCUSED)
    monkeypatch.setattr(maximized, "MonitorFromWindow", monitor)
    return desktop


def test_windows_are_followed_only_while_someone_needs_them(desktop: Desktop):
    desktop.zoomed.add(OTHER)
    windows, bar = MaximizedWindows(), QObject()
    assert not windows.maximized_on(8) and not windows._timer.isActive()
    windows.follow(bar)
    assert windows.maximized_on(8) and not windows.maximized_on(7) and windows._timer.isActive()
    windows.unfollow(bar)
    assert not windows.maximized_on(8) and not windows._timer.isActive()


def test_the_poll_sees_the_focused_and_the_maximized_windows_change(desktop: Desktop):
    windows = MaximizedWindows()
    windows.follow(QObject())
    changes: list[None] = []
    windows.changed.connect(lambda: changes.append(None))

    windows._poll()
    assert changes == []
    # Maximized in place
    desktop.zoomed.add(FOCUSED)
    windows._poll()
    windows._poll()
    assert windows.maximized_on(7) and len(changes) == 1
    # Moved to another monitor while maximized, then restored
    desktop.monitors[FOCUSED] = 8
    windows._poll()
    desktop.zoomed.clear()
    windows._poll()
    assert not windows.maximized_on(8) and len(changes) == 3


def test_a_focus_change_finds_maximized_windows_that_never_had_the_focus(desktop: Desktop):
    windows = MaximizedWindows()
    windows.follow(QObject())
    # Shown by a switch of virtual desktop
    desktop.zoomed.add(OTHER)
    windows._poll()
    assert not windows.maximized_on(8)
    windows._on_focus(FOCUSED)
    assert windows.maximized_on(8)

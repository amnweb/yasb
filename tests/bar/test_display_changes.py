# pyright: reportPrivateUsage=false

import ctypes
from collections.abc import Iterator
from typing import Any, cast

import pytest
from PyQt6 import sip
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlEngine

from core.bar import manager as bar_manager
from core.bar.appbar import RECLAIM_DELAY_MS, AppBarManager
from core.bar.manager import MONITOR_CHECK_DELAY_MS, BarManager
from core.utils.win32 import app_bar
from core.utils.win32.app_bar import APPBAR_CALLBACK_MESSAGE, AppBarEdge, AppBarMessage, AppBarNotify, Win32AppBar
from core.utils.win32.structs import APPBARDATA, MSG
from core.validation.config import YasbConfig
from tests.support.qt import wait

LAPTOP = r"\\?\DISPLAY#BOE0B69#5&1&0&UID4357"
EXTERNAL = r"\\?\DISPLAY#AUSAA46#5&1&0&UID4352"


def test_monitors_that_swap_display_devices_have_moved():
    before = {r"\\.\DISPLAY1": LAPTOP, r"\\.\DISPLAY2": EXTERNAL}
    after = {r"\\.\DISPLAY1": EXTERNAL, r"\\.\DISPLAY2": LAPTOP}
    assert BarManager._moved_monitors(before, after) == {LAPTOP, EXTERNAL}


@pytest.mark.parametrize(
    "after",
    [
        {r"\\.\DISPLAY1": LAPTOP, r"\\.\DISPLAY2": EXTERNAL},
        # Unplugged, or still asleep
        {r"\\.\DISPLAY1": LAPTOP},
        {},
        # Plugged in
        {r"\\.\DISPLAY1": LAPTOP, r"\\.\DISPLAY2": EXTERNAL, r"\\.\DISPLAY3": r"\\?\DISPLAY#DEL0001#1"},
    ],
)
def test_monitors_that_keep_their_display_device_have_not_moved(after: dict[str, str]):
    assert BarManager._moved_monitors({r"\\.\DISPLAY1": LAPTOP, r"\\.\DISPLAY2": EXTERNAL}, after) == set()


@pytest.fixture
def monitors(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    current = {r"\\.\DISPLAY1": LAPTOP, r"\\.\DISPLAY2": EXTERNAL}
    monkeypatch.setattr(bar_manager, "display_monitors", lambda: dict(current))
    return current


@pytest.fixture
def reloads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    messages: list[str] = []
    monkeypatch.setattr(bar_manager, "reload_application", messages.append)
    return messages


@pytest.fixture
def manager(qapp: QGuiApplication, monitors: dict[str, str], reloads: list[str]) -> Iterator[BarManager]:
    engine = QQmlEngine()
    manager = BarManager(YasbConfig.model_validate({"bars": {}}), engine)
    yield manager
    manager._disconnect_reload_signals()
    sip.delete(manager)
    sip.delete(engine)


def _screen_moves(qapp: QGuiApplication) -> None:
    screen = qapp.primaryScreen()
    assert screen is not None
    screen.geometryChanged.emit(screen.geometry())
    wait(MONITOR_CHECK_DELAY_MS + 200)


def test_bars_reload_when_monitors_swap_display_devices(
    qapp: QGuiApplication, manager: BarManager, monitors: dict[str, str], reloads: list[str]
):
    monitors[r"\\.\DISPLAY1"], monitors[r"\\.\DISPLAY2"] = EXTERNAL, LAPTOP
    _screen_moves(qapp)
    assert len(reloads) == 1
    # Only once, however many screens move after that
    _screen_moves(qapp)
    assert len(reloads) == 1


def test_bars_stay_when_a_screen_moves_on_the_same_monitor(
    qapp: QGuiApplication, manager: BarManager, reloads: list[str]
):
    _screen_moves(qapp)
    assert reloads == []


class FakeShell:
    """Gives an app bar no space while another bar holds its edge."""

    def __init__(self) -> None:
        self.edge_taken = False
        self.positions = 0

    def __call__(self, message: int, data: APPBARDATA) -> int:
        if message == AppBarMessage.SetPos:
            self.positions += 1
            if self.edge_taken:
                data.rc.top = data.rc.bottom
        return 1


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> FakeShell:
    fake = FakeShell()
    monkeypatch.setattr(app_bar, "SHAppBarMessage", fake)
    monkeypatch.setattr(app_bar, "GetWindowLongPtr", _no_window_style)
    monkeypatch.setattr(app_bar, "SetWindowLongPtr", _no_window_style)
    return fake


def _no_window_style(*_: int) -> int:
    return 0


def _reserve(qapp: QGuiApplication, reserve_space: bool = True) -> Win32AppBar:
    screen = qapp.primaryScreen()
    assert screen is not None
    reservation = Win32AppBar()
    reservation.create_appbar(1, AppBarEdge.Top, 24, screen, reserve_space=reserve_space)
    return reservation


def _height(reservation: Win32AppBar) -> int:
    assert reservation.app_bar_data is not None
    return reservation.app_bar_data.rc.bottom - reservation.app_bar_data.rc.top


def test_a_bar_left_without_space_asks_again_once_the_edge_is_free(qapp: QGuiApplication, shell: FakeShell):
    shell.edge_taken = True
    reservation = _reserve(qapp)
    assert _height(reservation) == 0

    shell.edge_taken = False
    assert reservation.reclaim()
    assert _height(reservation) == 24
    assert shell.positions == 2

    assert not reservation.reclaim()
    assert shell.positions == 2


def test_a_bar_that_gave_up_its_space_never_asks_for_it(qapp: QGuiApplication, shell: FakeShell):
    shell.edge_taken = True
    reservation = _reserve(qapp)
    # Hidden, or auto-hide turned on
    reservation.remove_appbar()
    shell.edge_taken = False
    assert not reservation.reclaim()
    assert shell.positions == 1


def test_a_bar_that_reserves_no_space_never_asks_for_it(qapp: QGuiApplication, shell: FakeShell):
    reservation = _reserve(qapp, reserve_space=False)
    assert not reservation.reclaim()
    assert shell.positions == 0


class FakeBar:
    def __init__(self) -> None:
        self.reclaims = 0
        self.bar_id = "fake"

    def reclaim_app_bar(self) -> None:
        self.reclaims += 1


def _notify(appbars: AppBarManager, hwnd: int, code: int) -> None:
    msg = MSG(hwnd=hwnd, message=APPBAR_CALLBACK_MESSAGE, wParam=code)
    appbars.nativeEventFilter(b"windows_generic_MSG", sip.voidptr(ctypes.addressof(msg)))


def test_a_burst_of_position_changes_makes_each_bar_ask_once(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AppBarManager, "_instance", None)
    appbars = AppBarManager()
    bars = {1: FakeBar(), 2: FakeBar()}
    appbars._bars.update(cast(dict[int, Any], bars))

    # Paces shell event bursts to process across multiple frames without stalling.
    for hwnd in (1, 2, 1, 2, 1):
        _notify(appbars, hwnd, AppBarNotify.PosChanged)
        wait(RECLAIM_DELAY_MS // 2)
    assert [bar.reclaims for bar in bars.values()] == [0, 0]
    wait(RECLAIM_DELAY_MS + 100)
    assert [bar.reclaims for bar in bars.values()] == [1, 1]

    _notify(appbars, 1, AppBarNotify.StateChange)
    wait(RECLAIM_DELAY_MS + 100)
    assert [bar.reclaims for bar in bars.values()] == [1, 1]

    # A later burst is a new change
    _notify(appbars, 2, AppBarNotify.PosChanged)
    wait(RECLAIM_DELAY_MS + 100)
    assert [bar.reclaims for bar in bars.values()] == [2, 2]

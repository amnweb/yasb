# pyright: reportPrivateUsage=false

from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest
from PyQt6.QtCore import QEventLoop, QPoint, QTimer
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QApplication, QMenu

from core.bar import Bar
from core.bar_helper import AppBarManager
from core.utils.win32 import app_bar
from core.validation.bar import BarConfig

type MakeBar = Callable[..., Bar]


class _FakeAppBar:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def create_appbar(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append("create")

    def remove_appbar(self) -> None:
        self.calls.append("remove")


def _wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.fixture
def registered_bars(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    registered: list[int] = []

    def register_bar(self: AppBarManager, hwnd: int, bar_widget: Bar) -> None:
        registered.append(hwnd)

    def unregister_bar(self: AppBarManager, hwnd: int) -> None:
        pass

    monkeypatch.setattr(AppBarManager, "register_bar", register_bar)
    monkeypatch.setattr(AppBarManager, "unregister_bar", unregister_bar)
    return registered


@pytest.fixture
def make_bar(qapp: QApplication, monkeypatch: pytest.MonkeyPatch, registered_bars: list[int]) -> Iterator[MakeBar]:
    monkeypatch.setattr(app_bar, "Win32AppBar", _FakeAppBar)
    bars: list[Bar] = []

    def make(**config: Any) -> Bar:
        screen = QApplication.primaryScreen()
        assert screen is not None
        bar = Bar(
            bar_id="test-bar",
            bar_name="test-bar",
            bar_screen=screen,
            stylesheet="",
            widgets={"left": [], "center": [], "right": []},
            config=BarConfig.model_validate(config),
            init=True,
        )
        bars.append(bar)
        return bar

    yield make
    for bar in bars:
        bar.skip_animation = True
        bar.close()


# One entry per option that switches on its own code path, plus a few realistic combinations.
BAR_CONFIGS: dict[str, dict[str, Any]] = {
    "defaults": {},
    "bottom": {"alignment": {"position": "bottom"}},
    "align-left": {"alignment": {"align": "left"}},
    "align-right": {"alignment": {"align": "right"}},
    "padding": {"padding": {"top": 4, "left": 8, "bottom": 4, "right": 8}},
    "adaptive": {"style": "adaptive"},
    "adaptive-bottom": {"style": "adaptive", "alignment": {"position": "bottom"}},
    "width-auto": {"dimensions": {"width": "auto"}},
    "width-pixels": {"dimensions": {"width": 600, "height": 40}},
    "width-percent": {"dimensions": {"width": "50%"}},
    "no-animation": {"animation": {"enabled": False}},
    "fade-animation": {"animation": {"type": "fade"}},
    "blur": {"blur_effect": {"enabled": True, "round_corners": True}},
    "always-on-top": {"window_flags": {"always_on_top": True}},
    "windows-app-bar": {"window_flags": {"windows_app_bar": True}},
    "hide-on-fullscreen": {"window_flags": {"always_on_top": True, "hide_on_fullscreen": True}},
    "hide-on-maximized": {"window_flags": {"hide_on_maximized": True}},
    "auto-hide": {"window_flags": {"auto_hide": True}},
    "no-context-menu": {"context_menu": False},
    "no-stretch": {"layouts": {"left": {"stretch": False}, "center": {"stretch": False}, "right": {"stretch": False}}},
    "auto-hide-bottom-slide": {
        "alignment": {"position": "bottom"},
        "animation": {"type": "slide"},
        "window_flags": {"auto_hide": True, "always_on_top": True},
    },
    "app-bar-auto-width-adaptive": {
        "style": "adaptive",
        "dimensions": {"width": "auto"},
        "window_flags": {"windows_app_bar": True, "always_on_top": True, "hide_on_fullscreen": True},
    },
}


@pytest.mark.parametrize("config", BAR_CONFIGS.values(), ids=BAR_CONFIGS.keys())
def test_bar_lifecycle(make_bar: MakeBar, config: dict[str, Any]):
    bar = make_bar(**config)
    assert bar.isVisible()
    assert cast(_FakeAppBar, bar.app_bar_manager).calls[0] == "create"

    bar.position_bar()
    bar.show()
    assert bar.isVisible()

    bar.skip_animation = True
    bar.hide()
    assert not bar.isVisible()


@pytest.mark.parametrize("position", ["top", "bottom"])
def test_bar_sits_at_its_screen_edge(make_bar: MakeBar, position: str):
    padding = {"top": 3, "left": 0, "bottom": 5, "right": 0}
    bar = make_bar(alignment={"position": position}, padding=padding, animation={"enabled": False})
    screen = bar.target_screen.geometry()

    if position == "top":
        assert bar.y() == screen.top() + padding["top"]
    else:
        assert bar.geometry().bottom() == screen.bottom() - padding["bottom"]


def test_auto_hide_sets_up_its_manager(make_bar: MakeBar):
    bar = make_bar(window_flags={"auto_hide": True})

    assert bar.autohide_manager is not None
    assert bar.autohide_manager.is_enabled()


def test_hide_on_maximized_starts_the_watcher(make_bar: MakeBar):
    bar = make_bar(window_flags={"hide_on_maximized": True})

    assert bar._maximized_watcher is not None


def test_auto_width_uses_its_manager(make_bar: MakeBar):
    bar = make_bar(dimensions={"width": "auto"})

    assert bar._auto_width_manager is not None
    bar._auto_width_manager.sync()


@pytest.mark.parametrize(
    "window_flags, registered",
    [
        ({}, False),
        ({"windows_app_bar": True}, True),
        ({"always_on_top": True, "hide_on_fullscreen": True}, True),
    ],
)
def test_app_bar_registration(
    make_bar: MakeBar, registered_bars: list[int], window_flags: dict[str, bool], registered: bool
):
    make_bar(window_flags=window_flags)

    assert bool(registered_bars) == registered


@pytest.mark.parametrize("animation_type", ["slide", "fade"])
def test_animations_run_to_completion(make_bar: MakeBar, animation_type: str):
    bar = make_bar(animation={"enabled": True, "type": animation_type, "duration": 20})
    _wait(80)

    bar.hide()
    _wait(120)
    assert not bar.isVisible()

    bar.show_bar()
    _wait(120)
    assert bar.isVisible()


@pytest.mark.parametrize("enabled", [True, False])
def test_context_menu(make_bar: MakeBar, enabled: bool):
    bar = make_bar(context_menu=enabled, animation={"enabled": False})
    point = QPoint(5, 5)

    bar.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, bar.mapToGlobal(point)))
    menus = bar.findChildren(QMenu)

    if not enabled:
        assert menus == []
        return
    assert len(menus) >= 1
    texts = [action.text() for action in menus[0].actions() if action.text()]
    assert texts[0] == "Bar: test-bar"
    assert {"Task Manager", "Take Screenshot", "Enable Auto Hide", "Reload Bar", "Exit"} <= set(texts)
    menus[0].close()

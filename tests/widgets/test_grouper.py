# pyright: reportPrivateUsage=false

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from core.utils.widget_builder import WidgetBuilder
from core.widgets.base import BaseWidget
from core.widgets.yasb.grouper import STATE_FILE, GrouperWidget

type MakeGrouper = Callable[..., GrouperWidget]

EXPANDED_LABEL = "expanded"
COLLAPSED_LABEL = "collapsed"


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path / "YASB"


@pytest.fixture
def make_grouper(qapp: QApplication, state_dir: Path) -> Iterator[MakeGrouper]:
    groupers: list[GrouperWidget] = []

    def make(screen_name: str = "DISPLAY1", collapse: bool = True) -> GrouperWidget:
        configs = {
            "child": {"type": "yasb.custom.CustomWidget", "options": {"class_name": "child", "label": "child"}},
            "group": {
                "type": "yasb.grouper.GrouperWidget",
                "options": {
                    "widgets": ["child"],
                    "collapse_options": {
                        "enabled": collapse,
                        "expanded_label": EXPANDED_LABEL,
                        "collapsed_label": COLLAPSED_LABEL,
                    },
                },
            },
        }
        grouper = WidgetBuilder(configs).build_widget("group")
        assert isinstance(grouper, GrouperWidget)
        # BarManager sets the screen before the bar is shown
        grouper.screen_name = screen_name
        groupers.append(grouper)
        grouper.show()
        qapp.processEvents()
        return grouper

    yield make
    for grouper in groupers:
        for child in grouper._child_widgets:
            child.timer.stop()
        grouper.close()


def _child(grouper: GrouperWidget) -> BaseWidget:
    return grouper._child_widgets[0]


def _button(grouper: GrouperWidget) -> QPushButton:
    assert grouper._collapse_button is not None
    return grouper._collapse_button


def test_starts_collapsed_without_saved_state(make_grouper: MakeGrouper):
    grouper = make_grouper()

    assert _child(grouper).isHidden()
    assert _button(grouper).text() == COLLAPSED_LABEL


def test_expanded_state_survives_restart(make_grouper: MakeGrouper):
    _button(make_grouper()).click()

    restarted = make_grouper()

    assert not _child(restarted).isHidden()
    assert _button(restarted).text() == EXPANDED_LABEL


def test_collapsed_again_survives_restart(make_grouper: MakeGrouper):
    grouper = make_grouper()
    _button(grouper).click()
    _button(grouper).click()

    restarted = make_grouper()

    assert _child(restarted).isHidden()
    assert _button(restarted).text() == COLLAPSED_LABEL


def test_state_is_kept_per_screen(make_grouper: MakeGrouper):
    _button(make_grouper(screen_name="DISPLAY1")).click()

    assert not _child(make_grouper(screen_name="DISPLAY1")).isHidden()
    assert _child(make_grouper(screen_name="DISPLAY2")).isHidden()


def test_unreadable_state_file_falls_back_to_collapsed(make_grouper: MakeGrouper, state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / STATE_FILE).write_text("{not json", encoding="utf-8")

    grouper = make_grouper()
    assert _child(grouper).isHidden()

    # Toggling replaces the broken file with a valid one
    _button(grouper).click()
    assert json.loads((state_dir / STATE_FILE).read_text(encoding="utf-8")) == {"DISPLAY1:group": False}


def test_nothing_is_saved_without_collapse_button(make_grouper: MakeGrouper, state_dir: Path):
    grouper = make_grouper(collapse=False)
    grouper._toggle_collapsed()

    assert not (state_dir / STATE_FILE).exists()

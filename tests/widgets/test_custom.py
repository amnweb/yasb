# pyright: reportPrivateUsage=false

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from core.validation.widgets.yasb.custom import CustomConfig
from core.widgets.yasb import custom
from core.widgets.yasb.custom import CustomWidget, CustomWorker

type MakeWidget = Callable[..., CustomWidget]


class _InlineThread:
    def __init__(self, target: Callable[[], None]) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


@pytest.fixture
def make_widget(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MakeWidget]:
    monkeypatch.setattr(custom, "threading", SimpleNamespace(Thread=_InlineThread))
    widgets: list[CustomWidget] = []

    def make(**config: Any) -> CustomWidget:
        widget = CustomWidget(CustomConfig.model_validate({"class_name": "test", **config}))
        widgets.append(widget)
        return widget

    yield make
    for widget in widgets:
        widget.timer.stop()
        widget.close()


def _texts(labels: list[QLabel]) -> list[str]:
    return [label.text() for label in labels]


def _worker_output(code: str, return_format: str) -> object:
    worker = CustomWorker(subprocess.list2cmdline([sys.executable, "-c", code]), False, None, return_format, False)
    received: list[object] = []
    worker.data_ready.connect(received.append)
    worker.run()
    return received[0]


# --- reading the command's output ----------------------------------------------------


def test_json_output_becomes_data():
    assert _worker_output("import json; print(json.dumps({'cpu': 7}))", "json") == {"cpu": 7}


def test_output_that_is_not_json_becomes_none():
    assert _worker_output("print('not json')", "json") is None


def test_string_output_is_stripped():
    assert _worker_output("print('  hello  ')", "string") == "hello"


# --- the label -------------------------------------------------------------------------


def test_command_output_fills_the_label(make_widget: MakeWidget):
    widget = make_widget(label="CPU {data[0]}%", exec_options={"run_cmd": "echo [7,3]"})

    assert _texts(widget._widgets) == ["CPU 7%"]


def test_string_output_fills_the_label(make_widget: MakeWidget):
    widget = make_widget(label="{data}", exec_options={"run_cmd": "echo hello", "return_format": "string"})

    assert _texts(widget._widgets) == ["hello"]


def test_a_missing_key_shows_the_template_instead_of_crashing(make_widget: MakeWidget):
    widget = make_widget(label="{data[5]}", exec_options={"run_cmd": "echo [7]"})

    assert _texts(widget._widgets) == ["{data[5]}"]


def test_long_output_is_truncated(make_widget: MakeWidget):
    widget = make_widget(
        label="{data}",
        label_max_length=3,
        exec_options={"run_cmd": "echo abcdef", "return_format": "string"},
    )

    assert _texts(widget._widgets) == ["abc..."]


def test_an_icon_span_keeps_its_own_label(make_widget: MakeWidget):
    widget = make_widget(
        label="<span>\uf2db</span> {data}",
        exec_options={"run_cmd": "echo hello", "return_format": "string"},
    )

    assert _texts(widget._widgets) == ["\uf2db", "hello"]


def test_hide_empty_hides_the_widget_until_there_is_output(make_widget: MakeWidget):
    widget = make_widget(
        label="{data}",
        exec_options={"run_cmd": "exit 0", "return_format": "string", "hide_empty": True},
    )
    assert widget.isHidden(), "an empty result left the widget on the bar"

    widget._handle_exec_data("back")
    assert not widget.isHidden()
    assert _texts(widget._widgets) == ["back"]


def test_the_alt_label_swaps_in_on_toggle(make_widget: MakeWidget):
    widget = make_widget(
        label="{data}",
        label_alt="alt {data}",
        exec_options={"run_cmd": "echo hello", "return_format": "string"},
    )

    widget._run_callback("toggle_label")

    assert all(label.isHidden() for label in widget._widgets)
    assert not any(label.isHidden() for label in widget._widgets_alt)
    assert _texts(widget._widgets_alt) == ["alt hello"]


def test_a_quoted_argument_reaches_the_command_intact(make_widget: MakeWidget):
    widget = make_widget(
        label="{data}",
        exec_options={"run_cmd": f'"{sys.executable}" -c "print(42)"', "return_format": "string"},
    )

    assert _texts(widget._widgets) == ["42"]


# --- the tooltip -----------------------------------------------------------------------


@pytest.fixture
def tooltips(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    shown: list[str] = []

    def set_tooltip(widget: QWidget, text: str, delay: int = 400, position: str | None = None) -> None:
        shown.append(text)

    monkeypatch.setattr(custom, "set_tooltip", set_tooltip)
    return shown


def test_the_tooltip_formats_the_data(make_widget: MakeWidget, tooltips: list[str]):
    make_widget(label="{data[0]}", tooltip=True, tooltip_label="CPU {data[0]}%", exec_options={"run_cmd": "echo [7]"})

    assert tooltips[-1] == "CPU 7%"


def test_a_tooltip_that_cannot_be_formatted_shows_the_raw_data(make_widget: MakeWidget, tooltips: list[str]):
    make_widget(label="{data[0]}", tooltip=True, tooltip_label="{data[9]}", exec_options={"run_cmd": "echo [7]"})

    assert tooltips[-1] == "[7]"


def test_a_tooltip_without_a_label_shows_the_data_as_json(make_widget: MakeWidget, tooltips: list[str]):
    widget = make_widget(label="{data}", tooltip=True)

    widget._handle_exec_data({"cpu": 7})

    assert tooltips[-1] == json.dumps({"cpu": 7}, indent=2)


# --- callbacks -------------------------------------------------------------------------


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    commands: list[list[str]] = []

    def popen(args: list[str], **kwargs: object) -> None:
        commands.append(args)

    monkeypatch.setattr(custom, "subprocess", SimpleNamespace(Popen=popen))
    return commands


def test_exec_fills_the_data_into_its_arguments(make_widget: MakeWidget, launched: list[list[str]]):
    widget = make_widget(label="{data}")
    widget._handle_exec_data({"file": "notes.txt"})

    widget._run_callback("exec notepad.exe {data[file]}")

    assert launched == [["notepad.exe", "notes.txt"]]


def test_exec_passes_an_unknown_key_through_unchanged(make_widget: MakeWidget, launched: list[list[str]]):
    widget = make_widget(label="{data}")
    widget._handle_exec_data({"file": "notes.txt"})

    widget._run_callback("exec notepad.exe {data[missing]}")

    assert launched == [["notepad.exe", "{data[missing]}"]]

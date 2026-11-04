from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl, pyqtBoundSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.services.dnd import status as status_module
from core.services.dnd.dnd_api import DndService
from core.services.dnd.status import DoNotDisturb
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


class Events:
    """Stands in for EventService, so a test can send what Windows' callback sends."""

    def __init__(self) -> None:
        self.signals: dict[str, list[pyqtBoundSignal]] = {}

    def register_event(self, event: str, signal: pyqtBoundSignal) -> None:
        self.signals.setdefault(event, []).append(signal)

    def unregister_event(self, event: str, signal: pyqtBoundSignal) -> None:
        self.signals[event].remove(signal)

    def emit_event(self, event: str, *args: Any) -> None:
        for signal in self.signals.get(event, []):
            signal.emit(*args)


class Dnd:
    """Stands in for DndService, so the tests never change Windows' do not disturb."""

    MODES = DndService.MODES
    status = "disabled"
    written: list[str] = []

    @classmethod
    def initialize_wnf_listener(cls) -> None:
        pass

    @classmethod
    def get_status(cls) -> str:
        return cls.status

    @classmethod
    def set_status(cls, mode: str) -> None:
        cls.written.append(mode)


@pytest.fixture
def events(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Events:
    events = Events()
    Dnd.status = "disabled"
    Dnd.written = []
    monkeypatch.setattr(status_module, "EventService", lambda: events)
    monkeypatch.setattr(status_module, "DndService", Dnd)
    return events


def test_the_mode_is_read_after_the_bar_is_up_and_follows_windows(events: Events):
    Dnd.status = "priority"
    dnd = DoNotDisturb()
    assert dnd.property("status") == "unknown" and not dnd.property("available")
    wait(10)
    assert dnd.property("status") == "priority" and dnd.property("active")
    events.emit_event("dnd_status_changed", "disabled")
    assert dnd.property("status") == "disabled" and not dnd.property("active")


def test_toggle_turns_the_chosen_mode_on_and_any_mode_off(events: Events):
    dnd = DoNotDisturb()
    wait(10)
    dnd.toggle("alarms")
    assert dnd.property("status") == "alarms"
    dnd.toggle("alarms")
    dnd.toggle("priority")
    dnd.toggle("priority")
    assert Dnd.written == ["alarms", "disabled", "priority", "disabled"]


def test_cycle_goes_off_priority_alarms(events: Events):
    dnd = DoNotDisturb()
    wait(10)
    for _ in range(3):
        dnd.cycle()
    assert Dnd.written == ["priority", "alarms", "disabled"]


def test_nothing_is_written_where_windows_has_no_do_not_disturb_or_for_a_wrong_mode(events: Events):
    Dnd.status = "unknown"
    dnd = DoNotDisturb()
    wait(10)
    dnd.toggle("priority")
    dnd.cycle()
    dnd.setStatus("priority")
    events.emit_event("dnd_status_changed", "disabled")
    dnd.setStatus("sleeping")
    assert Dnd.written == []


def test_the_widget_stops_listening_once_qml_deleted_it(events: Events):
    dnd = DoNotDisturb()
    assert len(events.signals["dnd_status_changed"]) == 1
    sip.delete(dnd)
    assert events.signals["dnd_status_changed"] == []


def test_the_bar_icon_follows_the_mode(events: Events):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Dnd" / "Dnd.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    icon = find_item(widget, "icon")
    assert icon is not None
    for name in ("offIcon", "priorityIcon", "alarmsIcon"):
        widget.setProperty(name, name)
    assert icon.property("text") == "offIcon"
    for mode, glyph in (("priority", "priorityIcon"), ("alarms", "alarmsIcon"), ("disabled", "offIcon")):
        events.emit_event("dnd_status_changed", mode)
        assert icon.property("text") == glyph
    assert not warnings
    sip.delete(widget)

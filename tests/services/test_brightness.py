from datetime import time
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMetaObject, QModelIndex, QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.brightness import control as control_module
from core.services.brightness.control import DisplayBrightness, DisplayList, is_night
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

BUILT_IN, EXTERNAL = 1, 2


class FakeBrightness(QObject):
    """Stands in for BrightnessService, so the tests never touch the real displays."""

    brightness_changed = pyqtSignal(int, object)
    contrast_changed = pyqtSignal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self.displays: dict[int, dict[str, Any]] = {
            BUILT_IN: {"name": "Built-in display", "brightness": 70, "contrast": None},
            EXTERNAL: {"name": "DELL P2419H", "brightness": 40, "contrast": 50},
        }
        self.set: list[tuple[str, int, int]] = []
        self.poll_interval = -1
        self.refreshes = 0

    def instance(self, poll_interval: int) -> FakeBrightness:
        self.poll_interval = poll_interval
        return self

    def get_brightness(self, hmonitor: int) -> int | None:
        return self.displays[hmonitor]["brightness"] if hmonitor in self.displays else None

    def get_contrast(self, hmonitor: int) -> int | None:
        return self.displays[hmonitor]["contrast"]

    def supports_contrast(self, hmonitor: int) -> bool:
        return self.displays[hmonitor]["contrast"] is not None

    def get_monitors(self) -> list[tuple[int, str]]:
        return [(hmonitor, display["name"]) for hmonitor, display in self.displays.items()]

    def get_monitor_subtitle(self, _hmonitor: int, index: int = 0) -> str:
        return f"Monitor {index + 1}"

    def set_brightness(self, hmonitor: int, value: int) -> None:
        self.set.append(("brightness", hmonitor, value))
        self.displays[hmonitor]["brightness"] = value
        self.brightness_changed.emit(hmonitor, value)

    def set_contrast(self, hmonitor: int, value: int) -> None:
        self.set.append(("contrast", hmonitor, value))
        self.displays[hmonitor]["contrast"] = value

    def refresh_now(self) -> None:
        self.refreshes += 1


@pytest.fixture
def service(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeBrightness:
    service = FakeBrightness()
    monkeypatch.setattr(control_module, "BrightnessService", service)
    monkeypatch.setattr(control_module, "MonitorFromWindow", lambda _hwnd: EXTERNAL)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    return service


def started(window: QQuickWindow | None = None) -> DisplayBrightness:
    control = DisplayBrightness()
    control.setProperty("window", window)
    wait(10)
    return control


def test_night_may_cross_midnight():
    assert is_night(time(21, 0), time(20, 0), time(6, 30))
    assert is_night(time(5, 0), time(20, 0), time(6, 30))
    assert not is_night(time(12, 0), time(20, 0), time(6, 30))
    assert is_night(time(13, 0), time(12, 0), time(14, 0))
    assert not is_night(time(15, 0), time(12, 0), time(14, 0))


def test_the_list_changes_values_in_place_and_resets_only_for_other_displays(qapp: QGuiApplication):
    model = DisplayList()
    row = {"monitor": 1, "name": "A", "subtitle": "", "brightness": 10, "contrast": -1}
    model.update([row])
    resets: list[bool] = []
    changed: list[int] = []

    def on_changed(first: QModelIndex, _last: QModelIndex, _roles: Any = None) -> None:
        changed.append(first.row())

    model.modelReset.connect(lambda: resets.append(True))
    model.dataChanged.connect(on_changed)
    model.update([{**row, "brightness": 20}])
    assert changed == [0] and not resets and model.rows[0]["brightness"] == 20
    model.update([row, {**row, "monitor": 2}])
    assert resets and model.property("count") == 2


def test_the_window_display_and_every_display_come_from_the_service(service: FakeBrightness):
    window = QQuickWindow()
    control = started(window)
    assert service.poll_interval == 60
    assert (control.property("brightness"), control.property("available")) == (40, True)
    assert [(row["name"], row["brightness"], row["contrast"]) for row in control.property("displays").rows] == [
        ("Built-in display", 70, -1),
        ("DELL P2419H", 40, 50),
    ]


def test_settings_reach_the_service_and_its_changes_reach_the_widget(service: FakeBrightness):
    control = started(QQuickWindow())
    changes: list[bool] = []
    control.changed.connect(lambda: changes.append(True))
    control.setBrightness(55)
    control.setDisplayBrightness(BUILT_IN, 20)
    control.setDisplayContrast(EXTERNAL, 80)
    assert service.set == [("brightness", EXTERNAL, 55), ("brightness", BUILT_IN, 20), ("contrast", EXTERNAL, 80)]
    # Only the window's own display changes its brightness
    assert len(changes) == 1 and control.property("brightness") == 55
    assert [(row["brightness"], row["contrast"]) for row in control.property("displays").rows] == [(20, -1), (55, 80)]
    control.refresh()
    assert service.refreshes == 1


def test_without_a_window_or_on_a_display_without_brightness_nothing_is_set(
    service: FakeBrightness, monkeypatch: pytest.MonkeyPatch
):
    control = started()
    assert (control.property("brightness"), control.property("available")) == (-1, False)
    control.setBrightness(50)
    monkeypatch.setattr(control_module, "MonitorFromWindow", lambda _hwnd: 99)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    control.setProperty("window", QQuickWindow())
    control.setBrightness(50)
    assert service.set == [] and not control.property("available")


def load_widget() -> tuple[QQuickItem, QQuickWindow, QQmlEngine, list[str]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Brightness" / "Brightness.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    widget.setParentItem(host.contentItem())
    host.show()
    wait(10)
    return widget, host, engine, warnings


def test_the_bar_shows_the_level_and_hides_where_brightness_cant_be_controlled(
    service: FakeBrightness, monkeypatch: pytest.MonkeyPatch
):
    widget, host, _engine, warnings = load_widget()
    icon, label = find_item(widget, "icon"), find_item(widget, "label")
    assert icon is not None and label is not None
    widget.setProperty("icons", ["dim", "half", "bright"])
    widget.setProperty("label", "{percent}%")
    assert widget.property("implicitWidth") > 0
    assert (icon.property("text"), label.property("text")) == ("half", "40%")
    service.set_brightness(EXTERNAL, 100)
    assert icon.property("text") == "bright"
    service.set_brightness(EXTERNAL, 0)
    assert icon.property("text") == "dim"

    service.displays[EXTERNAL]["brightness"] = None
    service.brightness_changed.emit(EXTERNAL, None)
    assert widget.property("visible") is False and widget.property("implicitWidth") == 0
    assert icon.property("text") == ""
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_auto_light_sets_each_level_once_when_day_and_night_change(
    service: FakeBrightness, monkeypatch: pytest.MonkeyPatch
):
    night = [True]

    def is_night(*_: time) -> bool:
        return night[0]

    monkeypatch.setattr(control_module, "is_night", is_night)
    widget, host, _engine, warnings = load_widget()
    widget.setProperty("nightLevel", 30)
    widget.setProperty("dayLevel", 90)
    for _ in range(2):
        QMetaObject.invokeMethod(widget, "applyAutoLight")
    night[0] = False
    QMetaObject.invokeMethod(widget, "applyAutoLight")
    assert service.set == [("brightness", EXTERNAL, 30), ("brightness", EXTERNAL, 90)]
    assert not warnings
    sip.delete(widget)
    sip.delete(host)

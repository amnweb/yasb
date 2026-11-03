import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.battery import monitor as monitor_module
from core.widgets.services.battery.battery_api import POWER_TIME_UNLIMITED, BatteryData
from core.widgets.services.battery.monitor import BatteryMonitor
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

ON_BATTERY = BatteryData(
    percent=60,
    is_charging=False,
    power_plugged=False,
    time_remaining=9000,
    rate=-12.345,
    voltage=12.4567,
    capacity=30000,
    full_capacity=50000,
    designed_capacity=60000,
    temperature=None,
    cycle_count=120,
    chemistry="LiP",
    health_percent=83.3,
)
CHARGING = BatteryData(8, True, True, POWER_TIME_UNLIMITED, None, None, None, None, None, None, None, None, None)


class FakeApi:
    def __init__(self) -> None:
        self.status: BatteryData | None = ON_BATTERY

    def get_status(self) -> BatteryData | None:
        return self.status


@pytest.fixture
def api(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    api = FakeApi()
    monkeypatch.setattr(monitor_module.BatteryAPI, "instance", lambda: api)
    return api


def create_widget() -> tuple[QQmlEngine, QQuickItem, QQuickItem]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Battery" / "Battery.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    # Qt only counts an item visible inside a visible parent
    root = QQuickItem()
    widget.setParentItem(root)
    return engine, root, widget


def item(widget: QQuickItem, name: str) -> QQuickItem:
    found = find_item(widget, name)
    assert found is not None, name
    return found


def test_the_monitor_publishes_the_battery_status(api: FakeApi):
    monitor = BatteryMonitor()
    wait(10)
    assert monitor.property("available") is True
    data = monitor.property("data")
    assert (data["percent"], data["charging"], data["timeText"], data["timeNatural"]) == (
        60,
        False,
        "2:30:00",
        "2 hours",
    )
    assert data["temperature"] is None

    api.status = None
    monitor.refresh()
    assert monitor.property("available") is False


def test_the_widget_fills_the_label_placeholders(api: FakeApi):
    _engine, _root, widget = create_widget()
    widget.setProperty("label", "{percent}% {power}W {voltage}V {temperature} {health}% {chemistry} {nope}")
    label = find_item(widget, "label")
    assert label is not None
    assert label.property("text") == "60% 12.3W 12.46V N/A 83.3% LiP {nope}"
    assert widget.property("level") == "medium"
    assert item(widget, "icon").property("text") == ""

    widget.setProperty("showAlternate", True)
    assert label.property("text") == "60% | remaining: 2:30:00"
    widget.setProperty("timeRemainingNatural", True)
    assert label.property("text") == "60% | remaining: 2 hours"


def test_the_widget_shows_charging(api: FakeApi):
    api.status = CHARGING
    _engine, _root, widget = create_widget()
    widget.setProperty("showAlternate", True)
    assert widget.property("status") == "charging"
    assert widget.property("level") == "critical"
    assert item(widget, "icon").property("text") == ""
    assert item(widget, "label").property("text") == "8% | remaining: unlimited"


def test_the_widget_hides_without_a_battery(api: FakeApi):
    api.status = None
    _engine, _root, widget = create_widget()
    assert widget.property("visible") is False and widget.property("implicitWidth") == 0

    widget.setProperty("hideUnsupported", False)
    assert widget.property("visible") is True
    assert item(widget, "label").property("text") == "Battery info not available"

# pyright: reportPrivateUsage=false

from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QEvent, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.utils.stat_popup import PinnablePopup
from core.validation.widgets.yasb.temperature import SensorThresholds, TemperatureConfig
from core.widgets.services.temperature.graph import TemperatureGraph
from core.widgets.services.temperature.libre import (
    TemperatureHistory,
    TemperatureReading,
    TemperatureSnapshot,
    TemperatureWorker,
    celsius,
    decode_temperatures,
)
from core.widgets.yasb.temperature import TemperatureWidget


def reading(
    identifier: str = "/amdcpu/0/temperature/2",
    value: float | None = 52,
    name: str = "Core (Tctl/Tdie)",
    hardware: str = "/amdcpu/0",
    kind: str = "cpu",
) -> TemperatureReading:
    return TemperatureReading(identifier, hardware, "CPU model" if kind == "cpu" else "GPU model", kind, name, value)


@pytest.mark.parametrize(
    "node, expected",
    [
        ({"RawValue": 51.25, "Value": "51,3 °C"}, 51.25),
        ({"Value": "62,5 °C"}, 62.5),
        ({"Value": "86 °F"}, 30),
        ({"RawValue": 0}, 0),
        ({"RawValue": None, "Value": "—"}, None),
        ({"RawValue": float("nan"), "Value": "N/A"}, None),
        ({"RawValue": True}, None),
        ({"Value": "99999 °C"}, None),
    ],
)
def test_temperature_parsing_preserves_valid_zero_and_missing_readings(node: dict[str, object], expected: float | None):
    assert celsius(node) == expected


def test_sensor_tree_keeps_component_identity_and_excludes_other_sensor_types():
    root = {
        "Children": [
            {
                "HardwareId": "/amdcpu/0",
                "Text": "CPU model",
                "Children": [
                    {
                        "Text": "Temperatures",
                        "Children": [
                            {"SensorId": "/amdcpu/0/temperature/2", "Text": "Core (Tctl/Tdie)", "Value": "52 °C"},
                            {"SensorId": "/amdcpu/0/clock/0", "Text": "Core", "Value": "4500 MHz"},
                        ],
                    }
                ],
            },
            {
                "HardwareId": "/gpu-amd/0",
                "Text": "Integrated GPU",
                "Children": [{"SensorId": "/gpu-amd/0/temperature/4", "Text": "GPU VR SoC", "Value": "43 °C"}],
            },
            {
                "HardwareId": "/nvme/0",
                "Text": "SSD",
                "Children": [{"SensorId": "/nvme/0/temperature/0", "Value": "40 °C"}],
            },
        ]
    }
    sensors = decode_temperatures(root)
    assert len(sensors) == 2
    assert sensors[0].hardware_name == "CPU model" and sensors[0].value == 52
    assert sensors[1].kind == "gpu" and sensors[1].name == "GPU VR SoC"
    assert not decode_temperatures({"Children": "invalid"})


def test_history_tracks_real_time_and_missing_samples_without_replacing_them_with_zero():
    history = TemperatureHistory(120)
    first = history.collect((reading(value=50),), 1)
    history.collect((reading(value=60),), 60)
    offline = history.collect((), 100, "Offline")
    assert offline.sensors[0].value is None
    assert offline.histories[first.sensors[0].sensor_id][-1] == (100, None)
    restored = history.collect((reading(value=55),), 125)
    assert restored.histories[first.sensors[0].sensor_id] == ((60, 60), (100, None), (125, 55))
    assert first.histories[first.sensors[0].sensor_id] == ((1, 50),)


def test_worker_recovers_after_offline_and_preserves_sensor_metadata(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
):
    worker = TemperatureWorker("127.0.0.1", 8085, 1000, 120)
    try:
        monkeypatch.setattr(
            worker._client, "read", Mock(side_effect=[(reading(),), OSError("Offline"), (reading(value=60),)])
        )
        assert worker.poll(1).sensors[0].value == 52
        unavailable = worker.poll(2)
        assert unavailable.sensors[0].value is None and "unavailable" in unavailable.status
        restored = worker.poll(3)
        assert restored.sensors[0].value == 60 and restored.status == ""
        assert len(restored.histories[reading().sensor_id]) == 3
    finally:
        worker.stop()


def test_temperature_graph_keeps_celsius_above_100_and_does_not_connect_across_gaps(qapp: QApplication):
    graph = TemperatureGraph()
    graph.resize(400, 130)
    graph.set_readings(((1, 105), (2, 110), (3, None), (4, 115), (5, 120)), 5, 120)
    assert graph.maximum == 120 and graph.minimum == 0
    assert not graph._fill_enabled
    assert graph._line_path is not None
    moves = sum(graph._line_path.elementAt(i).isMoveTo() for i in range(graph._line_path.elementCount()))
    assert moves == 2
    graph.set_readings(((6, None),), 6, 120)
    assert graph._line_path is not None and graph._line_path.isEmpty()
    graph.deleteLater()


def test_thresholds_are_optional_validated_and_scaled_in_celsius(qapp: QApplication):
    assert not TemperatureConfig().thresholds
    with pytest.raises(ValueError):
        SensorThresholds(warning=90, critical=80)
    graph = TemperatureGraph()
    graph.set_readings(((1, 110),), 1, 120, SensorThresholds(warning=80, critical=100))
    assert graph._color_bands[0][1] == pytest.approx(80 / 120 * 100)
    assert graph._color_bands[1][1] == pytest.approx(100 / 120 * 100)
    graph.deleteLater()


class FakeWorker(QObject):
    data_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.history = TemperatureHistory(120)
        self.latest = self.history.collect(
            (
                reading(),
                reading("/amdcpu/0/temperature/3", 48, "CCD1 (Tdie)"),
                reading("/gpu-amd/5/temperature/0", 45, "GPU Core", "/gpu-amd/5", "gpu"),
                reading("/gpu-amd/5/temperature/1", 55, "GPU Memory", "/gpu-amd/5", "gpu"),
                reading("/gpu-amd/5/temperature/7", 60, "GPU Hot Spot", "/gpu-amd/5", "gpu"),
                reading("/gpu-amd/0/temperature/4", 43, "GPU VR SoC", "/gpu-amd/0", "gpu"),
            ),
            1,
        )

    def isRunning(self) -> bool:
        return True


@pytest.fixture
def widget(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[TemperatureWidget]:
    worker = FakeWorker()
    monkeypatch.setattr(TemperatureWorker, "get_instance", Mock(return_value=worker))
    instance = TemperatureWidget(
        TemperatureConfig.model_validate(
            {
                "hardware_labels": {"/amdcpu/0": "CPU", "/gpu-amd/5": "GPU 0", "/gpu-amd/0": "GPU 1"},
                "menu": {"blur": False, "round_corners": False},
            }
        )
    )
    yield instance
    popup = instance.findChildren(PinnablePopup)
    for item in popup:
        item.hide()
        item.deleteLater()
    instance.deleteLater()


def popup_for(widget: TemperatureWidget) -> PinnablePopup:
    widget._show_popup()
    from core.utils.utilities import PopupWidget

    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    return popup


def test_components_and_sensors_switch_in_same_native_popup(widget: TemperatureWidget):
    popup = popup_for(widget)
    assert list(button.text() for button in widget._component_buttons.values()) == ["CPU", "GPU 0", "GPU 1"]
    assert widget._selected_sensors["/amdcpu/0"] == "/amdcpu/0/temperature/2"
    assert popup.stat_labels["current"].text() == "52 °C"
    widget._component_buttons["/gpu-amd/5"].click()
    widget._sensor_buttons["/gpu-amd/5/temperature/7"].click()
    assert popup.isVisible() and not popup._is_closing
    assert popup.stat_labels["current"].text() == "60 °C"
    widget._component_buttons["/gpu-amd/0"].click()
    assert [button.text() for button in widget._sensor_buttons.values()] == ["VR SoC"]
    widget._component_buttons["/gpu-amd/5"].click()
    assert widget._sensor_buttons["/gpu-amd/5/temperature/7"].isChecked()


def test_history_keeps_collecting_while_closed_and_survives_reopening(widget: TemperatureWidget):
    popup = popup_for(widget)
    popup.hide()
    history = TemperatureHistory(120)
    history.collect((reading(value=50),), 1)
    widget._receive(history.collect((reading(value=60),), 2))
    reopened = popup_for(widget)
    assert reopened.stat_labels["minimum"].text() == "50 °C"
    assert reopened.stat_labels["maximum"].text() == "60 °C"
    assert len(widget._graph._readings) == 2


def test_pin_persists_during_selection_and_offline_does_not_show_zero(widget: TemperatureWidget):
    popup = popup_for(widget)
    pin = next(button for button in popup.findChildren(QPushButton) if "pin-btn" in str(button.property("class")))
    pin.click()
    popup.event(QEvent(QEvent.Type.WindowDeactivate))
    assert popup.isVisible() and popup.is_pinned
    widget._component_buttons["/gpu-amd/5"].click()
    history = TemperatureHistory(120)
    history.collect(widget._snapshot.sensors, 1)
    widget._receive(history.collect((), 2, "Libre unavailable"))
    assert popup.stat_labels["current"].text() == "—"
    assert widget._status.isVisible()
    assert popup.is_pinned and "pinned" in str(pin.property("class"))


def test_optional_thresholds_color_the_current_value(widget: TemperatureWidget):
    widget.config.thresholds[reading().sensor_id] = SensorThresholds(warning=50, critical=60)
    popup = popup_for(widget)
    assert "warning" in str(popup.stat_labels["current"].property("class"))
    history = TemperatureHistory(120)
    widget._receive(history.collect((reading(value=65),), 2))
    assert "critical" in str(popup.stat_labels["current"].property("class"))


def test_empty_start_keeps_status_and_native_layout_usable(widget: TemperatureWidget):
    widget._receive(TemperatureSnapshot((), {}, 1, "Libre unavailable"))
    popup = popup_for(widget)
    assert popup.stat_labels["current"].text() == "—"
    assert not widget._component_frame.isVisible()
    assert not widget._sensor_frame.isVisible()
    assert widget._status.text() == "Libre unavailable"


def test_temperature_popup_widgets_fit_within_the_standard_width(widget: TemperatureWidget, qapp: QApplication):
    popup = popup_for(widget)
    popup.setStyleSheet("""
        .temperature-popup { min-width: 400px; max-width: 800px; }
        .header { padding: 14px 16px; }
        .stats { padding: 10px; }
        .stat-item { padding: 8px; margin: 6px; border: 1px solid #292929; }
        .stat-value { font-size: 18px; }
        .stat-value.primary { font-size: 26px; }
        .graph-container { min-height: 130px; max-height: 130px; }
    """)
    qapp.processEvents()
    assert popup.width() == 400
    for child in popup.findChildren(QLabel) + popup.findChildren(QPushButton):
        if child.isVisible():
            assert popup.rect().contains(child.rect().translated(child.mapTo(popup, child.rect().topLeft())))

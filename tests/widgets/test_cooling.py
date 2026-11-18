# pyright: reportPrivateUsage=false

import io
import json
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QEvent, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.stat_popup import PinnablePopup
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.cpu import CpuConfig
from core.validation.widgets.yasb.gpu import GpuConfig
from core.widgets.services.cooling.libre import FanReading, decode_fans, gpu_fans, motherboard_fans, rpm_value
from core.widgets.services.cooling.view import CoolingSection
from core.widgets.services.cpu.cpu_api import CpuWorker
from core.widgets.services.gpu.gpu_api import GpuData, GpuWorker
from core.widgets.services.temperature.libre import (
    LibreTemperatures,
    TemperatureHistory,
    TemperatureSnapshot,
    TemperatureWorker,
)
from core.widgets.yasb.cpu import CpuWidget
from core.widgets.yasb.gpu import GpuWidget


def fans() -> tuple[FanReading, ...]:
    return (
        FanReading("/lpc/chip/fan/0", "/lpc/chip", "Motherboard", "Fan #1", 0),
        FanReading("/lpc/chip/fan/1", "/lpc/chip", "Motherboard", "Fan #2", 1200),
        FanReading("/gpu-amd/5/fan/0", "/gpu-amd/5", "GPU Card", "GPU Fan", 0),
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0 RPM", 0),
        ("1200 RPM", 1200),
        ("1,5 RPM", 1.5),
        ("1.2e3 RPM", 1200),
        ("-20 RPM", None),
        ("60 %", None),
        ("N/A", None),
        (True, None),
        (float("nan"), None),
    ],
)
def test_rpm_values_distinguish_stopped_missing_and_control_percent(raw: object, expected: float | None):
    assert rpm_value({"RawValue": raw}) == expected


def tree() -> dict[str, object]:
    return {
        "Children": [
            {
                "HardwareId": "/lpc/chip",
                "Text": "Motherboard",
                "Children": [
                    {"SensorId": "/lpc/chip/fan/0", "Text": "Fan #1", "Value": "0 RPM"},
                    {"SensorId": "/lpc/chip/control/0", "Text": "Fan #1", "Value": "80 %"},
                ],
            },
            {
                "HardwareId": "/gpu-amd/5",
                "Text": "GPU Card",
                "Children": [
                    {"SensorId": "/gpu-amd/5/fan/0", "Text": "GPU Fan", "Value": "500 RPM"},
                    {"SensorId": "/gpu-amd/5/temperature/0", "Text": "GPU Core", "Value": "45 °C"},
                ],
            },
        ]
    }


def test_fan_decoder_excludes_percentage_controls_and_keeps_owner():
    readings = decode_fans(tree())
    assert len(readings) == 2
    assert readings[0].rpm == 0 and readings[0].hardware_name == "Motherboard"
    assert len(motherboard_fans(readings)) == 1
    assert gpu_fans(readings, "GPU Card")[0].rpm == 500
    assert not gpu_fans(readings, "Integrated GPU")


def test_identical_gpu_names_require_explicit_hardware_mapping():
    original = fans()[2]
    other = original._replace(sensor_id="/gpu-amd/7/fan/0", hardware_id="/gpu-amd/7", rpm=800)
    assert not gpu_fans((original, other), "GPU Card")
    assert gpu_fans((original, other), "GPU Card", "/gpu-amd/7") == (other,)


def test_same_http_response_supplies_temperature_and_fans(monkeypatch: pytest.MonkeyPatch):
    client = LibreTemperatures("127.0.0.1", 8085)
    request = Mock(return_value=io.BytesIO(json.dumps(tree()).encode()))
    monkeypatch.setattr(client.opener, "open", request)
    assert len(client.read()) == 1
    assert len(client.fans) == 2
    request.assert_called_once_with(client.url, timeout=0.75)


def test_fan_metadata_survives_disconnection_without_reusing_stale_rpm():
    history = TemperatureHistory(120)
    first = history.collect((), 1, fans=fans())
    missing = history.collect((), 2)
    assert len(missing.fans) == 3
    assert all(item.rpm is None for item in missing.fans)
    assert first.fans[0].rpm == 0


def test_explicit_cpu_and_pump_labels_use_only_configured_sensors(qapp: QApplication):
    section = CoolingSection({"CPU Fan": "/lpc/chip/fan/1", "Pump": "/missing/fan/0"})
    try:
        section.update_readings(fans())
        assert section.values["CPU Fan"].text() == "1200 RPM"
        assert section.values["Pump"].text() == "—"
    finally:
        section.deleteLater()


class FanWorker(QObject):
    data_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.latest = TemperatureSnapshot((), {}, 1, fans=fans())

    def isRunning(self) -> bool:
        return True


def test_cpu_native_popup_shows_original_fan_names_updates_and_keeps_pin(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
):
    fan_worker = FanWorker()
    monkeypatch.setattr(TemperatureWorker, "get_instance", Mock(return_value=fan_worker))
    monkeypatch.setattr(CpuWorker, "get_instance", Mock(return_value=Mock()))
    monkeypatch.setattr(CpuWidget, "_worker", None)
    monkeypatch.setattr(CpuWidget, "_instances", [])
    widget = CpuWidget(
        CpuConfig.model_validate(
            {"menu": {"enabled": True, "show_fan_rpm": True, "blur": False, "round_corners": False}}
        )
    )
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    try:
        assert widget._cooling is not None
        assert len(widget._cooling.values) == 2
        assert widget._cooling.values["/lpc/chip/fan/0"].text() == "0 RPM"
        popup._pin_buttons[0][0].click()
        popup.event(QEvent(QEvent.Type.WindowDeactivate))
        history = TemperatureHistory(120)
        history.collect((), 1, fans=fans())
        fan_worker.data_ready.emit(history.collect((), 2))
        assert all(value.text() == "—" for value in widget._cooling.values.values())
        assert popup.isVisible() and popup.is_pinned
    finally:
        popup.hide()
        popup.deleteLater()
        widget.deleteLater()


def test_gpu_rpm_tracks_selected_adapter_and_does_not_invent_integrated_fans(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
):
    fan_worker = FanWorker()
    monkeypatch.setattr(TemperatureWorker, "get_instance", Mock(return_value=fan_worker))
    monkeypatch.setattr(GpuWorker, "get_instance", Mock(return_value=Mock()))
    monkeypatch.setattr(GpuWidget, "_worker", None)
    monkeypatch.setattr(GpuWidget, "_instances", [])
    widget = GpuWidget(
        GpuConfig.model_validate(
            {
                "menu": {
                    "enabled": True,
                    "show_fan_rpm": True,
                    "adapter_selector": True,
                    "blur": False,
                    "round_corners": False,
                    "show_fan_speed": False,
                }
            }
        )
    )
    dedicated = GpuData(
        0, "GPU Card", 5, 16 * 1024**3, 0, 16 * 1024**3, 8 * 1024**3, 0, 40, 0, 0, adapter_id="dedicated"
    )
    integrated = dedicated._replace(gpu_index=1, name="Integrated GPU", adapter_id="integrated", mem_total=0)
    widget._receive_adapters([dedicated, integrated])
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    try:
        assert widget._cooling is not None
        assert widget._cooling.values["/gpu-amd/5/fan/0"].text() == "0 RPM"
        widget._selector_buttons["integrated"].click()
        assert list(value.text() for value in widget._cooling.values.values()) == ["—"]
        widget._selector_buttons["dedicated"].click()
        assert widget._cooling.values["/gpu-amd/5/fan/0"].text() == "0 RPM"
        assert popup.isVisible()
    finally:
        popup.hide()
        popup.deleteLater()
        widget.deleteLater()


def test_default_configs_keep_cooling_opt_in():
    assert not CpuConfig().menu.show_fan_rpm
    assert not GpuConfig().menu.show_fan_rpm

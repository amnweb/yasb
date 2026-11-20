# pyright: reportPrivateUsage=false

import json
from collections.abc import Iterator
from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication

from core.validation.widgets.yasb.wireless_battery import WirelessBatteryConfig
from core.widgets.services.wireless_battery.wireless_battery_api import WirelessDevice, parse_devices
from core.widgets.yasb import wireless_battery
from core.widgets.yasb.wireless_battery import WirelessBatteryWidget

SAMPLE = json.dumps(
    [
        {
            "key": "kysona:373B:1085",
            "name": "CX Wireless mouse",
            "via": "2.4 GHz receiver",
            "kind": "mouse",
            "percent": 85,
            "level": "",
            "detail": "",
            "charging": False,
            "asleep": False,
            "connected": True,
            "millivolts": 4029,
            "graceSec": 1800,
        },
        {
            "key": "hs",
            "name": "Headset",
            "via": "USB",
            "kind": "headset",
            "percent": -1,
            "level": "Low",
            "detail": "",
            "charging": True,
            "asleep": False,
            "connected": True,
        },
        {"key": "kb", "name": "Keyboard", "kind": "keyboard", "percent": 10, "connected": False},
    ]
)


def _dev(**kw: Any) -> WirelessDevice:
    base: dict[str, Any] = {
        "key": "k",
        "name": "Dev",
        "via": "",
        "kind": "mouse",
        "percent": 50,
        "level": "",
        "detail": "",
        "charging": False,
        "asleep": False,
        "connected": True,
        "millivolts": None,
    }
    base.update(kw)
    return WirelessDevice(**base)


def test_parse_devices():
    devices = parse_devices(SAMPLE)
    assert [d.name for d in devices] == ["CX Wireless mouse", "Headset", "Keyboard"]
    assert devices[0].percent == 85 and devices[0].millivolts == 4029
    assert devices[1].percent is None and devices[1].charging and devices[1].level == "Low"
    assert devices[2].connected is False


def test_parse_devices_tolerates_noise_and_rejects_garbage():
    assert parse_devices("warning\n[]") == []
    with pytest.raises(ValueError):
        parse_devices("no json here")


@pytest.fixture
def make_widget(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    class _NoWorker:
        @classmethod
        def get_instance(cls, *_: Any) -> Any:
            raise AssertionError("worker must not start in tests")

    monkeypatch.setattr(WirelessBatteryWidget, "_worker", object())  # pretend a worker already runs
    monkeypatch.setattr(wireless_battery, "WirelessBatteryWorker", _NoWorker)

    created: list[WirelessBatteryWidget] = []

    def _make(**options: Any) -> WirelessBatteryWidget:
        widget = WirelessBatteryWidget(WirelessBatteryConfig(**options))
        created.append(widget)
        return widget

    yield _make
    for w in created:
        if w in WirelessBatteryWidget._instances:
            WirelessBatteryWidget._instances.remove(w)
        w.deleteLater()


def test_default_config_validates():
    cfg = WirelessBatteryConfig()
    assert cfg.executable == "BatteryHub.exe"


def test_select_hides_disconnected_and_filters_kind(make_widget: Any):
    devices = parse_devices(SAMPLE)
    w = make_widget()
    assert [d.key for d in w._select(devices)] == ["hs", "kysona:373B:1085"]
    assert [d.key for d in make_widget(show_disconnected=True)._select(devices)] == ["hs", "kb", "kysona:373B:1085"]
    assert [d.key for d in make_widget(kinds=["mouse"])._select(devices)] == ["kysona:373B:1085"]
    assert [d.key for d in make_widget(devices=["headset"])._select(devices)] == ["hs"]


def test_status_and_icon(make_widget: Any):
    w = make_widget()
    assert w._status_for(_dev(percent=10)) == "critical"
    assert w._status_for(_dev(percent=25)) == "low"
    assert w._status_for(_dev(percent=80)) == "normal"
    assert w._status_for(_dev(percent=None)) == "unknown"
    assert w._status_for(_dev(charging=True, asleep=True, percent=80)) == "charging asleep normal"
    assert w._status_for(_dev(connected=False)) == "disconnected"
    assert w._icon_for(_dev(kind="mouse")) == w.config.icons.mouse
    assert w._icon_for(_dev(kind="other")) == w.config.icons.default
    assert w._icon_for(_dev(charging=True)) == w.config.icons.charging


def test_render_builds_one_frame_per_device(make_widget: Any):
    w = make_widget(hide_when_empty=True)
    w._render(parse_devices(SAMPLE))
    assert len(w._device_frames) == 2
    w._render([])
    assert w._device_frames == []
    assert not w.isVisible()

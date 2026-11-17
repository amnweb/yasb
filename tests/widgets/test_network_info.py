# pyright: reportPrivateUsage=false

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton

from core.validation.widgets.yasb.traffic import TrafficWidgetConfig
from core.widgets.services.traffic import network_info
from core.widgets.services.traffic.network_info import INFO_FIELDS, NetworkInfoService, parse_public_info
from core.widgets.yasb.traffic import TrafficWidget


def public_response() -> dict[str, Any]:
    return {
        "ip": "203.0.113.42",
        "success": True,
        "country": "Example",
        "latitude": 0,
        "longitude": 0,
        "connection": {"isp": "Example ISP", "org": "Example Org"},
        "timezone": {"id": "UTC"},
    }


@pytest.fixture
def service(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NetworkInfoService:
    def address(_interface: str) -> str:
        return "192.0.2.10"

    monkeypatch.setattr(network_info, "local_ip", address)
    return NetworkInfoService("auto", cache_path=tmp_path / "info.json")


def test_public_data_parser_handles_zero_coordinates_and_missing_optional_fields():
    data = parse_public_info(public_response())
    assert data["Location"] == "0, 0"
    assert data["Timezone"] == "UTC"
    assert data["Currency"] == ""
    with pytest.raises(ValueError):
        parse_public_info({"success": False, "message": "Limit exceeded"})


def test_fresh_cache_does_not_start_an_http_lookup(service: NetworkInfoService, monkeypatch: pytest.MonkeyPatch):
    service._data = {"IP address": "203.0.113.42", "IP local": "192.0.2.10"}
    service._timestamp = time.time()

    def no_thread(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Fresh cache must not start an HTTP worker")

    monkeypatch.setattr(network_info.threading, "Thread", no_thread)
    service.refresh()
    assert service.snapshot()["IP address"] == "203.0.113.42"


def test_primary_result_is_published_before_currency_lookup(
    service: NetworkInfoService, monkeypatch: pytest.MonkeyPatch
):
    published: list[dict[str, str]] = []

    def record(data: dict[str, str], _status: str) -> None:
        published.append(dict(data))

    service.changed.connect(record)

    def request(url: str) -> dict[str, Any]:
        if url == "https://ipwho.is/":
            return public_response()
        assert published and not published[0]["Currency"]
        return {"ip": "203.0.113.42", "currency": "USD"}

    monkeypatch.setattr(service, "_request", request)
    service._run()
    assert published[0]["IP local"] == "192.0.2.10"
    assert published[-1]["Currency"] == "USD"
    cached = json.loads(service.cache_path.read_text(encoding="utf-8"))
    assert cached["data"]["Currency"] == "USD"


def test_offline_lookup_keeps_saved_data_and_does_not_fake_public_ip(
    service: NetworkInfoService, monkeypatch: pytest.MonkeyPatch
):
    service._data = {"IP address": "203.0.113.42", "IP local": "192.0.2.10"}

    def offline(_url: str) -> dict[str, Any]:
        raise OSError("Offline")

    monkeypatch.setattr(service, "_request", offline)
    service._run()
    assert service.snapshot()["IP address"] == "203.0.113.42"
    assert "offline" in service.status
    assert not service._busy
    service._data = {}
    service._run()
    assert "IP address" not in service.snapshot()


def test_concurrent_refreshes_are_coalesced(service: NetworkInfoService, monkeypatch: pytest.MonkeyPatch):
    service._busy = True

    def no_thread(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Only one HTTP worker may run")

    monkeypatch.setattr(network_info.threading, "Thread", no_thread)
    service.refresh(force=True)
    assert service._busy


@pytest.mark.parametrize("cached", ["not-json", "[]", '{"timestamp":"bad","data":{}}'])
def test_invalid_cache_does_not_prevent_start(qapp: QApplication, tmp_path: Path, cached: str):
    path = tmp_path / "info.json"
    path.write_text(cached, encoding="utf-8")
    service = NetworkInfoService("auto", cache_path=path)
    assert not service._data


@pytest.fixture
def widget(service: NetworkInfoService, monkeypatch: pytest.MonkeyPatch) -> Iterator[TrafficWidget]:
    service._data = {"IP address": "203.0.113.42", "IP local": "192.0.2.10", "Country": "Example"}
    service._timestamp = time.time()

    def make_service(*_args: object, **_kwargs: object) -> NetworkInfoService:
        return service

    def no_counters(_widget: TrafficWidget) -> None:
        pass

    def setup(widget: TrafficWidget, _interval: int, _callbacks: object) -> None:
        widget._is_internet_connected = True

    import core.widgets.yasb.traffic as traffic_module

    monkeypatch.setattr(traffic_module, "NetworkInfoService", make_service)
    monkeypatch.setattr(TrafficWidget, "_initialize_instance_counters", no_counters)
    monkeypatch.setattr(TrafficWidget, "_setup_callbacks_and_timers", setup)
    instance = TrafficWidget(
        TrafficWidgetConfig.model_validate(
            {
                "menu": {
                    "blur": False,
                    "round_corners": False,
                    "show_network_info": True,
                    "pinnable": True,
                }
            }
        )
    )
    yield instance
    if instance._menu_widget is not None:
        instance._menu_widget.hide()
        instance._menu_widget.deleteLater()
    instance.deleteLater()


def test_info_and_back_buttons_keep_the_same_native_popup(widget: TrafficWidget):
    widget._toggle_menu()
    popup = widget._menu_widget
    assert popup is not None
    buttons = popup.findChildren(QPushButton)
    info = next(button for button in buttons if button.property("class") == "info-button")
    back = next(button for button in buttons if button.property("class") == "back-button")
    info.click()
    assert popup.isVisible()
    assert widget._info_page is not None and widget._info_page.isVisible()
    assert widget._traffic_page is not None and not widget._traffic_page.isVisible()
    assert set(widget._info_labels) == set(INFO_FIELDS)
    assert widget._info_labels["IP address"].text() == "203.0.113.42"
    assert widget._info_labels["IP address"].textFormat() == Qt.TextFormat.PlainText
    back.click()
    assert popup.isVisible()
    assert widget._traffic_page.isVisible()
    assert not widget._info_page.isVisible()


def test_reopening_popup_does_not_lose_info_label_references(widget: TrafficWidget):
    widget._toggle_menu()
    old_popup = widget._menu_widget
    assert old_popup is not None
    old_popup.hide()
    widget._toggle_menu()
    assert widget._menu_widget is not old_popup
    widget._show_network_info(True)
    assert len(widget._info_labels) == len(INFO_FIELDS)


def test_network_info_is_opt_in():
    assert not TrafficWidgetConfig().menu.show_network_info


def test_pin_state_is_shared_by_both_network_pages(widget: TrafficWidget):
    from PyQt6.QtCore import QEvent

    from core.utils.stat_popup import PinnablePopup

    widget._toggle_menu()
    popup = widget._menu_widget
    assert isinstance(popup, PinnablePopup)
    pins = [button for button in popup.findChildren(QPushButton) if button.isCheckable()]
    assert len(pins) == 2
    pins[0].click()
    assert popup.is_pinned and all(button.isChecked() for button in pins)
    widget._show_network_info(True)
    popup.event(QEvent(QEvent.Type.WindowDeactivate))
    assert popup.isVisible()
    pins[1].click()
    assert not popup.is_pinned and not any(button.isChecked() for button in pins)

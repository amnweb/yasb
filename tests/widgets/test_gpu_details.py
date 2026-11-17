# pyright: reportPrivateUsage=false

from collections.abc import Iterator
from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication

from core.utils.stat_popup import PinnablePopup
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.gpu import GpuConfig
from core.widgets.services.gpu.gpu_api import GpuApi, GpuData, GpuWorker
from core.widgets.services.gpu.libre import GpuClocks, LibreGpuClocks, clock_mhz, decode_clocks, match_clocks
from core.widgets.yasb.gpu import GpuWidget


def sample(index: int, name: str, dedicated_gb: int, identity: str, usage: float = 10) -> GpuData:
    return GpuData(
        index,
        name,
        usage,
        dedicated_gb * 1024**3,
        1024**3,
        max(0, dedicated_gb - 1) * 1024**3,
        8 * 1024**3,
        512 * 1024**2,
        0,
        0,
        0,
        adapter_id=identity,
        core_clock=1200,
        memory_clock=2400,
    )


@pytest.fixture
def widget(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[GpuWidget]:
    worker = GpuWorker(2000)

    def no_start(_worker: GpuWorker) -> None:
        pass

    monkeypatch.setattr(GpuWorker, "start", no_start)
    monkeypatch.setattr(GpuWorker, "_instance", worker)
    monkeypatch.setattr(GpuWidget, "_worker", None)
    monkeypatch.setattr(GpuWidget, "_instances", [])
    instance = GpuWidget(
        GpuConfig.model_validate(
            {
                "menu": {
                    "enabled": True,
                    "blur": False,
                    "round_corners": False,
                    "adapter_selector": True,
                    "adapter_order": "dedicated_first",
                    "show_clocks": True,
                    "show_combined_memory": True,
                    "show_memory_bars": True,
                    "show_temperature": False,
                    "show_power": False,
                    "show_fan_speed": False,
                    "show_graph_fill": False,
                "highlight_usage": True,
                }
            }
        )
    )
    yield instance
    popup = PopupWidget.open_popup_for(instance)
    if popup is not None:
        popup.hide()
        popup.deleteLater()
    instance.deleteLater()


def test_dedicated_gpu_is_default_without_changing_system_index(widget: GpuWidget):
    integrated = sample(0, "Integrated", 0, "igpu")
    dedicated = sample(1, "Dedicated", 16, "dgpu")
    widget._receive_adapters([integrated, dedicated])
    assert widget._selected_id == "dgpu"
    assert widget._last_gpu_data == dedicated
    assert widget._last_gpu_data is not None
    assert widget._last_gpu_data.gpu_index == 1
    assert widget._ordered_adapters() == ["dgpu", "igpu"]


def test_each_gpu_keeps_its_own_history(widget: GpuWidget):
    widget._receive_adapters([sample(0, "Integrated", 0, "igpu", 5), sample(1, "Dedicated", 16, "dgpu", 60)])
    widget._receive_adapters([sample(0, "Integrated", 0, "igpu", 7), sample(1, "Dedicated", 16, "dgpu", 80)])
    widget._select_adapter("igpu")
    assert list(widget._history) == [5, 7]
    widget._select_adapter("dgpu")
    assert list(widget._history) == [60, 80]


def test_inline_selector_switches_without_closing_or_resizing_popup(widget: GpuWidget):
    widget._receive_adapters([sample(0, "Integrated", 0, "igpu"), sample(1, "Dedicated", 16, "dgpu")])
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    assert "primary" in str(popup.stat_labels["usage"].property("class"))
    before = popup.size()
    assert widget._selector_buttons["dgpu"].text() == "GPU 0"
    assert widget._selector_buttons["igpu"].text() == "GPU 1"
    widget._selector_buttons["igpu"].click()
    assert popup.isVisible()
    assert widget._selected_id == "igpu"
    assert popup.size() == before
    assert widget._selector_buttons["igpu"].isChecked()
    assert popup.stat_labels["core_clock"].text() == "1200 MHz"


def test_memory_cards_and_bars_use_dedicated_plus_shared_totals(widget: GpuWidget):
    data = sample(0, "Dedicated", 16, "dgpu")._replace(mem_used=4 * 1024**3, mem_shared_used=1024**3)
    widget._receive_adapters([data])
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    assert popup.stat_labels["mem_combined"].text() == "5.0 GB / 24.0 GB"
    assert widget._memory_bars["mem"].value() == 250
    assert widget._memory_bars["mem_shared"].value() == 125
    assert widget._memory_bars["mem_combined"].value() == 208
    assert popup.graph is not None and not popup.graph._fill_enabled
    widget._update_popup(data._replace(core_clock=None, memory_clock=None))
    assert popup.stat_labels["core_clock"].text() == "\u2014"
    assert popup.stat_labels["memory_clock"].text() == "\u2014"


def test_disappearing_adapter_falls_back_without_mixing_histories(widget: GpuWidget):
    widget._receive_adapters([sample(0, "Integrated", 0, "igpu", 3), sample(1, "Dedicated", 16, "dgpu", 99)])
    widget._receive_adapters([sample(0, "Integrated", 0, "igpu", 6)])
    assert widget._selected_id == "igpu"
    assert list(widget._history) == [3, 6]


def test_clock_parser_and_exact_device_matching():
    root: dict[str, Any] = {
        "Children": [
            {
                "HardwareId": "/gpu-amd/5",
                "Text": "AMD Radeon RX 9070 XT",
                "Children": [
                    {"SensorId": "/gpu-amd/5/clock/0", "Text": "GPU Core", "Value": "2,5 GHz"},
                    {"SensorId": "/gpu-amd/5/clock/2", "Text": "GPU Memory", "Value": "2505 MHz"},
                ],
            }
        ]
    }
    clocks = decode_clocks(root)
    assert clocks == [GpuClocks("/gpu-amd/5", "AMD Radeon RX 9070 XT", 2500, 2505)]
    assert match_clocks(clocks, "AMD Radeon RX 9070 XT") == clocks[0]
    assert match_clocks(clocks, "AMD Radeon(TM) Graphics") is None
    assert match_clocks(clocks * 2, "AMD Radeon RX 9070 XT") is None
    assert match_clocks(clocks, "Different Windows Name", "/gpu-amd/5") == clocks[0]
    assert clock_mhz({"Value": "N/A"}) is None


def test_offline_libre_does_not_report_zero_clocks(monkeypatch: pytest.MonkeyPatch):
    client = LibreGpuClocks("127.0.0.1", 8085)

    def offline(*_args: object, **_kwargs: object) -> None:
        raise OSError("Offline")

    monkeypatch.setattr(client.opener, "open", offline)
    assert client.read() == []
    assert GpuWidget._clock_text(None) == "\u2014"


def test_all_adapter_enumeration_keeps_idle_dxgi_device():
    api = object.__new__(GpuApi)
    api._collect_all = True
    api._dxgi_gpus = [
        {"name": "Integrated", "vram_total": 0, "shared_total": 1024, "luid_str": "idle", "vendor_id": 0x1002},
        {"name": "Dedicated", "vram_total": 1024, "shared_total": 1024, "luid_str": "busy", "vendor_id": 0x1002},
    ]
    info = api._build_luid_info(["busy"])
    assert set(info) == {"idle", "busy"}
    api._collect_all = False
    assert set(api._build_luid_info(["busy"])) == {"busy"}


def test_gpu_defaults_preserve_original_behavior():
    config = GpuConfig()
    assert not config.menu.adapter_selector
    assert not config.menu.show_clocks
    assert not config.menu.show_combined_memory
    assert config.menu.show_graph_fill
    assert not config.menu.highlight_usage

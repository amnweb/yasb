# pyright: reportPrivateUsage=false

import ctypes
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QGridLayout

from core.utils.stat_popup import GraphWidget, PinnablePopup
from core.utils.utilities import PopupWidget
from core.utils.win32.structs import ENUM_PAGE_FILE_INFORMATION, PERFORMANCE_INFORMATION
from core.utils.win32.typecheck import CArgObject
from core.validation.widgets.yasb.memory import MemoryConfig, MemoryGraphColorsConfig
from core.widgets.services.memory import hardware, memory_api
from core.widgets.services.memory.hardware import HardwareCache, MemoryHardware, MemoryModule
from core.widgets.services.memory.memory_api import MemoryAPI, MemoryData, MemoryWorker, SwapMemory, VirtualMemory
from core.widgets.yasb.memory import MemoryWidget


def test_hardware_query_keeps_configured_and_rated_speed_distinct(monkeypatch: pytest.MonkeyPatch):
    class Properties:
        def __init__(self, capacity: int, configured: int, rated: int):
            self.values = {"Capacity": capacity, "ConfiguredClockSpeed": configured, "Speed": rated}

        def Item(self, name: str) -> SimpleNamespace:
            return SimpleNamespace(Value=self.values[name])

    rows = [SimpleNamespace(Properties_=Properties(16 * 1024**3, 5600, 4800)) for _ in range(2)]
    rows.append(SimpleNamespace(Properties_=Properties(0, 0, 0)))

    def query(*_args: object) -> list[SimpleNamespace]:
        return rows

    def connect(*_args: object) -> SimpleNamespace:
        return SimpleNamespace(ExecQuery=query)

    def create(_name: str) -> SimpleNamespace:
        return SimpleNamespace(ConnectServer=connect)

    monkeypatch.setattr(hardware, "create_dispatch", create)
    result = hardware.read_hardware()
    assert len(result.modules) == 2
    assert result.installed_bytes == 32 * 1024**3
    assert result.modules[0].configured_speed == 5600
    assert result.modules[0].rated_speed == 4800
    assert MemoryWidget._speed_text(result) == "5600 MT/s"
    assert MemoryWidget._modules_text(result) == "2 \u00d7 16.0 GB"


def test_unknown_configured_speed_does_not_display_rated_speed():
    result = MemoryHardware((MemoryModule(16 * 1024**3, None, 4800),))
    assert MemoryWidget._speed_text(result) == "\u2014"


def test_reserved_memory_uses_installed_minus_windows_usable():
    physical = MemoryHardware((MemoryModule(16 * 1024**3, 5600, 4800),))
    usable = 15 * 1024**3
    data = MemoryData(
        VirtualMemory(usable, usable // 2, 50, usable // 2, usable // 2), SwapMemory(0, 0, 0, 0), 0, physical
    )
    assert data.reserved_bytes == 1024**3
    assert data._replace(hardware=MemoryHardware()).reserved_bytes is None
    assert data._replace(virtual=data.virtual._replace(total=0)).reserved_bytes is None
    assert data._replace(virtual=data.virtual._replace(total=17 * 1024**3)).reserved_bytes == 0


def test_failed_hardware_query_preserves_cache_and_retries_later(monkeypatch: pytest.MonkeyPatch):
    cache = HardwareCache()
    previous = MemoryHardware((MemoryModule(8 * 1024**3, 3200, 3200),))
    cache._value = previous
    uninitialized: list[bool] = []
    monkeypatch.setattr(hardware, "CoInitialize", lambda: 0)
    monkeypatch.setattr(hardware, "CoUninitialize", lambda: uninitialized.append(True))

    def fail():
        raise OSError("WMI unavailable")

    monkeypatch.setattr(hardware, "read_hardware", fail)
    cache._refresh()
    assert cache.snapshot() == previous
    assert uninitialized == [True]
    assert cache._loading is False


def test_sampler_does_not_wait_for_pending_hardware_query(monkeypatch: pytest.MonkeyPatch):
    cache = HardwareCache()
    cache._loading = True
    monkeypatch.setattr(MemoryAPI, "_hardware_cache", cache)
    monkeypatch.setattr(MemoryAPI, "virtual_memory", lambda: VirtualMemory(100, 50, 50, 50, 50))
    monkeypatch.setattr(MemoryAPI, "swap_memory", lambda: SwapMemory(0, 0, 0, 0))
    monkeypatch.setattr(MemoryAPI, "_get_cached_bytes", lambda: 0)
    assert MemoryAPI.get_data(include_hardware=True).hardware == MemoryHardware()


def test_pagefile_sizes_are_summed_from_pages(monkeypatch: pytest.MonkeyPatch):
    def enumerate_files(callback: Callable[..., Any], context: Any) -> bool:
        for size, used in ((1000, 100), (500, 50)):
            info = ENUM_PAGE_FILE_INFORMATION(ctypes.sizeof(ENUM_PAGE_FILE_INFORMATION), 0, size, used, used)
            assert callback(context, ctypes.pointer(info), "pagefile.sys") == 1
        return True

    monkeypatch.setattr(memory_api.psapi, "EnumPageFilesW", enumerate_files)
    assert MemoryAPI._pagefile_totals(4096) == (1500 * 4096, 150 * 4096)


def test_pagefile_failure_is_distinct_from_no_pagefile(monkeypatch: pytest.MonkeyPatch):
    def fail(*_args: object) -> bool:
        return False

    def empty(*_args: object) -> bool:
        return True

    monkeypatch.setattr(memory_api.psapi, "EnumPageFilesW", fail)
    assert MemoryAPI._pagefile_totals(4096) is None
    monkeypatch.setattr(memory_api.psapi, "EnumPageFilesW", empty)
    assert MemoryAPI._pagefile_totals(4096) == (0, 0)


def test_swap_uses_real_pagefiles_instead_of_commit_limit(monkeypatch: pytest.MonkeyPatch):
    def performance(pointer: CArgObject, _size: int) -> bool:
        info = ctypes.cast(pointer, ctypes.POINTER(PERFORMANCE_INFORMATION)).contents
        info.PageSize = 4096
        info.CommitLimit = 999999
        info.PhysicalTotal = 1
        return True

    monkeypatch.setattr(memory_api.psapi, "GetPerformanceInfo", performance)

    def totals(_size: int) -> tuple[int, int]:
        return 10000, 2500

    monkeypatch.setattr(MemoryAPI, "_pagefile_totals", totals)
    assert MemoryAPI.swap_memory() == SwapMemory(10000, 2500, 7500, 25)


@pytest.mark.parametrize(
    "values",
    [
        {"warning_threshold": 90, "critical_threshold": 70},
        {"warning_threshold": 70, "critical_threshold": 70},
        {"warning_threshold": -1},
        {"critical_threshold": 101},
        {"normal": "not-a-color"},
    ],
)
def test_invalid_graph_configuration_is_rejected(values: dict[str, object]):
    with pytest.raises(ValidationError):
        MemoryGraphColorsConfig.model_validate(values)


def test_new_options_are_opt_in():
    menu = MemoryConfig().menu
    assert not menu.show_hardware_details
    assert not menu.show_swap_total
    assert not menu.highlight_usage
    assert not menu.graph_colors.enabled


def test_graph_keeps_historical_segments_in_each_color(qapp: QApplication):
    graph = GraphWidget()
    graph.resize(240, 120)
    graph.set_data([30, 80, 96, 80, 30])
    graph.set_color_bands([(0, 70, "#00ff00"), (70, 90, "#ffff00"), (90, 100, "#ff0000")])
    image = QImage(graph.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    graph.render(painter)
    painter.end()
    colors = {image.pixelColor(x, y).name() for y in range(image.height()) for x in range(image.width())}
    assert {"#00ff00", "#ffff00", "#ff0000"} <= colors
    graph.close()


def test_graph_without_bands_preserves_css_color(qapp: QApplication):
    graph = GraphWidget()
    graph.setStyleSheet("color: #4cc2ff;")
    graph.resize(100, 60)
    graph.set_data([30, 30])
    image = QImage(graph.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    graph.render(painter)
    painter.end()
    assert graph._color_bands == ()
    assert any(image.pixelColor(x, y).name() == "#4cc2ff" for y in range(image.height()) for x in range(image.width()))
    graph.close()


def test_colored_fill_uses_band_colors_and_smooth_boundary_stops(qapp: QApplication):
    graph = GraphWidget()
    graph.resize(240, 120)
    graph.set_color_bands([(0, 70, "#00ff00"), (70, 90, "#ffff00"), (90, 100, "#ff0000")])
    gradient = graph._fill_gradient(QColor("#4cc2ff"))
    stops = gradient.stops()
    assert {color.name() for _, color in stops} == {"#00ff00", "#ffff00", "#ff0000"}
    assert len(stops) == 6
    assert 0 < stops[1][0] < stops[2][0] < stops[3][0] < stops[4][0] < 1
    assert stops[0][1].alpha() == graph.FILL_TOP_OPACITY
    assert stops[-1][1].alpha() == graph.FILL_BOTTOM_OPACITY
    # Sample the fill between the yellow and green stops, away from the stroke.
    graph.set_data([99, 99])
    image = QImage(graph.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    graph.render(painter)
    painter.end()
    boundary_y = round((stops[3][0] + stops[4][0]) / 2 * graph.height())
    mixed = image.pixelColor(graph.width() // 2, boundary_y)
    assert 0 < mixed.red() < mixed.green()
    assert mixed.blue() == 0
    graph.close()


def test_graph_can_render_only_the_line_without_any_fill(qapp: QApplication):
    graph = GraphWidget()
    graph.setStyleSheet("background: transparent; color: #4cc2ff;")
    graph.resize(120, 80)
    graph.set_data([50, 50])
    graph.set_fill_enabled(False)
    image = QImage(graph.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    graph.render(painter)
    painter.end()
    assert image.pixelColor(60, 65).name() == "#000000"
    assert any(image.pixelColor(60, y).name() == "#4cc2ff" for y in range(35, 45))
    graph.close()


def test_original_popup_grid_displays_and_refreshes_extra_data(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    worker = MemoryWorker(1000)

    def no_start(_worker: MemoryWorker) -> None:
        pass

    monkeypatch.setattr(MemoryWorker, "start", no_start)
    monkeypatch.setattr(MemoryWorker, "_instance", worker)
    monkeypatch.setattr(MemoryWidget, "_worker", None)
    monkeypatch.setattr(MemoryWidget, "_instances", [])
    widget = MemoryWidget(
        MemoryConfig.model_validate(
            {
                "menu": {
                    "enabled": True,
                    "round_corners": False,
                    "blur": False,
                    "show_hardware_details": True,
                    "show_swap_total": True,
                    "highlight_usage": True,
                    "show_usage_bar": True,
                    "graph_colors": {"enabled": True},
                }
            }
        )
    )
    data = MemoryData(
        VirtualMemory(15 * 1024**3, 7 * 1024**3, 53, 8 * 1024**3, 7 * 1024**3),
        SwapMemory(4 * 1024**3, 1024**3, 3 * 1024**3, 25),
        2 * 1024**3,
        MemoryHardware((MemoryModule(16 * 1024**3, 5600, 4800),)),
    )
    widget._last_data = data
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    try:
        assert len(popup.stat_labels) == 10
        assert popup.stat_labels["installed"].text() == "16.0 GB"
        assert popup.stat_labels["reserved"].text() == "1.0 GB"
        assert popup.stat_labels["speed"].text() == "5600 MT/s"
        assert popup.stat_labels["modules"].text() == "1 \u00d7 16.0 GB"
        assert popup.stat_labels["swap"].text() == "1.0 GB / 4.0 GB"
        used_card = popup.stat_labels["used"].parentWidget()
        util_card = popup.stat_labels["util"].parentWidget()
        assert used_card is not None and util_card is not None
        stats_frame = used_card.parentWidget()
        assert stats_frame is not None
        grid = stats_frame.layout()
        assert isinstance(grid, QGridLayout)
        assert grid.getItemPosition(grid.indexOf(util_card))[:2] == (0, 0)
        assert grid.getItemPosition(grid.indexOf(used_card))[:2] == (0, 1)
        assert widget._usage_bar is not None and widget._usage_bar.value() == 530
        assert "primary" in str(used_card.property("class"))
        assert "primary" in str(popup.stat_labels["util"].property("class"))
        assert popup.graph is not None and len(popup.graph._color_bands) == 3
        widget._update_popup(data._replace(hardware=MemoryHardware()))
        assert popup.stat_labels["speed"].text() == "\u2014"
        assert popup.stat_labels["reserved"].text() == "\u2014"
        assert worker._include_hardware
    finally:
        popup.hide()
        popup.deleteLater()
        widget.deleteLater()


def test_original_popup_defaults_keep_six_stats(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    worker = MemoryWorker(1000)

    def no_start(_worker: MemoryWorker) -> None:
        pass

    monkeypatch.setattr(MemoryWorker, "start", no_start)
    monkeypatch.setattr(MemoryWorker, "_instance", worker)
    monkeypatch.setattr(MemoryWidget, "_worker", None)
    monkeypatch.setattr(MemoryWidget, "_instances", [])
    widget = MemoryWidget(
        MemoryConfig.model_validate({"menu": {"enabled": True, "round_corners": False, "blur": False}})
    )
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    try:
        assert len(popup.stat_labels) == 6
        assert popup.graph is not None and popup.graph._color_bands == ()
        assert "primary" not in str(popup.stat_labels["util"].property("class"))
        assert not worker._include_hardware
    finally:
        popup.hide()
        popup.deleteLater()
        widget.deleteLater()

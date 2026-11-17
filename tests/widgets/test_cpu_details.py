# pyright: reportPrivateUsage=false

import pytest
from PyQt6.QtWidgets import QApplication

from core.utils.stat_popup import PinnablePopup
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.cpu import CpuConfig
from core.widgets.services.cpu.cpu_api import CpuWorker
from core.widgets.yasb.cpu import CpuWidget


def test_native_cpu_can_highlight_usage_without_highlighting_other_stats(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
):
    worker = CpuWorker(1000)

    def no_start(_worker: CpuWorker) -> None:
        pass

    monkeypatch.setattr(CpuWorker, "start", no_start)
    monkeypatch.setattr(CpuWorker, "_instance", worker)
    monkeypatch.setattr(CpuWidget, "_worker", None)
    monkeypatch.setattr(CpuWidget, "_instances", [])
    widget = CpuWidget(
        CpuConfig.model_validate(
            {
                "menu": {
                    "enabled": True,
                    "blur": False,
                    "round_corners": False,
                    "highlight_usage": True,
                }
            }
        )
    )
    widget._show_popup()
    popup = PopupWidget.open_popup_for(widget)
    assert isinstance(popup, PinnablePopup)
    try:
        assert "primary" in str(popup.stat_labels["usage"].property("class"))
        assert "primary" not in str(popup.stat_labels["freq"].property("class"))
        assert len(popup.stat_labels) == 4
        assert not CpuConfig().menu.highlight_usage
    finally:
        popup.hide()
        popup.deleteLater()
        widget.deleteLater()

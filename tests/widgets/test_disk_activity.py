# pyright: reportPrivateUsage=false

from ctypes import wintypes
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar

from core.utils.stat_popup import PinnablePopup
from core.validation.widgets.yasb.disk import DiskConfig
from core.widgets.services.disk.activity import DiskActivity, DiskActivityReader, DiskActivityWorker
from core.widgets.yasb.disk import ClickableDiskWidget, DiskWidget


def test_activity_reader_converts_idle_to_busy_and_keeps_missing_values(monkeypatch: pytest.MonkeyPatch):
    import core.widgets.services.disk.activity as activity

    reader = DiskActivityReader.__new__(DiskActivityReader)
    reader.query = None
    reader.counters = {"C": (None, None, None)}
    assert reader.collect()["C"] == DiskActivity()
    monkeypatch.setattr(activity.pdh, "PdhCollectQueryData", Mock(return_value=0))
    reader.query = wintypes.HANDLE(1)
    monkeypatch.setattr(reader, "_value", Mock(side_effect=[23.5, 2048.0, -1.0]))
    assert reader.collect()["C"] == DiskActivity(76.5, 2048.0, 0.0)
    monkeypatch.setattr(reader, "_value", Mock(side_effect=[-5.0, None, 0.0]))
    assert reader.collect()["C"] == DiskActivity(100.0, None, 0.0)


@pytest.mark.parametrize(
    "value, text", [(None, "—"), (0, "0 B/s"), (1024, "1.0 KB/s"), (1048576, "1.0 MB/s"), (1073741824, "1.0 GB/s")]
)
def test_transfer_units(value: float | None, text: str):
    assert DiskWidget._rate_text(value) == text


def test_disk_popup_shows_live_activity_capacity_and_pin(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    worker = Mock()
    monkeypatch.setattr(DiskActivityWorker, "get_instance", Mock(return_value=worker))
    monkeypatch.setattr(DiskWidget, "_get_volume_label", Mock(return_value="Data"))
    space = {"total": {"gb": "100.0GB"}, "free": {"gb": "60.0GB"}, "used": {"gb": "40.0GB", "percent": "40.0%"}}
    monkeypatch.setattr(DiskWidget, "_get_space", Mock(return_value=space))
    config = DiskConfig.model_validate(
        {
            "group_label": {
                "title": "Disk",
                "pinnable": True,
                "show_activity": True,
                "show_used_space": True,
                "blur": False,
                "round_corners": False,
            }
        }
    )
    widget = DiskWidget(config)
    try:
        widget.show_group_label()
        popup = widget.dialog
        assert isinstance(popup, PinnablePopup)
        popup.setStyleSheet("""
            .disk-group { min-width: 400px; }
            .disk-group-row { margin: 6px 16px; padding: 8px; border: 1px solid #292929; }
            .activity-value { font-size: 18px; }
            .activity-value.usage { font-size: 26px; }
        """)
        popup.adjustSize()
        qapp.processEvents()
        widget._update_activity({"C": DiskActivity(100, 1023 * 1048576, 1023 * 1048576)})
        qapp.processEvents()
        cards = popup.findChildren(ClickableDiskWidget)
        assert len(cards) == 1
        for card in cards:
            # The painted card is inset by its CSS margin; every child must stay inside it.
            bounds = card.rect().adjusted(16, 6, -16, -6)
            for child in [*card.findChildren(QLabel), *card.findChildren(QProgressBar)]:
                rect = child.rect().translated(child.mapTo(card, child.rect().topLeft()))
                assert bounds.contains(rect), (child.property("class"), bounds, rect)
        assert "40.0GB / 100.0GB" in [label.text() for label in popup.findChildren(QLabel)]
        widget._update_activity({"C": DiskActivity(32.5, 1048576, 2048)})
        assert [label.text() for label in widget._activity_labels["C"]] == ["32%", "1.0 MB/s", "2.0 KB/s"]
        popup._pin_buttons[0][0].click()
        popup.event(QEvent(QEvent.Type.WindowDeactivate))
        assert popup.is_pinned and popup.isVisible()
        popup._pin_buttons[0][0].click()
        widget._update_activity({})
        assert all(label.text() == "—" for label in widget._activity_labels["C"])
    finally:
        if hasattr(widget, "dialog"):
            widget.dialog.hide()
            widget.dialog.deleteLater()
        widget.deleteLater()

# pyright: reportPrivateUsage=false

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from core.app.windows import alert_dialog
from tests.support.qt import wait


def ignore(_: object) -> None:
    pass


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alert_dialog, "user32", SimpleNamespace(MessageBeep=ignore))
    monkeypatch.setattr(alert_dialog, "enable_mica", ignore)


def test_an_alert_raised_during_work_shows_once_the_work_is_done(qapp: QApplication):
    alert_dialog.show_alert("Failed to load the bar file", "Showing the built-in bar")
    # Like a bar that keeps loading after it reported the error
    assert not alert_dialog._alerts
    wait(10)
    [dialog] = alert_dialog._alerts
    assert dialog.isVisible() and dialog.property("heading") == "Failed to load the bar file"
    alert_dialog.close_alerts()
    assert not alert_dialog._alerts

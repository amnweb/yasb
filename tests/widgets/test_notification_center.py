# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl, pyqtBoundSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.utils.icons.service import IconService
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.notifications import center as center_module
from core.widgets.services.notifications.center import NotificationCenter
from core.widgets.services.notifications.windows_notification import NotificationItem
from settings import QML_IMPORT_PATH
from tests.support.qt import wait

SENT = datetime(2026, 10, 31, 9, 30, tzinfo=UTC)


class Events:
    """Stands in for EventService: records what the widget sends and lets a test send to it."""

    def __init__(self) -> None:
        self.signals: dict[str, list[pyqtBoundSignal]] = {}
        self.sent: list[tuple[str, tuple[Any, ...]]] = []

    def register_event(self, event: str, signal: pyqtBoundSignal) -> None:
        self.signals.setdefault(event, []).append(signal)

    def unregister_event(self, event: str, signal: pyqtBoundSignal) -> None:
        self.signals[event].remove(signal)

    def emit_event(self, event: str, *args: Any) -> None:
        self.sent.append((event, args))
        for signal in self.signals.get(event, []):
            signal.emit(*args)


class Dnd:
    status = "disabled"
    written: list[str] = []

    @classmethod
    def initialize_wnf_listener(cls) -> None:
        pass

    @classmethod
    def get_status(cls) -> str:
        return cls.status

    @classmethod
    def set_status(cls, mode: str) -> None:
        cls.written.append(mode)


@pytest.fixture
def events(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Events:
    events = Events()
    Dnd.status = "disabled"
    Dnd.written = []
    monkeypatch.setattr(center_module, "EventService", lambda: events)
    monkeypatch.setattr(center_module, "DndService", Dnd)
    monkeypatch.setattr(center_module, "_listener", SimpleNamespace(total_notifications=3))
    return events


def item(notification_id: int, aumid: str = "Contoso.Mail", **fields: Any) -> NotificationItem:
    return NotificationItem(
        id=notification_id,
        aumid=aumid,
        app_name=fields.pop("app_name", "Mail"),
        title=fields.pop("title", f"Message {notification_id}"),
        body=fields.pop("body", "Hello"),
        created_at=SENT,
        **fields,
    )


def test_it_starts_with_the_listeners_count_and_asks_for_the_list(events: Events):
    center = NotificationCenter()
    assert center.property("count") == 3
    assert events.sent == [("WindowsNotificationRefresh", ("",))]
    events.emit_event("WindowsNotificationUpdate", 5)
    assert center.property("count") == 5


def test_notifications_reach_qml_as_plain_entries(events: Events):
    center = NotificationCenter()
    events.emit_event(
        "WindowsNotificationsChanged",
        [item(4, logo=r"C:\Art\logo.png", logo_circle=True, attribution="via Web"), item(9, aumid="", app_name="Tool")],
    )
    first, second = center.property("notifications")
    assert (first["id"], first["appId"], first["title"], first["attribution"]) == (
        4,
        "Contoso.Mail",
        "Message 4",
        "via Web",
    )
    assert first["time"] == SENT.timestamp() * 1000
    assert first["logo"] == QUrl.fromLocalFile(r"C:\Art\logo.png").toString() and first["logoCircle"]
    assert first["icon"].startswith("image://icon/app/") and first["hero"] == ""
    # Windows can't always name the sender, and then there's no icon to ask for
    assert (second["appId"], second["icon"]) == ("", "")
    assert center.property("allowed")


def test_turned_off_access_is_told_apart_from_an_empty_list(events: Events):
    center = NotificationCenter()
    events.emit_event("WindowsNotificationsChanged", None)
    assert center.property("notifications") == [] and not center.property("allowed")


def test_the_actions_reach_the_listener(events: Events):
    center = NotificationCenter()
    mail = item(4)
    events.emit_event("WindowsNotificationsChanged", [mail])
    events.sent.clear()
    center.clearAll()
    center.clearApp("Contoso.Mail")
    center.dismiss(4)
    center.activate(4)
    center.activate(77)
    assert events.sent == [
        ("WindowsNotificationClear", ("",)),
        ("WindowsNotificationClearApp", ("Contoso.Mail",)),
        ("WindowsNotificationRemove", (4,)),
        ("WindowsNotificationActivate", (mail,)),
    ]


def test_do_not_disturb_is_read_after_the_bar_is_up_and_follows_windows(events: Events):
    Dnd.status = "priority"
    center = NotificationCenter()
    assert not center.property("doNotDisturbAvailable")
    wait(10)
    assert center.property("doNotDisturbAvailable") and center.property("doNotDisturb")
    events.emit_event("dnd_status_changed", "disabled")
    assert not center.property("doNotDisturb")
    center.setDoNotDisturb(True)
    assert Dnd.written == ["priority"] and center.property("doNotDisturb")


def test_app_icons_ask_again_once_the_icon_service_loaded_them(events: Events):
    center = NotificationCenter()
    events.emit_event("WindowsNotificationsChanged", [item(4)])
    before = center.property("notifications")[0]["icon"]
    IconService.instance().icons_changed.emit()
    after = center.property("notifications")[0]["icon"]
    assert after != before


def test_a_deleted_widget_stops_listening(events: Events):
    center = NotificationCenter()
    assert all(len(signals) == 1 for signals in events.signals.values())
    sip.delete(center)
    assert all(signals == [] for signals in events.signals.values())


def test_the_widget_shows_waiting_notifications_and_groups_by_app(events: Events):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    path = BUILTIN_WIDGETS_DIR / "Notifications" / "Notifications.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    widget = component.createWithInitialProperties({"hideEmpty": True})
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    # In a window like on a bar, where Qt keeps the items' visibility up to date
    window = QQuickWindow()
    widget.setParentItem(window.contentItem())
    # Hidden with nothing to show, and taking no space so the bar leaves no gap
    assert not widget.property("shown") and widget.property("implicitWidth") == 0
    widget.setProperty("hideEmpty", False)
    events.emit_event("WindowsNotificationsChanged", [item(4), item(5, aumid="Contoso.Chat", app_name="Chat"), item(6)])
    wait(10)
    assert widget.findChild(QQuickItem, "dot").property("visible")
    groups = widget.property("groups")
    groups = groups.toVariant() if hasattr(groups, "toVariant") else groups
    assert [(group["appName"], len(group["items"])) for group in groups] == [("Mail", 2), ("Chat", 1)]
    # Windows can still count toasts the list can't read, which the popup has nothing to show for
    events.emit_event("WindowsNotificationUpdate", 2)
    events.emit_event("WindowsNotificationsChanged", [])
    wait(10)
    assert not widget.findChild(QQuickItem, "dot").property("visible")
    widget.setProperty("hideEmpty", True)
    assert not widget.property("shown") and widget.property("implicitWidth") == 0
    sip.delete(widget)
    sip.delete(window)

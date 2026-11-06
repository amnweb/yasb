import logging
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, Qt, QUrl
from PyQt6.QtGui import QGuiApplication, QKeyEvent
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.bar.backdrop import Backdrop
from core.qml_types import register_qml_types
from core.services.power_menu import session as session_module
from core.services.power_menu.session import PowerSession
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


class FakeOperations:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return lambda: self.calls.append(name)


@pytest.fixture
def operations(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeOperations:
    operations = FakeOperations()
    monkeypatch.setattr(session_module, "PowerOperations", lambda: operations)
    monkeypatch.setattr(session_module, "get_windows_username", lambda: "Ada Lovelace")
    monkeypatch.setattr(session_module, "get_user_email", lambda: "ada@example.com")
    monkeypatch.setattr(session_module, "get_account_type", lambda: "Administrator")
    monkeypatch.setattr(session_module, "get_user_avatar_path", lambda: None)
    monkeypatch.setattr(session_module, "GetTickCount64", lambda: 93_784_000)
    return operations


def test_the_session_shows_the_user_and_runs_commands(operations: FakeOperations, caplog: pytest.LogCaptureFixture):
    session = PowerSession()
    assert session.property("userName") == "Ada Lovelace"
    assert session.property("email") == "ada@example.com"
    assert session.property("accountType") == "Administrator"
    assert session.property("avatar") == QUrl()
    assert session.property("uptime") == 0
    session.refresh()
    assert session.property("uptime") == 93_784

    for action in ("lock", "sleep", "force_shutdown"):
        session.run(action)
    with caplog.at_level(logging.WARNING):
        session.run("explode")
    assert operations.calls == ["lock", "sleep", "force_shutdown"]
    assert "unknown action 'explode'" in caplog.text


def load_widget() -> tuple[QQuickItem, QQuickWindow, QQmlEngine, list[str]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "PowerMenu" / "PowerMenu.qml")))
    widget = component.createWithInitialProperties({"animationDuration": 10})
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    widget.setParentItem(host.contentItem())
    return widget, host, engine, warnings


def opened(widget: QQuickItem) -> bool:
    """Whether the widget holds an open menu window. QObject.property() gives a stale pointer for it, QML's reader doesn't."""
    return QQmlProperty.read(widget, "opened") is not None


def open_menu(widget: QQuickItem) -> QQuickWindow:
    before = set(QGuiApplication.topLevelWindows())
    widget.metaObject().invokeMethod(widget, "open")  # type: ignore[union-attr]
    [window] = [window for window in QGuiApplication.topLevelWindows() if window not in before and window.isVisible()]
    assert isinstance(window, QQuickWindow)
    wait(50)
    return window


def text_of(window: QQuickWindow) -> list[str]:
    """The words on the menu, without the icon glyphs."""

    def walk(item: QQuickItem) -> list[str]:
        texts = [item.property("text")] if item.metaObject().className() == "QQuickText" else []  # type: ignore[union-attr]
        return texts + [text for child in item.childItems() for text in walk(child)]

    return [text for text in walk(window.contentItem()) if text and not "" <= text[0] <= ""]  # type: ignore[arg-type]


def test_the_menu_shows_the_user_and_buttons_and_runs_the_one_clicked(operations: FakeOperations):
    widget, host, _engine, warnings = load_widget()
    assert (widget.property("implicitWidth"), widget.property("implicitHeight")) == (16, 16)
    window = open_menu(widget)
    # Blurred like the bar's popups, which the bar's own backdrop setting turns on or off
    [backdrop] = window.findChildren(Backdrop)
    assert backdrop.property("bar") is host
    assert backdrop.property("item").width() == window.width()
    assert opened(widget)
    texts = text_of(window)
    assert ["Ada Lovelace", "ada@example.com", "Administrator"] == texts[:3]
    assert texts[3:8] == ["Lock", "Sign out", "Sleep", "Restart", "Shut down"]
    assert texts[-1] == "Up 1 d 2 h"

    button = find_item(window.contentItem(), "power-sleep")  # type: ignore[arg-type]
    assert button is not None
    button.metaObject().invokeMethod(button, "click")  # type: ignore[union-attr]
    wait(100)
    assert operations.calls == ["sleep"]
    assert sip.isdeleted(window) or not window.isVisible()
    assert not opened(widget)
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_escape_closes_the_menu_without_running_anything(operations: FakeOperations):
    widget, host, engine, _ = load_widget()
    window = open_menu(widget)
    # The open menu is held, so the garbage collector leaves it alone
    engine.collectGarbage()
    wait(10)
    assert not sip.isdeleted(window) and window.isVisible()
    first = find_item(window.contentItem(), "power-lock")  # type: ignore[arg-type]
    assert first is not None and first.hasActiveFocus()
    QGuiApplication.sendEvent(
        window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    )
    wait(100)
    assert sip.isdeleted(window) or not window.isVisible()
    assert operations.calls == []
    sip.delete(widget)
    sip.delete(host)


def test_a_custom_button_list_replaces_the_default(operations: FakeOperations):
    widget, host, _engine, warnings = load_widget()
    widget.setProperty("buttons", [{"action": "hibernate", "label": "Hibernate"}])
    window = open_menu(widget)
    assert find_item(window.contentItem(), "power-lock") is None  # type: ignore[arg-type]
    assert find_item(window.contentItem(), "power-hibernate") is not None  # type: ignore[arg-type]
    assert not warnings
    window.close()
    wait(10)
    sip.delete(widget)
    sip.delete(host)

import copy
from typing import Any

import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.bar.manager import QML_IMPORT_PATH
from core.events.service import EventService
from core.events.win32 import WinEvent
from core.qml_types import register_qml_types
from core.utils.win32 import event_listener
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.active_window import tracker as tracker_module
from core.widgets.services.active_window.tracker import ActiveWindowTracker
from tests.support.qt import find_item, wait

SCREEN = "\\\\.\\DISPLAY1"


def _window(hwnd: int, title: str, process: str = "notes.exe", screen: str = SCREEN) -> dict[str, Any]:
    return {
        "hwnd": hwnd,
        "title": title,
        "class_name": "AppWindow",
        "process": {"name": process, "pid": 1000 + hwnd, "path": ""},
        "monitor_hwnd": 1,
        "monitor_info": {"device": screen},
        "rect": {},
    }


class Desktop:
    def __init__(self) -> None:
        self.windows: dict[int, dict[str, Any]] = {}
        self.foreground = 0

    def focus(self, window: dict[str, Any]) -> None:
        self.windows[window["hwnd"]] = window
        self.foreground = window["hwnd"]
        EventService().emit_event(WinEvent.EventSystemForeground, window["hwnd"], WinEvent.EventSystemForeground)


@pytest.fixture
def desktop(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Desktop:
    desktop = Desktop()

    def hwnd_info(hwnd: int) -> dict[str, Any] | None:
        return copy.deepcopy(desktop.windows.get(hwnd))

    def app_name(pid: int) -> str:
        return f"App {pid}"

    monkeypatch.setattr(event_listener, "ensure_system_event_listener", lambda: None)
    monkeypatch.setattr(tracker_module, "GetForegroundWindow", lambda: desktop.foreground)
    monkeypatch.setattr(tracker_module, "get_hwnd_info", hwnd_info)
    monkeypatch.setattr(tracker_module, "get_app_name_from_pid", app_name)
    return desktop


def test_the_tracker_follows_the_foreground_window(desktop: Desktop):
    tracker = ActiveWindowTracker()
    desktop.focus(_window(1, "Notes"))
    assert tracker.property("text") == "Notes"
    assert tracker.property("hasWindow")
    assert tracker.property("window")["app_name"] == "App 1001"


def test_an_ignored_window_keeps_the_last_one(desktop: Desktop):
    tracker = ActiveWindowTracker()
    tracker.setProperty("ignoreProcesses", ["skip.exe"])
    desktop.focus(_window(1, "Notes"))
    desktop.focus(_window(2, "Skipped", process="skip.exe"))
    assert tracker.property("text") == "Notes"


def test_rewrite_max_length_and_the_alternate_label(desktop: Desktop):
    tracker = ActiveWindowTracker()
    tracker.setProperty("rewrite", [{"pattern": "Notes", "replacement": "notes", "case": "upper"}])
    tracker.setProperty("maxLength", 3)
    tracker.setProperty("ellipsis", "…")
    wait(10)
    desktop.focus(_window(1, "Notes"))
    assert tracker.property("text") == "NOT…"
    tracker.toggleLabel()
    assert tracker.property("text") == "[class_name='AppWindow' exe='notes.exe' hwnd=1]"


def test_only_windows_on_the_bars_monitor_are_shown(desktop: Desktop, monkeypatch: pytest.MonkeyPatch):
    def screen_monitor(screen_name: str) -> int:
        return 1 if screen_name == "DELL P2419H (1)" else 2

    monkeypatch.setattr(tracker_module, "screen_monitor", screen_monitor)
    tracker = ActiveWindowTracker()
    tracker.setProperty("screenName", "DELL P2419H (1)")
    tracker.setProperty("noWindowLabel", "Desktop")
    wait(10)
    desktop.focus(_window(1, "Notes"))
    assert tracker.property("text") == "Notes"

    tracker.setProperty("screenName", "DELL P2419H (2)")
    wait(10)
    assert not tracker.property("hasWindow")
    assert tracker.property("text") == "Desktop"


def test_the_widget_shows_the_active_window(desktop: Desktop):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "ActiveWindow" / "ActiveWindow.qml"))
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    assert not widget.property("visible")

    desktop.focus(_window(1, "Notes"))
    title = find_item(widget, "title")
    assert title is not None and title.property("text") == "Notes"
    assert widget.property("shown")

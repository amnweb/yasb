import copy
from typing import Any

import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.qml_types import register_qml_types
from core.services.active_window import tracker as tracker_module
from core.services.active_window.tracker import ActiveWindowTracker
from core.utils.win32 import event_listener
from core.utils.win32.constants import (
    HSHELL_MONITORCHANGED,
    HSHELL_REDRAW,
    HSHELL_RUDEAPPACTIVATED,
    HSHELL_WINDOWACTIVATED,
    HSHELL_WINDOWDESTROYED,
)
from core.utils.win32.shell_hook import shell_event
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
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
        shell_event(HSHELL_WINDOWACTIVATED).emit(window["hwnd"])


@pytest.fixture
def desktop(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Desktop:
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


def test_each_uwp_app_is_named_from_its_frames_aumid(desktop: Desktop, monkeypatch: pytest.MonkeyPatch):
    calculator = "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
    settings = "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel"
    aumids = {1: calculator, 2: settings}
    names = {calculator: "Calculator", settings: "Settings"}
    monkeypatch.setattr(tracker_module, "get_aumid_for_window", aumids.get)
    monkeypatch.setattr(tracker_module, "get_app_name_from_aumid", names.get)
    tracker = ActiveWindowTracker()
    for hwnd, name in ((1, "Calculator"), (2, "Settings")):
        # The frames of every UWP app belong to the same ApplicationFrameHost.exe
        frame = _window(hwnd, name, process="ApplicationFrameHost.exe")
        frame["class_name"] = "ApplicationFrameWindow"
        frame["process"]["pid"] = 500
        desktop.focus(frame)
        assert tracker.property("window")["app_name"] == name


def test_an_ignored_window_keeps_the_last_one(desktop: Desktop):
    tracker = ActiveWindowTracker()
    tracker.setProperty("ignoreProcesses", ["skip.exe"])
    desktop.focus(_window(1, "Notes"))
    desktop.focus(_window(2, "Skipped", process="skip.exe"))
    assert tracker.property("text") == "Notes"


def test_a_cloaked_window_is_not_kept(desktop: Desktop):
    tracker = ActiveWindowTracker()

    def cloak(hwnd: int) -> None:
        EventService().emit_event(WinEvent.EventObjectCloaked, hwnd, WinEvent.EventObjectCloaked)

    desktop.focus(_window(1, "Notes"))
    cloak(5)
    assert tracker.property("text") == "Notes"

    # komorebi cloaks the windows of the workspace it leaves, and on an empty one focuses the desktop, which has
    # no title
    desktop.foreground = 99
    cloak(1)
    assert not tracker.property("hasWindow")

    # A window already in front takes its place
    desktop.focus(_window(1, "Notes"))
    desktop.windows[2] = _window(2, "Mail")
    desktop.foreground = 2
    cloak(1)
    assert tracker.property("text") == "Mail"


def test_the_shell_reports_title_changes_and_closing(desktop: Desktop):
    tracker = ActiveWindowTracker()
    desktop.focus(_window(1, "Notes"))
    # A full-screen app is activated with the shell's rude code
    desktop.windows[2] = _window(2, "Game")
    desktop.foreground = 2
    shell_event(HSHELL_RUDEAPPACTIVATED).emit(2)
    assert tracker.property("text") == "Game"

    desktop.windows[2]["title"] = "Game - paused"
    shell_event(HSHELL_REDRAW).emit(1)
    assert tracker.property("text") == "Game"
    shell_event(HSHELL_REDRAW).emit(2)
    assert tracker.property("text") == "Game - paused"

    desktop.foreground = 0
    shell_event(HSHELL_WINDOWDESTROYED).emit(2)
    assert not tracker.property("hasWindow")


def test_minimizing_the_window_clears_it_and_restoring_brings_it_back(desktop: Desktop):
    tracker = ActiveWindowTracker()

    def minimize(hwnd: int, event: WinEvent) -> None:
        EventService().emit_event(event, hwnd, event)

    desktop.focus(_window(1, "Notes"))
    # The only window on screen: nothing else comes to the front
    desktop.foreground = 0
    minimize(1, WinEvent.EventSystemMinimizeStart)
    assert not tracker.property("hasWindow")

    desktop.foreground = 1
    minimize(1, WinEvent.EventSystemMinimizeEnd)
    assert tracker.property("text") == "Notes"

    # With another window behind it, that one takes its place
    desktop.windows[2] = _window(2, "Mail")
    desktop.foreground = 2
    minimize(1, WinEvent.EventSystemMinimizeStart)
    assert tracker.property("text") == "Mail"


def test_rewrite_max_length_and_the_alternate_label(desktop: Desktop):
    tracker = ActiveWindowTracker()
    tracker.setProperty("rewrite", [{"pattern": "Notes", "replacement": "notes", "case": "upper"}])
    tracker.setProperty("maxLength", 3)
    tracker.setProperty("ellipsis", "...")
    wait(10)
    desktop.focus(_window(1, "Notes"))
    assert tracker.property("text") == "NOT..."
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


def test_a_window_moved_to_another_monitor_follows_it(desktop: Desktop, monkeypatch: pytest.MonkeyPatch):
    def screen_monitor(screen_name: str) -> int:
        return 1 if screen_name == "DELL P2419H (1)" else 2

    monkeypatch.setattr(tracker_module, "screen_monitor", screen_monitor)
    first, second = ActiveWindowTracker(), ActiveWindowTracker()
    first.setProperty("screenName", "DELL P2419H (1)")
    second.setProperty("screenName", "DELL P2419H (2)")
    wait(10)
    desktop.focus(_window(1, "Notes"))
    assert first.property("text") == "Notes" and not second.property("hasWindow")

    # komorebi moves the window in front without a focus change, and only the shell says so
    desktop.windows[1]["monitor_hwnd"] = 2
    shell_event(HSHELL_MONITORCHANGED).emit(1)
    assert not first.property("hasWindow") and second.property("text") == "Notes"


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

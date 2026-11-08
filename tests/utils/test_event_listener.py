# pyright: reportPrivateUsage=false

from collections.abc import Callable

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.utils.win32 import event_listener
from core.utils.win32.bindings.kernel32 import GetModuleHandle
from core.utils.win32.bindings.user32 import CreateWindowEx, DestroyWindow
from core.utils.win32.constants import WS_CHILD, WS_POPUP
from core.utils.win32.event_listener import SystemEventListener
from tests.support.qt import wait

OBJID_CLIENT = -4


class Recorder(QObject):
    received = pyqtSignal(int, WinEvent)


@pytest.fixture
def wanted(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> set[WinEvent]:
    """The events asked for, apart from the ones other tests asked for."""
    events: set[WinEvent] = set()
    monkeypatch.setattr(event_listener, "_wanted", events)
    return events


def until(condition: Callable[[], bool]) -> bool:
    for _ in range(100):
        if condition():
            return True
        wait(10)
    return False


def test_the_thread_hooks_what_was_asked_for_and_lets_go_on_stop(wanted: set[WinEvent]):
    listener = SystemEventListener()
    wanted.add(WinEvent.EventSystemForeground)
    listener.start()
    assert until(lambda: set(listener._hooks) == {WinEvent.EventSystemForeground})

    # Asked for once it runs
    wanted.add(WinEvent.EventObjectDestroy)
    listener.request_hooks()
    assert until(lambda: set(listener._hooks) == {WinEvent.EventSystemForeground, WinEvent.EventObjectDestroy})

    listener.stop()
    assert listener.wait(1000)
    assert listener._hooks == {}
    assert listener._thread_id == 0


def test_a_stop_before_the_thread_runs_still_ends_it(wanted: set[WinEvent]):
    listener = SystemEventListener()
    listener.stop()
    listener.start()
    assert listener.wait(1000)


def test_only_events_about_windows_themselves_go_on(wanted: set[WinEvent]):
    heard: list[int] = []
    recorder = Recorder()

    def hear(hwnd: int, _event: WinEvent) -> None:
        heard.append(hwnd)

    recorder.received.connect(hear)
    EventService().register_event(WinEvent.EventObjectNameChange, recorder.received)
    try:
        listener = SystemEventListener()
        name_change = WinEvent.EventObjectNameChange.value
        listener._event_handler(None, name_change, 42, 0, 0, 0, 0)
        # A menu item or text inside the window, and an event without a window
        listener._event_handler(None, name_change, 43, OBJID_CLIENT, 0, 0, 0)
        listener._event_handler(None, name_change, 44, 0, 3, 0, 0)
        listener._event_handler(None, name_change, None, 0, 0, 0, 0)
        assert heard == [42]
    finally:
        EventService().unregister_event(WinEvent.EventObjectNameChange, recorder.received)


def test_windows_inside_another_window_are_left_out(wanted: set[WinEvent]):
    heard: list[int] = []
    recorder = Recorder()

    def hear(hwnd: int, _event: WinEvent) -> None:
        heard.append(hwnd)

    recorder.received.connect(hear)
    EventService().register_event(WinEvent.EventObjectShow, recorder.received)
    module = GetModuleHandle(None)
    top = CreateWindowEx(0, "STATIC", "YASB listener test", WS_POPUP, 0, 0, 100, 100, None, None, module, None)
    button = CreateWindowEx(0, "BUTTON", "child", WS_CHILD, 0, 0, 50, 20, top, None, module, None)
    try:
        assert top and button
        listener = SystemEventListener()
        show = WinEvent.EventObjectShow.value
        listener._event_handler(None, show, button, 0, 0, 0, 0)
        listener._event_handler(None, show, top, 0, 0, 0, 0)
        assert heard == [top]
    finally:
        DestroyWindow(top)
        EventService().unregister_event(WinEvent.EventObjectShow, recorder.received)


def test_nothing_starts_the_hook_again_once_yasb_quits(wanted: set[WinEvent], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(event_listener, "_listener", None)
    monkeypatch.setattr(event_listener, "_quitting", False)
    event_listener._stop_system_event_listener()
    # Services stopping after the hook, such as the taskbar, must not leave a thread no one stops
    event_listener.ensure_system_event_listener()
    assert event_listener._listener is None


class SilentEvents:
    """Stands in for EventService, so the test leaves no signals registered behind."""

    def register_event(self, *_args: object) -> None:
        pass

    def emit_event(self, *_args: object) -> None:
        pass


def test_every_widget_shares_one_thread_and_one_hook_per_event(wanted: set[WinEvent], monkeypatch: pytest.MonkeyPatch):
    events = SilentEvents()
    monkeypatch.setattr(event_listener, "EventService", lambda: events)
    monkeypatch.setattr(event_listener, "_listener", None)
    monkeypatch.setattr(event_listener, "_signals", {})
    monkeypatch.setattr(event_listener, "_quitting", False)
    # Each call is a real hook in Windows, which the bookkeeping alone would not show twice
    hooked: list[int] = []
    set_hook = event_listener.user32.SetWinEventHook

    def counting_set_hook(event_min: int, *rest: object) -> int:
        hooked.append(event_min)
        return set_hook(event_min, *rest)

    monkeypatch.setattr(event_listener.user32, "SetWinEventHook", counting_set_hook)
    foreground, destroy, cloaked = (
        WinEvent.EventSystemForeground,
        WinEvent.EventObjectDestroy,
        WinEvent.EventObjectCloaked,
    )
    # Widgets on two bars asking for the same events
    for event in (foreground, destroy, foreground, cloaked, destroy, foreground):
        event_listener.win_event(event)
    listener = event_listener._listener
    assert listener is not None
    try:
        assert until(lambda: set(listener._hooks) == {foreground, destroy, cloaked})
        assert len(event_listener._signals) == 3
        event_listener.win_event(foreground)
        listener.request_hooks()
        wait(50)
        assert event_listener._listener is listener
        assert sorted(hooked) == sorted(event.value for event in (foreground, destroy, cloaked))
    finally:
        event_listener._stop_system_event_listener()
    assert listener.isFinished()

# pyright: reportPrivateUsage=false

import threading
from collections.abc import Callable
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMetaObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.power_plan import power_plan_api as api
from core.utils.win32.bindings.kernel32 import SetEvent
from core.widget_files import find_widget_file
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
CUSTOM = "b60d10e3-b6df-4b8c-ac73-cc64ed772441"


def _until(ready: Callable[[], bool]) -> None:
    for _ in range(100):
        if ready():
            return
        wait(20)
    assert ready()


def test_popup_selects_the_plan_confirmed_by_windows(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    plans: list[api.Plan] = [{"id": BALANCED, "name": "Balanced"}, {"id": CUSTOM, "name": "Quiet Studio"}]
    active = BALANCED
    rejected = True
    calls: list[str] = []
    events: list[int] = []
    gui_thread = threading.get_ident()

    def read() -> api.Snapshot:
        assert threading.get_ident() != gui_thread
        return api.Snapshot(plans, active)

    def select(plan_id: str) -> api.Snapshot:
        nonlocal active
        assert threading.get_ident() != gui_thread
        calls.append(plan_id)
        if rejected:
            raise RuntimeError("Windows refused the plan change.")
        active = plan_id
        return read()

    key = Mock(handle=1)

    def watch(_key: int, _subtree: bool, _flags: int, event: int, _async: bool) -> int:
        events.append(event)
        return 0

    monkeypatch.setattr(api.winreg, "OpenKey", Mock(return_value=key))
    monkeypatch.setattr(api, "RegNotifyChangeKeyValue", watch)
    monkeypatch.setattr(api, "_read_plans", read)
    monkeypatch.setattr(api, "_select_plan", select)
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    path = find_widget_file("PowerPlan")
    assert path is not None
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]

    try:
        label = find_item(widget, "label")
        assert label is not None
        _until(lambda: label.property("text") == "Balanced")

        QMetaObject.invokeMethod(widget, "togglePopup")
        _until(lambda: any(window.title() == "Power Plans" and window.isVisible() for window in qapp.topLevelWindows()))
        window = next(
            window for window in qapp.topLevelWindows() if window.title() == "Power Plans" and window.isVisible()
        )
        assert isinstance(window, QQuickWindow)
        content = window.contentItem()
        assert content is not None
        balanced = find_item(content, f"plan-{BALANCED}")
        custom = find_item(content, f"plan-{CUSTOM}")
        notice = find_item(content, "notice")
        assert balanced is not None and custom is not None and notice is not None
        _until(custom.isEnabled)
        assert balanced.property("selected") and not custom.property("selected")

        QMetaObject.invokeMethod(custom, "clicked")
        _until(lambda: notice.property("text") == "Windows refused the plan change.")
        assert label.property("text") == "Balanced"
        assert balanced.property("selected") and not custom.property("selected")

        rejected = False
        QMetaObject.invokeMethod(custom, "clicked")
        _until(lambda: label.property("text") == "Quiet Studio")
        assert not balanced.property("selected") and custom.property("selected")
        assert not notice.isVisible()
        assert calls == [CUSTOM, CUSTOM]

        active = BALANCED
        assert len(events) == 1 and SetEvent(events[0])
        _until(lambda: label.property("text") == "Balanced")
        assert balanced.property("selected") and not custom.property("selected")
        assert events == [events[0], events[0]]
    finally:
        sip.delete(widget)
        sip.delete(engine)
    key.Close.assert_called_once()


def test_a_plan_chosen_while_the_plans_are_read_is_applied_after(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch
):
    jobs: list[tuple[Callable[[], object], Callable[[object, str], None]]] = []

    def schedule(work: Callable[[], object], done: Callable[[object, str], None], _failure: str) -> None:
        jobs.append((work, done))

    plans: list[api.Plan] = [{"id": BALANCED, "name": "Balanced"}, {"id": CUSTOM, "name": "Quiet Studio"}]
    select = Mock(return_value=api.Snapshot(plans, CUSTOM))
    monkeypatch.setattr(api, "run_in_worker", schedule)
    monkeypatch.setattr(api, "_select_plan", select)
    monkeypatch.setattr(api.winreg, "OpenKey", Mock(side_effect=OSError))
    power = api.PowerPlans()
    # As when the popup has just opened: its refresh is still reading
    power.selectPlan(CUSTOM)
    assert len(jobs) == 1
    jobs[0][1](api.Snapshot(plans, BALANCED), "")

    assert len(jobs) == 2
    work, done = jobs[1]
    done(work(), "")
    select.assert_called_once_with(CUSTOM)
    assert power.property("activeId") == CUSTOM and not power.property("loading")
    sip.delete(power)

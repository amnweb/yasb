# pyright: reportPrivateUsage=false

from collections.abc import Callable
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem

from core.qml_types import register_qml_types
from core.services.komorebi import workspaces as workspaces_module
from core.services.komorebi.client import KomorebiClient
from core.services.komorebi.workspaces import KomorebiWorkspacesModel
from core.utils.icons.service import IconService
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

# The monitor handles komorebi knows the two screens by
PRIMARY = 101
SECOND = 202


class FakeListener(QObject):
    """Stands in for the thread that reads komorebi's named pipe."""

    state_changed = pyqtSignal(object)
    finished = pyqtSignal()

    def __init__(self, made: list[FakeListener]) -> None:
        super().__init__()
        self.started = False
        self.stopped = False
        made.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def wait(self, _timeout: int = 0) -> bool:
        return True


def window(hwnd: int, title: str = "") -> dict[str, Any]:
    return {"hwnd": hwnd, "title": title, "exe": f"app{hwnd}.exe"}


def workspace(
    name: str | None = None,
    tiled: tuple[dict[str, Any], ...] = (),
    floating: tuple[dict[str, Any], ...] = (),
    **extra: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "containers": {"elements": [{"windows": {"elements": [item], "focused": 0}} for item in tiled], "focused": 0},
        "monocle_container": None,
        "maximized_window": None,
        "floating_windows": {"elements": list(floating), "focused": 0},
        "layout": {"Default": "BSP"},
        "layer": "Tiling",
        "tile": True,
    } | extra


def monitor(handle: int, workspaces: list[dict[str, Any]], focused: int = 0) -> dict[str, Any]:
    return {"id": handle, "workspaces": {"elements": workspaces, "focused": focused}}


def komorebi_state(*monitors: dict[str, Any], focused: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "monitors": {"elements": list(monitors), "focused": focused},
        "float_override": False,
        "is_paused": False,
    } | extra


def three_workspaces(focused: int = 0) -> dict[str, Any]:
    return komorebi_state(
        monitor(
            PRIMARY,
            [
                workspace("Code", tiled=(window(1, "Editor"), window(2, "Terminal"))),
                workspace(),
                workspace("Web", floating=(window(3, "Browser"),), layer="Floating"),
            ],
            focused=focused,
        ),
        monitor(SECOND, [workspace("Chat", tiled=(window(4),))]),
    )


@pytest.fixture
def listeners(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> list[FakeListener]:
    made: list[FakeListener] = []
    monkeypatch.setattr(workspaces_module, "_feed", None)
    monkeypatch.setattr(workspaces_module, "KomorebiEventListener", lambda: FakeListener(made))

    def screen_monitor(name: str) -> int:
        return SECOND if name == "DISPLAY2" else PRIMARY

    monkeypatch.setattr(workspaces_module, "screen_monitor", screen_monitor)
    return made


def send(listener: FakeListener, state: dict[str, Any] | None) -> None:
    listener.state_changed.emit(state)
    wait(5)


def summary(model: KomorebiWorkspacesModel) -> list[tuple[Any, ...]]:
    return [
        (item["index"], item["name"], item["active"], item["populated"], item["windowCount"])
        for item in model.property("workspaces")
    ]


def test_workspaces_come_from_the_bars_monitor_in_komorebis_order(listeners: list[FakeListener]):
    model = KomorebiWorkspacesModel()
    assert not model.property("connected") and model.property("workspaces") == []
    [listener] = listeners
    assert listener.started

    send(listener, three_workspaces(focused=2))
    assert model.property("connected") and model.property("monitorIndex") == 0
    assert summary(model) == [(0, "Code", False, True, 2), (1, "", False, False, 0), (2, "Web", True, True, 1)]
    web = model.property("workspaces")[2]
    assert (web["focused"], web["layout"], web["layer"], web["tile"], web["icons"]) == (
        True,
        "BSP",
        "Floating",
        True,
        [],
    )

    model.setProperty("screenName", "DISPLAY2")
    assert model.property("monitorIndex") == 1 and summary(model) == [(0, "Chat", True, True, 1)]
    # The second monitor shows its workspace without having komorebi's focus
    assert not model.property("workspaces")[0]["focused"]
    sip.delete(model)


def test_monocle_maximized_and_komorebis_switches_are_read(listeners: list[FakeListener]):
    model = KomorebiWorkspacesModel()
    monocle = workspace(monocle_container={"windows": {"elements": [window(5)], "focused": 0}})
    maximized = workspace(maximized_window=window(6), layout={"Custom": {}}, tile=False)
    send(listeners[0], komorebi_state(monitor(PRIMARY, [monocle, maximized]), float_override=True, is_paused=True))
    first, second = model.property("workspaces")
    assert (first["monocle"], first["maximized"], first["windowCount"]) == (True, False, 1)
    assert (second["monocle"], second["maximized"], second["windowCount"]) == (False, True, 1)
    assert (second["layout"], second["tile"]) == ("Custom", False)
    assert model.property("floatOverride") and model.property("paused")
    sip.delete(model)


def test_a_disconnect_clears_the_workspaces_and_a_broken_state_is_ignored(listeners: list[FakeListener]):
    model = KomorebiWorkspacesModel()
    announced: list[bool] = []
    model.dataChanged.connect(lambda: announced.append(True))
    send(listeners[0], three_workspaces())
    send(listeners[0], three_workspaces())
    assert len(announced) == 1

    send(listeners[0], {"monitors": "nope"})
    assert len(model.property("workspaces")) == 3

    send(listeners[0], None)
    assert not model.property("connected") and model.property("workspaces") == []
    assert model.property("monitorIndex") == -1
    sip.delete(model)


def test_icons_follow_the_app_icon_options(listeners: list[FakeListener], monkeypatch: pytest.MonkeyPatch):
    def thread_and_process(hwnd: int) -> tuple[int, int]:
        # Windows 1 and 2 belong to the same process
        return 0, 7 if hwnd < 3 else hwnd

    monkeypatch.setattr(workspaces_module, "get_window_thread_process_id", thread_and_process)
    model = KomorebiWorkspacesModel()
    send(listeners[0], three_workspaces(focused=2))

    def icons() -> list[list[int]]:
        return [[icon["hwnd"] for icon in item["icons"]] for item in model.property("workspaces")]

    model.setProperty("appIcons", {"enabledPopulated": True})
    assert icons() == [[1, 2], [], []]
    first = model.property("workspaces")[0]["icons"][0]
    assert first["title"] == "Editor" and first["source"].startswith("image://")

    model.setProperty("appIcons", {"enabledPopulated": True, "enabledActive": True, "maxIcons": 1})
    assert icons() == [[1], [], [3]]
    model.setProperty("appIcons", {"enabledPopulated": True, "enabledActive": True, "hideFloating": True})
    assert icons() == [[1, 2], [], []]
    model.setProperty("appIcons", {"enabledPopulated": True, "hideDuplicates": True})
    assert icons() == [[1], [], []]
    sip.delete(model)


def test_a_model_made_after_an_icon_loaded_asks_for_the_loaded_one(listeners: list[FakeListener]):
    def source(model: KomorebiWorkspacesModel) -> str:
        return model.property("workspaces")[0]["icons"][0]["source"]

    first = KomorebiWorkspacesModel()
    first.setProperty("appIcons", {"enabledPopulated": True})
    send(listeners[0], three_workspaces(focused=2))
    while_loading = source(first)
    # The icon finishes loading
    IconService.instance().icons_changed.emit()
    loaded = source(first)
    assert loaded != while_loading

    # A bar reloading its file makes a new model, which QML must not hand the blank image it kept for the old URL
    second = KomorebiWorkspacesModel()
    second.setProperty("appIcons", {"enabledPopulated": True})
    assert source(second) == loaded
    sip.delete(first)
    sip.delete(second)


def test_switching_asks_komorebic_for_the_monitors_workspace(
    listeners: list[FakeListener], monkeypatch: pytest.MonkeyPatch
):
    calls: list[tuple[int, int]] = []
    pending: list[tuple[Callable[[], object], Callable[[object, str], None]]] = []

    def activate(_client: KomorebiClient, monitor: int, workspace: int, wait: bool = False) -> None:
        calls.append((monitor, workspace))

    def run_later(work: Callable[[], object], done: Callable[[object, str], None], _failure: str) -> None:
        pending.append((work, done))

    monkeypatch.setattr(KomorebiClient, "activate_workspace", activate)
    monkeypatch.setattr(workspaces_module, "run_in_worker", run_later)

    def finish() -> None:
        work, done = pending.pop(0)
        done(work(), "")

    model = KomorebiWorkspacesModel()
    model.activateWorkspace(1)
    assert pending == []

    model.setProperty("screenName", "DISPLAY2")
    send(
        listeners[0], komorebi_state(monitor(PRIMARY, [workspace()]), monitor(SECOND, [workspace() for _ in range(3)]))
    )
    model.activateWorkspace(9)
    assert pending == []
    # Scrolling up goes back and wraps; while komorebic runs, only the last request waits
    model.switchWorkspace(120)
    model.switchWorkspace(-120)
    model.activateWorkspace(2)
    finish()
    finish()
    assert calls == [(1, 2), (1, 2)] and pending == []
    model.switchWorkspace(-120)
    finish()
    assert calls[-1] == (1, 1)
    sip.delete(model)


def test_one_listener_runs_while_any_widget_exists(listeners: list[FakeListener]):
    first, second = KomorebiWorkspacesModel(), KomorebiWorkspacesModel()
    assert len(listeners) == 1
    send(listeners[0], three_workspaces())
    assert summary(first) == summary(second)

    sip.delete(first)
    assert not listeners[0].stopped
    sip.delete(second)
    assert listeners[0].stopped

    # A widget made while the old listener stops, as a reloaded bar does, starts a new one once it has
    third = KomorebiWorkspacesModel()
    send(listeners[0], three_workspaces())
    assert len(listeners) == 1 and not third.property("connected")
    listeners[0].finished.emit()
    assert len(listeners) == 2 and listeners[1].started

    # Quitting stops it for good
    workspaces_module.workspace_feed().close()
    assert listeners[1].stopped
    listeners[1].finished.emit()
    assert len(listeners) == 2
    sip.delete(third)


def make_widget(engine: QQmlEngine, properties: dict[str, Any]) -> tuple[QQuickItem, list[str]]:
    register_qml_types()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    path = BUILTIN_WIDGETS_DIR / "KomorebiWorkspaces" / "KomorebiWorkspaces.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    initial: dict[str | None, Any] = {name: value for name, value in properties.items()}
    widget = component.createWithInitialProperties(initial)
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    return widget, warnings


def labels(widget: QQuickItem) -> list[str]:
    found: list[str] = []
    for index in range(4):
        button = find_item(widget, f"workspace-{index}")
        if button is not None and button.isVisible():
            label = find_item(button, "label")
            assert label is not None
            found.append(label.property("text"))
    return found


def test_the_widget_labels_workspaces_by_their_state(listeners: list[FakeListener]):
    engine = QQmlEngine()
    widget, warnings = make_widget(
        engine,
        {
            "emptyLabel": "{index}",
            "populatedLabel": "{name}*",
            "activeLabel": "[{name}@{monitor_index}]",
            "defaultName": "ws{index}",
        },
    )
    offline = find_item(widget, "offline")
    assert offline is not None and offline.property("text") == "Komorebi Offline"
    assert widget.property("visible")

    send(listeners[0], three_workspaces(focused=2))
    assert labels(widget) == ["Code*", "2", "[Web@1]"]
    widget.setProperty("hideEmptyWorkspaces", True)
    assert labels(widget) == ["Code*", "[Web@1]"]

    # An empty workspace still shows while the monitor shows it
    widget.setProperty("zeroBasedIndex", True)
    send(listeners[0], three_workspaces(focused=1))
    assert labels(widget) == ["Code*", "[ws1@0]", "Web*"]

    widget.setProperty("hideIfOffline", True)
    send(listeners[0], None)
    assert not widget.property("visible") and widget.property("implicitWidth") == 0
    assert not warnings
    sip.delete(widget)


def test_the_widget_shows_float_override_and_the_layer(listeners: list[FakeListener]):
    engine = QQmlEngine()
    widget, warnings = make_widget(engine, {"showWorkspaceLayer": True})
    float_override, layer = find_item(widget, "float-override"), find_item(widget, "layer")
    assert float_override is not None and layer is not None

    send(listeners[0], three_workspaces(focused=0) | {"float_override": True})
    assert float_override.isVisible() and layer.property("text") == "Tiling"
    send(listeners[0], three_workspaces(focused=2))
    assert not float_override.isVisible() and layer.property("text") == "Floating"
    assert not warnings
    sip.delete(widget)

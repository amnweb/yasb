import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6.QtCore import QByteArray, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QHostAddress
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtWebSockets import QWebSocket, QWebSocketServer

from core.qml_types import register_qml_types
from core.services.glazewm.binding_mode import GlazewmBindingModes
from core.services.glazewm.client import GlazewmClient
from core.services.glazewm.connection import GlazewmConnection
from core.services.glazewm.tiling_direction import GlazewmTiling
from core.services.glazewm.workspaces import GlazewmWorkspaceList
from core.utils.icons.image_provider import window_icon_url
from core.utils.icons.service import IconService
from tests.support.qt import wait


def until(condition: Callable[[], Any], timeout_ms: int = 3000) -> None:
    for _ in range(timeout_ms // 10):
        if condition():
            return
        wait(10)
    assert condition()


class FakeGlazewm(QObject):
    """A local GlazeWM IPC server that answers queries from a table, so the tests never need GlazeWM."""

    def __init__(self) -> None:
        super().__init__()
        self.server = QWebSocketServer("glazewm", QWebSocketServer.SslMode.NonSecureMode, self)
        assert self.server.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 0)
        self.uri = f"ws://127.0.0.1:{self.server.serverPort()}"
        self.server.newConnection.connect(self._accept)
        self.clients: list[QWebSocket] = []
        self.commands: list[str] = []
        self.answers: dict[str, Any] = {}

    def _accept(self) -> None:
        client = self.server.nextPendingConnection()
        assert client is not None
        self.clients.append(client)

        def received(text: str) -> None:
            self._message(client, text)

        client.textMessageReceived.connect(received)

    def _message(self, client: QWebSocket, text: str) -> None:
        if text.startswith("command "):
            self.commands.append(text.removeprefix("command "))
            data: Any = {"subjectContainerId": "container"}
        elif text.startswith("sub "):
            data = {"subscriptionId": "subscription"}
        else:
            data = self.answers.get(text, {})
        response = {"messageType": "client_response", "clientMessage": text, "data": data, "success": True}
        client.sendTextMessage(json.dumps(response))

    def send_event(self, kind: str, data: dict[str, Any] | None = None) -> None:
        for client in self.clients:
            message = {"messageType": "event_subscription", "data": {"eventType": kind, **(data or {})}}
            client.sendTextMessage(json.dumps(message))

    def stop(self) -> None:
        for client in self.clients:
            client.close()
        self.server.close()


@pytest.fixture
def glazewm(qapp: QGuiApplication) -> Iterator[FakeGlazewm]:
    server = FakeGlazewm()
    yield server
    server.stop()


def connected[T: GlazewmConnection](model: T, server: FakeGlazewm) -> T:
    model.setProperty("serverUri", server.uri)
    until(lambda: model.property("connected"))
    return model


def test_tiling_direction_follows_glazewm(glazewm: FakeGlazewm):
    glazewm.answers["query tiling-direction"] = {"tilingDirection": "vertical"}
    model = connected(GlazewmTiling(), glazewm)
    until(lambda: model.property("direction") == "vertical")

    glazewm.answers["query tiling-direction"] = {"tilingDirection": "horizontal"}
    glazewm.send_event("tiling_direction_changed")
    until(lambda: model.property("direction") == "horizontal")


def test_tiling_direction_toggles(glazewm: FakeGlazewm):
    model = connected(GlazewmTiling(), glazewm)
    model.toggleTilingDirection()
    until(lambda: glazewm.commands == ["toggle-tiling-direction"])


def test_tiling_direction_clears_when_glazewm_goes_away(glazewm: FakeGlazewm):
    glazewm.answers["query tiling-direction"] = {"tilingDirection": "vertical"}
    model = connected(GlazewmTiling(), glazewm)
    until(lambda: model.property("direction") == "vertical")
    glazewm.stop()
    until(lambda: not model.property("connected"))
    assert model.property("direction") == ""


def test_unknown_tiling_direction_is_ignored(glazewm: FakeGlazewm):
    glazewm.answers["query tiling-direction"] = {"tilingDirection": "diagonal"}
    model = connected(GlazewmTiling(), glazewm)
    wait(100)
    assert model.property("direction") == ""


def test_binding_mode_follows_glazewm(glazewm: FakeGlazewm):
    glazewm.answers["query binding-modes"] = {"bindingModes": []}
    model = connected(GlazewmBindingModes(), glazewm)
    wait(50)
    assert not model.property("active") and model.property("name") == ""

    glazewm.answers["query binding-modes"] = {"bindingModes": [{"name": "resize", "displayName": "Resize"}]}
    glazewm.send_event("binding_modes_changed")
    until(lambda: model.property("active"))
    assert model.property("name") == "resize" and model.property("displayName") == "Resize"

    glazewm.answers["query binding-modes"] = {"bindingModes": [{"name": "pause", "displayName": None}]}
    glazewm.send_event("binding_modes_changed")
    until(lambda: model.property("name") == "pause")
    assert model.property("displayName") == "pause"


def test_binding_mode_controls_ask_glazewm(glazewm: FakeGlazewm):
    model = connected(GlazewmBindingModes(), glazewm)
    model.disableBindingMode()  # nothing active yet, so nothing to send
    model.enableBindingMode("resize")
    until(lambda: glazewm.commands == ["wm-enable-binding-mode --name resize"])

    glazewm.answers["query binding-modes"] = {"bindingModes": [{"name": "resize", "displayName": "Resize"}]}
    glazewm.send_event("binding_modes_changed")
    until(lambda: model.property("active"))
    model.disableBindingMode()
    until(lambda: glazewm.commands[-1] == "wm-disable-binding-mode --name resize")


def test_malformed_binding_modes_are_ignored(glazewm: FakeGlazewm):
    client = GlazewmClient(glazewm.uri, ["query binding-modes"])
    received: list[object] = []
    client.binding_mode_changed.connect(received.append)
    glazewm.answers["query binding-modes"] = {"bindingModes": {"name": "resize"}}
    client.connect()
    until(lambda: glazewm.clients)
    wait(100)
    assert received == []
    client.close()


def test_workspaces_still_connect_through_the_shared_base(glazewm: FakeGlazewm):
    glazewm.answers["query monitors"] = {
        "monitors": [
            {
                "hardwareId": "screen",
                "handle": 1,
                "children": [
                    {"type": "workspace", "name": "2", "displayName": "", "hasFocus": False, "children": []},
                    {"type": "workspace", "name": "1", "displayName": "One", "hasFocus": True, "children": []},
                ],
            }
        ]
    }
    model = GlazewmWorkspaceList()
    model.setProperty("monitorExclusive", False)
    connected(model, glazewm)
    until(lambda: len(model.property("workspaces")) == 2)
    assert [workspace["name"] for workspace in model.property("workspaces")] == ["1", "2"]
    model.activateWorkspace("2")
    until(lambda: glazewm.commands == ["focus --workspace 2"])


def test_workspace_icons_use_the_shared_icon_revision(glazewm: FakeGlazewm):
    # A private counter starting at 0 (as after a bar reload) could land on a URL another widget already got a
    # loading placeholder for, and QML would keep showing that cached placeholder.
    window = {"type": "window", "handle": 1234, "title": "App", "processName": "app", "state": {"type": "tiling"}}
    workspace = {"type": "workspace", "name": "1", "hasFocus": True, "children": [window]}
    glazewm.answers["query monitors"] = {"monitors": [{"hardwareId": "screen", "handle": 1, "children": [workspace]}]}
    icons = IconService.instance()
    icons.icons_changed.emit()  # the service has moved on before this model exists
    model = GlazewmWorkspaceList()
    model.setProperty("monitorExclusive", False)
    model.setProperty("appIcons", {"enabledPopulated": True, "enabledFocused": True})
    connected(model, glazewm)

    def source() -> str | None:
        workspaces = model.property("workspaces")
        return workspaces[0]["icons"][0]["source"] if workspaces and workspaces[0]["icons"] else None

    until(lambda: source() == window_icon_url(1234, icons.revision))
    icons.icons_changed.emit()
    assert source() == window_icon_url(1234, icons.revision)


@pytest.mark.parametrize("name", ["GlazewmTiling", "GlazewmBindingModes"])
def test_qml_can_create_each_model(glazewm: FakeGlazewm, name: str):
    register_qml_types()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    source = f'import Yasb\n{name} {{ serverUri: "{glazewm.uri}" }}\n'
    component.setData(QByteArray(source.encode()), QUrl())
    model = component.create()
    assert model is not None, [error.toString() for error in component.errors()]
    until(lambda: model.property("connected"))

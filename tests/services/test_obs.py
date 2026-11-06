import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6.QtCore import QMetaObject, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QHostAddress
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWebSockets import QWebSocket, QWebSocketProtocol, QWebSocketServer

from core.qml_types import register_qml_types
from core.services.obs import studio as studio_module
from core.services.obs.studio import WRONG_PASSWORD, ObsConnection, ObsStudio, authentication
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

SALT, CHALLENGE = "salt", "challenge"


def until(condition: Callable[[], Any], timeout_ms: int = 3000) -> None:
    for _ in range(timeout_ms // 10):
        if condition():
            return
        wait(10)
    assert condition()


class FakeObs(QObject):
    """A local obs-websocket 5 server that answers requests from a table, so the tests never need OBS."""

    def __init__(self, password: str = "", port: int = 0) -> None:
        super().__init__()
        self.password = password
        self.server = QWebSocketServer("obs", QWebSocketServer.SslMode.NonSecureMode, self)
        assert self.server.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), port)
        self.port = self.server.serverPort()
        self.server.newConnection.connect(self._accept)
        self.clients: list[QWebSocket] = []
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.answers: dict[str, dict[str, Any]] = {}

    def _accept(self) -> None:
        client = self.server.nextPendingConnection()
        assert client is not None
        self.clients.append(client)

        def received(text: str) -> None:
            self._message(client, text)

        client.textMessageReceived.connect(received)
        hello: dict[str, Any] = {"obsWebSocketVersion": "5.5.0", "rpcVersion": 1}
        if self.password:
            hello["authentication"] = {"challenge": CHALLENGE, "salt": SALT}
        self._send(client, 0, hello)

    def _message(self, client: QWebSocket, text: str) -> None:
        message = json.loads(text)
        op, data = message["op"], message["d"]
        if op == 1:
            if self.password and data.get("authentication") != authentication(self.password, SALT, CHALLENGE):
                client.close(QWebSocketProtocol.CloseCode(4009), "Authentication failed.")
                return
            self._send(client, 2, {"negotiatedRpcVersion": 1})
        elif op == 6:
            kind = data["requestType"]
            self.requests.append((kind, data.get("requestData", {})))
            response = {
                "requestType": kind,
                "requestId": data["requestId"],
                "requestStatus": {"result": True, "code": 100},
                "responseData": self.answers.get(kind, {}),
            }
            self._send(client, 7, response)

    def send_event(self, kind: str, data: dict[str, Any]) -> None:
        for client in self.clients:
            self._send(client, 5, {"eventType": kind, "eventIntent": 0, "eventData": data})

    def _send(self, client: QWebSocket, op: int, data: dict[str, Any]) -> None:
        client.sendTextMessage(json.dumps({"op": op, "d": data}))

    def stop(self) -> None:
        for client in self.clients:
            client.close()
        self.server.close()


@pytest.fixture
def obs(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeObs]:
    monkeypatch.setattr(ObsConnection, "_feeds", {})
    monkeypatch.setattr(studio_module, "RETRY_MS", 50)
    server = FakeObs()
    yield server
    server.stop()


def studio(port: int, password: str = "") -> ObsStudio:
    obs_studio = ObsStudio()
    # The fake listens on IPv4 only; localhost would try IPv6 first
    obs_studio.setProperty("host", "127.0.0.1")
    obs_studio.setProperty("port", port)
    obs_studio.setProperty("password", password)
    return obs_studio


def test_it_reads_what_obs_is_doing(obs: FakeObs):
    obs.answers = {
        "GetRecordStatus": {"outputActive": True, "outputPaused": False, "outputDuration": 5000},
        "GetCurrentProgramScene": {"sceneName": "Gameplay"},
        "GetStudioModeEnabled": {"studioModeEnabled": True},
    }
    watched = studio(obs.port)
    until(lambda: watched.property("connected") and watched.property("scene") == "Gameplay")
    assert watched.property("recording") == {"active": True, "paused": False, "duration": 5000}
    assert watched.property("studioMode") and not watched.property("virtualCam")


def test_events_keep_it_current(obs: FakeObs):
    watched = studio(obs.port)
    until(lambda: watched.property("connected"))
    obs.answers["GetRecordStatus"] = {"outputActive": True, "outputPaused": True, "outputDuration": 1200}
    obs.send_event("RecordStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_PAUSED"})
    obs.send_event("CurrentProgramSceneChanged", {"sceneName": "Break"})
    obs.send_event("VirtualcamStateChanged", {"outputActive": True})
    until(lambda: watched.property("recording")["duration"] == 1200)
    assert watched.property("recording")["paused"]
    assert watched.property("scene") == "Break" and watched.property("virtualCam")


def test_controls_ask_obs(obs: FakeObs):
    watched = studio(obs.port)
    until(lambda: watched.property("connected") and len(obs.requests) >= 5)
    obs.requests.clear()
    watched.toggleRecord()
    watched.toggleRecordPause()
    watched.toggleStream()
    watched.toggleVirtualCam()
    watched.toggleStudioMode()
    until(lambda: len(obs.requests) >= 5)
    assert obs.requests[:5] == [
        ("ToggleRecord", {}),
        ("ToggleRecordPause", {}),
        ("ToggleStream", {}),
        ("ToggleVirtualCam", {}),
        ("SetStudioModeEnabled", {"studioModeEnabled": True}),
    ]


def test_the_password_answers_obs(obs: FakeObs):
    obs.password = "secret"
    watched = studio(obs.port, "secret")
    until(lambda: watched.property("connected"))
    refused = studio(obs.port, "wrong")
    until(lambda: refused.property("error") == WRONG_PASSWORD)
    assert not refused.property("connected")


def test_it_connects_again_once_obs_is_back(obs: FakeObs):
    watched = studio(obs.port)
    until(lambda: watched.property("connected"))
    port = obs.port
    obs.stop()
    until(lambda: not watched.property("connected"))
    restarted = FakeObs(port=port)
    try:
        until(lambda: watched.property("connected"))
    finally:
        restarted.stop()


def test_widgets_with_the_same_server_share_one_connection(obs: FakeObs):
    first, second = studio(obs.port), studio(obs.port)
    until(lambda: first.property("connected") and second.property("connected"))
    assert len(obs.clients) == 1


def test_the_widget_shows_a_recording(obs: FakeObs):
    obs.answers["GetRecordStatus"] = {"outputActive": True, "outputPaused": False, "outputDuration": 61000}
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Obs" / "Obs.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    QQmlProperty.write(item, "host", "127.0.0.1")
    QQmlProperty.write(item, "port", obs.port)
    # An item counts as visible only in a window, as on a bar
    host = QQuickWindow()
    item.setParentItem(host.contentItem())
    host.show()
    try:
        recording = find_item(item, "recording")
        assert recording is not None
        until(lambda: item.isVisible() and recording.isVisible())
        QMetaObject.invokeMethod(item, "togglePopup")
        wait(50)
        assert not warnings, warnings
    finally:
        popup = item.findChild(QObject, "popup")
        if popup is not None:
            QMetaObject.invokeMethod(popup, "hide")
        item.setParentItem(None)
        item.deleteLater()
        host.close()
        wait(20)

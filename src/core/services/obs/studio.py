"""OBS Studio through its WebSocket server (obs-websocket 5).

Qt's WebSocket runs on the GUI thread's event loop, so there is no thread: nothing to stop, and nothing for YASB to wait
for when it quits. A connection is shared by every widget with the same host, port and password, and tries again every
few seconds while OBS is not running.
"""

import base64
import hashlib
import json
import logging
import uuid
from typing import Any, ClassVar, cast

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtNetwork import QAbstractSocket
from PyQt6.QtWebSockets import QWebSocket

from core.utils.feed import Feed
from core.utils.qml import qml_property

RPC_VERSION = 1
# Events about the program scene, the outputs and the studio mode switch
EVENTS = (1 << 2) | (1 << 6) | (1 << 10)
RETRY_MS = 5000
# How often the recording and stream times are asked for while one runs
POLL_MS = 1000
OP_HELLO, OP_IDENTIFY, OP_IDENTIFIED, OP_EVENT, OP_REQUEST, OP_RESPONSE = 0, 1, 2, 5, 6, 7
# The close code OBS sends for a wrong password
AUTHENTICATION_FAILED = 4009
WRONG_PASSWORD = "OBS refused the password."

PAUSED = "OBS_WEBSOCKET_OUTPUT_PAUSED"
RECONNECTING = "OBS_WEBSOCKET_OUTPUT_RECONNECTING"


def authentication(password: str, salt: str, challenge: str) -> str:
    """The answer to OBS's challenge, as obs-websocket 5 defines it."""
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def idle_state() -> dict[str, Any]:
    return {
        "recording": {"active": False, "paused": False, "duration": 0},
        "streaming": {
            "active": False,
            "reconnecting": False,
            "duration": 0,
            "congestion": 0.0,
            "skippedFrames": 0,
            "totalFrames": 0,
        },
        "virtualCam": False,
        "studioMode": False,
        "scene": "",
    }


class ObsConnection(Feed[tuple[str, int, str]]):
    """One connection to OBS and what it reports, keyed by host, port and password."""

    _feeds: ClassVar[dict[Any, Any]] = {}
    error: str

    def __init__(self, key: tuple[str, int, str]) -> None:
        super().__init__(key)
        self.host, self.port, self.password = key
        self.connected = False
        self.state = idle_state()
        self._socket = QWebSocket(parent=self)
        self._socket.textMessageReceived.connect(self._message)
        self._socket.disconnected.connect(self._lost)
        self._socket.errorOccurred.connect(self._lost)
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._ask_times)
        self._timer.start(0)

    # Connects, unless a connection is open or opening
    @pyqtSlot()
    def fetch(self) -> None:
        self._timer.stop()
        if self._socket.state() == QAbstractSocket.SocketState.UnconnectedState:
            self._socket.open(QUrl(f"ws://{self.host}:{self.port}"))

    def request(self, kind: str, data: dict[str, Any] | None = None) -> None:
        if self._socket.state() != QAbstractSocket.SocketState.ConnectedState:
            return
        message: dict[str, Any] = {"requestType": kind, "requestId": uuid.uuid4().hex}
        if data is not None:
            message["requestData"] = data
        self._send(OP_REQUEST, message)

    def _send(self, op: int, data: dict[str, Any]) -> None:
        self._socket.sendTextMessage(json.dumps({"op": op, "d": data}))

    def _lost(self, *_args: object) -> None:
        # Both the error and the disconnect report a lost connection, and the socket is aborted to be opened again
        error = WRONG_PASSWORD if self._socket.closeCode().value == AUTHENTICATION_FAILED else ""
        self._socket.abort()
        self._poll.stop()
        if self.connected or error != self.error:
            self.connected, self.error = False, error
            self.state = idle_state()
            self.changed.emit()
        if not self._timer.isActive():
            self._timer.start(RETRY_MS)

    def _message(self, text: str) -> None:
        try:
            message = json.loads(text)
            op, data = int(message["op"]), cast(dict[str, Any], message.get("d") or {})
        except ValueError, KeyError, TypeError:
            logging.debug("OBS sent a message YASB could not read: %s", text[:200])
            return
        if op == OP_HELLO:
            identify: dict[str, Any] = {"rpcVersion": RPC_VERSION, "eventSubscriptions": EVENTS}
            challenge = data.get("authentication")
            if isinstance(challenge, dict):
                challenge = cast(dict[str, Any], challenge)
                identify["authentication"] = authentication(
                    self.password, str(challenge.get("salt", "")), str(challenge.get("challenge", ""))
                )
            self._send(OP_IDENTIFY, identify)
        elif op == OP_IDENTIFIED:
            self.connected, self.error = True, ""
            self.changed.emit()
            for kind in (
                "GetRecordStatus",
                "GetStreamStatus",
                "GetVirtualCamStatus",
                "GetStudioModeEnabled",
                "GetCurrentProgramScene",
            ):
                self.request(kind)
        elif op == OP_EVENT:
            self._apply(str(data.get("eventType", "")), cast(dict[str, Any], data.get("eventData") or {}))
        elif op == OP_RESPONSE:
            self._apply(str(data.get("requestType", "")), cast(dict[str, Any], data.get("responseData") or {}))

    def _apply(self, kind: str, data: dict[str, Any]) -> None:
        recording, streaming = self.state["recording"], self.state["streaming"]
        state = {**self.state, "recording": dict(recording), "streaming": dict(streaming)}
        if kind == "RecordStateChanged":
            state["recording"]["active"] = bool(data.get("outputActive"))
            state["recording"]["paused"] = data.get("outputState") == PAUSED
            # Its time starts and stops with it
            self.request("GetRecordStatus")
        elif kind == "GetRecordStatus":
            state["recording"] = {
                "active": bool(data.get("outputActive")),
                "paused": bool(data.get("outputPaused")),
                "duration": int(data.get("outputDuration") or 0),
            }
        elif kind == "StreamStateChanged":
            state["streaming"]["active"] = bool(data.get("outputActive"))
            state["streaming"]["reconnecting"] = data.get("outputState") == RECONNECTING
            self.request("GetStreamStatus")
        elif kind == "GetStreamStatus":
            state["streaming"] = {
                "active": bool(data.get("outputActive")),
                "reconnecting": bool(data.get("outputReconnecting")),
                "duration": int(data.get("outputDuration") or 0),
                "congestion": float(data.get("outputCongestion") or 0.0),
                "skippedFrames": int(data.get("outputSkippedFrames") or 0),
                "totalFrames": int(data.get("outputTotalFrames") or 0),
            }
        elif kind in ("VirtualcamStateChanged", "GetVirtualCamStatus"):
            state["virtualCam"] = bool(data.get("outputActive"))
        elif kind in ("StudioModeStateChanged", "GetStudioModeEnabled"):
            state["studioMode"] = bool(data.get("studioModeEnabled"))
        elif kind in ("CurrentProgramSceneChanged", "GetCurrentProgramScene"):
            state["scene"] = str(data.get("sceneName") or data.get("currentProgramSceneName") or "")
        else:
            return
        running = state["recording"]["active"] or state["streaming"]["active"]
        if running and not self._poll.isActive():
            self._poll.start()
        elif not running:
            self._poll.stop()
        if state != self.state:
            self.state = state
            self.changed.emit()

    def _ask_times(self) -> None:
        if self.state["recording"]["active"]:
            self.request("GetRecordStatus")
        if self.state["streaming"]["active"]:
            self.request("GetStreamStatus")


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(studio: ObsStudio) -> Any:
        return studio.setting(name)

    def set_value(studio: ObsStudio, value: Any) -> None:
        studio.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class ObsStudio(QObject):
    """What OBS Studio is doing, for one widget, and controlling it: recording, streaming, the virtual camera and
    studio mode. Durations are in milliseconds."""

    settingsChanged = pyqtSignal()
    obsChanged = pyqtSignal()

    host = _setting(str, "host", settingsChanged)
    port = _setting(int, "port", settingsChanged)
    # obs-websocket's server password; empty when its authentication is off
    password = _setting(str, "password", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {"host": "localhost", "port": 4455, "password": ""}
        self._connection: ObsConnection | None = None
        # QML sets the settings after creating the object, so the connection is joined once they are in
        self._join_timer = QTimer(self)
        self._join_timer.setSingleShot(True)
        self._join_timer.timeout.connect(self._join)
        self._join_timer.start(0)

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if value != self._settings[name]:
            self._settings[name] = value
            self.settingsChanged.emit()
            self._join_timer.start(0)

    def _join(self) -> None:
        key = (str(self._settings["host"]), int(self._settings["port"]), str(self._settings["password"]))
        if self._connection is not None:
            if self._connection.key == key:
                return
            self._connection.changed.disconnect(self.obsChanged)
            self._connection.leave(self)
        self._connection = ObsConnection.join(key, self)
        self._connection.changed.connect(self.obsChanged)
        self.obsChanged.emit()

    def _state(self, name: str) -> Any:
        return (self._connection.state if self._connection is not None else idle_state())[name]

    @qml_property(bool, notify=obsChanged)
    def connected(self) -> bool:
        return self._connection is not None and self._connection.connected

    # Why OBS is not connected, when there is more to it than OBS not running, such as a wrong password
    @qml_property(str, notify=obsChanged)
    def error(self) -> str:
        return self._connection.error if self._connection is not None else ""

    # {active, paused, duration}
    @qml_property("QVariantMap", notify=obsChanged)
    def recording(self) -> dict[str, Any]:
        return self._state("recording")

    # {active, reconnecting, duration, congestion, skippedFrames, totalFrames}, congestion from 0 to 1
    @qml_property("QVariantMap", notify=obsChanged)
    def streaming(self) -> dict[str, Any]:
        return self._state("streaming")

    @qml_property(bool, notify=obsChanged)
    def virtualCam(self) -> bool:
        return self._state("virtualCam")

    @qml_property(bool, notify=obsChanged)
    def studioMode(self) -> bool:
        return self._state("studioMode")

    # The program scene's name
    @qml_property(str, notify=obsChanged)
    def scene(self) -> str:
        return self._state("scene")

    def _request(self, kind: str, data: dict[str, Any] | None = None) -> None:
        if self._connection is not None:
            self._connection.request(kind, data)

    @pyqtSlot()
    def toggleRecord(self) -> None:
        self._request("ToggleRecord")

    @pyqtSlot()
    def toggleRecordPause(self) -> None:
        self._request("ToggleRecordPause")

    @pyqtSlot()
    def toggleStream(self) -> None:
        self._request("ToggleStream")

    @pyqtSlot()
    def toggleVirtualCam(self) -> None:
        self._request("ToggleVirtualCam")

    @pyqtSlot()
    def toggleStudioMode(self) -> None:
        self._request("SetStudioModeEnabled", {"studioModeEnabled": not self.studioMode})

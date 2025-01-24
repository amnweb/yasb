import json
import logging
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QAbstractSocket
from PyQt6.QtWebSockets import QWebSocket

from settings import DEBUG

logger = logging.getLogger("glazewm_client")

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


@dataclass
class Workspace:
    name: str
    display_name: str
    focus: bool = False
    is_displayed: bool = False
    num_windows: int = 0


@dataclass
class Monitor:
    name: str
    hwnd: int
    workspaces: list[Workspace]


class MessageType(StrEnum):
    EVENT_SUBSCRIPTION = auto()
    CLIENT_RESPONSE = auto()


class QueryType(StrEnum):
    MONITORS = "query monitors"
    TILING_DIRECTION = "query tiling-direction"


class TilingDirection(StrEnum):
    HORIZONTAL = auto()
    VERTICAL = auto()


class GlazewmClient(QObject):
    workspaces_data_processed = pyqtSignal(list)
    tiling_direction_processed = pyqtSignal(str)
    glazewm_connection_status = pyqtSignal(bool)

    def __init__(self, uri: str, initial_messages: list[str] | None = None, reconnect_interval=4000) -> None:
        super().__init__()
        self.initial_messages = initial_messages if initial_messages else []

        self._uri = QUrl(uri)
        self._websocket = QWebSocket()
        self._websocket.connected.connect(self._on_connected)
        self._websocket.textMessageReceived.connect(self._handle_message)
        self._websocket.stateChanged.connect(self._on_state_changed)
        self._websocket.errorOccurred.connect(self._on_error)

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setInterval(reconnect_interval)
        self._reconnect_timer.timeout.connect(self.connect)

    def activate_workspace(self, workspace_name: str):
        self._websocket.sendTextMessage(f"command focus --workspace {workspace_name}")

    def toggle_tiling_direction(self):
        self._websocket.sendTextMessage("command toggle-tiling-direction")

    def connect(self):
        logger.debug(f"Connecting to {self._uri}...")
        self._websocket.open(self._uri)

    def _on_connected(self) -> None:
        logger.debug(f"Connected to {self._uri}")
        for message in self.initial_messages:
            logger.debug(f"Sent initial message: {message}")
            self._websocket.sendTextMessage(message)

        # Stop reconnect timer
        self._reconnect_timer.stop()

    def _on_state_changed(self, state: QAbstractSocket.SocketState):
        logger.debug(f"WebSocket state changed: {state}")
        self.glazewm_connection_status.emit(state == QAbstractSocket.SocketState.ConnectedState)

    def _on_error(self, error: QAbstractSocket.SocketError) -> None:
        logger.warning(f"WebSocket error: {error}\nReconnecting...")
        self._reconnect_timer.start()

    def _handle_message(self, message: str):
        try:
            response = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON data.")
            return

        if response.get("messageType") == MessageType.EVENT_SUBSCRIPTION:
            self._websocket.sendTextMessage(QueryType.MONITORS)
            self._websocket.sendTextMessage(QueryType.TILING_DIRECTION)
        elif response.get("messageType") == MessageType.CLIENT_RESPONSE:
            data = response.get("data", {})
            if response.get("clientMessage") == QueryType.MONITORS:
                monitors = data.get("monitors", [])
                self.workspaces_data_processed.emit(self._process_workspaces(monitors))
            elif response.get("clientMessage") == QueryType.TILING_DIRECTION:
                tiling_direction = TilingDirection(data.get("tilingDirection", TilingDirection.HORIZONTAL))
                self.tiling_direction_processed.emit(tiling_direction)

    def _process_workspaces(self, data: list[dict[str, Any]]) -> list[Monitor]:
        monitors: list[Monitor] = []
        for mon in data:
            monitor_name: str | None = mon.get("hardwareId")
            handle: int | None = mon.get("handle")
            if not monitor_name or not handle:
                logger.warning("Monitor name or hwnd not found")
                continue
            workspaces_data = [
                Workspace(
                    name=child.get("name", ""),
                    display_name=child.get("displayName", ""),
                    is_displayed=child.get("isDisplayed", False),
                    focus=child.get("hasFocus", False),
                    num_windows=len(child.get("children", [])),
                )
                for child in mon.get("children", [])
                if child.get("type") == "workspace"
            ]
            monitors.append(
                Monitor(
                    name=monitor_name,
                    hwnd=handle,
                    workspaces=workspaces_data,
                )
            )
        return monitors

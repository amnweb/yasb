import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, cast

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
class Window:
    id: str
    title: str
    handle: int
    class_name: str
    process_name: str
    display_state: str
    is_floating: bool


@dataclass
class Workspace:
    name: str
    display_name: str
    focus: bool = False
    is_displayed: bool = False
    num_windows: int = 0
    windows: list[Window] = field(default_factory=list)


@dataclass
class Monitor:
    name: str
    hwnd: int
    workspaces: list[Workspace]


@dataclass
class BindingMode:
    name: str
    display_name: str


class MessageType(StrEnum):
    EVENT_SUBSCRIPTION = auto()
    CLIENT_RESPONSE = auto()


class QueryType(StrEnum):
    MONITORS = "query monitors"
    TILING_DIRECTION = "query tiling-direction"
    BINDING_MODES = "query binding-modes"


class TilingDirection(StrEnum):
    HORIZONTAL = auto()
    VERTICAL = auto()


class GlazewmClient(QObject):
    workspaces_data_processed = pyqtSignal(list)
    tiling_direction_processed = pyqtSignal(TilingDirection)
    binding_mode_changed = pyqtSignal(BindingMode)
    glazewm_connection_status = pyqtSignal(bool)

    def __init__(
        self,
        uri: str,
        initial_messages: list[str] | None = None,
        reconnect_interval: int = 4000,
    ):
        super().__init__()
        self.initial_messages = initial_messages if initial_messages else []

        self._uri = QUrl(uri)
        self._websocket = QWebSocket()
        self._websocket.connected.connect(self._on_connected)  # type: ignore
        self._websocket.textMessageReceived.connect(self._handle_message)  # type: ignore
        self._websocket.stateChanged.connect(self._on_state_changed)  # type: ignore
        self._websocket.errorOccurred.connect(self._on_error)  # type: ignore

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setInterval(reconnect_interval)
        self._reconnect_timer.timeout.connect(self.connect)  # type: ignore

    def activate_workspace(self, workspace_name: str):
        self._websocket.sendTextMessage(f"command focus --workspace {workspace_name}")

    def toggle_tiling_direction(self):
        self._websocket.sendTextMessage("command toggle-tiling-direction")

    def disable_binding_mode(self, binding_mode_name: str):
        self._websocket.sendTextMessage(f"command wm-disable-binding-mode --name {binding_mode_name}")

    def enable_binding_mode(self, binding_mode_name: str):
        self._websocket.sendTextMessage(f"command wm-enable-binding-mode --name {binding_mode_name}")

    def focus_next_workspace(self):
        self._websocket.sendTextMessage("command focus --next-active-workspace-on-monitor")

    def focus_prev_workspace(self):
        self._websocket.sendTextMessage("command focus --prev-active-workspace-on-monitor")

    def connect(self):
        if self._websocket.state() == QAbstractSocket.SocketState.ConnectedState:
            return
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
            self._websocket.sendTextMessage(QueryType.BINDING_MODES)
        elif response.get("messageType") == MessageType.CLIENT_RESPONSE:
            raw_data: Any = response.get("data")
            if not isinstance(raw_data, dict):
                logger.warning(f"Expected 'data' to be a dict, got {type(raw_data).__name__}")
                return
            data = cast(dict[str, Any], raw_data)
            if response.get("clientMessage") == QueryType.MONITORS:
                monitors = data.get("monitors", [])
                if monitors is None:
                    logger.warning("Expected 'monitors' to be a list, got None")
                    return
                self.workspaces_data_processed.emit(self._process_workspaces(monitors))
            elif response.get("clientMessage") == QueryType.TILING_DIRECTION:
                tiling_direction = TilingDirection(data.get("tilingDirection", TilingDirection.HORIZONTAL))
                self.tiling_direction_processed.emit(tiling_direction)
            elif response.get("clientMessage") == QueryType.BINDING_MODES:
                binding_modes = data.get("bindingModes", [])
                if binding_modes is None:
                    logger.warning(f"Expected 'bindingModes' to be a list, got {type(binding_modes).__name__}")
                    return
                self.binding_mode_changed.emit(self._process_binding_modes(binding_modes))

    def _process_workspaces(self, data: list[dict[str, Any]]) -> list[Monitor]:
        monitors: list[Monitor] = []
        for mon in data:
            monitor_name: str | None = mon.get("hardwareId")
            handle: int | None = mon.get("handle")
            if not handle:
                logger.warning("Monitor handle not found")
                continue
            if not monitor_name:
                monitor_name = f"Unknown_{handle}"
            workspaces_data = [
                Workspace(
                    name=child.get("name", ""),
                    display_name=child.get("displayName", ""),
                    is_displayed=child.get("isDisplayed", False),
                    focus=child.get("hasFocus", False),
                    num_windows=len(child.get("children", [])),
                    windows=self._read_windows(child),
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

    def _process_binding_modes(self, data: list[dict[str, Any]]) -> BindingMode:
        if len(data) == 0:
            return BindingMode(name=None, display_name=None)

        return BindingMode(
            name=data[0].get("name", None),
            display_name=data[0].get("displayName", None),
        )

    def _read_windows(self, parent):
        windows = []
        for child in parent.get("children", []):
            if child.get("type") == "window":
                windows.append(
                    Window(
                        id=child.get("id"),
                        title=child.get("title"),
                        handle=child.get("handle"),
                        class_name=child.get("className"),
                        process_name=child.get("processName"),
                        display_state=child.get("displayState"),
                        is_floating=child.get("state").get("type") == "floating",
                    )
                )
            elif child.get("type") == "split":
                windows.extend(self._read_windows(child))
        return windows

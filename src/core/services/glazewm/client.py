import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, cast

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QAbstractSocket
from PyQt6.QtWebSockets import QWebSocket

logger = logging.getLogger("glazewm_client")


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
    focus: bool = False  # Global focus - only ONE workspace has this True
    is_displayed: bool = False
    num_windows: int = 0
    windows: list[Window] = field(default_factory=list[Window])


@dataclass
class Monitor:
    name: str
    hwnd: int
    workspaces: list[Workspace]


@dataclass
class BindingMode:
    name: str | None
    display_name: str | None


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
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.initial_messages = initial_messages if initial_messages else []

        self._uri = QUrl(uri)
        self._closed = False
        self._websocket = QWebSocket(parent=self)
        self._websocket.connected.connect(self._on_connected)  # type: ignore
        self._websocket.textMessageReceived.connect(self._handle_message)  # type: ignore
        self._websocket.stateChanged.connect(self._on_state_changed)  # type: ignore
        self._websocket.errorOccurred.connect(self._on_error)  # type: ignore

        self._reconnect_timer = QTimer(self)
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

    def focus_next_workspace_global(self):
        self._websocket.sendTextMessage("command focus --next-active-workspace")

    def focus_prev_workspace_global(self):
        self._websocket.sendTextMessage("command focus --prev-active-workspace")

    def connect(self):
        if self._websocket.state() != QAbstractSocket.SocketState.UnconnectedState:
            return
        self._closed = False
        logger.debug("Connecting to %s", self._uri.toString())
        self._websocket.open(self._uri)

    def close(self) -> None:
        self._closed = True
        self._reconnect_timer.stop()
        self._websocket.abort()

    def _on_connected(self) -> None:
        logger.debug("Connected to %s", self._uri.toString())
        for message in self.initial_messages:
            logger.debug("Sent initial message: %s", message)
            self._websocket.sendTextMessage(message)

        # Stop reconnect timer
        self._reconnect_timer.stop()

    def _on_state_changed(self, state: QAbstractSocket.SocketState):
        logger.debug("WebSocket state changed: %s", state)
        self.glazewm_connection_status.emit(state == QAbstractSocket.SocketState.ConnectedState)
        if state == QAbstractSocket.SocketState.UnconnectedState and not self._closed:
            self._reconnect_timer.start()

    def _on_error(self, error: QAbstractSocket.SocketError) -> None:
        if not self._closed:
            logger.debug("WebSocket error: %s. Reconnecting...", error)
            self._reconnect_timer.start()

    def _handle_message(self, message: str):
        try:
            response = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON data.")
            return

        if not isinstance(response, dict):
            logger.warning("Expected a JSON object from GlazeWM")
            return
        response = cast(dict[str, Any], response)

        if response.get("messageType") == MessageType.EVENT_SUBSCRIPTION:
            for message in self.initial_messages:
                if message in QueryType:
                    self._websocket.sendTextMessage(message)
        elif response.get("messageType") == MessageType.CLIENT_RESPONSE:
            if response.get("success") is False:
                logger.warning("GlazeWM request failed: %s", response.get("error"))
                return
            raw_data: Any = response.get("data")
            if not isinstance(raw_data, dict):
                logger.warning("Expected 'data' to be a dict, got %s", type(raw_data).__name__)
                return
            data = cast(dict[str, Any], raw_data)
            if response.get("clientMessage") == QueryType.MONITORS:
                monitors = data.get("monitors", [])
                if not isinstance(monitors, list):
                    logger.warning("Expected 'monitors' to be a list")
                    return
                self.workspaces_data_processed.emit(self._process_workspaces(cast(list[dict[str, Any]], monitors)))
            elif response.get("clientMessage") == QueryType.TILING_DIRECTION:
                try:
                    tiling_direction = TilingDirection(data.get("tilingDirection", TilingDirection.HORIZONTAL))
                except ValueError:
                    logger.warning("Unknown tiling direction: %s", data.get("tilingDirection"))
                    return
                self.tiling_direction_processed.emit(tiling_direction)
            elif response.get("clientMessage") == QueryType.BINDING_MODES:
                binding_modes = data.get("bindingModes", [])
                if not isinstance(binding_modes, list):
                    logger.warning("Expected 'bindingModes' to be a list, got %s", type(binding_modes).__name__)
                    return
                self.binding_mode_changed.emit(self._process_binding_modes(cast(list[dict[str, Any]], binding_modes)))

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
            workspaces_data: list[Workspace] = []
            for child in mon.get("children", []):
                if child.get("type") != "workspace":
                    continue
                windows = self._read_windows(child)
                workspaces_data.append(
                    Workspace(
                        name=child.get("name", ""),
                        display_name=child.get("displayName", ""),
                        is_displayed=child.get("isDisplayed", False),
                        focus=child.get("hasFocus", False),
                        num_windows=len(windows),
                        windows=windows,
                    )
                )
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

    def _read_windows(self, parent: dict[str, Any]) -> list[Window]:
        windows: list[Window] = []
        for child in parent.get("children", []):
            if child.get("type") == "window":
                state: dict[str, Any] = child.get("state") or {}
                windows.append(
                    Window(
                        id=child.get("id"),
                        title=child.get("title"),
                        handle=child.get("handle"),
                        class_name=child.get("className"),
                        process_name=child.get("processName"),
                        display_state=child.get("displayState"),
                        is_floating=state.get("type") == "floating",
                    )
                )
            elif child.get("type") == "split":
                windows.extend(self._read_windows(child))
        return windows

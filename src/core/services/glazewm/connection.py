from typing import ClassVar

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.services.glazewm.client import GlazewmClient

DEFAULT_SERVER_URI = "ws://localhost:6123"


class GlazewmConnection(QObject):
    """Base for GlazeWM QML types: owns the connection and restarts it when the server changes."""

    connectionChanged = pyqtSignal()
    serverUriChanged = pyqtSignal()

    # Subscription and queries sent on connect. Queries are re-sent after every subscribed event.
    MESSAGES: ClassVar[list[str]] = []

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server_uri = DEFAULT_SERVER_URI
        self._client: GlazewmClient | None = None
        self._connected = False

        # QML supplies the server after constructing the model.
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

    def _get_server_uri(self) -> str:
        return self._server_uri

    def _set_server_uri(self, value: str) -> None:
        if self._server_uri == value:
            return
        self._server_uri = value
        self.serverUriChanged.emit()
        self._start_timer.start()

    serverUri = pyqtProperty(str, _get_server_uri, _set_server_uri, notify=serverUriChanged)

    @pyqtProperty(bool, notify=connectionChanged)
    def connected(self) -> bool:
        return self._connected

    @property
    def client(self) -> GlazewmClient | None:
        """The live client, or None while disconnected."""
        return self._client if self._connected else None

    def _bind(self, client: GlazewmClient) -> None:
        """Connect the client's data signals."""

    def _unbind(self, client: GlazewmClient) -> None:
        """Disconnect what _bind connected."""

    def _reset(self) -> None:
        """Clear the data when the connection drops."""

    def _start(self) -> None:
        if self._client is not None:
            self._unbind(self._client)
            self._client.glazewm_connection_status.disconnect(self._on_connection)
            self._client.close()
            self._client.deleteLater()
        self._on_connection(False)
        self._client = GlazewmClient(self._server_uri, self.MESSAGES, parent=self)
        self._bind(self._client)
        self._client.glazewm_connection_status.connect(self._on_connection)
        self._client.connect()

    @pyqtSlot(bool)
    def _on_connection(self, connected: bool) -> None:
        if not connected:
            self._reset()
        if connected != self._connected:
            self._connected = connected
            self.connectionChanged.emit()

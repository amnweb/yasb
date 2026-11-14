from typing import ClassVar

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.services.glazewm.client import GlazewmClient

DEFAULT_SERVER_URI = "ws://localhost:6123"


class _SharedClient(QObject):
    """The GlazeWM connection every model with the same server and messages shares, open while one of them exists.

    A bar reload makes its new widgets before it deletes the old ones, so the connection and the data GlazeWM last
    sent outlive the reload, and the new widgets don't show GlazeWM offline while they connect again.
    """

    _shared: ClassVar[dict[tuple[str, tuple[str, ...]], _SharedClient]] = {}

    def __init__(self, uri: str, messages: list[str]) -> None:
        super().__init__()
        self.client = GlazewmClient(uri, messages, parent=self)
        self._users = 0
        # The last model leaves from its destroyed signal, while it is still connected to the client's signals
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(0)
        self._close_timer.timeout.connect(self.client.close)
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self.client.close)

    @classmethod
    def acquire(cls, uri: str, messages: list[str]) -> _SharedClient:
        key = (uri, tuple(messages))
        shared = cls._shared.get(key)
        if shared is None:
            shared = cls._shared[key] = cls(uri, messages)
        shared._users += 1
        shared._close_timer.stop()
        shared.client.connect()
        return shared

    @pyqtSlot()
    def release(self) -> None:
        self._users -= 1
        if self._users == 0:
            self._close_timer.start()


class GlazewmConnection(QObject):
    """Base for GlazeWM QML types: shares a connection to the server and moves to another when the server changes."""

    connectionChanged = pyqtSignal()
    serverUriChanged = pyqtSignal()

    # Subscription and queries sent on connect. Queries are re-sent after subscribed events.
    MESSAGES: ClassVar[list[str]] = []

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server_uri = DEFAULT_SERVER_URI
        self._shared: _SharedClient | None = None
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
        return self._shared.client if self._shared is not None and self._connected else None

    def _bind(self, client: GlazewmClient) -> None:
        """Connect the client's data signals and take the data it already has."""

    def _unbind(self, client: GlazewmClient) -> None:
        """Disconnect what _bind connected."""

    def _reset(self) -> None:
        """Clear the data when the connection drops."""

    def _start(self) -> None:
        if self._shared is not None:
            self._leave(self._shared)
        shared = _SharedClient.acquire(self._server_uri, self.MESSAGES)
        self._shared = shared
        self.destroyed.connect(shared.release)
        shared.client.glazewm_connection_status.connect(self._on_connection)
        self._on_connection(shared.client.connected)
        self._bind(shared.client)

    def _leave(self, shared: _SharedClient) -> None:
        self.destroyed.disconnect(shared.release)
        shared.client.glazewm_connection_status.disconnect(self._on_connection)
        self._unbind(shared.client)
        shared.release()
        self._on_connection(False)

    @pyqtSlot(bool)
    def _on_connection(self, connected: bool) -> None:
        if not connected:
            self._reset()
        if connected != self._connected:
            self._connected = connected
            self.connectionChanged.emit()

from time import monotonic

from PyQt6.QtNetwork import QHostAddress
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWebSockets import QWebSocketServer

from core.widgets.services.glazewm.client import GlazewmClient


def _wait_until(predicate):
    deadline = monotonic() + 6
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    return predicate()


def test_reconnects_after_server_closes_cleanly(qapp):
    server = QWebSocketServer("GlazeWM test", QWebSocketServer.SslMode.NonSecureMode)
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 0)
    initial_messages = ["sub -e workspace_updated", "query monitors"]
    client = GlazewmClient(f"ws://127.0.0.1:{server.serverPort()}", initial_messages)
    errors = QSignalSpy(client._websocket.errorOccurred)
    disconnected = QSignalSpy(client._websocket.disconnected)
    peers = []
    messages = []

    def accept_connection():
        peer = server.nextPendingConnection()
        peers.append(peer)
        messages.append([])
        peer.textMessageReceived.connect(messages[-1].append)

    server.newConnection.connect(accept_connection)
    try:
        client.connect()
        assert _wait_until(lambda: messages == [initial_messages])
        assert not client._reconnect_timer.isActive()

        peers[0].close()
        assert _wait_until(lambda: len(disconnected) == 1)
        assert len(errors) == 0
        assert _wait_until(lambda: messages == [initial_messages, initial_messages]), (
            f"Clean close emitted {len(disconnected)} disconnected signals and {len(errors)} errors. "
            f"Reconnect timer active: {client._reconnect_timer.isActive()}. Messages: {messages}"
        )
        assert not client._reconnect_timer.isActive()
    finally:
        client._websocket.abort()
        client._reconnect_timer.stop()
        for peer in peers:
            peer.abort()
            peer.deleteLater()
        server.close()

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


def connection(kind: str, name: str, **fields: Any) -> dict[str, Any]:
    """A connection as the watcher reports it."""
    return {
        "kind": kind,
        "name": name,
        "ssid": name if kind == "wifi" else "",
        "mobileType": "",
        "adapter": {"wifi": "Wi-Fi", "ethernet": "Ethernet"}.get(kind, name),
        "adapterId": f"{kind}-id",
        "ipAddress": "",
        "connectivity": "internet",
        "metered": False,
        "signal": -1,
        **fields,
    }


class FakeWatcher(QObject):
    """Stands in for ConnectionWatcher.instance(), without reading Windows."""

    changed = pyqtSignal(object)
    networkChanged = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.connection: dict[str, Any] = {}
        self.subscribers: dict[int, int] = {}

    def subscribe(self, key: int, signal_interval: int = 0) -> None:
        self.subscribers[key] = signal_interval

    def unsubscribe(self, key: int) -> None:
        self.subscribers.pop(key, None)

    def change(self, connection: dict[str, Any]) -> None:
        self.connection = connection
        self.changed.emit(connection)
        self.networkChanged.emit()

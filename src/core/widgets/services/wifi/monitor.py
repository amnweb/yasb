import logging
import queue
import threading
from collections.abc import Callable
from typing import Any, override

from PyQt6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from winrt.windows.devices.wifi import WiFiConnectionStatus

from core.utils.qml import qml_property
from core.utils.win32.constants import WlanNotificationAcm
from core.widgets.services.wifi import wlan
from core.widgets.services.wifi.connection import ConnectionMonitor
from core.widgets.services.wifi.wlan import Network, ScanStatus, WlanClient

logger = logging.getLogger("wifi_widget")

MIN_INTERVAL_MS = 500
MAX_INTERVAL_MS = 60000
# Some adapters never report the end of a scan
SCAN_TIMEOUT_MS = 10000
ERROR_SHOWN_MS = 4000

ROLES = ["ssid", "hidden", "quality", "secured", "connected", "known", "autoConnect"]

# Error messages and the settings pages that fix them.
SCAN_ERRORS = {
    ScanStatus.ACCESS_DENIED: ("Location services are turned off", "ms-settings:privacy-location"),
    ScanStatus.ADAPTER_OFF: ("Wi-Fi is turned off", "ms-settings:network-wifi"),
    ScanStatus.UNAVAILABLE: ("Wi-Fi is not available", ""),
    ScanStatus.ERROR: ("Could not search for networks", ""),
}
CONNECT_ERRORS = {
    WiFiConnectionStatus.INVALID_CREDENTIAL: "Wrong password",
    WiFiConnectionStatus.NETWORK_NOT_AVAILABLE: "Network not available",
    WiFiConnectionStatus.TIMEOUT: "The connection timed out",
    WiFiConnectionStatus.ACCESS_REVOKED: "Access to Wi-Fi was revoked",
    WiFiConnectionStatus.UNSUPPORTED_AUTHENTICATION_PROTOCOL: "This network's security is not supported",
}
# Notifications that change the network list.
LIST_CHANGES = {
    WlanNotificationAcm.SCAN_COMPLETE,
    WlanNotificationAcm.SCAN_LIST_REFRESH,
    WlanNotificationAcm.CONNECTION_COMPLETE,
    WlanNotificationAcm.DISCONNECTED,
    WlanNotificationAcm.PROFILE_CHANGE,
}


def network_row(network: Network) -> dict[str, Any]:
    return {
        "ssid": network.ssid,
        "hidden": network.ssid == "",
        "quality": network.quality,
        "secured": network.secured,
        "connected": network.connected,
        "known": network.profile != "",
        "autoConnect": network.auto_connect,
    }


def sort_networks(networks: list[Network]) -> list[Network]:
    """Sort connected networks first, then by quality, with hidden networks last."""
    return sorted(networks, key=lambda network: (not network.connected, network.ssid == "", -network.quality))


class NetworkList(QAbstractListModel):
    """Network rows keyed by SSID. In-place updates preserve open row state."""

    countChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < len(self._rows) or not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        return self._rows[index.row()][ROLES[role - Qt.ItemDataRole.UserRole]]

    @qml_property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def update(self, rows: list[dict[str, Any]]) -> None:
        count = len(self._rows)
        wanted = {row["ssid"] for row in rows}
        for index in reversed(range(len(self._rows))):
            if self._rows[index]["ssid"] not in wanted:
                self.beginRemoveRows(QModelIndex(), index, index)
                del self._rows[index]
                self.endRemoveRows()
        for index, row in enumerate(rows):
            current = next((i for i in range(index, len(self._rows)) if self._rows[i]["ssid"] == row["ssid"]), -1)
            if current == -1:
                self.beginInsertRows(QModelIndex(), index, index)
                self._rows.insert(index, dict(row))
                self.endInsertRows()
                continue
            if current != index:
                self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), index)
                self._rows.insert(index, self._rows.pop(current))
                self.endMoveRows()
            if self._rows[index] != row:
                self._rows[index] = dict(row)
                self.dataChanged.emit(self.index(index), self.index(index))
        if len(self._rows) != count:
            self.countChanged.emit()

    def find(self, ssid: str) -> dict[str, Any] | None:
        return next((row for row in self._rows if row["ssid"] == ssid), None)


class WlanWorker:
    """Run WLAN requests serially on one thread so closing cannot race a scan."""

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[Callable[[], None] | None] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None

    def submit(self, work: Callable[[], None]) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="WlanWorker", daemon=True)
            self._thread.start()
        self._queue.put(work)

    def stop(self) -> None:
        """Finish queued requests before stopping the thread."""
        if self._thread is not None:
            self._queue.put(None)
            self._thread = None

    def _run(self) -> None:
        while (work := self._queue.get()) is not None:
            try:
                work()
            except RuntimeError:
                # The widget was destroyed while the request was running.
                pass
            except Exception:
                logger.exception("Wi-Fi request failed")


class WifiMonitor(QObject):
    """Report connection status and, while watching, nearby Wi-Fi networks."""

    statusChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    _networksRead = pyqtSignal(object)
    _scanned = pyqtSignal(str, object)
    _notified = pyqtSignal(int)
    _connected = pyqtSignal(str, int)
    _done = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._update_interval = 1000
        self._exact_strength = False
        self._watching = False
        self._networks = NetworkList(self)
        self._scanning = False
        # SSID being joined; empty for a hidden network, None when idle.
        self._connecting: str | None = None
        self._error = ""
        self._error_link = ""
        # WLAN handle calls run on the worker because they may block on the service.
        self._wlan = WlanClient(self._notified.emit)
        self._worker = WlanWorker()
        self._monitor = ConnectionMonitor.instance()
        self._status = self._monitor.status
        self._monitor.statusChanged.connect(self._on_status)
        self._networksRead.connect(self._on_networks)
        self._scanned.connect(self._on_scanned)
        self._notified.connect(self._on_notification)
        self._connected.connect(self._on_connected)
        self._done.connect(self._after_change)

        # Start polling after QML applies the interval.
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._subscribe)
        self._start_timer.start()

        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.setInterval(SCAN_TIMEOUT_MS)
        self._scan_timer.timeout.connect(self._on_scan_finished)

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(ERROR_SHOWN_MS)
        self._error_timer.timeout.connect(lambda: self._set_error(""))

        monitor, key, client, worker = self._monitor, id(self), self._wlan, self._worker

        def release() -> None:
            monitor.unsubscribe(key)
            worker.submit(client.close)
            worker.stop()

        self.destroyed.connect(release)

    # {kind: wifi, ethernet or none, name, strength: 0 to 100 or -1, ipAddress}
    @qml_property("QVariantMap", notify=statusChanged)
    def status(self) -> dict[str, Any]:
        return self._status

    def _get_update_interval(self) -> int:
        return self._update_interval

    def _set_update_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value != self._update_interval:
            self._update_interval = value
            self.settingsChanged.emit()
            self._subscribe()

    updateInterval = pyqtProperty(int, _get_update_interval, _set_update_interval, notify=settingsChanged)

    def _get_exact_strength(self) -> bool:
        return self._exact_strength

    def _set_exact_strength(self, value: bool) -> None:
        if value != self._exact_strength:
            self._exact_strength = value
            self.settingsChanged.emit()
            self._subscribe()

    # Use WLAN quality instead of signal bars in 25-point steps.
    exactStrength = pyqtProperty(bool, _get_exact_strength, _set_exact_strength, notify=settingsChanged)

    def _get_watching(self) -> bool:
        return self._watching

    def _set_watching(self, value: bool) -> None:
        if value == self._watching:
            return
        self._watching = value
        self.settingsChanged.emit()
        if value:
            self.scan()
        else:
            self._worker.submit(self._wlan.close)
            self._scan_timer.stop()
            self._scanning = False
            self.stateChanged.emit()

    # Scan and track networks while the popup is open.
    watching = pyqtProperty(bool, _get_watching, _set_watching, notify=settingsChanged)

    # [{ssid, hidden, quality, secured, connected, known, autoConnect}], connected first
    @qml_property(QObject, constant=True)
    def networks(self) -> NetworkList:
        return self._networks

    @qml_property(bool, notify=stateChanged)
    def scanning(self) -> bool:
        return self._scanning

    @qml_property(bool, notify=stateChanged)
    def connecting(self) -> bool:
        return self._connecting is not None

    # SSID being joined; empty for a hidden network.
    @qml_property(str, notify=stateChanged)
    def connectingTo(self) -> str:
        return self._connecting or ""

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    # Settings page for the error, or empty if none.
    @qml_property(str, notify=stateChanged)
    def errorLink(self) -> str:
        return self._error_link

    def _subscribe(self) -> None:
        self._monitor.subscribe(id(self), self._update_interval, self._exact_strength)

    def _on_status(self, status: dict[str, Any]) -> None:
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

    def _set_error(self, error: str, link: str = "") -> None:
        if (error, link) != (self._error, self._error_link):
            self._error, self._error_link = error, link
            self.stateChanged.emit()

    def _run(self, work: Callable[[], None]) -> None:
        """Run WinRT calls separately so the serialized WLAN queue stays responsive."""

        def run() -> None:
            try:
                work()
            except RuntimeError:
                # The widget was destroyed while the request was running.
                pass
            except Exception:
                logger.exception("Wi-Fi request failed")

        threading.Thread(target=run, daemon=True).start()

    @pyqtSlot()
    def scan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self._scan_timer.start()
        self.stateChanged.emit()
        client = self._wlan

        def scan() -> None:
            result = client.scan()
            # Keep the previous results until the new scan finishes.
            self._scanned.emit(str(result), client.networks() if result == ScanStatus.SUCCESS else [])

        self._worker.submit(scan)

    def _on_scanned(self, result: str, networks: list[Network]) -> None:
        if result != ScanStatus.SUCCESS:
            self._scan_timer.stop()
            self._scanning = False
            self._set_error(*SCAN_ERRORS[ScanStatus(result)])
            self._networks.update([])
            self.stateChanged.emit()
            return
        # Keep connection errors until their timer expires; clear scan errors on success.
        if not self._error_timer.isActive():
            self._set_error("")
        self._on_networks(networks)

    def _read_networks(self) -> None:
        if not self._watching:
            return
        client = self._wlan
        self._worker.submit(lambda: self._networksRead.emit(client.networks()))

    def _after_change(self) -> None:
        if self._watching:
            self._read_networks()
        else:
            # The change reopened the handle after the popup closed.
            self._worker.submit(self._wlan.close)

    def _on_networks(self, networks: list[Network]) -> None:
        if not self._watching:
            return
        # Keep existing results if an adapter briefly reports no networks between scans.
        if not networks and self._networks.count:
            return
        self._networks.update([network_row(network) for network in sort_networks(networks)])

    def _on_notification(self, code: int) -> None:
        if code in (WlanNotificationAcm.SCAN_COMPLETE, WlanNotificationAcm.SCAN_FAIL):
            self._on_scan_finished()
        elif code in (WlanNotificationAcm.CONNECTION_COMPLETE, WlanNotificationAcm.DISCONNECTED):
            self._monitor.refresh()
        if code in LIST_CHANGES:
            self._read_networks()

    def _on_scan_finished(self) -> None:
        self._scan_timer.stop()
        if self._scanning:
            self._scanning = False
            self.stateChanged.emit()
            self._read_networks()

    @pyqtSlot(str, str, bool)
    def connectTo(self, ssid: str, password: str, autoConnect: bool) -> None:
        """Join a network, with its saved profile when the password is empty."""
        self._connect(ssid, password, autoConnect, False)

    @pyqtSlot(str, str, bool)
    def connectHidden(self, ssid: str, password: str, autoConnect: bool) -> None:
        """Join a hidden network using the name entered by the user."""
        self._connect(ssid, password, autoConnect, True)

    def _connect(self, ssid: str, password: str, auto_connect: bool, hidden: bool) -> None:
        if self._connecting is not None or not ssid:
            return
        self._connecting = "" if hidden else ssid
        self._error_timer.stop()
        self._set_error("")
        self.stateChanged.emit()
        self._run(lambda: self._connected.emit(ssid, int(wlan.connect(ssid, password, auto_connect, hidden))))

    def _on_connected(self, ssid: str, result: int) -> None:
        self._connecting = None
        status = WiFiConnectionStatus(result)
        if status != WiFiConnectionStatus.SUCCESS:
            logger.debug("Could not connect to the network: %s", status.name)
            self._set_error(CONNECT_ERRORS.get(status, "Could not connect"))
            self._error_timer.start()
        self.stateChanged.emit()
        self._monitor.refresh()
        self._read_networks()

    @pyqtSlot()
    def disconnectNetwork(self) -> None:
        def disconnect() -> None:
            wlan.disconnect()
            self._done.emit()

        self._run(disconnect)

    @pyqtSlot(str)
    def forget(self, ssid: str) -> None:
        client = self._wlan

        def forget() -> None:
            if (profile := _profile(client, ssid)) is not None:
                client.forget(profile)
                self._done.emit()

        self._worker.submit(forget)

    @pyqtSlot(str, bool)
    def setAutoConnect(self, ssid: str, autoConnect: bool) -> None:
        client = self._wlan
        connected = bool((row := self._networks.find(ssid)) and row["connected"])

        def reconnect() -> None:
            wlan.connect(ssid, "", autoConnect)
            self._done.emit()

        def change() -> None:
            if (profile := _profile(client, ssid)) is None:
                return
            client.set_auto_connect(profile, autoConnect)
            self._done.emit()
            # Windows disconnects when the active profile changes.
            if connected:
                self._run(reconnect)

        self._worker.submit(change)


def _profile(client: WlanClient, ssid: str) -> str | None:
    networks = client.networks(profiles=False)
    return next((network.profile for network in networks if network.ssid == ssid and network.profile), None)

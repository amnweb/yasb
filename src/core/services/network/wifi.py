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
from winrt.windows.devices.radios import Radio, RadioAccessStatus, RadioKind, RadioState
from winrt.windows.devices.wifi import WiFiConnectionStatus
from winrt.windows.foundation import EventRegistrationToken

from core.services.network import wlan
from core.services.network.wlan import ScanStatus, WifiNetwork, WlanClient
from core.utils.qml import qml_property
from core.utils.win32.constants import E_ACCESSDENIED, WlanNotificationAcm
from core.utils.win32.structs import WLAN_NOTIFICATION_DATA

logger = logging.getLogger("network")

# Some adapters never report the end of a scan
SCAN_TIMEOUT_MS = 10000
ERROR_SHOWN_MS = 4000

ROLES = ["ssid", "hidden", "quality", "secured", "connected", "known", "autoConnect"]

SCAN_ERRORS = {ScanStatus.ACCESS_DENIED: "accessDenied", ScanStatus.ERROR: "scanFailed"}
CONNECT_ERRORS = {
    WiFiConnectionStatus.INVALID_CREDENTIAL: "invalidCredential",
    WiFiConnectionStatus.NETWORK_NOT_AVAILABLE: "networkNotAvailable",
    WiFiConnectionStatus.TIMEOUT: "timeout",
    WiFiConnectionStatus.ACCESS_REVOKED: "accessRevoked",
    WiFiConnectionStatus.UNSUPPORTED_AUTHENTICATION_PROTOCOL: "unsupportedAuthenticationProtocol",
}
# Notifications that change the network list.
LIST_CHANGES = {
    WlanNotificationAcm.SCAN_COMPLETE,
    WlanNotificationAcm.SCAN_LIST_REFRESH,
    WlanNotificationAcm.CONNECTION_COMPLETE,
    WlanNotificationAcm.DISCONNECTED,
    WlanNotificationAcm.PROFILE_CHANGE,
}


def network_row(network: WifiNetwork) -> dict[str, Any]:
    return {
        "ssid": network.ssid,
        "hidden": network.ssid == "",
        "quality": network.quality,
        "secured": network.secured,
        "connected": network.connected,
        "known": network.profile != "",
        "autoConnect": network.auto_connect,
    }


def sort_networks(networks: list[WifiNetwork]) -> list[WifiNetwork]:
    """Sort connected networks first, then by quality, with hidden networks last."""
    return sorted(networks, key=lambda network: (not network.connected, network.ssid == "", -network.quality))


def wifi_radio() -> Radio | None:
    return next((radio for radio in Radio.get_radios_async().get() if radio.kind == RadioKind.WI_FI), None)


class WifiNetworkList(QAbstractListModel):
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
    """Run WLAN and radio requests serially on one thread so closing cannot race a scan."""

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[Callable[[], None] | None] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None

    def submit(self, work: Callable[[], None]) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="WlanWorker", daemon=True)
            self._thread.start()
        self._queue.put(work)

    def stop(self, *final: Callable[[], None]) -> None:
        """Finish queued requests and these final ones, then stop the thread. A worker that never ran does nothing."""
        if self._thread is not None:
            for work in final:
                self._queue.put(work)
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


class RadioWatch:
    """The Wi-Fi radio's state handler while the list is watched. Used only on the worker thread."""

    def __init__(self, on_state: Callable[[bool], None]) -> None:
        self._on_state = on_state
        self._watched: tuple[Radio, EventRegistrationToken] | None = None

    def start(self) -> None:
        if self._watched is not None or (radio := wifi_radio()) is None:
            return
        token = radio.add_state_changed(lambda sender, _args: self._on_state(sender.state == RadioState.ON))
        self._watched = radio, token
        self._on_state(radio.state == RadioState.ON)

    def stop(self) -> None:
        if self._watched is not None:
            radio, token = self._watched
            radio.remove_state_changed(token)
            self._watched = None


class WifiNetworks(QObject):
    """Nearby Wi-Fi networks and the Wi-Fi switch, scanned and tracked while watching."""

    settingsChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    _networksRead = pyqtSignal(object)
    _scanned = pyqtSignal(str, object)
    _notified = pyqtSignal(int)
    _connected = pyqtSignal(str)
    _failed = pyqtSignal(str)
    _radio = pyqtSignal(bool)
    _done = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watching = False
        self._networks = WifiNetworkList(self)
        self._available = False
        self._enabled = True
        self._scanning = False
        # SSID being joined; empty for a hidden network, None when idle.
        self._connecting: str | None = None
        self._error = ""
        # WLAN handle calls run on the worker because they may block on the service.
        self._wlan = WlanClient(self._on_wlan)
        self._worker = WlanWorker()
        self._radio_watch = RadioWatch(self._radio.emit)
        self._networksRead.connect(self._on_networks)
        self._scanned.connect(self._on_scanned)
        self._notified.connect(self._on_notification)
        self._connected.connect(self._on_connected)
        self._failed.connect(self._on_failed)
        self._radio.connect(self._on_radio)
        self._done.connect(self._after_change)

        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.setInterval(SCAN_TIMEOUT_MS)
        self._scan_timer.timeout.connect(self._on_scan_timeout)

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(ERROR_SHOWN_MS)
        self._error_timer.timeout.connect(self._clear_error)

        client, worker, radio_watch = self._wlan, self._worker, self._radio_watch
        # The radio watch and the WLAN handle exist only once the worker has run.
        self.destroyed.connect(lambda: worker.stop(radio_watch.stop, client.close))

    def _get_watching(self) -> bool:
        return self._watching

    def _set_watching(self, value: bool) -> None:
        if value == self._watching:
            return
        self._watching = value
        self.settingsChanged.emit()
        if value:
            # The radio watch reports the current state, and turning Wi-Fi on scans.
            self._worker.submit(self._radio_watch.start)
            if self._enabled:
                self.scan()
        else:
            self._worker.submit(self._radio_watch.stop)
            self._worker.submit(self._wlan.close)
            self._scan_timer.stop()
            self._scanning = False
            self.stateChanged.emit()

    # Scan and track networks while the popup is open.
    watching = pyqtProperty(bool, _get_watching, _set_watching, notify=settingsChanged)

    # [{ssid, hidden, quality, secured, connected, known, autoConnect}], connected first
    @qml_property(QObject, constant=True)
    def networks(self) -> WifiNetworkList:
        return self._networks

    # The PC has a Wi-Fi adapter, known after the first scan.
    @qml_property(bool, notify=stateChanged)
    def available(self) -> bool:
        return self._available

    # Wi-Fi is turned on.
    @qml_property(bool, notify=stateChanged)
    def enabled(self) -> bool:
        return self._enabled

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

    # Empty, or accessDenied (location access is off), scanFailed, radioDenied, connectFailed, invalidCredential,
    # networkNotAvailable, timeout, accessRevoked or unsupportedAuthenticationProtocol
    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    def _clear_error(self) -> None:
        if self._error:
            self._error = ""
            self.stateChanged.emit()

    def _on_wlan(self, data: WLAN_NOTIFICATION_DATA) -> None:
        self._notified.emit(data.NotificationCode)

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

    def _on_scanned(self, result: str, networks: list[WifiNetwork]) -> None:
        status = ScanStatus(result)
        self._available = status != ScanStatus.UNAVAILABLE
        if status in (ScanStatus.SUCCESS, ScanStatus.ADAPTER_OFF):
            self._enabled = status == ScanStatus.SUCCESS
        if status != ScanStatus.SUCCESS:
            self._scan_timer.stop()
            self._scanning = False
            self._error_timer.stop()
            self._error = SCAN_ERRORS.get(status, "")
            self._networks.update([])
            self.stateChanged.emit()
            return
        # Keep connection errors until their timer expires; clear scan errors on success.
        if not self._error_timer.isActive():
            self._error = ""
        self.stateChanged.emit()
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

    def _on_networks(self, networks: list[WifiNetwork]) -> None:
        if not self._watching:
            return
        # Keep existing results if an adapter briefly reports no networks between scans.
        if not networks and self._networks.count:
            return
        self._networks.update([network_row(network) for network in sort_networks(networks)])

    def _on_notification(self, code: int) -> None:
        if code in (WlanNotificationAcm.SCAN_COMPLETE, WlanNotificationAcm.SCAN_FAIL):
            self._on_scan_finished()
        elif code in (WlanNotificationAcm.INTERFACE_ARRIVAL, WlanNotificationAcm.INTERFACE_REMOVAL):
            if self._watching:
                self.scan()
        if code in LIST_CHANGES:
            self._read_networks()

    def _on_scan_timeout(self) -> None:
        self._on_scan_finished()
        self._read_networks()

    def _on_scan_finished(self) -> None:
        self._scan_timer.stop()
        if self._scanning:
            self._scanning = False
            self.stateChanged.emit()

    def _on_radio(self, on: bool) -> None:
        if on == self._enabled:
            return
        self._enabled = on
        if not on:
            # A scan cannot finish once the radio is off, and its results and errors no longer apply.
            self._scan_timer.stop()
            self._scanning = False
            self._networks.update([])
            if self._error in SCAN_ERRORS.values():
                self._error = ""
        self.stateChanged.emit()
        if on and self._watching:
            self.scan()

    @pyqtSlot(bool)
    def setEnabled(self, on: bool) -> None:
        """Turn Wi-Fi on or off, as the Wi-Fi switch in Windows does. Windows may ask the user the first time."""

        def change() -> None:
            if Radio.request_access_async().get() != RadioAccessStatus.ALLOWED:
                self._failed.emit("radioDenied")
                return
            if (radio := wifi_radio()) is not None:
                radio.set_state_async(RadioState.ON if on else RadioState.OFF).get()

        self._worker.submit(change)

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
        self._error = ""
        self.stateChanged.emit()

        def join() -> None:
            # Always answer, so a failure cannot leave the network connecting.
            error = "connectFailed"
            try:
                status = wlan.connect(ssid, password, auto_connect, hidden)
                error = "" if status == WiFiConnectionStatus.SUCCESS else CONNECT_ERRORS.get(status, error)
            except OSError as problem:
                logger.debug("Could not connect to the network: %s", problem)
                if problem.winerror == E_ACCESSDENIED:
                    error = "accessDenied"
            finally:
                self._connected.emit(error)

        self._run(join)

    def _on_connected(self, error: str) -> None:
        self._connecting = None
        if error:
            self._on_failed(error)
        else:
            self.stateChanged.emit()
        self._read_networks()

    def _on_failed(self, error: str) -> None:
        logger.debug("Wi-Fi request failed: %s", error)
        self._error = error
        self._error_timer.start()
        self.stateChanged.emit()

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

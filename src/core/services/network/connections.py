"""The network connection Windows uses for internet, read again when Windows reports a network change."""

import ctypes
import logging
import threading
from collections.abc import Iterator
from typing import Any, cast

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtProperty, pyqtSignal
from winrt.windows.networking.connectivity import (
    ConnectionProfile,
    ConnectionProfileFilter,
    NetworkAdapter,
    NetworkConnectivityLevel,
    NetworkCostType,
    NetworkInformation,
    WwanDataClass,
)
from winrt.windows.security.authorization.appcapabilityaccess import AppCapability, AppCapabilityAccessStatus

from core.services.network.adapters import adapter_key, read_adapter
from core.services.network.wlan import WlanClient
from core.utils.qml import qml_property
from core.utils.win32.constants import E_INVALIDARG, WLAN_NOTIFICATION_SOURCE_MSM, WlanNotificationMsm
from core.utils.win32.structs import WLAN_NOTIFICATION_DATA

logger = logging.getLogger("network")

MIN_INTERVAL_MS = 500
MAX_INTERVAL_MS = 60000
# IANA interface types of Ethernet and of mobile broadband adapters (GSM and CDMA)
ETHERNET = 6
MOBILE_BROADBAND = (243, 244)
# The network type Windows shows after a mobile operator's name, by data class, newest first
MOBILE_TYPES = (
    (WwanDataClass.NEW_RADIO_NON_STANDALONE | WwanDataClass.NEW_RADIO_STANDALONE, "5G"),
    (WwanDataClass.LTE_ADVANCED, "LTE"),
    (WwanDataClass.UMTS | WwanDataClass.HSDPA | WwanDataClass.HSUPA, "3G"),
    (WwanDataClass.GPRS | WwanDataClass.EDGE, "2G"),
)

CONNECTIVITY = {
    NetworkConnectivityLevel.NONE: "none",
    NetworkConnectivityLevel.LOCAL_ACCESS: "local",
    NetworkConnectivityLevel.CONSTRAINED_INTERNET_ACCESS: "constrained",
    NetworkConnectivityLevel.INTERNET_ACCESS: "internet",
}

DISCONNECTED: dict[str, Any] = {
    "kind": "none",
    "name": "",
    "ssid": "",
    "mobileType": "",
    "adapter": "",
    "adapterId": "",
    "ipAddress": "",
    "connectivity": "none",
    "metered": False,
    "signal": -1,
}


def _internet_profile() -> ConnectionProfile | None:
    # WinRT stubs mark the result as required, but Windows returns None when offline.
    return cast(ConnectionProfile | None, NetworkInformation.get_internet_connection_profile())


def _network_adapter(profile: ConnectionProfile | None) -> NetworkAdapter | None:
    if profile is None:
        return None
    try:
        # WinRT stubs mark the adapter as required, but Windows can return None.
        return cast(NetworkAdapter | None, profile.network_adapter)
    except OSError as error:
        # Some profiles, such as a VPN's in the connected list, raise this instead.
        if error.winerror != E_INVALIDARG:
            raise
        return None


def _adapter_id(profile: ConnectionProfile | None) -> str | None:
    adapter = _network_adapter(profile)
    return str(adapter.network_adapter_id) if adapter is not None else None


def _profiles() -> Iterator[ConnectionProfile | None]:
    """The internet profile, then every connected one. Windows can leave a VPN out of the connected profiles."""
    yield _internet_profile()
    connected = ConnectionProfileFilter()
    connected.is_connected = True
    yield from NetworkInformation.find_connection_profiles_async(connected).get()


def connection_profile(adapter_id: str) -> ConnectionProfile | None:
    """A fresh profile of the connection on this adapter; profiles Windows returned earlier do not update."""
    return next((profile for profile in _profiles() if _adapter_id(profile) == adapter_id), None)


def _mobile_type(profile: ConnectionProfile) -> str:
    # Only profiles Windows marks as cellular have details, unlike the one it reports while mobile data reconnects.
    if not profile.is_wwan_connection_profile:
        return ""
    data_class = profile.wwan_connection_profile_details.get_current_data_class()
    return next((text for data_classes, text in MOBILE_TYPES if data_class & data_classes), "")


def _connection(profile: ConnectionProfile, network_adapter: NetworkAdapter) -> dict[str, Any]:
    adapter_id = str(network_adapter.network_adapter_id)
    adapter = read_adapter(adapter_id)
    cost = profile.get_connection_cost()
    if profile.is_wlan_connection_profile:
        kind = "wifi"
    elif network_adapter.iana_interface_type == ETHERNET:
        kind = "ethernet"
    elif network_adapter.iana_interface_type in MOBILE_BROADBAND:
        kind = "mobile"
    else:
        kind = "other"
    mobile = kind == "mobile"
    # Windows shows Wi-Fi in up to 4 bars, which need no location access, and mobile in up to 5.
    full_bars = 5 if mobile else 4
    bars = profile.get_signal_bars()
    return {
        "kind": kind,
        # A mobile profile is named with an id; Windows shows the operator's network name instead.
        "name": next(iter(profile.get_network_names()), "") if mobile else profile.profile_name,
        "ssid": profile.wlan_connection_profile_details.get_connected_ssid() if kind == "wifi" else "",
        "mobileType": _mobile_type(profile) if mobile else "",
        "adapter": adapter.name if adapter is not None else "",
        "adapterId": adapter_id,
        "ipAddress": adapter.ip_address if adapter is not None else "",
        "connectivity": CONNECTIVITY.get(profile.get_network_connectivity_level(), "none"),
        "metered": cost.network_cost_type in (NetworkCostType.FIXED, NetworkCostType.VARIABLE),
        "signal": min(bars, full_bars) * 100 // full_bars if bars is not None else -1,
    }


def read_connection(interface: str = "auto") -> dict[str, Any] | None:
    """The connection Windows uses for internet, or with an adapter name such as Ethernet the one on that adapter."""
    if interface == "auto":
        profile = _internet_profile()
    else:
        key = adapter_key(interface)
        profile = connection_profile(key) if key is not None else None
    network_adapter = _network_adapter(profile)
    if profile is None or network_adapter is None:
        return None
    return _connection(profile, network_adapter)


class ConnectionWatcher(QObject):
    """The internet connection, shared by all widgets. Windows' network change events wake one worker thread. While a
    widget shows the signal of a Wi-Fi connection, Windows reports each change of the exact signal while location access
    is on, and reports each change of that access; without it, and for a mobile connection, the bars are read again on
    a timer."""

    # The internet connection, when it changes
    changed = pyqtSignal(object)
    # Each network change Windows reports, for widgets that read a connection of their own
    networkChanged = pyqtSignal()

    _instance: ConnectionWatcher | None = None

    @classmethod
    def instance(cls) -> ConnectionWatcher:
        if cls._instance is None:
            cls._instance = ConnectionWatcher()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        # Replaced, never changed in place, so other threads can read it.
        self.connection: dict[str, Any] = DISCONNECTED
        # Each subscriber's signal refresh interval in ms, 0 when it does not show the signal.
        self._subscribers: dict[int, int] = {}
        # Exact Wi-Fi signal quality by adapter id, from WLAN events.
        self._qualities: dict[str, int] = {}
        # This process's location access, which Windows signal changes need.
        self._location_allowed = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._network_changed = threading.Event()
        self._stopping = False
        self._thread: threading.Thread | None = None
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self.stop)

    def subscribe(self, key: int, signal_interval: int = 0) -> None:
        with self._lock:
            self._subscribers[key] = signal_interval
        # Set before the thread starts, so its first read includes this subscriber.
        self._network_changed.set()
        if self._thread is None and not self._stopping:
            self._thread = threading.Thread(target=self._run, name="ConnectionWatcher", daemon=True)
            self._thread.start()
        self._wake.set()

    def unsubscribe(self, key: int) -> None:
        with self._lock:
            self._subscribers.pop(key, None)
        self._wake.set()

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._thread is not None:
            self._thread.join(2)
            self._thread = None

    def _on_network_changed(self) -> None:
        self._network_changed.set()
        self._wake.set()
        self.networkChanged.emit()

    def _on_location_changed(self, location: AppCapability) -> None:
        # Windows reports every change of the location settings, so act only when this process's access changes.
        allowed = location.check_access() == AppCapabilityAccessStatus.ALLOWED
        with self._lock:
            if allowed == self._location_allowed:
                return
            self._location_allowed = allowed
        self._network_changed.set()
        self._wake.set()

    def _on_wlan(self, data: WLAN_NOTIFICATION_DATA) -> None:
        if data.NotificationCode != WlanNotificationMsm.SIGNAL_QUALITY_CHANGE or not data.pData:
            return
        quality = int(ctypes.cast(data.pData, ctypes.POINTER(ctypes.c_ulong)).contents.value)
        with self._lock:
            self._qualities = {**self._qualities, str(data.InterfaceGuid.to_uuid()): quality}
        self._wake.set()

    def _run(self) -> None:
        token = NetworkInformation.add_network_status_changed(lambda _sender: self._on_network_changed())
        location = AppCapability.create("location")
        location_token = location.add_access_changed(lambda sender, _args: self._on_location_changed(sender))
        self._on_location_changed(location)
        wlan = WlanClient(self._on_wlan, WLAN_NOTIFICATION_SOURCE_MSM)
        try:
            while not self._stopping:
                self._wake.clear()
                with self._lock:
                    subscribed = bool(self._subscribers)
                    intervals = [interval for interval in self._subscribers.values() if interval]
                connection = self.connection
                if subscribed and self._network_changed.is_set():
                    self._network_changed.clear()
                    connection = self._read(wlan, bool(intervals))
                with self._lock:
                    quality = self._qualities.get(connection["adapterId"])
                if connection["kind"] == "wifi" and quality is not None:
                    connection = {**connection, "signal": quality}
                if connection != self.connection and not self._stopping:
                    self.connection = connection
                    self.changed.emit(connection)
                # Windows reports no change of the bars, only of the exact Wi-Fi signal with location access.
                polling = bool(intervals) and (
                    connection["kind"] == "mobile" or (connection["kind"] == "wifi" and quality is None)
                )
                if not self._wake.wait(min(intervals) / 1000 if polling else None):
                    # Profiles do not update, so the bars are read with the connection again.
                    self._network_changed.set()
        finally:
            NetworkInformation.remove_network_status_changed(token)
            location.remove_access_changed(location_token)
            wlan.close()

    def _read(self, wlan: WlanClient, showing_signal: bool) -> dict[str, Any]:
        try:
            connection = read_connection() or DISCONNECTED
        except Exception:
            logger.exception("Could not read the network connection")
            connection = DISCONNECTED
        with self._lock:
            location_allowed = self._location_allowed
        qualities: dict[str, int] = {}
        # Signal changes and quality need location access. A closed handle registers again when access returns.
        if showing_signal and location_allowed and connection["kind"] == "wifi":
            if wlan.open() and wlan.notifying:
                qualities = wlan.connected_qualities()
        else:
            wlan.close()
        with self._lock:
            self._qualities = qualities
        return connection


class NetworkConnections(QObject):
    """The network connection Windows uses for internet."""

    primaryChanged = pyqtSignal()
    settingsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._signal_interval = 1000
        self._watcher = ConnectionWatcher.instance()
        self._primary = self._watcher.connection
        self._watcher.changed.connect(self._on_changed)

        # Subscribe after QML applies the interval.
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._subscribe)
        self._start_timer.start()

        watcher, key = self._watcher, id(self)
        self.destroyed.connect(lambda: watcher.unsubscribe(key))

    # {kind: wifi, ethernet, mobile, other or none, name, ssid, mobileType: 5G, LTE, 3G, 2G or empty, adapter,
    #  adapterId, ipAddress, connectivity: none, local, constrained or internet, metered, signal: 0 to 100 or -1}
    @qml_property("QVariantMap", notify=primaryChanged)
    def primary(self) -> dict[str, Any]:
        return self._primary

    def _get_signal_interval(self) -> int:
        return self._signal_interval

    def _set_signal_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value != self._signal_interval:
            self._signal_interval = value
            self.settingsChanged.emit()
            self._subscribe()

    # How often to read the signal bars of Wi-Fi without location access and of mobile.
    signalInterval = pyqtProperty(int, _get_signal_interval, _set_signal_interval, notify=settingsChanged)

    def _subscribe(self) -> None:
        self._watcher.subscribe(id(self), self._signal_interval)

    def _on_changed(self, connection: dict[str, Any]) -> None:
        if connection != self._primary:
            self._primary = connection
            self.primaryChanged.emit()

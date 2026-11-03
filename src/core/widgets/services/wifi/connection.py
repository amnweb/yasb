import logging
import threading
from typing import Any, cast

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal
from winrt.windows.networking import HostNameType
from winrt.windows.networking.connectivity import ConnectionProfile, IPInformation, NetworkAdapter, NetworkInformation

from core.widgets.services.wifi.wlan import WlanClient

logger = logging.getLogger("wifi_widget")

# kind is wifi, ethernet or none; strength is 0 to 100, and -1 without Wi-Fi
DISCONNECTED: dict[str, Any] = {"kind": "none", "name": "", "strength": -1, "ipAddress": ""}


def _ip_address(profile: ConnectionProfile) -> str:
    """Return the IPv4 address assigned to this profile's adapter."""
    # WinRT stubs mark these fields as required, but Windows can return None.
    adapter = cast(NetworkAdapter | None, profile.network_adapter)
    if adapter is None:
        return ""
    for host in NetworkInformation.get_host_names():
        info = cast(IPInformation | None, host.ip_information)
        if host.type != HostNameType.IPV4 or info is None:
            continue
        host_adapter = cast(NetworkAdapter | None, info.network_adapter)
        if host_adapter is not None and host_adapter.network_adapter_id == adapter.network_adapter_id:
            return host.canonical_name
    return ""


def connection_status(wlan: WlanClient | None = None) -> dict[str, Any]:
    """Return the internet connection and, when available, exact Wi-Fi quality."""
    # Windows returns None when offline, despite the WinRT type hints.
    profile = cast(ConnectionProfile | None, NetworkInformation.get_internet_connection_profile())
    if profile is None:
        return DISCONNECTED
    status = {"kind": "ethernet", "name": profile.profile_name, "strength": -1, "ipAddress": _ip_address(profile)}
    if not profile.is_wlan_connection_profile:
        return status
    # Signal bars need no location permission but use 25-point steps.
    strength = min(profile.get_signal_bars() or 0, 4) * 25
    if wlan is not None and (quality := wlan.connected_quality()) is not None:
        strength = quality
    return {**status, "kind": "wifi", "strength": strength}


class ConnectionMonitor(QObject):
    """Poll connection status on a worker thread at the shortest subscriber interval."""

    statusChanged = pyqtSignal(object)

    _instance: ConnectionMonitor | None = None

    @classmethod
    def instance(cls) -> ConnectionMonitor:
        if cls._instance is None:
            cls._instance = ConnectionMonitor()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._status = DISCONNECTED
        # Each widget's polling interval (ms) and exact-strength setting.
        self._subscribers: dict[int, tuple[int, bool]] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = False
        self._thread: threading.Thread | None = None
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self.stop)

    @property
    def status(self) -> dict[str, Any]:
        return self._status

    def subscribe(self, key: int, interval: int, exact: bool) -> None:
        with self._lock:
            self._subscribers[key] = (interval, exact)
        if self._thread is None and not self._stopping:
            self._thread = threading.Thread(target=self._run, name="ConnectionMonitor", daemon=True)
            self._thread.start()
        self._wake.set()

    def unsubscribe(self, key: int) -> None:
        with self._lock:
            self._subscribers.pop(key, None)

    def refresh(self) -> None:
        """Request an immediate status update."""
        self._wake.set()

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._thread is not None:
            self._thread.join(2)
            self._thread = None

    def _run(self) -> None:
        wlan = WlanClient()
        try:
            while not self._stopping:
                with self._lock:
                    subscribers = list(self._subscribers.values())
                if not subscribers:
                    self._wake.wait()
                    self._wake.clear()
                    continue
                exact = any(exact for _, exact in subscribers)
                try:
                    status = connection_status(wlan if exact else None)
                except Exception:
                    logger.exception("Could not read the network connection")
                    status = DISCONNECTED
                if status != self._status and not self._stopping:
                    self._status = status
                    self.statusChanged.emit(status)
                self._wake.wait(min(interval for interval, _ in subscribers) / 1000)
                self._wake.clear()
        finally:
            wlan.close()

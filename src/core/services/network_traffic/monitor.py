import atexit
import logging
import threading
import time
from datetime import date
from typing import Any, ClassVar

from PyQt6.QtCore import QCoreApplication, QMetaObject, QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from winrt.windows.networking.connectivity import ConnectionProfile, NetworkConnectivityLevel, NetworkInformation

from core.services.network_traffic.adapters import Adapter, ProfileKey, find_profile, read_adapter, read_counters
from core.services.network_traffic.usage import Session, read_history
from core.utils.qml import qml_property
from core.utils.worker import run_in_worker

logger = logging.getLogger("network_traffic")
MIN_INTERVAL_MS = 1000
MAX_INTERVAL_MS = 60000
HISTORY_INTERVAL_SECONDS = 60

EMPTY_DATA: dict[str, Any] = {
    "connected": False,
    "available": False,
    "internetAvailable": None,
    "profileName": "",
    "adapterName": "",
    "ipAddress": "",
    "isWifi": False,
    "interfaces": [],
    "uploadRate": 0.0,
    "downloadRate": 0.0,
    "sessionUploaded": 0,
    "sessionDownloaded": 0,
    "sessionSeconds": 0,
}
EMPTY_HISTORY: dict[str, Any] = {"daily": [], "hourly": [], "updatedAt": 0, "loading": False}


class TrafficSampler(QObject):
    """One live sampler and one history request for an adapter, shared by every widget watching it. The adapter is
    auto, the one Windows uses for internet, or one named like Ethernet or Wi-Fi."""

    changed = pyqtSignal(object, str)
    historyChanged = pyqtSignal()
    _ready = pyqtSignal(object, object, str)
    _failed = pyqtSignal()
    _instances: ClassVar[dict[str, TrafficSampler]] = {}

    @classmethod
    def instance(cls, interface: str = "auto") -> TrafficSampler:
        # Windows matches adapter names in any case, and so do these
        key = interface.casefold()
        if key not in cls._instances:
            cls._instances[key] = cls(interface)
        return cls._instances[key]

    def __init__(self, interface: str = "auto") -> None:
        super().__init__()
        self.interface = interface
        self._subscribers: dict[int, int] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._reset = False
        self._thread: threading.Thread | None = None
        self._session = Session()
        # The network and its adapter, looked up again when Windows reports a network change
        self._network_changed = threading.Event()
        self._active: tuple[ProfileKey, ConnectionProfile] | None = None
        self._adapter: Adapter | None = None
        self.history = EMPTY_HISTORY
        self._history_key: tuple[ProfileKey, date] | None = None
        self._history_pending = False
        self._next_history = 0.0
        self._ready.connect(self._publish)
        self._failed.connect(self._worker_failed)
        self._restart = QTimer(self)
        self._restart.setSingleShot(True)
        self._restart.setInterval(1000)
        self._restart.timeout.connect(self._restart_worker)
        stopping, wake = self._stopping, self._wake
        self.destroyed.connect(lambda: (stopping.set(), wake.set()))
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self.stop)

    def subscribe(self, key: int, interval: int) -> None:
        if self._stopping.is_set():
            return
        with self._lock:
            self._subscribers[key] = interval
        if self._thread is None or not self._thread.is_alive():
            self._start_worker()
        self._wake.set()

    def unsubscribe(self, key: int) -> None:
        with self._lock:
            self._subscribers.pop(key, None)
        self._wake.set()

    def reset(self) -> None:
        with self._lock:
            self._reset = True
        self._wake.set()

    def refresh(self) -> None:
        self._next_history = 0
        self._wake.set()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        self._restart.stop()

    def _finish(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(2)

    def _start_worker(self) -> None:
        self._restart.stop()
        self._thread = threading.Thread(target=self._run, name=f"NetworkTraffic {self.interface}", daemon=True)
        atexit.register(self._finish)
        try:
            self._thread.start()
        except RuntimeError:
            atexit.unregister(self._finish)
            self._thread = None
            logger.exception("Could not start the network traffic worker")
            self._worker_failed()

    @pyqtSlot()
    def _worker_failed(self) -> None:
        if not self._stopping.is_set():
            self._publish(None, EMPTY_DATA, "Network statistics are unavailable.")
            if self._subscribers:
                self._restart.start()

    @pyqtSlot()
    def _restart_worker(self) -> None:
        if not self._stopping.is_set() and self._subscribers:
            if self._thread is not None and self._thread.is_alive():
                self._restart.start()
            else:
                self._start_worker()

    def _run(self) -> None:
        last_error = ""
        token = None
        self._network_changed.set()
        try:
            token = NetworkInformation.add_network_status_changed(lambda _sender: self._network_changed.set())
            while not self._stopping.is_set():
                self._wake.clear()
                if self._stopping.is_set():
                    break
                with self._lock:
                    interval = min(self._subscribers.values(), default=0)
                    reset, self._reset = self._reset, False
                if not interval:
                    self._session.previous = None
                    self._wake.wait()
                    continue
                try:
                    key, data = self._sample(reset)
                    error = last_error = ""
                except Exception as problem:
                    self._session.previous = None
                    self._network_changed.set()
                    key, data, error = None, EMPTY_DATA, "Network statistics are unavailable."
                    if str(problem) != last_error:
                        logger.exception("Could not read network traffic")
                        last_error = str(problem)
                if not self._stopping.is_set():
                    self._ready.emit(key, data, error)
                self._wake.wait(interval / 1000)
        except Exception:
            if not self._stopping.is_set():
                logger.exception("The network traffic worker stopped unexpectedly")
                self._failed.emit()
        finally:
            if token is not None:
                NetworkInformation.remove_network_status_changed(token)
            atexit.unregister(self._finish)

    def _sample(self, reset: bool) -> tuple[ProfileKey | None, dict[str, Any]]:
        if self._network_changed.is_set():
            self._network_changed.clear()
            self._active = find_profile(self.interface)
            self._adapter = read_adapter(self._active[0][0]) if self._active is not None else None
        active = self._active
        if active is None:
            self._session.previous = None
            if reset:
                self._session = Session()
            return None, EMPTY_DATA
        key, profile = active
        adapter = read_counters(self._adapter) if self._adapter is not None else None
        try:
            level = profile.get_network_connectivity_level()
        except OSError:
            level = None
        connected = adapter.connected if adapter is not None else level not in (None, NetworkConnectivityLevel.NONE)
        data = {
            **EMPTY_DATA,
            **self._session.sample(key, adapter, time.monotonic(), reset),
            "profileName": key[1],
            "adapterName": adapter.name if adapter else key[1],
            "ipAddress": adapter.ip_address if adapter else "",
            "interfaces": [adapter.name] if adapter else [],
            "connected": connected,
            "available": connected,
            "internetAvailable": level == NetworkConnectivityLevel.INTERNET_ACCESS if level is not None else None,
            "isWifi": profile.is_wlan_connection_profile,
        }
        return key if connected else None, data

    @pyqtSlot(object, object, str)
    def _publish(self, key: ProfileKey | None, data: dict[str, Any], error: str) -> None:
        if self._stopping.is_set() or not self._subscribers:
            return
        history_key = (key, date.today()) if key is not None else None
        if history_key != self._history_key:
            self._history_key = history_key
            self._next_history = 0
            self._set_history({**EMPTY_HISTORY, "loading": history_key is not None})
        self.changed.emit(data, error)
        self._request_history()

    def _set_history(self, history: dict[str, Any]) -> None:
        if self.history != history:
            self.history = history
            self.historyChanged.emit()

    def _request_history(self) -> None:
        key = self._history_key
        if (
            key is None
            or self._history_pending
            or time.monotonic() < self._next_history
            or not self._subscribers
            or self._stopping.is_set()
        ):
            return
        self._history_pending = True
        self._next_history = time.monotonic() + HISTORY_INTERVAL_SECONDS
        if not self.history["daily"] and not self.history["hourly"]:
            self._set_history({**self.history, "loading": True})

        def done(result: object, error: str) -> None:
            self._history_pending = False
            if self._stopping.is_set():
                return
            if key != self._history_key:
                self._request_history()
            elif isinstance(result, dict) and result:
                self._set_history({**EMPTY_HISTORY, **result})
            else:
                self._set_history({**self.history, "loading": False})
                if error:
                    logger.debug("Windows usage history unavailable: %s", error)

        try:
            run_in_worker(lambda: read_history(self.interface, *key), done, "Could not read Windows usage history.")
        except RuntimeError as error:
            done(None, str(error))


class NetworkTrafficMonitor(QObject):
    dataChanged = pyqtSignal()
    historyChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    stateChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._interface = "auto"
        self._interval = MIN_INTERVAL_MS
        self._data = EMPTY_DATA
        self._error = ""
        self._loading = True
        self._source: TrafficSampler | None = None
        self._leave: QMetaObject.Connection | None = None
        self._start = QTimer(self)
        self._start.setSingleShot(True)
        self._start.timeout.connect(self._subscribe)
        self._start.start(0)

    @qml_property("QVariantMap", notify=dataChanged)
    def data(self) -> dict[str, Any]:
        return self._data

    @qml_property("QVariantMap", notify=historyChanged)
    def history(self) -> dict[str, Any]:
        return self._source.history if self._source is not None and self._data["connected"] else EMPTY_HISTORY

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    @qml_property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._loading

    def _get_interface(self) -> str:
        return self._interface

    def _set_interface(self, value: str) -> None:
        value = value.strip() or "auto"
        if value.lower() == "auto":
            value = "auto"
        if value != self._interface:
            self._interface = value
            self.settingsChanged.emit()
            if self._source is not None:
                self._subscribe()

    interfaceName = pyqtProperty(str, _get_interface, _set_interface, notify=settingsChanged)

    def _get_interval(self) -> int:
        return self._interval

    def _set_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value != self._interval:
            self._interval = value
            self.settingsChanged.emit()
            if self._source is not None:
                self._subscribe()

    updateInterval = pyqtProperty(int, _get_interval, _set_interval, notify=settingsChanged)

    @pyqtSlot()
    def _subscribe(self) -> None:
        source, key = TrafficSampler.instance(self._interface), id(self)
        if source is not self._source:
            if self._source is not None:
                # Moving to another adapter: what the old one showed no longer applies
                self._source.changed.disconnect(self._on_data)
                self._source.historyChanged.disconnect(self.historyChanged)
                self._source.unsubscribe(key)
                if self._leave is not None:
                    self.destroyed.disconnect(self._leave)
                self._data, self._error, self._loading = EMPTY_DATA, "", True
                self.dataChanged.emit()
                self.historyChanged.emit()
                self.stateChanged.emit()
            self._source = source
            source.changed.connect(self._on_data)
            source.historyChanged.connect(self.historyChanged)
            self._leave = self.destroyed.connect(lambda: source.unsubscribe(key))
        source.subscribe(key, self._interval)

    @pyqtSlot(object, str)
    def _on_data(self, data: dict[str, Any], error: str) -> None:
        if data != self._data:
            was_connected = self._data["connected"]
            self._data = data
            self.dataChanged.emit()
            if was_connected != data["connected"]:
                self.historyChanged.emit()
        if self._loading or self._error != error:
            self._loading, self._error = False, error
            self.stateChanged.emit()

    @pyqtSlot()
    def reset(self) -> None:
        if self._source is not None and self._data["connected"]:
            self._source.reset()

    @pyqtSlot()
    def refresh(self) -> None:
        if self._source is not None:
            self._source.refresh()

# pyright: reportPrivateUsage=false

import threading
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QJSValue, QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from winrt.windows.foundation import AsyncStatus
from winrt.windows.networking.connectivity import DataUsageGranularity

from core.qml_types import register_qml_types
from core.services.network.adapters import Adapter
from core.services.network.connections import ConnectionWatcher
from core.services.network_traffic import monitor as monitor_module
from core.services.network_traffic import usage as usage_module
from core.services.network_traffic.monitor import EMPTY_DATA, EMPTY_HISTORY, NetworkTrafficMonitor, TrafficSampler
from core.services.network_traffic.usage import Session
from core.widget_files import BUILTIN_WIDGETS_DIR, find_widget_file
from settings import QML_IMPORT_PATH
from tests.support.network import FakeWatcher, connection
from tests.support.qt import find_item, wait

KEY = ("wired", "Home")
OTHER = ("wireless", "Office")
SAMPLE: dict[str, Any] = {
    **EMPTY_DATA,
    "downloadRate": 250000.0,
    "uploadRate": 125000.0,
    "sessionDownloaded": 2048,
    "sessionUploaded": 1024,
    "sessionSeconds": 125,
    "available": True,
    "connected": True,
    "internetAvailable": True,
    "profileName": "Home",
    "adapterName": "Ethernet",
    "ipAddress": "192.0.2.10",
    "interfaces": ["Ethernet"],
}
STAMP = int(datetime.combine(date.today(), time.min).timestamp() * 1000)
POINT = {"stamp": STAMP, "downloaded": 1024**3, "uploaded": 1024**2}
HISTORY = {**EMPTY_HISTORY, "daily": [POINT], "hourly": [POINT], "updatedAt": STAMP}


@pytest.fixture(autouse=True)
def watcher(monkeypatch: pytest.MonkeyPatch) -> FakeWatcher:
    fake = FakeWatcher()
    monkeypatch.setattr(ConnectionWatcher, "instance", lambda: fake)
    return fake


def test_live_rates_and_session_restart_when_the_profile_changes_or_is_reset():
    session = Session()
    session.sample(KEY, Adapter("wired", "Ethernet", 1000, 2000, True), 1, False)
    data = session.sample(KEY, Adapter("wired", "Ethernet", 1400, 2600, True), 3, False)
    assert (data["uploadRate"], data["downloadRate"]) == (200, 300)
    assert (data["sessionUploaded"], data["sessionDownloaded"]) == (400, 600)

    data = session.sample(OTHER, Adapter("wireless", "Wi-Fi", 90000, 90000, True), 4, False)
    assert data["sessionUploaded"] == data["downloadRate"] == 0
    data = session.sample(OTHER, Adapter("wireless", "Wi-Fi", 90100, 90200, True), 5, False)
    assert data["sessionDownloaded"] == 200
    data = session.sample(OTHER, Adapter("wireless", "Wi-Fi", 90200, 90400, True), 6, True)
    assert data["sessionDownloaded"] == data["sessionSeconds"] == 0


def test_daily_history_keeps_local_midnights_across_a_clock_change(monkeypatch: pytest.MonkeyPatch):
    zone = ZoneInfo("Europe/Belgrade")
    calls: list[tuple[datetime, datetime, DataUsageGranularity]] = []
    now = datetime(2026, 11, 5, 12, tzinfo=zone)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return now.astimezone(tz)

    def midnight(day: date) -> datetime:
        return datetime.combine(day, time.min, zone).astimezone(UTC)

    def request(start: datetime, end: datetime, grain: DataUsageGranularity, _states: object) -> SimpleNamespace:
        calls.append((start, end, grain))
        step = timedelta(hours=1 if grain == DataUsageGranularity.PER_HOUR else 24)
        count = 1 if grain == DataUsageGranularity.TOTAL else (end - start) // step

        def wait_for_result(_timeout: float) -> AsyncStatus:
            return AsyncStatus.COMPLETED

        return SimpleNamespace(
            wait=wait_for_result,
            get_results=lambda: [SimpleNamespace(bytes_received=200, bytes_sent=100)] * count,
        )

    monkeypatch.setattr(usage_module, "datetime", Clock)
    monkeypatch.setattr(usage_module, "_midnight", midnight)

    def connection_profile(_adapter_id: str) -> SimpleNamespace:
        return SimpleNamespace(profile_name="Home", get_network_usage_async=request)

    monkeypatch.setattr(usage_module, "connection_profile", connection_profile)

    history = usage_module.read_history(KEY, now.date())
    days = [datetime.fromtimestamp(point["stamp"] / 1000, zone) for point in history["daily"]]
    assert len(days) == 30 and len(history["hourly"]) == 12
    assert all(day.time() == time.min for day in days)
    assert [day.date() for day in days] == [now.date() - timedelta(days=day) for day in range(29, -1, -1)]
    assert any(
        end - start == timedelta(hours=25) and grain == DataUsageGranularity.TOTAL for start, end, grain in calls
    )
    assert history["daily"][-1]["downloaded"] == 2400


def test_widgets_naming_the_same_adapter_share_one_sampler(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(TrafficSampler, "_instances", {})
    ethernet = TrafficSampler.instance("Ethernet")
    assert TrafficSampler.instance("ethernet") is ethernet
    assert TrafficSampler.instance() is not ethernet
    for sampler in TrafficSampler._instances.values():
        sip.delete(sampler)


class FakeSampler(TrafficSampler):
    def __init__(self, interface: str = "auto") -> None:
        QObject.__init__(self)
        self.interface = interface
        self.subscribers: dict[int, int] = {}
        self.history = HISTORY
        self.resets = self.refreshes = 0

    def subscribe(self, key: int, interval: int) -> None:
        self.subscribers[key] = interval

    def unsubscribe(self, key: int) -> None:
        self.subscribers.pop(key, None)

    def reset(self) -> None:
        self.resets += 1

    def refresh(self) -> None:
        self.refreshes += 1


@pytest.fixture
def samplers(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, FakeSampler]]:
    """A fake sampler for each adapter name a monitor asks for."""
    created: dict[str, FakeSampler] = {}

    def instance(_cls: type[TrafficSampler], interface: str = "auto") -> FakeSampler:
        if interface not in created:
            created[interface] = FakeSampler(interface)
        return created[interface]

    monkeypatch.setattr(TrafficSampler, "instance", classmethod(instance))
    yield created
    for source in created.values():
        source.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


@pytest.fixture
def sampler(samplers: dict[str, FakeSampler]) -> FakeSampler:
    return cast(FakeSampler, TrafficSampler.instance())


def test_monitor_uses_initial_settings_and_moves_to_the_adapter_it_names(samplers: dict[str, FakeSampler]):
    monitor = NetworkTrafficMonitor()
    monitor.setProperty("interfaceName", "Wi-Fi")
    monitor.setProperty("updateInterval", 2500)
    assert not samplers
    wait(5)
    wifi = samplers["Wi-Fi"]
    assert wifi.subscribers == {id(monitor): 2500}
    wifi.changed.emit({**SAMPLE, "adapterName": "Wi-Fi"}, "")
    assert monitor.property("data")["adapterName"] == "Wi-Fi"
    assert monitor.property("history")["daily"] == [POINT]

    monitor.setProperty("interfaceName", "Ethernet")
    ethernet = samplers["Ethernet"]
    assert not wifi.subscribers and ethernet.subscribers == {id(monitor): 2500}
    # Nothing of Wi-Fi shows while Ethernet has not reported yet
    assert monitor.property("data")["connected"] is False and monitor.property("loading")
    wifi.changed.emit({**SAMPLE, "adapterName": "Wi-Fi"}, "")
    assert monitor.property("data")["connected"] is False
    ethernet.changed.emit(SAMPLE, "")
    assert monitor.property("data")["adapterName"] == "Ethernet"
    monitor.setProperty("updateInterval", 0)
    assert ethernet.subscribers[id(monitor)] == 1000
    sip.delete(monitor)
    assert not ethernet.subscribers


@pytest.fixture
def widget(samplers: dict[str, FakeSampler], sampler: FakeSampler) -> Iterator[Callable[..., QQuickItem]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def on_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(on_warnings)
    created: list[QQuickItem] = []
    hosts: list[QQuickWindow] = []

    def create(**properties: Any) -> QQuickItem:
        component = QQmlComponent(
            engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "NetworkTraffic/NetworkTraffic.qml"))
        )
        item = component.createWithInitialProperties(cast(dict[str | None, Any], properties))
        assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
        created.append(item)
        host = QQuickWindow()
        host.setGeometry(0, 0, 600, 40)
        item.setParentItem(host.contentItem())
        item.setSize(host.size().toSizeF())
        host.show()
        hosts.append(host)
        wait(5)
        for source in samplers.values():
            source.changed.emit(SAMPLE, "")
        return item

    yield create
    for item in created:
        sip.delete(item)
    for host in hosts:
        host.close()
        sip.delete(host)
    sip.delete(engine)
    assert not warnings, warnings


def test_network_traffic_is_discovered_as_a_builtin_qml_widget():
    assert find_widget_file("NetworkTraffic") == BUILTIN_WIDGETS_DIR / "NetworkTraffic/NetworkTraffic.qml"


def test_bar_label_is_optional_and_session_label_can_be_overridden(widget: Callable[..., QQuickItem]):
    item = widget()
    label = find_item(item, "label")
    assert label is not None and label.property("text") == ""
    item.setProperty("label", "My traffic")
    assert label.property("text") == "My traffic"
    item.setProperty("showAlternate", True)
    assert label.property("text") == "↓ 2.0 KiB  ↑ 1.0 KiB"
    item.setProperty("alternateLabel", "My session")
    assert label.property("text") == "My session"


def test_offline_hiding_releases_layout_space(widget: Callable[..., QQuickItem], sampler: FakeSampler):
    item = widget(hideWhenOffline=True)
    assert item.isVisible() and item.implicitWidth() > 0
    sampler.changed.emit(EMPTY_DATA, "")
    assert not item.isVisible() and item.implicitWidth() == 0 and item.implicitHeight() == 0
    sampler.changed.emit(SAMPLE, "")
    assert item.isVisible() and item.implicitWidth() > 0


def test_popup_switches_history_period_and_keeps_live_data_when_history_is_unavailable(
    widget: Callable[..., QQuickItem], sampler: FakeSampler
):
    item = widget()
    popup = item.findChild(QObject, "menu")
    assert popup is not None
    QMetaObject.invokeMethod(item, "togglePopup")
    wait(30)
    window = next(window for window in QGuiApplication.topLevelWindows() if window.title() == "Network Traffic")
    assert isinstance(window, QQuickWindow) and window.isVisible()
    content = window.contentItem()
    assert content is not None
    panel = find_item(content, "trafficContent")
    status = find_item(content, "connection")
    assert panel is not None and panel.property("hasHistory")
    assert status is not None and status.property("text") == "Ethernet · 192.0.2.10 ·"
    assert panel.property("downloadText") == "2.0 Mbps"
    assert panel.property("uploadText") == "1.0 Mbps"
    item.setProperty("speedUnit", "bytes")
    assert panel.property("downloadText") == "244.1 KiB/s"
    assert panel.property("uploadText") == "122.1 KiB/s"
    item.setProperty("speedUnit", "bits")
    for period in (0, 1, 2):
        panel.setProperty("period", period)
        points = panel.property("points")
        assert len(points.toVariant() if isinstance(points, QJSValue) else points) == 1

    sampler.history = EMPTY_HISTORY
    sampler.historyChanged.emit()
    assert not panel.property("hasHistory")
    assert panel.property("downloadText") == "2.0 Mbps"
    sampler.changed.emit(EMPTY_DATA, "Network statistics are unavailable.")
    assert status.property("text") == "Network statistics are unavailable."
    QMetaObject.invokeMethod(popup, "hide")


def test_public_stats_and_actions_are_available_to_custom_qml(
    widget: Callable[..., QQuickItem], samplers: dict[str, FakeSampler]
):
    item = widget(interfaceName="Ethernet")
    assert item.property("stats")["downloadRate"] == 250000
    assert not item.property("loading") and item.property("error") == ""
    QMetaObject.invokeMethod(item, "resetUsage")
    QMetaObject.invokeMethod(item, "refresh")
    ethernet = samplers["Ethernet"]
    assert ethernet.resets == ethernet.refreshes == 1


def test_history_requests_are_shared_and_old_profile_results_are_discarded(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch
):
    jobs: list[tuple[Callable[[], object], Callable[[object, str], None]]] = []
    keys: list[tuple[str, str]] = []

    def schedule(work: Callable[[], object], done: Callable[[object, str], None], _failure: str) -> None:
        jobs.append((work, done))

    def read(key: tuple[str, str], _today: date) -> dict[str, Any]:
        keys.append(key)
        return HISTORY

    monkeypatch.setattr(monitor_module, "run_in_worker", schedule)
    monkeypatch.setattr(monitor_module, "read_history", read)
    source = TrafficSampler()
    source._subscribers = {1: 1000, 2: 2000}
    try:
        source._publish(KEY, SAMPLE, "")
        source._publish(KEY, SAMPLE, "")
        assert len(jobs) == 1 and source.history["loading"]
        source._publish(OTHER, SAMPLE, "")
        work, done = jobs[0]
        done(work(), "")
        assert len(jobs) == 2 and source.history["daily"] == []
        work, done = jobs[1]
        done(work(), "")
        assert keys == [KEY, OTHER]
        assert source.history["daily"] == [POINT]
        source.refresh()
        source._publish(OTHER, SAMPLE, "")
        jobs[-1][1](None, "Access denied")
        assert source.history["daily"] == [POINT]
        assert not source.history["loading"]
    finally:
        source.stop()
        sip.delete(source)


def test_the_network_is_looked_up_again_only_when_the_network_changes(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch, watcher: FakeWatcher
):
    lookups: list[str] = []
    received = 0

    def read_connection(interface: str) -> dict[str, Any]:
        lookups.append(interface)
        return connection("ethernet", "Home", adapterId="wired")

    def read_adapter(_key: str) -> Adapter:
        return Adapter("wired", "Ethernet", 0, 0, True)

    def read_counters(adapter: Adapter) -> Adapter:
        nonlocal received
        received += 1000
        return replace(adapter, downloaded=received)

    monkeypatch.setattr(monitor_module, "read_connection", read_connection)
    monkeypatch.setattr(monitor_module, "read_adapter", read_adapter)
    monkeypatch.setattr(monitor_module, "read_counters", read_counters)
    source = TrafficSampler()
    source._network_changed.set()
    try:
        key, _ = source._sample(False)
        _, data = source._sample(False)
        assert key == KEY and lookups == ["auto"]
        assert data["downloadRate"] > 0 and data["internetAvailable"] is True and data["isWifi"] is False
        watcher.networkChanged.emit()
        source._sample(False)
        assert lookups == ["auto", "auto"]
    finally:
        sip.delete(source)


def test_the_sampler_watches_connections_only_while_widgets_use_it(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch, watcher: FakeWatcher
):
    source = TrafficSampler()
    monkeypatch.setattr(source, "_start_worker", lambda: None)
    try:
        source.subscribe(1, 1000)
        source.subscribe(2, 2000)
        assert watcher.subscribers == {id(source): 0}
        source.unsubscribe(1)
        assert id(source) in watcher.subscribers
        source.unsubscribe(2)
        assert not watcher.subscribers
    finally:
        sip.delete(source)


def test_stop_wakes_the_live_worker_without_waiting_for_a_native_call(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch
):
    entered, release = threading.Event(), threading.Event()

    def sample(_reset: bool) -> tuple[None, dict[str, Any]]:
        entered.set()
        assert release.wait(3)
        return None, EMPTY_DATA

    source = TrafficSampler()
    monkeypatch.setattr(source, "_sample", sample)
    try:
        source.subscribe(1, 1000)
        assert entered.wait(1)
        source.stop()
        assert source._thread is not None and source._thread.is_alive()
    finally:
        release.set()
        source._finish()
        sip.delete(source)

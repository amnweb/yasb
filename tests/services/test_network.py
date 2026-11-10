# pyright: reportPrivateUsage=false

import ctypes
import threading
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QModelIndex, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from winrt.windows.devices.radios import RadioAccessStatus, RadioKind, RadioState
from winrt.windows.devices.wifi import WiFiConnectionStatus
from winrt.windows.networking.connectivity import NetworkConnectivityLevel, NetworkCostType, WwanDataClass
from winrt.windows.security.authorization.appcapabilityaccess import AppCapabilityAccessStatus

from core.qml_types import register_qml_types
from core.services.network import connections as connections_module
from core.services.network import wifi as wifi_module
from core.services.network.adapters import Adapter
from core.services.network.connections import DISCONNECTED, ConnectionWatcher, NetworkConnections
from core.services.network.wifi import WifiNetworkList, WifiNetworks, network_row, sort_networks
from core.services.network.wlan import ScanStatus, WifiNetwork
from core.utils.win32.constants import E_ACCESSDENIED, E_INVALIDARG, WlanNotificationAcm, WlanNotificationMsm
from core.utils.win32.structs import GUID
from core.widget_files import BUILTIN_WIDGETS_DIR, find_widget_file
from settings import QML_IMPORT_PATH
from tests.support.network import FakeWatcher, connection
from tests.support.qt import find_item, wait

HOME = connection("wifi", "Home", adapterId="9f2c1e5a-0b6d-4c3e-8a71-5d4f6e7a8b9c", signal=75, ipAddress="192.168.0.10")
ETHERNET = connection("ethernet", "Network 2", ipAddress="10.0.0.5")
# A tester's LTE modem, as Windows reported it
MOBILE_ADAPTER_ID = "a46dd20b-d9b6-4859-bebb-a1585f5e2ee9"
MOBILE = connection(
    "mobile",
    "Orange",
    mobileType="LTE",
    adapter="Sieć komórkowa",
    adapterId=MOBILE_ADAPTER_ID,
    ipAddress="10.222.0.1",
    metered=True,
    signal=100,
)
NETWORKS = [
    WifiNetwork("Cafe", 40, False, False),
    WifiNetwork("", 90, True, False),
    WifiNetwork("Home", 70, True, True, profile="Home", auto_connect=True),
    WifiNetwork("Neighbour", 80, True, False),
]


def until(condition: Callable[[], bool], timeout: int = 1000) -> bool:
    for _ in range(timeout // 10):
        if condition():
            return True
        wait(10)
    return condition()


class FakeWindows:
    """Stands in for Windows' connection reads, network change event, location access and WLAN signal events."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.connection: dict[str, Any] | None = None
        self.reads = 0
        self.handlers: list[Callable[[object], None]] = []
        self.removed = 0
        # Location access lets Windows send signal changes to a newly opened handle.
        self.location = False
        self.location_handlers: list[Callable[[Any, Any], None]] = []
        self.opened = False
        self.notifying = False
        self.qualities: dict[str, int] = {}
        self.on_wlan: Callable[[Any], None] | None = None
        monkeypatch.setattr(connections_module, "read_connection", self.read)
        monkeypatch.setattr(connections_module, "NetworkInformation", self)
        monkeypatch.setattr(connections_module, "WlanClient", self.wlan)
        monkeypatch.setattr(connections_module, "AppCapability", self)

    def read(self) -> dict[str, Any] | None:
        self.reads += 1
        return dict(self.connection) if self.connection is not None else None

    def add_network_status_changed(self, handler: Callable[[object], None]) -> int:
        self.handlers.append(handler)
        return 1

    def remove_network_status_changed(self, _token: int) -> None:
        self.removed += 1

    def network_changed(self) -> None:
        for handler in self.handlers:
            handler(None)

    def create(self, _capability: str) -> FakeWindows:
        return self

    def check_access(self) -> AppCapabilityAccessStatus:
        return AppCapabilityAccessStatus.ALLOWED if self.location else AppCapabilityAccessStatus.DENIED_BY_USER

    def add_access_changed(self, handler: Callable[[Any, Any], None]) -> int:
        self.location_handlers.append(handler)
        return 2

    def remove_access_changed(self, _token: int) -> None:
        self.location_handlers.clear()

    def location_changed(self, location: bool) -> None:
        """Change a location setting; Windows reports it whether or not this process's access changes."""
        self.location = location
        for handler in self.location_handlers:
            handler(self, None)

    def wlan(self, on_notification: Callable[[Any], None], _source: int) -> FakeWindows:
        self.on_wlan = on_notification
        return self

    def open(self) -> bool:
        if not self.opened:
            self.opened = True
            self.notifying = self.location
        return True

    def connected_qualities(self) -> dict[str, int]:
        return dict(self.qualities)

    def close(self) -> None:
        self.opened = self.notifying = False

    def signal_changed(self, adapter_id: str, quality: int) -> None:
        self.qualities[adapter_id] = quality
        value = ctypes.c_ulong(quality)
        data = SimpleNamespace(
            NotificationCode=WlanNotificationMsm.SIGNAL_QUALITY_CHANGE,
            pData=ctypes.addressof(value),
            InterfaceGuid=GUID.from_string(adapter_id),
        )
        assert self.on_wlan is not None
        self.on_wlan(data)


class FakeProfile:
    """A connection profile. Without an adapter id, reading the adapter raises, as Windows does for a VPN's copy in
    the connected profiles."""

    def __init__(self, name: str, adapter_id: str | None, interface_type: int = connections_module.ETHERNET) -> None:
        self.profile_name = name
        self.is_wlan_connection_profile = False
        self.is_wwan_connection_profile = False
        self._adapter_id = adapter_id
        self._interface_type = interface_type

    @property
    def network_adapter(self) -> SimpleNamespace:
        if self._adapter_id is None:
            raise OSError(None, "The parameter is incorrect.", None, E_INVALIDARG)
        return SimpleNamespace(network_adapter_id=self._adapter_id, iana_interface_type=self._interface_type)

    def get_connection_cost(self) -> SimpleNamespace:
        return SimpleNamespace(
            network_cost_type=NetworkCostType.UNRESTRICTED, over_data_limit=False, approaching_data_limit=False
        )

    def get_network_connectivity_level(self) -> NetworkConnectivityLevel:
        return NetworkConnectivityLevel.INTERNET_ACCESS

    def get_network_names(self) -> list[str]:
        # As Windows names this PC's Ethernet
        return [self.profile_name]

    def get_signal_bars(self) -> int | None:
        return None


class FakeMobileProfile(FakeProfile):
    """A tester's LTE connection. Windows names its profile with an id and its network after the operator."""

    def __init__(self, bars: int | None) -> None:
        super().__init__("165082F3-CAFB-4CBB-B1A7-67D7DDA35278", MOBILE_ADAPTER_ID, interface_type=243)
        self.is_wwan_connection_profile = True
        self.wwan_connection_profile_details = SimpleNamespace(
            get_current_data_class=lambda: WwanDataClass.LTE_ADVANCED
        )
        self.bars = bars

    def get_network_names(self) -> list[str]:
        return ["Orange"]

    def get_signal_bars(self) -> int | None:
        return self.bars


def no_adapter_details(_adapter_id: str) -> None:
    return None


def test_a_vpn_is_read_from_the_internet_profile_also_by_its_adapter_name(monkeypatch: pytest.MonkeyPatch):
    # Cloudflare WARP: its internet profile reads fine, but its copy in the connected profiles raises.
    warp, ethernet = FakeProfile("CloudflareWARP", "warp-id", interface_type=53), FakeProfile("Ethernet", "ethernet-id")
    connected = [FakeProfile("CloudflareWARP", None), ethernet]

    def find_connection_profiles_async(_filter: object) -> SimpleNamespace:
        return SimpleNamespace(get=lambda: connected)

    windows = SimpleNamespace(
        get_internet_connection_profile=lambda: warp, find_connection_profiles_async=find_connection_profiles_async
    )
    monkeypatch.setattr(connections_module, "NetworkInformation", windows)
    monkeypatch.setattr(connections_module, "adapter_key", {"CloudflareWARP": "warp-id", "Ethernet": "ethernet-id"}.get)
    monkeypatch.setattr(connections_module, "read_adapter", no_adapter_details)

    vpn = connections_module.read_connection()
    assert vpn is not None and (vpn["kind"], vpn["name"]) == ("other", "CloudflareWARP")
    assert connections_module.read_connection("CloudflareWARP") == vpn
    wired = connections_module.read_connection("Ethernet")
    assert wired is not None and (wired["kind"], wired["name"]) == ("ethernet", "Ethernet")
    assert connections_module.read_connection("Bluetooth") is None


def test_a_mobile_connection_is_read_with_its_operator_network_type_and_bars(monkeypatch: pytest.MonkeyPatch):
    lte = FakeMobileProfile(bars=5)
    windows = SimpleNamespace(get_internet_connection_profile=lambda: lte)
    monkeypatch.setattr(connections_module, "NetworkInformation", windows)
    modem = Adapter(MOBILE_ADAPTER_ID, "Sieć komórkowa", 0, 0, True, "10.222.0.1")
    monkeypatch.setattr(connections_module, "read_adapter", {MOBILE_ADAPTER_ID: modem}.get)

    mobile = connections_module.read_connection()
    assert mobile is not None
    assert (mobile["kind"], mobile["name"], mobile["mobileType"], mobile["signal"]) == ("mobile", "Orange", "LTE", 100)
    assert (mobile["adapter"], mobile["ipAddress"]) == ("Sieć komórkowa", "10.222.0.1")
    # Windows showed 3 of its 5 bars in a room with worse reception.
    lte.bars = 3
    assert (connections_module.read_connection() or {})["signal"] == 60

    # While mobile data reconnects, Windows reports a profile named after the adapter, not marked as cellular.
    reconnecting = FakeProfile("Sieć komórkowa", MOBILE_ADAPTER_ID, interface_type=243)
    windows.get_internet_connection_profile = lambda: reconnecting
    mobile = connections_module.read_connection()
    assert mobile is not None
    assert (mobile["kind"], mobile["mobileType"], mobile["signal"]) == ("mobile", "", -1)


@pytest.fixture
def windows(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWindows:
    return FakeWindows(monkeypatch)


@pytest.fixture
def watcher(windows: FakeWindows) -> Iterator[ConnectionWatcher]:
    source = ConnectionWatcher()
    yield source
    source.stop()
    sip.delete(source)


def test_the_connection_is_read_again_only_when_windows_reports_a_change(
    windows: FakeWindows, watcher: ConnectionWatcher
):
    changes: list[None] = []
    watcher.networkChanged.connect(lambda: changes.append(None))
    windows.connection = ETHERNET
    watcher.subscribe(1, 1000)
    assert until(lambda: watcher.connection == ETHERNET)
    wait(100)
    assert windows.reads == 1

    windows.connection = {**ETHERNET, "connectivity": "local"}
    windows.network_changed()
    assert until(lambda: watcher.connection["connectivity"] == "local")
    assert windows.reads == 2 and len(changes) == 1
    watcher.stop()
    assert windows.removed == 1


def test_wifi_signal_bars_are_no_longer_polled_once_a_cable_carries_the_internet(
    windows: FakeWindows, watcher: ConnectionWatcher
):
    windows.connection = HOME
    watcher.subscribe(1, 500)
    assert until(lambda: windows.reads >= 3, 1500)

    # Windows prefers the cable, so the Wi-Fi signal is no longer shown.
    windows.connection = ETHERNET
    windows.network_changed()
    assert until(lambda: watcher.connection == ETHERNET)
    reads = windows.reads
    wait(700)
    assert windows.reads == reads


def test_mobile_signal_bars_are_polled_until_wifi_takes_over(windows: FakeWindows, watcher: ConnectionWatcher):
    # Windows reports no change of mobile bars, even with location access.
    windows.location = True
    windows.connection = MOBILE
    watcher.subscribe(1, 500)
    assert until(lambda: windows.reads >= 3, 1500)

    # Wi-Fi takes over, and with location access Windows reports its signal changes.
    windows.qualities = {HOME["adapterId"]: 62}
    windows.connection = HOME
    windows.network_changed()
    assert until(lambda: watcher.connection["signal"] == 62)
    reads = windows.reads
    wait(700)
    assert windows.reads == reads


def test_widgets_without_the_signal_never_poll(windows: FakeWindows, watcher: ConnectionWatcher):
    windows.connection = HOME
    watcher.subscribe(1)
    assert until(lambda: watcher.connection == HOME)
    wait(700)
    assert windows.reads == 1


def test_with_location_access_the_signal_follows_windows_changes_instead_of_polling(
    windows: FakeWindows, watcher: ConnectionWatcher
):
    windows.connection = HOME
    windows.location = True
    windows.qualities = {HOME["adapterId"]: 62}
    watcher.subscribe(1, 500)
    assert until(lambda: watcher.connection["signal"] == 62)
    windows.signal_changed(HOME["adapterId"], 81)
    assert until(lambda: watcher.connection["signal"] == 81)
    wait(700)
    assert windows.reads == 1


def test_location_access_changes_switch_between_polling_and_signal_changes(
    windows: FakeWindows, watcher: ConnectionWatcher
):
    windows.connection = HOME
    windows.qualities = {HOME["adapterId"]: 62}
    watcher.subscribe(1, 500)
    assert until(lambda: windows.reads >= 3, 1500)
    assert watcher.connection["signal"] == 75 and not windows.opened

    windows.location_changed(True)
    assert until(lambda: watcher.connection["signal"] == 62)
    reads = windows.reads
    wait(700)
    assert windows.reads == reads

    # A change that leaves this process's access as it was, such as another app's, does nothing.
    windows.location_changed(True)
    wait(200)
    assert windows.reads == reads

    windows.location_changed(False)
    assert until(lambda: windows.reads >= reads + 3, 1500)
    assert watcher.connection["signal"] == 75 and not windows.opened


@pytest.fixture
def fake_watcher(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWatcher:
    fake = FakeWatcher()
    fake.connection = HOME
    monkeypatch.setattr(ConnectionWatcher, "instance", lambda: fake)
    return fake


def test_the_qml_type_reports_the_internet_connection_and_its_settings(fake_watcher: FakeWatcher):
    network = NetworkConnections()
    network.setProperty("signalInterval", 2000)
    wait(10)
    assert fake_watcher.subscribers == {id(network): 2000}
    assert network.property("primary")["ssid"] == "Home"

    fake_watcher.change(DISCONNECTED)
    assert network.property("primary") == DISCONNECTED
    sip.delete(network)
    assert not fake_watcher.subscribers


class FakeWlan:
    def __init__(self) -> None:
        self.scan_result = ScanStatus.SUCCESS
        self.found = list(NETWORKS)
        self.scans = 0
        self.reads = 0
        self.notify: Any = None
        self.forgotten: list[str] = []
        self.closes = 0
        # Track which threads call the WLAN handle.
        self.threads: set[threading.Thread] = set()

    def __call__(self, on_notification: Any = None) -> FakeWlan:
        self.notify = on_notification
        return self

    def notification(self, code: int) -> None:
        self.notify(SimpleNamespace(NotificationCode=code))

    def scan(self) -> ScanStatus:
        self.threads.add(threading.current_thread())
        self.scans += 1
        return self.scan_result

    def networks(self, profiles: bool = True) -> list[WifiNetwork]:
        self.threads.add(threading.current_thread())
        self.reads += 1
        return list(self.found)

    def close(self) -> None:
        self.threads.add(threading.current_thread())
        self.closes += 1

    def forget(self, profile: str) -> None:
        self.threads.add(threading.current_thread())
        self.forgotten.append(profile)


class FakeRadio:
    def __init__(self) -> None:
        self.kind = RadioKind.WI_FI
        self.state = RadioState.ON
        self.handlers: list[Callable[[Any, Any], None]] = []
        self.requested: list[RadioState] = []

    def add_state_changed(self, handler: Callable[[Any, Any], None]) -> int:
        self.handlers.append(handler)
        return len(self.handlers)

    def remove_state_changed(self, _token: int) -> None:
        self.handlers.pop()

    def set_state_async(self, state: RadioState) -> SimpleNamespace:
        self.requested.append(state)
        return SimpleNamespace(get=lambda: RadioAccessStatus.ALLOWED)

    def turn(self, state: RadioState) -> None:
        self.state = state
        for handler in list(self.handlers):
            handler(self, None)


@pytest.fixture
def client(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWlan:
    fake = FakeWlan()
    monkeypatch.setattr(wifi_module, "WlanClient", fake)
    return fake


@pytest.fixture
def radio(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeRadio:
    fake = FakeRadio()
    access = SimpleNamespace(get=lambda: RadioAccessStatus.ALLOWED)
    monkeypatch.setattr(wifi_module, "wifi_radio", lambda: fake)
    monkeypatch.setattr(wifi_module, "Radio", SimpleNamespace(request_access_async=lambda: access))
    return fake


@pytest.fixture
def wifi(client: FakeWlan, radio: FakeRadio) -> Iterator[WifiNetworks]:
    networks = WifiNetworks()
    yield networks
    # A Qt object without a parent is deleted by whoever created it, on its own thread. Left to Python, the garbage
    # collector can delete it from whichever thread it runs on.
    sip.delete(networks)


def rows(model: WifiNetworkList) -> list[str]:
    return [row["ssid"] for row in model.rows]


def test_networks_sort_connected_first_and_hidden_last():
    assert [network.ssid for network in sort_networks(NETWORKS)] == ["Home", "Neighbour", "Cafe", ""]


def test_the_list_updates_rows_in_place(qapp: QGuiApplication):
    model = WifiNetworkList()
    model.update([network_row(network) for network in sort_networks(NETWORKS)])
    inserted: list[int] = []

    def on_inserted(_parent: QModelIndex, first: int, _last: int) -> None:
        inserted.append(first)

    model.rowsInserted.connect(on_inserted)

    model.update([network_row(WifiNetwork("Cafe", 95, False, False)), network_row(NETWORKS[2])])
    assert rows(model) == ["Cafe", "Home"]
    assert model.rows[0]["quality"] == 95
    assert inserted == []


def test_watching_reads_the_list_and_scans(client: FakeWlan, wifi: WifiNetworks):
    wifi.setProperty("watching", True)
    wait(50)
    assert client.scans == 1 and wifi.property("scanning") is True
    assert wifi.property("available") is True and wifi.property("enabled") is True
    assert rows(wifi.property("networks")) == ["Home", "Neighbour", "Cafe", ""]

    client.found = [WifiNetwork("Home", 70, True, True, profile="Home")]
    reads = client.reads
    client.notification(WlanNotificationAcm.SCAN_COMPLETE)
    wait(50)
    assert wifi.property("scanning") is False
    assert rows(wifi.property("networks")) == ["Home"]
    # The finished scan is read once.
    assert client.reads == reads + 1


def test_without_a_wifi_adapter_nothing_is_an_error(client: FakeWlan, wifi: WifiNetworks):
    client.scan_result = ScanStatus.UNAVAILABLE
    wifi.setProperty("watching", True)
    wait(50)
    assert wifi.property("available") is False and wifi.property("error") == ""


def test_a_failed_scan_reports_its_error_code(client: FakeWlan, wifi: WifiNetworks):
    client.scan_result = ScanStatus.ACCESS_DENIED
    wifi.setProperty("watching", True)
    wait(50)
    assert wifi.property("error") == "accessDenied"
    assert wifi.property("networks").property("count") == 0


def test_the_switch_follows_and_changes_the_radio(client: FakeWlan, radio: FakeRadio, wifi: WifiNetworks):
    client.scan_result = ScanStatus.ACCESS_DENIED
    wifi.setProperty("watching", True)
    wait(50)
    assert radio.handlers and wifi.property("error") == "accessDenied"

    wifi.setEnabled(False)
    wait(50)
    assert radio.requested == [RadioState.OFF]
    radio.turn(RadioState.OFF)
    wait(50)
    assert wifi.property("enabled") is False and wifi.property("error") == ""
    assert wifi.property("networks").property("count") == 0

    # Reopening while Wi-Fi is off does not scan.
    wifi.setProperty("watching", False)
    wifi.setProperty("watching", True)
    wait(50)
    assert client.scans == 1

    radio.turn(RadioState.ON)
    wait(50)
    assert wifi.property("enabled") is True and client.scans == 2
    wifi.setProperty("watching", False)
    wait(50)
    assert not radio.handlers


def test_a_wrong_password_reports_its_error_code(wifi: WifiNetworks, monkeypatch: pytest.MonkeyPatch):
    joined: list[tuple[str, str, bool, bool]] = []

    def connect(ssid: str, password: str, auto: bool, hidden: bool = False) -> WiFiConnectionStatus:
        joined.append((ssid, password, auto, hidden))
        return WiFiConnectionStatus.INVALID_CREDENTIAL

    monkeypatch.setattr(wifi_module.wlan, "connect", connect)
    wifi.connectTo("Neighbour", "hunter22", False)
    assert wifi.property("connecting") is True and wifi.property("connectingTo") == "Neighbour"
    wait(100)
    assert joined == [("Neighbour", "hunter22", False, False)]
    assert wifi.property("connecting") is False
    assert wifi.property("error") == "invalidCredential"


def test_a_connection_that_fails_stops_connecting(wifi: WifiNetworks, monkeypatch: pytest.MonkeyPatch):
    def connect(*_args: Any) -> WiFiConnectionStatus:
        problem = OSError("Access is denied")
        problem.winerror = E_ACCESSDENIED
        raise problem

    monkeypatch.setattr(wifi_module.wlan, "connect", connect)
    wifi.connectTo("Neighbour", "", True)
    wait(100)
    assert wifi.property("connecting") is False
    assert wifi.property("error") == "accessDenied"


def test_forgetting_uses_the_saved_profile(client: FakeWlan, wifi: WifiNetworks):
    wifi.forget("Neighbour")
    wifi.forget("Home")
    wait(50)
    assert client.forgotten == ["Home"]


def test_the_wlan_handle_is_only_used_off_the_ui_thread(client: FakeWlan, wifi: WifiNetworks):
    wifi.setProperty("watching", True)
    client.notification(WlanNotificationAcm.SCAN_COMPLETE)
    wifi.forget("Home")
    wifi.setProperty("watching", False)
    wait(50)
    assert client.scans == 1 and client.forgotten == ["Home"] and client.closes >= 1
    assert len(client.threads) == 1
    assert threading.main_thread() not in client.threads


@pytest.fixture
def make_widget(fake_watcher: FakeWatcher, client: FakeWlan) -> Iterator[Callable[[], QQuickItem]]:
    """Creates the widget when called, so a test can set up the connection first, and deletes it with its root item and
    QML engine when the test ends; objects an engine created go before the engine."""
    made: list[tuple[QQmlEngine, QQuickItem, QQuickItem]] = []

    def create() -> QQuickItem:
        register_qml_types()
        engine = QQmlEngine()
        engine.addImportPath(QML_IMPORT_PATH)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Network" / "Network.qml")))
        widget = component.create()
        assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
        wait(10)
        # Qt counts an item as visible only when its parent is visible.
        root = QQuickItem()
        widget.setParentItem(root)
        made.append((engine, root, widget))
        return widget

    yield create
    for engine, root, widget in made:
        widget.setParentItem(None)
        sip.delete(widget)
        sip.delete(root)
        # QML deletes the widget's own objects, such as its WifiNetworks, with deleteLater: run those deletions now,
        # while their engine exists, as YASB does when it closes a bar
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        sip.delete(engine)


def item(widget: QQuickItem, name: str) -> QQuickItem:
    found = find_item(widget, name)
    assert found is not None, name
    return found


def test_network_is_discovered_as_a_builtin_qml_widget():
    assert find_widget_file("Network") == BUILTIN_WIDGETS_DIR / "Network/Network.qml"


def test_the_widget_fills_the_label_placeholders(fake_watcher: FakeWatcher, make_widget: Callable[[], QQuickItem]):
    widget = make_widget()
    label = item(widget, "label")
    widget.setProperty("label", "")
    assert label.property("visible") is False
    widget.setProperty("label", "{name} {signal}% {ip} {nope}")
    assert label.property("text") == "Home 75% 192.168.0.10 {nope}"
    widget.setProperty("showAlternate", True)
    assert label.property("text") == "Home"

    fake_watcher.change(DISCONNECTED)
    assert label.property("text") == "Disconnected"
    widget.setProperty("alternateLabel", "{signal}{ip}")
    assert label.property("visible") is False
    assert item(widget, "icon").property("glyph") == widget.property("disconnectedIcon")


def test_the_widget_shows_ethernet_a_vpn_and_mobile(fake_watcher: FakeWatcher, make_widget: Callable[[], QQuickItem]):
    fake_watcher.connection = ETHERNET
    widget = make_widget()
    # A cable has no signal, so a signal label leaves only the icon.
    widget.setProperty("label", "{signal}")
    assert item(widget, "label").property("visible") is False
    widget.setProperty("showAlternate", True)
    assert item(widget, "label").property("text") == "Network 2"
    assert item(widget, "icon").property("glyph") == widget.property("ethernetIcon")

    widget.setProperty("hideIfEthernet", True)
    assert widget.property("visible") is False and widget.property("implicitWidth") == 0
    fake_watcher.change(connection("other", "CloudflareWARP", ipAddress="172.16.0.2"))
    assert widget.property("visible") is True
    assert item(widget, "label").property("text") == "CloudflareWARP"
    assert item(widget, "icon").property("glyph") == widget.property("otherIcon")

    # Mobile shows its signal bars and is named as Windows names it.
    fake_watcher.change(MOBILE)
    assert item(widget, "label").property("text") == "Orange (LTE)"
    assert item(widget, "icon").property("glyph") == ""
    # Without a network name or type, such as while mobile data reconnects, the adapter's name.
    fake_watcher.change({**MOBILE, "name": "", "mobileType": ""})
    assert item(widget, "label").property("text") == "Sieć komórkowa"


def test_the_widget_marks_a_connection_without_internet(
    fake_watcher: FakeWatcher, make_widget: Callable[[], QQuickItem]
):
    widget = make_widget()
    assert item(widget, "icon").property("badge") == ""
    fake_watcher.change({**HOME, "connectivity": "constrained"})
    assert item(widget, "icon").property("badge") == widget.property("noInternetIcon")

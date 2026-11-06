import threading
from typing import Any

import pytest
from PyQt6.QtCore import QModelIndex, QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from winrt.windows.devices.wifi import WiFiConnectionStatus

from core.qml_types import register_qml_types
from core.services.wifi import monitor as monitor_module
from core.services.wifi.monitor import NetworkList, WifiMonitor, network_row, sort_networks
from core.services.wifi.wlan import Network, ScanStatus
from core.utils.win32.constants import WlanNotificationAcm
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

WIFI = {"kind": "wifi", "name": "Home", "strength": 75, "ipAddress": "192.168.0.10"}
ETHERNET = {"kind": "ethernet", "name": "Network 2", "strength": -1, "ipAddress": "10.0.0.5"}
NETWORKS = [
    Network("Cafe", 40, False, False),
    Network("", 90, True, False),
    Network("Home", 70, True, True, profile="Home", auto_connect=True),
    Network("Neighbour", 80, True, False),
]


class FakeConnection(QObject):
    statusChanged = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.status: dict[str, Any] = WIFI
        self.subscribers: dict[int, tuple[int, bool]] = {}
        self.refreshes = 0

    def subscribe(self, key: int, interval: int, exact: bool) -> None:
        self.subscribers[key] = (interval, exact)

    def unsubscribe(self, key: int) -> None:
        self.subscribers.pop(key, None)

    def refresh(self) -> None:
        self.refreshes += 1

    def change(self, status: dict[str, Any]) -> None:
        self.status = status
        self.statusChanged.emit(status)


class FakeWlan:
    def __init__(self) -> None:
        self.scan_result = ScanStatus.SUCCESS
        self.found = list(NETWORKS)
        self.scans = 0
        self.notify: Any = None
        self.forgotten: list[str] = []
        self.closes = 0
        # Track which threads call the WLAN handle.
        self.threads: set[threading.Thread] = set()

    def __call__(self, on_notification: Any = None) -> FakeWlan:
        self.notify = on_notification
        return self

    def scan(self) -> ScanStatus:
        self.threads.add(threading.current_thread())
        self.scans += 1
        return self.scan_result

    def networks(self, profiles: bool = True) -> list[Network]:
        self.threads.add(threading.current_thread())
        return list(self.found)

    def close(self) -> None:
        self.threads.add(threading.current_thread())
        self.closes += 1

    def forget(self, profile: str) -> None:
        self.threads.add(threading.current_thread())
        self.forgotten.append(profile)


@pytest.fixture
def connection(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    fake = FakeConnection()
    monkeypatch.setattr(monitor_module.ConnectionMonitor, "instance", lambda: fake)
    return fake


@pytest.fixture
def client(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWlan:
    fake = FakeWlan()
    monkeypatch.setattr(monitor_module, "WlanClient", fake)
    return fake


def rows(model: NetworkList) -> list[str]:
    return [row["ssid"] for row in model.rows]


def create_widget() -> tuple[QQmlEngine, QQuickItem, QQuickItem]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Wifi" / "Wifi.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    # Qt counts an item as visible only when its parent is visible.
    root = QQuickItem()
    widget.setParentItem(root)
    return engine, root, widget


def item(widget: QQuickItem, name: str) -> QQuickItem:
    found = find_item(widget, name)
    assert found is not None, name
    return found


def test_networks_sort_connected_first_and_hidden_last():
    assert [network.ssid for network in sort_networks(NETWORKS)] == ["Home", "Neighbour", "Cafe", ""]


def test_the_list_updates_rows_in_place(qapp: QGuiApplication):
    model = NetworkList()
    model.update([network_row(network) for network in sort_networks(NETWORKS)])
    inserted: list[int] = []

    def on_inserted(_parent: QModelIndex, first: int, _last: int) -> None:
        inserted.append(first)

    model.rowsInserted.connect(on_inserted)

    model.update([network_row(Network("Cafe", 95, False, False)), network_row(NETWORKS[2])])
    assert rows(model) == ["Cafe", "Home"]
    assert model.rows[0]["quality"] == 95
    assert inserted == []


def test_watching_reads_the_list_and_scans(connection: FakeConnection, client: FakeWlan):
    monitor = WifiMonitor()
    wait(10)
    assert id(monitor) in connection.subscribers
    monitor.setProperty("watching", True)
    wait(50)
    assert client.scans == 1 and monitor.property("scanning") is True
    assert rows(monitor.property("networks")) == ["Home", "Neighbour", "Cafe", ""]

    client.found = [Network("Home", 70, True, True, profile="Home")]
    client.notify(WlanNotificationAcm.SCAN_COMPLETE)
    wait(50)
    assert monitor.property("scanning") is False
    assert rows(monitor.property("networks")) == ["Home"]


def test_a_failed_scan_explains_and_links_to_settings(connection: FakeConnection, client: FakeWlan):
    client.scan_result = ScanStatus.ACCESS_DENIED
    monitor = WifiMonitor()
    monitor.setProperty("watching", True)
    wait(50)
    assert monitor.property("error") == "Location services are turned off"
    assert monitor.property("errorLink") == "ms-settings:privacy-location"
    assert monitor.property("networks").property("count") == 0


def test_a_wrong_password_shows_an_error(connection: FakeConnection, client: FakeWlan, monkeypatch: pytest.MonkeyPatch):
    joined: list[tuple[str, str, bool, bool]] = []

    def connect(ssid: str, password: str, auto: bool, hidden: bool = False) -> WiFiConnectionStatus:
        joined.append((ssid, password, auto, hidden))
        return WiFiConnectionStatus.INVALID_CREDENTIAL

    monkeypatch.setattr(monitor_module.wlan, "connect", connect)
    monitor = WifiMonitor()
    monitor.connectTo("Neighbour", "hunter22", False)
    assert monitor.property("connecting") is True and monitor.property("connectingTo") == "Neighbour"
    wait(100)
    assert joined == [("Neighbour", "hunter22", False, False)]
    assert monitor.property("connecting") is False
    assert monitor.property("error") == "Wrong password"
    assert connection.refreshes == 1


def test_forgetting_uses_the_saved_profile(connection: FakeConnection, client: FakeWlan):
    monitor = WifiMonitor()
    monitor.forget("Neighbour")
    monitor.forget("Home")
    wait(50)
    assert client.forgotten == ["Home"]


def test_the_widget_fills_the_label_placeholders(connection: FakeConnection, client: FakeWlan):
    _engine, _root, widget = create_widget()
    label = item(widget, "label")
    assert label.property("visible") is False
    widget.setProperty("label", "{wifi_name} {wifi_strength}% {ip_addr} {nope}")
    assert label.property("text") == "Home 75% 192.168.0.10 {nope}"
    widget.setProperty("showAlternate", True)
    assert label.property("text") == "Home"

    connection.change({"kind": "none", "name": "", "strength": -1, "ipAddress": ""})
    assert label.property("text") == "Disconnected"
    assert item(widget, "icon").property("glyph") == widget.property("disconnectedIcon")


def test_the_widget_shows_ethernet(connection: FakeConnection, client: FakeWlan):
    connection.status = ETHERNET
    _engine, _root, widget = create_widget()
    widget.setProperty("showAlternate", True)
    assert item(widget, "label").property("text") == "10.0.0.5"
    assert item(widget, "icon").property("glyph") == widget.property("ethernetIcon")

    widget.setProperty("hideIfEthernet", True)
    assert widget.property("visible") is False and widget.property("implicitWidth") == 0
    connection.change(WIFI)
    assert widget.property("visible") is True
    assert item(widget, "label").property("text") == "Home"


def test_the_wlan_handle_is_only_used_off_the_ui_thread(connection: FakeConnection, client: FakeWlan):
    monitor = WifiMonitor()
    monitor.setProperty("watching", True)
    client.notify(WlanNotificationAcm.SCAN_COMPLETE)
    monitor.forget("Home")
    monitor.setProperty("watching", False)
    wait(50)
    assert client.scans == 1 and client.forgotten == ["Home"] and client.closes >= 1
    assert len(client.threads) == 1
    assert threading.main_thread() not in client.threads

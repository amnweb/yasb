import threading
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.bluetooth import bluetooth_managers
from core.services.bluetooth import monitor as monitor_module
from core.services.bluetooth.bluetooth_managers import BluetoothManager
from core.services.bluetooth.bluetooth_types import BluetoothStatus, DeviceInfo, DeviceType, ScanResultStatus
from core.services.bluetooth.monitor import BluetoothMonitor, DeviceList, device_row
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

HEADPHONES = DeviceInfo(
    "WH-1000XM4",
    "00:00:00:00:00:01",
    address_int=1,
    connected=True,
    paired=True,
    device_type=DeviceType.HEADPHONES,
    battery=80,
    profiles=["mic", "audio"],
)
MOUSE = DeviceInfo("MX Master", "00:00:00:00:00:02", address_int=2, paired=True, device_type=DeviceType.MOUSE)
KEYBOARD = DeviceInfo(
    "keys", "00:00:00:00:00:03", address_int=3, connected=True, paired=True, is_le=True, device_type=DeviceType.KEYBOARD
)
PHONE = DeviceInfo("Pixel", "00:00:00:00:00:04", address_int=4, device_type=DeviceType.PHONE)


class FakeManager(QObject):
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(object, object)
    status_updated = pyqtSignal(object)
    refresh_failed = pyqtSignal(str)
    connection_finished = pyqtSignal(bool, str, object)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Any] = []
        self.has_pending_scan = False
        self.radio_allowed = True
        self.releases = 0

    def start(self) -> None:
        self.calls.append("start")

    def release(self) -> None:
        self.releases += 1

    def refresh(self) -> None:
        self.calls.append("refresh")

    def scan(self) -> None:
        self.calls.append("scan")

    def set_radio(self, on: bool) -> bool:
        self.calls.append(("radio", on))
        return self.radio_allowed

    def connect_device(self, address: str) -> None:
        self.calls.append(("connect", address))

    def disconnect_device(self, address: str) -> None:
        self.calls.append(("disconnect", address))

    def status(self, radio_on: bool, *devices: DeviceInfo) -> None:
        self.status_updated.emit(BluetoothStatus(radio_on=radio_on, devices=list(devices)))


@pytest.fixture
def manager(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeManager:
    fake = FakeManager()
    monkeypatch.setattr(monitor_module.BluetoothManager, "acquire", lambda: fake)
    return fake


def until(condition: Callable[[], Any]) -> None:
    for _ in range(200):
        if condition():
            return
        wait(10)
    assert condition()


def names(model: DeviceList) -> list[str]:
    return [row["name"] for row in model.rows]


@pytest.fixture
def widget(manager: FakeManager) -> Iterator[tuple[QQuickItem, list[str]]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Bluetooth" / "Bluetooth.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    host.resize(200, 36)
    item.setParentItem(host.contentItem())
    host.show()
    try:
        yield item, warnings
    finally:
        item.setParentItem(None)
        item.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        host.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def test_a_row_shows_battery_only_while_connected():
    assert device_row(HEADPHONES)["battery"] == 80
    assert device_row(DeviceInfo("Buds", "00:00:00:00:00:05", paired=True, battery=50))["battery"] == -1
    assert device_row(HEADPHONES)["canConnect"] is True and device_row(MOUSE)["canConnect"] is False


def test_the_bar_names_the_connected_devices(manager: FakeManager, widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    label, icon = find_item(item, "label"), find_item(item, "icon")
    assert label is not None and icon is not None
    for name, glyph in (("offIcon", "off"), ("onIcon", "on"), ("connectedIcon", "connected")):
        item.setProperty(name, glyph)
    assert label.property("visible") is False and icon.property("text") == "off"

    item.setProperty("label", "{device_name} ({device_count})")
    item.setProperty("deviceAliases", {"WH-1000XM4": "Headphones"})
    manager.status(True, HEADPHONES, MOUSE, KEYBOARD)
    assert label.property("text") == "Headphones, keys (2)"
    assert icon.property("text") == "connected"

    item.setProperty("maxLength", 8)
    assert label.property("text") == "Headphon..."
    item.setProperty("maxLength", 0)
    manager.status(True, MOUSE)
    assert label.property("text") == "No devices connected (0)" and icon.property("text") == "on"
    manager.status(False)
    assert icon.property("text") == "off"
    assert not warnings


def test_watching_refreshes_and_lists_the_paired_devices(manager: FakeManager):
    monitor = BluetoothMonitor()
    manager.status(True, MOUSE, HEADPHONES, KEYBOARD)
    assert names(monitor.property("devices")) == []
    monitor.setProperty("watching", True)
    assert manager.calls == ["start", "refresh"] and monitor.property("busy") is True
    # Connected first, then by name
    assert names(monitor.property("devices")) == ["keys", "WH-1000XM4", "MX Master"]
    manager.status(True, MOUSE, HEADPHONES)
    assert monitor.property("busy") is False
    assert names(monitor.property("devices")) == ["WH-1000XM4", "MX Master"]
    sip.delete(monitor)
    assert manager.releases == 1


def test_a_scan_lists_new_devices_apart_from_paired_ones(manager: FakeManager):
    monitor = BluetoothMonitor()
    monitor.setProperty("watching", True)
    monitor.scan()
    assert manager.calls[-1] == "scan" and monitor.property("busy") is True
    manager.scan_completed.emit(ScanResultStatus.SUCCESS, [HEADPHONES, MOUSE, PHONE])
    assert monitor.property("busy") is False
    assert names(monitor.property("devices")) == ["WH-1000XM4", "MX Master"]
    assert names(monitor.property("nearby")) == ["Pixel"]

    # A refresh keeps what the scan found until the device is paired
    monitor.refresh()
    manager.status(True, HEADPHONES, MOUSE)
    assert names(monitor.property("nearby")) == ["Pixel"]
    paired = DeviceInfo("Pixel", PHONE.address, address_int=4, paired=True, device_type=DeviceType.PHONE)
    manager.status(True, HEADPHONES, MOUSE, paired)
    assert names(monitor.property("nearby")) == []
    assert names(monitor.property("devices")) == ["WH-1000XM4", "MX Master", "Pixel"]


def test_turning_the_radio_off_empties_the_lists(manager: FakeManager):
    monitor = BluetoothMonitor()
    monitor.setProperty("watching", True)
    manager.scan_completed.emit(ScanResultStatus.SUCCESS, [HEADPHONES, PHONE])
    monitor.setRadio(False)
    assert manager.calls[-1] == ("radio", False)
    assert monitor.property("radioOn") is False and monitor.property("connected") == []
    manager.status(False)
    assert names(monitor.property("devices")) == [] and names(monitor.property("nearby")) == []
    assert monitor.property("busy") is False


def test_a_refused_radio_change_explains(manager: FakeManager):
    monitor = BluetoothMonitor()
    manager.status(True, HEADPHONES)
    manager.radio_allowed = False
    monitor.setRadio(False)
    assert monitor.property("radioOn") is True
    assert monitor.property("error") == "Unable to change Bluetooth power"


def test_scan_failures_explain(manager: FakeManager):
    monitor = BluetoothMonitor()
    monitor.setProperty("watching", True)
    manager.scan_completed.emit(ScanResultStatus.ERROR, [])
    assert monitor.property("error") == "Failed to scan for devices"
    manager.scan_completed.emit(ScanResultStatus.API_UNAVAILABLE, [])
    assert monitor.property("error") == "Bluetooth API unavailable"


def test_one_connection_at_a_time_and_a_failure_explains(manager: FakeManager):
    monitor = BluetoothMonitor()
    monitor.setProperty("watching", True)
    monitor.connectDevice(MOUSE.address)
    monitor.disconnectDevice(HEADPHONES.address)
    assert manager.calls[-1] == ("connect", MOUSE.address)
    assert monitor.property("pending") == MOUSE.address
    manager.connection_finished.emit(False, "Failed to connect device", MOUSE)
    assert monitor.property("pending") == ""
    assert monitor.property("error") == "Failed to connect device"
    monitor.disconnectDevice(HEADPHONES.address)
    assert manager.calls[-1] == ("disconnect", HEADPHONES.address)


def test_the_popup_lists_the_devices_with_their_actions(manager: FakeManager, widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    manager.status(True, HEADPHONES, MOUSE)
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    assert manager.calls[-1] == "refresh"
    manager.status(True, HEADPHONES, MOUSE)
    monitor = item.findChild(BluetoothMonitor)
    assert monitor is not None
    monitor.scan()
    manager.scan_completed.emit(ScanResultStatus.SUCCESS, [HEADPHONES, MOUSE, PHONE])
    content = window.contentItem()
    known, nearby = find_item(content, "known"), find_item(content, "nearby")
    assert known is not None and nearby is not None
    assert known.property("count") == 2 and nearby.property("count") == 1

    def action(address: str) -> str:
        popup.setProperty("expanded", address)
        buttons: list[QQuickItem] = []

        def collect(parent: QQuickItem) -> None:
            for child in parent.childItems():
                if child.objectName() == "action" and child.isVisible():
                    buttons.append(child)
                collect(child)

        collect(content)
        assert len(buttons) == 1
        return buttons[0].property("text")

    assert action(HEADPHONES.address) == "Disconnect"
    assert action(MOUSE.address) == "Manage"
    assert action(PHONE.address) == "Pair"
    assert not warnings


class Recorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.statuses: list[BluetoothStatus] = []

    def record(self, status: BluetoothStatus) -> None:
        self.statuses.append(status)


def test_the_manager_works_on_its_own_thread(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    threads: list[threading.Thread] = []

    async def radio_is_on() -> bool:
        threads.append(threading.current_thread())
        return False

    async def bind_radio(_on_changed: Any) -> None:
        return None

    def open_adapter_watch(_on_changed: Any) -> None:
        return None

    def no_native() -> None:
        raise RuntimeError("no BluetoothAPIs.dll")

    monkeypatch.setattr(bluetooth_managers, "radio_is_on", radio_is_on)
    monkeypatch.setattr(bluetooth_managers, "bind_radio", bind_radio)
    monkeypatch.setattr(bluetooth_managers, "open_adapter_watch", open_adapter_watch)
    monkeypatch.setattr(bluetooth_managers, "BluetoothNativeApi", no_native)
    manager = BluetoothManager.acquire()
    recorder = Recorder()
    manager.status_updated.connect(recorder.record)
    manager.start()
    until(lambda: recorder.statuses)
    assert recorder.statuses[-1].radio_on is False
    assert threads and threading.main_thread() not in threads
    manager.release()
    until(lambda: not manager._thread.is_alive())  # pyright: ignore[reportPrivateUsage]
    assert BluetoothManager.acquire() is not manager
    BluetoothManager.acquire().release()
    BluetoothManager._users = 0  # pyright: ignore[reportPrivateUsage]

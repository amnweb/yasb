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

from core.utils.qml import qml_property
from core.widgets.services.bluetooth.bluetooth_managers import BluetoothManager
from core.widgets.services.bluetooth.bluetooth_types import BluetoothStatus, DeviceInfo, ScanResultStatus

ERROR_SHOWN_MS = 4000

ROLES = ["address", "name", "kind", "connected", "known", "battery", "profiles", "canConnect"]

SCAN_ERRORS = {
    ScanResultStatus.API_UNAVAILABLE: "Bluetooth API unavailable",
    ScanResultStatus.ERROR: "Failed to scan for devices",
}


def known(device: DeviceInfo) -> bool:
    return bool(device.address) and (device.paired or device.remembered)


def device_row(device: DeviceInfo) -> dict[str, Any]:
    return {
        "address": device.address,
        "name": device.name,
        "kind": device.device_type.value,
        "connected": device.connected,
        "known": device.paired or device.remembered,
        # -1 when the device reports none or is not connected
        "battery": device.battery if device.battery is not None and device.connected else -1,
        "profiles": list(device.profiles),
        "canConnect": device.supports_connect,
    }


def sort_devices(devices: list[DeviceInfo]) -> list[DeviceInfo]:
    """Connected devices first, then by name."""
    return sorted(devices, key=lambda device: (not device.connected, device.name.lower()))


class DeviceList(QAbstractListModel):
    """Device rows keyed by address. In-place updates keep an open row open."""

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

    def addresses(self) -> set[str]:
        return {row["address"] for row in self._rows}

    def update(self, devices: list[DeviceInfo]) -> None:
        rows = [device_row(device) for device in sort_devices(devices)]
        count = len(self._rows)
        wanted = {row["address"] for row in rows}
        for index in reversed(range(len(self._rows))):
            if self._rows[index]["address"] not in wanted:
                self.beginRemoveRows(QModelIndex(), index, index)
                del self._rows[index]
                self.endRemoveRows()
        for index, row in enumerate(rows):
            current = next((i for i in range(index, len(self._rows)) if self._rows[i]["address"] == row["address"]), -1)
            if current == -1:
                self.beginInsertRows(QModelIndex(), index, index)
                self._rows.insert(index, row)
                self.endInsertRows()
                continue
            if current != index:
                self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), index)
                self._rows.insert(index, self._rows.pop(current))
                self.endMoveRows()
            if self._rows[index] != row:
                self._rows[index] = row
                self.dataChanged.emit(self.index(index), self.index(index))
        if len(self._rows) != count:
            self.countChanged.emit()


class BluetoothMonitor(QObject):
    """The radio and connected devices for the bar, and while watching, the devices for the popup."""

    statusChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    settingsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._radio_on = False
        self._connected: list[str] = []
        self._devices: list[DeviceInfo] = []
        self._known = DeviceList(self)
        self._nearby: dict[str, DeviceInfo] = {}
        self._nearby_list = DeviceList(self)
        self._watching = False
        self._busy = False
        # The list from the last scan stays until a scan or the known devices replace it
        self._inquiry = False
        self._pending = ""
        self._error = ""

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(ERROR_SHOWN_MS)
        self._error_timer.timeout.connect(lambda: self._set_error(""))

        self._manager = BluetoothManager.acquire()
        self._manager.status_updated.connect(self._on_status)
        self._manager.refresh_failed.connect(self._on_refresh_failed)
        self._manager.scan_started.connect(self._on_scan_started)
        self._manager.scan_completed.connect(self._on_scan_completed)
        self._manager.connection_finished.connect(self._on_connection_finished)
        self._manager.start()
        manager = self._manager
        self.destroyed.connect(lambda: manager.release())

    @qml_property(bool, notify=statusChanged)
    def radioOn(self) -> bool:
        return self._radio_on

    # Names of the paired devices that are connected
    @qml_property(list, notify=statusChanged)
    def connected(self) -> list[str]:
        return self._connected

    # [{address, name, kind, connected, known, battery, profiles, canConnect}], connected first
    @qml_property(QObject, constant=True)
    def devices(self) -> DeviceList:
        return self._known

    # Unpaired devices the last scan found
    @qml_property(QObject, constant=True)
    def nearby(self) -> DeviceList:
        return self._nearby_list

    @qml_property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    # Address of the device being connected or disconnected, or empty
    @qml_property(str, notify=stateChanged)
    def pending(self) -> str:
        return self._pending

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    def _get_watching(self) -> bool:
        return self._watching

    def _set_watching(self, value: bool) -> None:
        if value == self._watching:
            return
        self._watching = value
        self.settingsChanged.emit()
        if value:
            self._known.update([device for device in self._devices if known(device)])
            self._show_nearby()
            self.refresh()
        else:
            self._pending = ""
            self._set_busy(False)
            self.stateChanged.emit()

    # Refresh and track the devices while the popup is open
    watching = pyqtProperty(bool, _get_watching, _set_watching, notify=settingsChanged)

    @pyqtSlot()
    def refresh(self) -> None:
        self._inquiry = False
        self._set_error("")
        self._set_busy(True)
        self._manager.refresh()

    @pyqtSlot()
    def scan(self) -> None:
        self._inquiry = True
        self._set_error("")
        self._set_busy(True)
        self._manager.scan()

    @pyqtSlot(bool)
    def setRadio(self, on: bool) -> None:
        if not self._manager.set_radio(on):
            self._show_error("Unable to change Bluetooth power")
            return
        self._set_busy(True)
        self._set_radio(on, self._connected if on else [])

    @pyqtSlot(str)
    def connectDevice(self, address: str) -> None:
        if self._start_pending(address):
            self._manager.connect_device(address)

    @pyqtSlot(str)
    def disconnectDevice(self, address: str) -> None:
        if self._start_pending(address):
            self._manager.disconnect_device(address)

    def _start_pending(self, address: str) -> bool:
        if self._pending:
            return False
        self._pending = address
        self.stateChanged.emit()
        return True

    def _set_radio(self, on: bool, connected: list[str]) -> None:
        if (on, connected) != (self._radio_on, self._connected):
            self._radio_on, self._connected = on, connected
            self.statusChanged.emit()

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.stateChanged.emit()

    def _set_error(self, error: str) -> None:
        if error != self._error:
            self._error = error
            self.stateChanged.emit()

    def _show_error(self, error: str) -> None:
        self._set_error(error)
        self._error_timer.start()

    def _show_nearby(self) -> None:
        paired = self._known.addresses()
        self._nearby = {address: device for address, device in self._nearby.items() if address not in paired}
        self._nearby_list.update(list(self._nearby.values()))

    def _clear_lists(self) -> None:
        self._known.update([])
        self._nearby = {}
        self._nearby_list.update([])

    def _on_status(self, status: BluetoothStatus) -> None:
        self._devices = status.devices
        self._set_radio(
            status.radio_on, [device.name for device in status.connected_devices] if status.radio_on else []
        )
        if not self._watching:
            return
        if not status.radio_on:
            self._set_busy(False)
            self._clear_lists()
            return
        self._known.update([device for device in status.devices if known(device)])
        if not self._inquiry:
            self._show_nearby()
            self._set_busy(False)

    def _on_refresh_failed(self, message: str) -> None:
        if self._watching:
            self._set_busy(False)
            self._show_error(message or "Bluetooth refresh failed")

    def _on_scan_started(self) -> None:
        if self._watching:
            self._set_busy(True)

    def _on_scan_completed(self, status: ScanResultStatus, devices: list[DeviceInfo]) -> None:
        if not self._watching:
            return
        if not self._manager.has_pending_scan:
            self._set_busy(False)
        if status == ScanResultStatus.RADIO_OFF:
            self._set_radio(False, [])
            self._clear_lists()
            return
        if status in SCAN_ERRORS:
            self._show_error(SCAN_ERRORS[status])
            return
        self._known.update([device for device in devices if known(device)])
        if self._inquiry:
            self._nearby = {device.address: device for device in devices if device.address and not known(device)}
        self._inquiry = False
        self._show_nearby()

    def _on_connection_finished(self, success: bool, message: str, _device: DeviceInfo) -> None:
        self._pending = ""
        self.stateChanged.emit()
        if not success and self._watching:
            self._show_error(message)

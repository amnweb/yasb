import os
from dataclasses import replace
from functools import partial
from typing import override

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.ui.components.loader import LoaderLine
from core.utils.qobject import is_valid_qobject
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.bluetooth import BluetoothBatteryIconsConfig, BluetoothMenuConfig
from core.widgets.services.bluetooth.bluetooth_managers import BluetoothManager
from core.widgets.services.bluetooth.bluetooth_types import (
    BluetoothStatus,
    DeviceInfo,
    ScanResultStatus,
)

_BATTERY_BANDS: tuple[tuple[int, str], ...] = (
    (10, "empty"),
    (30, "low"),
    (60, "medium"),
    (90, "high"),
)


def _battery_icon(percent: int, icons: BluetoothBatteryIconsConfig) -> tuple[str, str]:
    for ceiling, name in _BATTERY_BANDS:
        if percent <= ceiling:
            return name, getattr(icons, name)
    return "full", icons.full


class BluetoothItem(QFrame):
    clicked = pyqtSignal()
    connect_pressed = pyqtSignal(object)
    disconnect_pressed = pyqtSignal(object)
    settings_pressed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active = False
        self._busy = False
        self._data = DeviceInfo(name="", address="")
        self._labels: dict[str, str] = {}

        self.setProperty("class", "bluetooth-item")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        details = QFrame(self)
        details.setProperty("class", "details-container")
        details.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(details)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.device_icon = QLabel(details)
        self.device_icon.setProperty("class", "icon")
        self.device_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_col = QWidget(details)
        text_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text = QVBoxLayout(text_col)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        self.device_name = QLabel(text_col)
        self.device_name.setProperty("class", "name")
        self.status_label = QLabel(text_col)
        self.status_label.setProperty("class", "status")
        text.addWidget(self.device_name)
        text.addWidget(self.status_label)

        self.battery_label = QLabel(details)
        self.battery_label.setProperty("class", "battery")
        self.battery_icon = QLabel(details)
        self.battery_icon.setProperty("class", "battery-icon")

        row.addWidget(self.device_icon)
        row.addWidget(text_col, 1)
        row.addWidget(self.battery_label)
        row.addWidget(self.battery_icon)

        self._actions = QFrame(self)
        self._actions.setProperty("class", "controls-container")
        self._actions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions = QHBoxLayout(self._actions)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(0)
        self.connect_button = QPushButton("Connect", self._actions)
        self.connect_button.setProperty("class", "connect")
        self.connect_button.clicked.connect(self._on_action_clicked)
        actions.addStretch(1)
        actions.addWidget(self.connect_button)
        self._actions.hide()

        root.addWidget(details)
        root.addWidget(self._actions)

    @property
    def data(self) -> DeviceInfo:
        return self._data

    @data.setter
    def data(self, data: DeviceInfo):
        self._data = data
        self.device_name.setText(data.name)
        self.device_icon.setText(data.icon)
        self.status_label.setText(data.status_text)
        show_battery = data.battery is not None and data.connected
        self.battery_label.setVisible(show_battery)
        self.battery_icon.setVisible(show_battery)
        if show_battery:
            self.battery_label.setText(f"{data.battery}%")
        if self._active and not self._busy:
            self.connect_button.setText(self._action_text())

    def set_labels(self, labels: dict[str, str]) -> None:
        self._labels = labels
        if self._active and not self._busy:
            self.connect_button.setText(self._action_text())

    @property
    def active(self) -> bool:
        return self._active

    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy(self, busy: bool, *, disconnecting: bool = False) -> None:
        self._busy = busy
        self.connect_button.setEnabled(not busy)
        if busy:
            key = "disconnecting" if disconnecting else "connecting"
            self.connect_button.setText(self._labels[key])
        elif self._active:
            self.connect_button.setText(self._action_text())

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        self.setProperty("class", f"bluetooth-item{' active' if active else ''}")
        refresh_widget_style(self)
        self._actions.setVisible(active)
        if active and not self._busy:
            self.connect_button.setEnabled(True)
            self.connect_button.setText(self._action_text())

    def _action_text(self) -> str:
        if not self._data.paired and not self._data.remembered:
            return self._labels["pair"]
        if not self._data.supports_connect:
            return self._labels["manage"]
        if self._data.connected:
            return self._labels["disconnect"]
        return self._labels["connect"]

    @pyqtSlot()
    def _on_action_clicked(self) -> None:
        if self._busy:
            return
        if (not self._data.paired and not self._data.remembered) or not self._data.supports_connect:
            self.settings_pressed.emit(self._data)
        elif self._data.connected:
            self.disconnect_pressed.emit(self._data)
        else:
            self.connect_pressed.emit(self._data)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            if self._actions.isVisible() and self._actions.geometry().contains(a0.pos()):
                return
            self.clicked.emit()
        super().mousePressEvent(a0)


class BluetoothSection(QFrame):
    item_clicked = pyqtSignal(object)
    connect_pressed = pyqtSignal(object)
    disconnect_pressed = pyqtSignal(object)
    settings_pressed = pyqtSignal(object)

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "section")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(title, self)
        title_label.setProperty("class", "section-title")
        self._layout.addWidget(title_label)
        self._items: dict[str, BluetoothItem] = {}

    @property
    def items(self) -> dict[str, BluetoothItem]:
        return self._items

    def sync(
        self,
        devices: dict[str, DeviceInfo],
        battery_icons: BluetoothBatteryIconsConfig,
        labels: dict[str, str],
    ) -> None:
        for address in set(self._items) - set(devices):
            item = self._items.pop(address)
            self._layout.removeWidget(item)
            item.deleteLater()

        ordered = sorted(devices.values(), key=lambda d: (not d.connected, d.name.lower()))
        for device in ordered:
            item = self._items.get(device.address)
            if item is None:
                item = BluetoothItem(self)
                item.clicked.connect(lambda _=False, i=item: self.item_clicked.emit(i))
                item.connect_pressed.connect(self.connect_pressed.emit)
                item.disconnect_pressed.connect(self.disconnect_pressed.emit)
                item.settings_pressed.connect(self.settings_pressed.emit)
                self._items[device.address] = item
                self._layout.addWidget(item)

            item.set_labels(labels)
            item.data = device
            if device.battery is not None and device.connected:
                level, glyph = _battery_icon(device.battery, battery_icons)
                item.battery_icon.setText(glyph)
                item.battery_icon.setProperty("class", f"battery-icon {level}")
                refresh_widget_style(item.battery_icon)

        for index, device in enumerate(ordered):
            self._layout.insertWidget(index + 1, self._items[device.address])

    def set_active(self, address: str | None) -> None:
        for key, item in self._items.items():
            item.set_active(key == address)


class BluetoothList(QScrollArea):
    connect_pressed = pyqtSignal(object)
    disconnect_pressed = pyqtSignal(object)
    settings_pressed = pyqtSignal(object)

    def __init__(self, paired_title: str, new_title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setViewportMargins(0, 0, -4, 0)
        self.viewport().setAutoFillBackground(False)

        container = QFrame(self)
        container.setProperty("class", "bluetooth-list")
        container.setAutoFillBackground(False)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.paired = BluetoothSection(paired_title, container)
        self.discovered = BluetoothSection(new_title, container)
        for section in (self.paired, self.discovered):
            section.item_clicked.connect(self._toggle_item)
            section.connect_pressed.connect(self.connect_pressed.emit)
            section.disconnect_pressed.connect(self.disconnect_pressed.emit)
            section.settings_pressed.connect(self.settings_pressed.emit)
            layout.addWidget(section)
        layout.addStretch(1)
        self.setWidget(container)

    def _toggle_item(self, item: BluetoothItem) -> None:
        if item.busy:
            return
        address = None if item.active else item.data.address
        self.paired.set_active(address if address in self.paired.items else None)
        self.discovered.set_active(address if address in self.discovered.items else None)

    def clear_active(self) -> None:
        self.paired.set_active(None)
        self.discovered.set_active(None)

    def find_item(self, address: str) -> BluetoothItem | None:
        return self.paired.items.get(address) or self.discovered.items.get(address)

    def clear_busy(self) -> None:
        for section in (self.paired, self.discovered):
            for item in section.items.values():
                if item.busy:
                    item.set_busy(False)


class BluetoothMenu(QObject):
    """Popup UI. Status/scan/connect events are forwarded from BluetoothWidget."""

    def __init__(self, parent: QWidget, menu_config: BluetoothMenuConfig, manager: BluetoothManager):
        super().__init__(parent)
        self._parent = parent
        self.menu_config = menu_config
        self.manager = manager

        self.popup: PopupWidget | None = None
        self.list: BluetoothList | None = None
        self.progress: LoaderLine | None = None
        self.power_button: QPushButton | None = None
        self.error_label: QLabel | None = None
        self._paired: dict[str, DeviceInfo] = {}
        self._discovered: dict[str, DeviceInfo] = {}
        self._inquiry = False
        self._scanning = False
        self._detached = False

    def detach(self) -> None:
        self._detached = True

    def _action_labels(self) -> dict[str, str]:
        labels = self.menu_config.labels
        return {
            "connect": labels.connect,
            "disconnect": labels.disconnect,
            "connecting": labels.connecting,
            "disconnecting": labels.disconnecting,
            "pair": labels.pair,
            "manage": labels.manage,
        }

    def show_menu(self):
        if self._detached:
            return
        popup = self.popup
        if popup and is_valid_qobject(popup) and popup.isVisible():
            popup.hide_animated()
            return
        if not (popup and is_valid_qobject(popup)):
            self._build()
        self._open()

    def _build(self) -> None:
        labels = self.menu_config.labels
        self.popup = PopupWidget(
            self._parent,
            self.menu_config.blur,
            self.menu_config.round_corners,
            self.menu_config.round_corners_type,
            self.menu_config.border_color,
            persistent=True,
        )
        self.popup.setProperty("class", "bluetooth-menu")

        root = QVBoxLayout(self.popup)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self.popup)
        header.setProperty("class", "header")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(0)

        title = QLabel(labels.title, header)
        title.setProperty("class", "title")
        radio_on = self.manager.is_radio_on()
        self.power_button = QPushButton(self._power_label(radio_on), header)
        self.power_button.setCheckable(True)
        self.power_button.setChecked(radio_on)
        self.power_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.power_button.setProperty("class", "power-button")
        self.power_button.toggled.connect(self._toggle_radio)
        header_row.addWidget(title, 1)
        header_row.addWidget(self.power_button)

        self.progress = LoaderLine(header)
        self.progress.configure(class_name="progress-bar", segment_ratio=0.40, height=2)
        self.progress.attach_to_widget(header)
        self.progress.stop()

        self.error_label = QLabel(self.popup)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setProperty("class", "error-message")
        self.error_label.hide()

        self.list = BluetoothList(
            labels.your_devices,
            labels.new_devices,
            self.popup,
        )
        self.list.connect_pressed.connect(self._connect)
        self.list.disconnect_pressed.connect(self._disconnect)
        self.list.settings_pressed.connect(self._open_device_settings)

        footer = QFrame(self.popup)
        footer.setProperty("class", "footer")
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(0)
        settings = QPushButton(labels.more_settings, footer)
        settings.setProperty("class", "settings-button")
        settings.clicked.connect(partial(self._open_uri, "ms-settings:bluetooth"))
        scan = QPushButton(self.menu_config.device_icons.scan, footer)
        scan.setProperty("class", "scan-icon")
        scan.clicked.connect(self._scan)
        footer_row.addWidget(settings)
        footer_row.addStretch(1)
        footer_row.addWidget(scan)

        root.addWidget(header)
        root.addWidget(self.error_label)
        root.addWidget(self.list, 1)
        root.addWidget(footer)
        self.popup.installEventFilter(self)
        self.popup.adjustSize()

    @override
    def eventFilter(self, obj: QObject, event) -> bool:
        if obj is self.popup and event.type() == QEvent.Type.Hide:
            self._scanning = False
            if is_valid_qobject(self.progress):
                self.progress.stop()
            if self.list is not None:
                self.list.clear_busy()
                self.list.clear_active()
        return super().eventFilter(obj, event)

    def _open(self) -> None:
        if not is_valid_qobject(self.popup):
            return
        if self.list is not None:
            self.list.clear_busy()
            self.list.clear_active()
        self._set_radio_ui(self.manager.is_radio_on())
        known = self.manager.devices()
        if known:
            self._paired = {d.address: self._decorate(d) for d in known if d.address and (d.paired or d.remembered)}
            self._apply_list()
        self.popup.adjustSize()
        self.popup.setPosition(
            alignment=self.menu_config.alignment,
            direction=self.menu_config.direction,
            offset_left=self.menu_config.offset_left,
            offset_top=self.menu_config.offset_top,
        )
        self.popup.show()
        self._refresh()

    def _refresh(self) -> None:
        """Reload paired devices via the shared manager snapshot."""
        if not is_valid_qobject(self.popup):
            return
        self._inquiry = False
        if is_valid_qobject(self.error_label):
            self.error_label.hide()
        self._start_loader()
        self.manager.refresh()

    def _scan(self) -> None:
        if not is_valid_qobject(self.popup):
            return
        self._inquiry = True
        if is_valid_qobject(self.error_label):
            self.error_label.hide()
        self._start_loader()
        self.manager.scan()

    def _start_loader(self) -> None:
        if is_valid_qobject(self.progress) and not self._scanning:
            self.progress.start()
            self._scanning = True

    def _stop_loader(self) -> None:
        if not self._scanning:
            return
        self._scanning = False
        if is_valid_qobject(self.progress):
            self.progress.stop()

    @pyqtSlot()
    def on_scan_started(self) -> None:
        if is_valid_qobject(self.popup) and self.popup.isVisible():
            self._start_loader()

    @pyqtSlot(object, object)
    def on_scan_completed(self, status: ScanResultStatus, devices: list[DeviceInfo]):
        if not is_valid_qobject(self.popup):
            return
        if not self.manager.has_pending_scan:
            self._stop_loader()
        if status == ScanResultStatus.RADIO_OFF:
            self._set_radio_ui(False)
            self._paired.clear()
            self._discovered.clear()
            self._apply_list()
            return
        if status == ScanResultStatus.API_UNAVAILABLE:
            self._show_error("Bluetooth API unavailable")
            return
        if status == ScanResultStatus.ERROR:
            self._show_error("Failed to scan for devices")
            return

        self._set_radio_ui(True)
        paired: dict[str, DeviceInfo] = {}
        discovered: dict[str, DeviceInfo] = {}
        for device in devices:
            if not device.address:
                continue
            decorated = self._decorate(device)
            if decorated.paired or decorated.remembered:
                paired[decorated.address] = decorated
            else:
                discovered[decorated.address] = decorated
        self._paired = paired
        if self._inquiry:
            self._discovered = {a: d for a, d in discovered.items() if a not in paired}
        else:
            self._discovered = {a: d for a, d in self._discovered.items() if a not in paired}
        self._inquiry = False
        self._apply_list()

    def apply_status(self, status: BluetoothStatus) -> None:
        """Apply manager status to the popup (called from BluetoothWidget only)."""
        if not is_valid_qobject(self.popup) or not self.popup.isVisible():
            return
        self._set_radio_ui(status.radio_on)
        if not status.radio_on:
            self._stop_loader()
            self._paired.clear()
            self._discovered.clear()
            self._apply_list()
            return
        # Always keep paired list in sync with manager (bar and popup share one truth)
        self._paired = {
            d.address: self._decorate(d) for d in status.devices if d.address and (d.paired or d.remembered)
        }
        if not self._inquiry:
            self._discovered = {a: d for a, d in self._discovered.items() if a not in self._paired}
            self._stop_loader()
        self._apply_list()

    def on_refresh_failed(self, message: str) -> None:
        if not is_valid_qobject(self.popup) or not self.popup.isVisible():
            return
        self._stop_loader()
        self._show_error(message or "Bluetooth refresh failed")

    @pyqtSlot(object)
    def _connect(self, device: DeviceInfo):
        item = self.list.find_item(device.address) if self.list else None
        if item is not None:
            item.set_busy(True, disconnecting=False)
        self.manager.connect_device(device.address)

    @pyqtSlot(object)
    def _disconnect(self, device: DeviceInfo):
        item = self.list.find_item(device.address) if self.list else None
        if item is not None:
            item.set_busy(True, disconnecting=True)
        self.manager.disconnect_device(device.address)

    @pyqtSlot(object)
    def _open_device_settings(self, _device: DeviceInfo):
        self._open_uri("ms-settings:bluetooth")

    def on_connection_finished(self, success: bool, message: str, device: DeviceInfo) -> None:
        if not is_valid_qobject(self.popup) or not self.popup.isVisible():
            return
        item = self.list.find_item(device.address) if self.list is not None else None
        if item is not None:
            item.set_busy(False)
        if not success:
            self._show_error(message)
            return
        if device.address and (device.paired or device.remembered):
            self._paired[device.address] = self._decorate(device)
        self._apply_list()

    @pyqtSlot(bool)
    def _toggle_radio(self, checked: bool):
        if is_valid_qobject(self.power_button):
            self.power_button.setText(self._power_label(checked))
            refresh_widget_style(self.power_button)
        self._start_loader()
        if not self.manager.set_radio(checked):
            self._set_radio_ui(not checked)
            self._stop_loader()
            self._show_error("Unable to change Bluetooth power")
            return

    def _decorate(self, device: DeviceInfo) -> DeviceInfo:
        device = replace(device)
        icons = self.menu_config.device_icons
        device.icon = getattr(icons, device.device_type.value, icons.generic)
        labels = self.menu_config.labels
        if device.connected and device.profiles:
            device.status_text = f"{labels.connected} {', '.join(device.profiles)}"
        elif device.connected:
            device.status_text = labels.connected
        else:
            device.status_text = labels.not_connected
        return device

    def _apply_list(self) -> None:
        if self.list is None or not is_valid_qobject(self.popup):
            return
        labels = self._action_labels()
        battery = self.menu_config.device_icons.battery
        self.list.paired.sync(self._paired, battery, labels)
        self.list.discovered.sync(self._discovered, battery, labels)

    def _power_label(self, radio_on: bool) -> str:
        labels = self.menu_config.labels
        return labels.power_on if radio_on else labels.power_off

    def _set_radio_ui(self, radio_on: bool) -> None:
        if is_valid_qobject(self.power_button):
            if self.power_button.isChecked() != radio_on:
                self.power_button.blockSignals(True)
                self.power_button.setChecked(radio_on)
                self.power_button.blockSignals(False)
            self.power_button.setText(self._power_label(radio_on))
            refresh_widget_style(self.power_button)
        if self.list is not None and is_valid_qobject(self.list):
            self.list.setEnabled(radio_on)

    def _show_error(self, message: str) -> None:
        if not is_valid_qobject(self.error_label):
            return
        self.error_label.setText(message)
        self.error_label.show()
        QTimer.singleShot(
            4000,
            lambda: self.error_label.hide() if is_valid_qobject(self.error_label) else None,
        )

    def _open_uri(self, uri: str) -> None:
        os.startfile(uri)
        if is_valid_qobject(self.popup):
            self.popup.hide_animated()

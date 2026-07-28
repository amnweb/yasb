import re

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QLabel

from core.utils.qobject import is_valid_qobject
from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.bluetooth import BluetoothConfig
from core.widgets.base import BaseWidget
from core.widgets.services.bluetooth.bluetooth_managers import BluetoothManager
from core.widgets.services.bluetooth.bluetooth_types import (
    BluetoothStatus,
    DeviceInfo,
    ScanResultStatus,
)
from core.widgets.services.bluetooth.bluetooth_widgets import BluetoothMenu


class BluetoothWidget(BaseWidget):
    validation_schema = BluetoothConfig

    def __init__(self, config: BluetoothConfig):
        super().__init__(class_name=f"bluetooth-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self.bluetooth_icon = self.config.icons.bluetooth_off
        self.connected_devices: list[str] | None = None
        self._bt_state = "bt-off"

        self._manager = BluetoothManager.acquire()
        self._bt_menu = BluetoothMenu(self, self.config.menu_config, self._manager)
        self._released = False

        self._manager.status_updated.connect(self._on_status_updated)
        self._manager.refresh_failed.connect(self._on_refresh_failed)
        self._manager.scan_started.connect(self._on_scan_started)
        self._manager.scan_completed.connect(self._on_scan_completed)
        self._manager.connection_finished.connect(self._on_connection_finished)
        self.destroyed.connect(lambda *_: self.stop())

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._bt_menu.show_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self._update_label(self.config.icons.bluetooth_off)
        self._manager.start()

    def stop(self):
        if self._released:
            return
        self._released = True
        for signal, slot in (
            (self._manager.status_updated, self._on_status_updated),
            (self._manager.refresh_failed, self._on_refresh_failed),
            (self._manager.scan_started, self._on_scan_started),
            (self._manager.scan_completed, self._on_scan_completed),
            (self._manager.connection_finished, self._on_connection_finished),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
        self._bt_menu.detach()
        self._manager.release()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label(self.bluetooth_icon, self.connected_devices)

    @pyqtSlot(object)
    def _on_status_updated(self, status: BluetoothStatus):
        if self._released or not is_valid_qobject(self):
            return
        self._update_bar(status)
        self._bt_menu.apply_status(status)

    def _update_bar(self, status: BluetoothStatus) -> None:
        if not status.radio_on:
            self.bluetooth_icon = self.config.icons.bluetooth_off
            self.connected_devices = None
            self._bt_state = "bt-off"
        else:
            connected = [d.name for d in status.connected_devices]
            if connected:
                self.bluetooth_icon = self.config.icons.bluetooth_connected
                self.connected_devices = connected
                self._bt_state = "bt-connected"
            else:
                self.bluetooth_icon = self.config.icons.bluetooth_on
                self.connected_devices = None
                self._bt_state = "bt-on"
        self._update_label(self.bluetooth_icon, self.connected_devices)

    @pyqtSlot(str)
    def _on_refresh_failed(self, message: str):
        if self._released:
            return
        self._bt_menu.on_refresh_failed(message)

    @pyqtSlot()
    def _on_scan_started(self):
        if self._released:
            return
        self._bt_menu.on_scan_started()

    @pyqtSlot(object, object)
    def _on_scan_completed(self, status: ScanResultStatus, devices: list[DeviceInfo]):
        if self._released:
            return
        self._bt_menu.on_scan_completed(status, devices)

    @pyqtSlot(bool, str, object)
    def _on_connection_finished(self, success: bool, message: str, device: DeviceInfo):
        if self._released:
            return
        self._bt_menu.on_connection_finished(success, message, device)

    def _set_bt_state_class(self, widget: QLabel) -> None:
        current_class = widget.property("class") or ""
        classes = [c for c in current_class.split() if c and c not in ("bt-off", "bt-on", "bt-connected")]
        classes.append(self._bt_state)
        widget.setProperty("class", " ".join(classes))
        refresh_widget_style(widget)

    def _update_label(self, icon: str, connected_devices: list[str] | None = None):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if connected_devices:
            if self.config.device_aliases:
                connected_devices = [
                    next(
                        (alias.alias for alias in self.config.device_aliases if alias.name.strip() == device.strip()),
                        device,
                    )
                    for device in connected_devices
                ]
            device_names = self.config.label_device_separator.join(connected_devices)
            tooltip_text = "Connected devices\n" + "\n".join(f"• {name}" for name in connected_devices)
        else:
            device_names = self.config.label_no_device
            tooltip_text = self.config.label_no_device

        label_options = {
            "{icon}": icon,
            "{device_name}": device_names,
            "{device_count}": len(connected_devices) if connected_devices else 0,
        }

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_bt_state_class(active_widgets[widget_index])
                else:
                    if self.config.max_length and len(formatted_text) > self.config.max_length:
                        formatted_text = formatted_text[: self.config.max_length] + self.config.max_length_ellipsis
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_bt_state_class(active_widgets[widget_index])
                widget_index += 1

        if self.config.tooltip:
            set_tooltip(self._widget_container, tooltip_text)

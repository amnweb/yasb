from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtBluetooth import (QBluetoothDeviceDiscoveryAgent,
                               QBluetoothDeviceInfo,
                               QBluetoothLocalDevice,
                               QBluetoothAddress)
from typing import Dict
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.bluetooth import VALIDATION_SCHEMA
import re
import logging
from settings import DEBUG
class BluetoothWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, label_alt: str, icons: Dict[str, str], container_padding: dict[str, int], callbacks: Dict[str, str]):
        super().__init__(class_name="bluetooth-widget")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._icons = icons
        self._padding = container_padding
        self.clear_devices_list()

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])

        self._widget_container = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        # Setup Bluetooth
        self._setup_bluetooth()
        
        # Register callbacks
        self.register_callback("toggle_label", self._toggle_label)
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        
        # Initial state update and discovery
        self._update_state()
        self.start_discovery()

    def _setup_bluetooth(self):
        self.local_device = QBluetoothLocalDevice()
        self.discovery_agent = None
        self._initialize_bluetooth()
        self.local_device.hostModeStateChanged.connect(self._handle_bluetooth_state)

    def clear_devices_list(self):
        self.known_devices = {}
        self.connected_device_names = []
        self.current_device_name = "No device"
        
    def _initialize_bluetooth(self):
        if self.local_device.isValid():
            if self.discovery_agent is None:
                self.discovery_agent = QBluetoothDeviceDiscoveryAgent()
                self.discovery_agent.deviceDiscovered.connect(self.device_discovered)
                self.discovery_agent.finished.connect(self.discovery_finished)
                
            self.local_device.deviceConnected.connect(self.device_connected)
            self.local_device.deviceDisconnected.connect(self.device_disconnected)
            return True
        return False

    @pyqtSlot(QBluetoothLocalDevice.HostMode)
    def _handle_bluetooth_state(self, mode):
        if mode != QBluetoothLocalDevice.HostMode.HostPoweredOff:           
            if self._initialize_bluetooth():
                self.start_discovery()
        else:
            self.clear_devices_list()
        self._update_state()


    def start_discovery(self):
        if self.discovery_agent and self.local_device.isValid():
            if DEBUG:
                logging.info("Starting device discovery...")
            if self.discovery_agent.isActive():
                self.discovery_agent.stop()
            self.discovery_agent.setLowEnergyDiscoveryTimeout(0)
            self.discovery_agent.start(QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.ClassicMethod)
            self._update_state()
        else:
            if DEBUG:
                logging.info("Bluetooth adapter not available")

    @pyqtSlot(QBluetoothDeviceInfo)
    def device_discovered(self, device_info):
        if not self.local_device.isValid() or self.local_device.hostMode() == QBluetoothLocalDevice.HostMode.HostPoweredOff:
            self.clear_devices_list()
            self._update_state()
            return
        
        addr = device_info.address().toString()
        name = device_info.name()
        
        if name and device_info.isValid():
            self.known_devices[addr] = name
            if DEBUG:
                logging.info(f"Found device: {name} ({addr})")

            connected_addrs = []
            if self.local_device.isValid() and self.local_device.hostMode() != QBluetoothLocalDevice.HostMode.HostPoweredOff:
                connected_addrs = [d.toString() for d in self.local_device.connectedDevices()]
                
            is_connected = (addr in connected_addrs and
                            device_info.coreConfigurations() != QBluetoothDeviceInfo.CoreConfiguration.UnknownCoreConfiguration)
            if DEBUG:
                logging.info(f"Device {name} connection state: {is_connected}")
            
            if is_connected:
                if name not in self.connected_device_names:
                    self.connected_device_names.append(name)
                    self.current_device_name = ", ".join(self.connected_device_names)
                    self._update_state()
            else:
                if name in self.connected_device_names:
                    self.connected_device_names.remove(name)
                    self.current_device_name = ", ".join(self.connected_device_names) if self.connected_device_names else "No device"
                    self._update_state()

    @pyqtSlot()
    def discovery_finished(self):
        self._update_state()
        self.start_discovery()
 
    @pyqtSlot(QBluetoothAddress)
    def device_connected(self, address):
        addr_str = address.toString()
        device_name = self.known_devices.get(addr_str, "Unknown device")
        if device_name not in self.connected_device_names:
            self.connected_device_names.append(device_name)
        self.current_device_name = ", ".join(self.connected_device_names)
        if DEBUG:
            logging.info(f"Device connected: {device_name} ({addr_str})")
        self._update_state()

    @pyqtSlot(QBluetoothAddress)
    def device_disconnected(self, address):
        addr_str = address.toString()
        device_name = self.known_devices.get(addr_str, "Unknown device")
        if device_name in self.connected_device_names:
            self.connected_device_names.remove(device_name)
        self.current_device_name = ", ".join(self.connected_device_names) if self.connected_device_names else "No device"
        if DEBUG:
            logging.info(f"Device disconnected: {device_name} ({addr_str})")
        self._update_state()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_state()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split(r'(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _update_label(self, icon=None):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        
        label_parts = re.split(r'(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        label_options = {
            "{icon}": icon,
            "{device_name}": self.current_device_name
        }
        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if '<span' in part and '</span>' in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def _update_state(self):
        if not self.local_device.isValid():
            bluetooth_icon = self._icons['bluetooth_off']
            self.clear_devices_list()
            self.current_device_name = "Bluetooth disabled"
            self._widget_container.setToolTip("Bluetooth is not available")
            self._update_label(bluetooth_icon)
            return
        
        mode = self.local_device.hostMode()
        if mode == QBluetoothLocalDevice.HostMode.HostPoweredOff:
            bluetooth_icon = self._icons['bluetooth_off']
            self.clear_devices_list()
            self._widget_container.setToolTip("Bluetooth is turned off")
            self._update_label(bluetooth_icon)
            return

        connected_devices = self.local_device.connectedDevices()
        if connected_devices:
            self.connected_device_names = []
            for device in connected_devices:
                addr = device.toString()
                if addr in self.known_devices:
                    name = self.known_devices[addr]
                    self.connected_device_names.append(name)
            
            if self.connected_device_names:
                bluetooth_icon = self._icons['bluetooth_connected']
                self.current_device_name = ", ".join(self.connected_device_names)
            else:
                bluetooth_icon = self._icons['bluetooth_on']
                self.current_device_name = "No device"
                self.connected_device_names = []
        else:
            bluetooth_icon = self._icons['bluetooth_on']
            self.current_device_name = "No device"
            self.connected_device_names = []
        
        tooltip = "Connected devices:\n" + "\n".join(f"• {name}" for name in self.connected_device_names) if self.connected_device_names else "No devices connected"
        self._widget_container.setToolTip(tooltip)
        self._update_label(bluetooth_icon)
        
    def get_current_device_name(self):
        connected_devices = self.local_device.connectedDevices()
        if connected_devices:
            addr = connected_devices[0].toString()
            return self.known_devices.get(addr, "Unknown device")
        return "No device"
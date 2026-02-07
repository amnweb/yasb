import logging
import re
import socket

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
)
from winrt.windows.networking.connectivity import NetworkInformation

from core.utils.utilities import add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.wifi.wifi_managers import NetworkInfo, WiFiInfo, WiFiWorker
from core.utils.widgets.wifi.wifi_widgets import WifiMenu
from core.validation.widgets.yasb.wifi import WifiConfig
from core.widgets.base import BaseWidget

logger = logging.getLogger("wifi_widget")


class WifiWidget(BaseWidget):
    validation_schema = WifiConfig
    _networks_cache: list[NetworkInfo] = []

    def __init__(self, config: WifiConfig):
        super().__init__(config.update_interval, class_name=f"wifi-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._ethernet_active = False
        self._wifi_menu = WifiMenu(self, self.config.menu_config)

        self._cached_wifi_info = WiFiInfo(0, "Disconnected", -1)

        # Worker thread that will fetch wifi info on an interval
        self._wifi_worker = WiFiWorker(self.config.get_exact_wifi_strength, self.config.update_interval)
        self._wifi_worker.result.connect(self._on_wifi_info_result)
        self._wifi_worker.start()

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self.config.label, self.config.label_alt)
        self._create_dynamically_label(
            self.config.ethernet_label,
            self.config.ethernet_label_alt,
            is_ethernet=True,
        )

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._wifi_menu.show_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _display_correct_label(self):
        active_widget_group = "ethernet" if self._ethernet_active else "wifi"
        widget_groups = {
            "wifi": (self._widgets, self._widgets_alt),
            "ethernet": (self._widgets_ethernet, self._widgets_ethernet_alt),
        }
        for name, (widgets, widgets_alt) in widget_groups.items():
            if name == active_widget_group:
                for widget in widgets:
                    widget.setVisible(not self._show_alt_label)
                for widget in widgets_alt:
                    widget.setVisible(self._show_alt_label)
            else:
                for widget in widgets:
                    widget.setVisible(False)
                for widget in widgets_alt:
                    widget.setVisible(False)

    def _toggle_label(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str, is_ethernet: bool = False):
        def process_content(content: str, is_alt: bool = False, is_ethernet: bool = False) -> list[QLabel]:
            label_parts = re.split("(<span.*?>.*?</span>)", content)  # Filters out empty parts before entering the loop
            label_parts = [part for part in label_parts if part]
            widgets: list[QLabel] = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label alt" if is_alt else "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                add_shadow(label, self.config.label_shadow.model_dump())
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt or is_ethernet:
                    label.hide()
                else:
                    label.show()
            return widgets

        if is_ethernet:
            self._widgets_ethernet = process_content(content, is_ethernet=True)
            self._widgets_ethernet_alt = process_content(content_alt, is_alt=True, is_ethernet=True)
        else:
            self._widgets = process_content(content)
            self._widgets_alt = process_content(content_alt, is_alt=True)

    def _on_wifi_info_result(self, wifi_info: WiFiInfo):
        """Handle WiFi info result from worker thread."""
        self._cached_wifi_info = wifi_info
        self._update_label()

    def _update_label(self):
        try:
            connection_info = NetworkInformation.get_internet_connection_profile()
            ip_addr = socket.gethostbyname(socket.gethostname())
            if connection_info is None or connection_info.is_wlan_connection_profile:  # type: ignore
                was_ethernet = self._ethernet_active
                self._ethernet_active = False
                if was_ethernet and self.config.hide_if_ethernet:
                    self.show()

                if self.config.get_exact_wifi_strength and self._cached_wifi_info.exact_quality >= 0:
                    wifi_strength = self._cached_wifi_info.exact_quality
                else:
                    wifi_strength = min(self._cached_wifi_info.bars, 4) * 25
                wifi_icon = self._get_wifi_icon(wifi_strength)
                wifi_name = self._cached_wifi_info.name
            else:
                self._ethernet_active = True
                if self.config.hide_if_ethernet:
                    self.hide()
                    return
                wifi_icon = self.config.ethernet_icon
                wifi_name = "Ethernet"
                wifi_strength = "N/A"

        except Exception as e:
            logger.error(f"Error in wifi widget update: {e}")
            ip_addr = "N/A"
            wifi_icon = wifi_name = wifi_strength = "N/A"

        self._display_correct_label()
        if self._ethernet_active:
            active_widgets = self._widgets_ethernet_alt if self._show_alt_label else self._widgets_ethernet
            active_label_content = (
                self.config.ethernet_label_alt if self._show_alt_label else self.config.ethernet_label
            )
        else:
            active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
            active_label_content = self.config.label_alt if self._show_alt_label else self.config.label

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        label_options = {
            "{wifi_icon}": wifi_icon,
            "{wifi_name}": wifi_name,
            "{wifi_strength}": wifi_strength,
            "{ip_addr}": ip_addr,
        }
        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if widget_index < len(active_widgets):
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def _get_wifi_icon(self, strength: int) -> str:
        if strength >= 80:
            bars = 4
        elif strength >= 60:
            bars = 3
        elif strength >= 40:
            bars = 2
        elif strength >= 20:
            bars = 1
        else:
            bars = 0
        return self.config.wifi_icons[bars]

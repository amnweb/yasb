import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.wifi import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
import os


class WifiWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        update_interval: int,
        wifi_icons: list[str],
        callbacks: dict[str, str],
    ):
        super().__init__(update_interval, class_name="wifi-widget")
        self._wifi_icons = wifi_icons

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
 
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()


    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content) #Filters out empty parts before entering the loop
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
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
                    label.setText("Loading") 
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.setProperty("class", "label alt") 
                    label.hide()
                else:
                    label.show()
            return widgets
        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

        
    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        try:
            # Retrieve WiFi information
            wifi_icon, wifi_strength = self._get_wifi_icon()
            wifi_name = self._get_wifi_name()
        except Exception:
            wifi_icon, wifi_name = "N/A", "N/A"
        label_options = {
            "{wifi_icon}": wifi_icon,
            "{wifi_name}": wifi_name,
            "{wifi_strength}": wifi_strength
        }
        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                 
                if '<span' in part and '</span>' in part:
                    # Update icon QLabel
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                else:
                    # Update normal QLabel
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        
                widget_index += 1


    def _get_wifi_strength(self):
        # Get the wifi strength from the system
        result = os.popen("netsh wlan show interfaces").read()
        # Return 0 if no wifi interface is found
        if "There is no wireless interface on the system." in result:
            return 0
        # Extract signal strength from the result
        for line in result.split("\n"):
            if "Signal" in line:  # FIXME: This will break if the system language is not English
                strength = line.split(":")[1].strip().split(" ")[0].replace("%", "")
                return int(strength)
        return 0

    def _get_wifi_name(self):
        result = os.popen("netsh wlan show interfaces").read()
        for line in result.split("\n"):
            if "SSID" in line:
                return line.split(":")[1].strip()
        return "No WiFi"

    def _get_wifi_icon(self):
        # Map strength to its corresponding icon
        strength = self._get_wifi_strength()
        if strength == 0:
            return self._wifi_icons[0], strength
        elif strength <= 25:
            return self._wifi_icons[1], strength
        elif strength <= 50:
            return self._wifi_icons[2], strength
        elif strength <= 75:
            return self._wifi_icons[3], strength
        else:
            return self._wifi_icons[4], strength
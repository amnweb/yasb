import re
import psutil
import humanize
from datetime import timedelta
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.battery import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from typing import Union
from core.utils.widgets.animation_manager import AnimationManager

class BatteryWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    def __init__(
            self,
            label: str,
            label_alt: str,
            update_interval: int,
            time_remaining_natural: bool,
            charging_options: dict[str, Union[str, bool]],
            status_thresholds: dict[str, int],
            status_icons: dict[str, str],
            animation: dict[str, str],
            callbacks: dict[str, str],
            container_padding: dict[str, int],
    ):
        super().__init__(update_interval, class_name="battery-widget")
        self._time_remaining_natural = time_remaining_natural
        self._status_thresholds = status_thresholds
        self._status_icons = status_icons
        self._battery_state = None
        self._blink = False
        self._show_alt = False
        self._last_threshold = None
        self._animation = animation
        self._icon_charging_format = charging_options['icon_format']
        self._icon_charging_blink = charging_options['blink_charging_icon']
        self._padding = container_padding
        
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content, self._label_alt_content)
  
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

        self.start_timer()

    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()


    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
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
        
    def _get_time_remaining(self) -> str:
        secs_left = self._battery_state.secsleft
        if secs_left == psutil.POWER_TIME_UNLIMITED:
            time_left = "unlimited"
        elif type(secs_left) == int:
            time_left = timedelta(seconds=secs_left)
            time_left = humanize.naturaldelta(time_left) if self._time_remaining_natural else str(time_left)
        else:
            time_left = "unknown"
        return time_left

    def _get_battery_threshold(self):
        percent = self._battery_state.percent

        if percent <= self._status_thresholds['critical']:
            return "critical"
        elif self._status_thresholds['critical'] < percent <= self._status_thresholds['low']:
            return "low"
        elif self._status_thresholds['low'] < percent <= self._status_thresholds['medium']:
            return "medium"
        elif self._status_thresholds['medium'] < percent <= self._status_thresholds['high']:
            return "high"
        elif self._status_thresholds['high'] < percent <= self._status_thresholds['full']:
            return "full"

    def _get_charging_icon(self, threshold: str):
        if self._battery_state.power_plugged:
            if self._icon_charging_blink and self._blink:
                empty_charging_icon = len(self._status_icons["icon_charging"]) * " "
                icon_str = self._icon_charging_format \
                    .replace("{charging_icon}", empty_charging_icon) \
                    .replace("{icon}", self._status_icons[f"icon_{threshold}"])
                self._blink = not self._blink
            else:
                icon_str = self._icon_charging_format\
                    .replace("{charging_icon}", self._status_icons["icon_charging"])\
                    .replace("{icon}", self._status_icons[f"icon_{threshold}"])
            return icon_str
        else:
            return self._status_icons[f"icon_{threshold}"]

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0         
        self._battery_state = psutil.sensors_battery()  
        # Check battery state
        if self._battery_state is None:
            for part in label_parts:
                part = part.strip()
                if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    if '<span' in part and '</span>' in part:
                        active_widgets[widget_index].hide()
                    active_widgets[widget_index].setText("Battery info not available")          
                    widget_index += 1
            return

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                threshold = self._get_battery_threshold()

                if self._battery_state.power_plugged:
                    threshold = "charging"

                time_remaining = self._get_time_remaining()
                is_charging_str = "yes" if self._battery_state.power_plugged else "no"
                charging_icon = self._get_charging_icon(threshold)
                battery_status = part\
                    .replace("{percent}", str(self._battery_state.percent)) \
                    .replace("{time_remaining}", time_remaining) \
                    .replace("{is_charging}", is_charging_str) \
                    .replace("{icon}", charging_icon)
                if '<span' in battery_status and '</span>' in battery_status:
                    # Ensure the icon is correctly set
                    icon = re.sub(r'<span.*?>|</span>', '', battery_status).strip()
                    active_widgets[widget_index].setText(icon)
                    icon = re.sub(r'<span.*?>|</span>', '', battery_status).strip()
                    active_widgets[widget_index].setText(icon)
                    existing_classes = active_widgets[widget_index].property("class")
                    new_classes = re.sub(r'status-\w+', '', existing_classes).strip()
                    active_widgets[widget_index].setProperty("class", f"{new_classes} status-{threshold}")
                else:
                    alt_class = "alt" if self._show_alt_label else ""
                    formatted_text = battery_status.format(battery_status) 
                    active_widgets[widget_index].setText(formatted_text)
                    active_widgets[widget_index].setProperty("class", f"label {alt_class} status-{threshold}")
                    active_widgets[widget_index].setStyleSheet('')
                widget_index += 1
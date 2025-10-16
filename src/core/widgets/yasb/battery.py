import re
from datetime import timedelta
from typing import Union

import humanize
import psutil
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.battery import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class BatteryWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        update_interval: int,
        time_remaining_natural: bool,
        hide_unsupported: bool,
        charging_options: dict[str, Union[str, bool]],
        status_thresholds: dict[str, int],
        status_icons: dict[str, str],
        animation: dict[str, str],
        callbacks: dict[str, str],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(update_interval, class_name=f"battery-widget {class_name}")
        self._time_remaining_natural = time_remaining_natural
        self._status_thresholds = status_thresholds
        self._status_icons = status_icons
        self._battery_state = None
        self._show_alt = False
        self._last_threshold = None
        self._animation = animation
        self._icon_charging_format = charging_options["icon_format"]
        self._icon_charging_blink = charging_options["blink_charging_icon"]
        self._icon_charging_blink_interval = charging_options["blink_interval"]
        self._hide_unsupported = hide_unsupported
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self._charging_blink_timer = QTimer(self)
        self._charging_blink_timer.setInterval(self._icon_charging_blink_interval)
        self._charging_blink_timer.timeout.connect(self._charging_blink)
        self._charging_icon_label = None

        self.start_timer()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

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

        if percent <= self._status_thresholds["critical"]:
            return "critical"
        elif self._status_thresholds["critical"] < percent <= self._status_thresholds["low"]:
            return "low"
        elif self._status_thresholds["low"] < percent <= self._status_thresholds["medium"]:
            return "medium"
        elif self._status_thresholds["medium"] < percent <= self._status_thresholds["high"]:
            return "high"
        elif self._status_thresholds["high"] < percent <= self._status_thresholds["full"]:
            return "full"

    def _get_charging_icon(self, threshold: str) -> str:
        icon = self._status_icons[f"icon_{threshold}"]
        if self._battery_state.power_plugged:
            return self._icon_charging_format.format(charging_icon=self._status_icons["icon_charging"], icon=icon)
        return icon

    def _charging_blink(self):
        """Toggle the blink class to create a blinking effect using CSS."""
        label = self._charging_icon_label
        if not label:
            return

        current_classes = label.property("class") or ""

        if "blink" in current_classes:
            new_classes = current_classes.replace("blink", "").strip()
            new_classes = re.sub(r"\s+", " ", new_classes)
        else:
            new_classes = f"{current_classes} blink".strip()

        label.setProperty("class", new_classes)
        refresh_widget_style(label)

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        self._battery_state = psutil.sensors_battery()

        if self._battery_state is None:
            if self._hide_unsupported:
                self.hide()
                self.timer.stop()
                return

            for part in label_parts:
                part = part.strip()
                if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    if "<span" in part and "</span>" in part:
                        active_widgets[widget_index].hide()
                    active_widgets[widget_index].setText("Battery info not available")
                    widget_index += 1
            return

        original_threshold = self._get_battery_threshold()
        threshold = "charging" if self._battery_state.power_plugged else original_threshold
        time_remaining = self._get_time_remaining()
        is_charging_str = "yes" if self._battery_state.power_plugged else "no"
        charging_icon = self._get_charging_icon(original_threshold)

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                battery_status = (
                    part.replace("{percent}", str(self._battery_state.percent))
                    .replace("{time_remaining}", time_remaining)
                    .replace("{is_charging}", is_charging_str)
                    .replace("{icon}", charging_icon)
                )
                if "<span" in battery_status and "</span>" in battery_status:
                    # icon-only QLabel
                    widget_label = active_widgets[widget_index]
                    icon = re.sub(r"<span.*?>|</span>", "", battery_status).strip()
                    widget_label.setText(icon)
                    # apply status‐class
                    existing_classes = widget_label.property("class")
                    new_classes = re.sub(r"status-\w+", "", existing_classes).strip()
                    widget_label.setProperty("class", f"{new_classes} status-{threshold}")
                    refresh_widget_style(widget_label)

                    # only blink when plugged AND blink_enabled
                    if self._battery_state.power_plugged and self._icon_charging_blink:
                        self._charging_icon_label = widget_label
                        if not self._charging_blink_timer.isActive():
                            self._charging_blink_timer.start()
                    else:
                        if self._charging_blink_timer.isActive():
                            self._charging_blink_timer.stop()
                        self._charging_icon_label = None
                        current_classes = widget_label.property("class") or ""
                        if "blink" in current_classes:
                            new_classes = current_classes.replace("blink", "").strip()
                            new_classes = re.sub(r"\s+", " ", new_classes)
                            widget_label.setProperty("class", new_classes)
                            refresh_widget_style(widget_label)
                else:
                    alt_class = "alt" if self._show_alt_label else ""
                    formatted_text = battery_status.format(battery_status)
                    active_widgets[widget_index].setText(formatted_text)
                    active_widgets[widget_index].setProperty("class", f"label {alt_class} status-{threshold}")
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

import psutil
import humanize
from datetime import timedelta
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.battery import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel
from typing import Union


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
            callbacks: dict[str, str]
    ):
        super().__init__(update_interval, class_name="battery-widget")
        self._time_remaining_natural = time_remaining_natural
        self._status_thresholds = status_thresholds
        self._status_icons = status_icons
        self._battery_state = None
        self._blink = False
        self._show_alt = False
        self._last_threshold = None

        self._icon_charging_format = charging_options['icon_format']
        self._icon_charging_blink = charging_options['blink_charging_icon']

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        self._label = QLabel()
        self._label_alt = QLabel()
        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")
        self.widget_layout.addWidget(self._label)
        self.widget_layout.addWidget(self._label_alt)

        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

        self._label.show()
        self._label_alt.hide()

        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label

        if self._show_alt_label:
            self._label.hide()
            self._label_alt.show()
        else:
            self._label.show()
            self._label_alt.hide()

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
        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        active_label.setText(active_label_content)

        self._battery_state = psutil.sensors_battery()

        threshold = self._get_battery_threshold()
        time_remaining = self._get_time_remaining()
        is_charging_str = "yes" if self._battery_state.power_plugged else "no"
        charging_icon = self._get_charging_icon(threshold)
        battery_status = active_label_content\
            .replace("{percent}", str(self._battery_state.percent)) \
            .replace("{time_remaining}", time_remaining) \
            .replace("{is_charging}", is_charging_str) \
            .replace("{icon}", charging_icon)

        if self._battery_state.power_plugged:
            threshold = "charging"

        alt_class = "alt" if self._show_alt_label else ""
        active_label.setText(battery_status)
        active_label.setProperty("class", f"label {alt_class} status-{threshold}")
        active_label.setStyleSheet('')

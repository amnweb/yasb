import ctypes
import logging
import re
from datetime import datetime

import screen_brightness_control as sbc
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import get_monitor_info
from core.validation.widgets.yasb.brightness import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

if DEBUG:
    logging.getLogger("screen_brightness_control").setLevel(logging.INFO)
else:
    logging.getLogger("screen_brightness_control").setLevel(logging.CRITICAL)

user32 = ctypes.WinDLL("user32", use_last_error=True)


class BrightnessWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        tooltip: bool,
        scroll_step: int,
        brightness_icons: list[str],
        brightness_toggle_level: list[int],
        brightness_menu: dict[str, str],
        hide_unsupported: bool,
        auto_light: bool,
        auto_light_icon: str,
        auto_light_night_level: int,
        auto_light_night_start_time: str,
        auto_light_night_end_time: str,
        auto_light_day_level: int,
        container_padding: dict[str, int],
        animation: dict[str, str],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="brightness-widget")
        self._show_alt_label = False

        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip = tooltip
        self._padding = container_padding
        self._brightness_icons = brightness_icons
        self._brightness_toggle_level = brightness_toggle_level
        self._brightness_menu = brightness_menu
        self._hide_unsupported = hide_unsupported
        self._auto_light = auto_light
        self._auto_light_icon = auto_light_icon
        self._auto_light_night_level = auto_light_night_level
        self._auto_light_night_start = datetime.strptime(auto_light_night_start_time, "%H:%M").time()
        self._auto_light_night_end = datetime.strptime(auto_light_night_end_time, "%H:%M").time()
        self._auto_light_day_level = auto_light_day_level
        self._step = scroll_step
        self._current_mode = None
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_level_next", self._toggle_level_next)
        self.register_callback("toggle_level_prev", self._toggle_level_prev)
        self.register_callback("toggle_brightness_menu", self._toggle_brightness_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.current_brightness = None
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_brightness)
        self.monitor_timer.start(3000)

        QTimer.singleShot(10, self._update_label)

        if self._auto_light:
            self._auto_light_timer = QTimer()
            self._auto_light_timer.timeout.connect(self.auto_light)
            self._auto_light_timer.start(60000)
            QTimer.singleShot(1000, self.auto_light)

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_level_next(self):
        monitor_info = self.get_monitor_handle()
        if not monitor_info:
            return
        current = self.get_brightness()
        if not self._brightness_toggle_level:
            return
        levels = self._brightness_toggle_level
        next_levels = [level for level in levels if level > current]
        if next_levels:
            self.set_brightness(next_levels[0], monitor_info["device_id"])
        else:
            self.set_brightness(levels[0], monitor_info["device_id"])

    def _toggle_level_prev(self):
        monitor_info = self.get_monitor_handle()
        if not monitor_info:
            return
        current = self.get_brightness()
        if not self._brightness_toggle_level:
            return
        levels = self._brightness_toggle_level
        prev_levels = [level for level in levels if level < current]
        if prev_levels:
            self.set_brightness(prev_levels[-1], monitor_info["device_id"])
        else:
            self.set_brightness(levels[-1], monitor_info["device_id"])

    def _toggle_brightness_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_brightness_menu()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        try:
            percent = self.get_brightness()
            if percent is None:
                if self._hide_unsupported:
                    self.hide()
                return
            if percent is not None:
                icon = self.get_brightness_icon(percent)
                if self._tooltip:
                    self.setToolTip(f"Brightness {percent}%")
            else:
                percent, icon = 0, "not supported"
        except Exception:
            percent, icon = 0, "not supported"

        label_options = {"{icon}": icon, "{percent}": percent}
        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def show_brightness_menu(self):
        self.dialog = PopupWidget(
            self,
            self._brightness_menu["blur"],
            self._brightness_menu["round_corners"],
            self._brightness_menu["round_corners_type"],
            self._brightness_menu["border_color"],
        )
        self.dialog.setProperty("class", "brightness-menu")

        # Create vertical layout for the dialog
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create brightness slider
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setProperty("class", "brightness-slider")
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)

        # Set current brightness
        try:
            current = self.get_brightness()
            self.brightness_slider.setValue(current)
        except:
            pass

        # Connect slider value change to brightness control
        self.brightness_slider.valueChanged.connect(self._on_slider_value_changed_if_not_dragging)
        self.brightness_slider.sliderReleased.connect(
            lambda: self._on_slider_value_changed(self.brightness_slider.value())
        )

        # Add slider to layout
        layout.addWidget(self.brightness_slider)
        self.dialog.setLayout(layout)

        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._brightness_menu["alignment"],
            direction=self._brightness_menu["direction"],
            offset_left=self._brightness_menu["offset_left"],
            offset_top=self._brightness_menu["offset_top"],
        )
        self.dialog.show()

    def _on_slider_value_changed_if_not_dragging(self, value):
        if not self.brightness_slider.isSliderDown():
            self._on_slider_value_changed(value)

    def _on_slider_value_changed(self, value):
        monitor_info = self.get_monitor_handle()
        if not monitor_info:
            return
        try:
            self.set_brightness(value, monitor_info["device_id"])
            self._update_label()
        except Exception as e:
            logging.error(f"Failed to set brightness: {e}")

    def extract_display_number(self, device_path: str) -> int:
        try:
            # Extract everything after 'DISPLAY'
            display_num = device_path.split("DISPLAY")[-1]
            # Convert to integer, removing any non-numeric chars, we need to get onlu integer
            return int("".join(filter(str.isdigit, display_num)))
        except (IndexError, ValueError):
            if DEBUG:
                logging.warning(f"Failed to extract display number from {device_path}")
            return None

    def get_monitor_handle(self):
        try:
            hwnd = int(self.winId())
            hmonitor = user32.MonitorFromWindow(hwnd, 2)
            monitor_info = get_monitor_info(hmonitor)

            if not monitor_info:
                if DEBUG:
                    logging.warning("Failed to get monitor info")
                return None

            if not isinstance(self.extract_display_number(monitor_info["device"]), int):
                if DEBUG:
                    logging.warning("Failed to get monitor number")
                return None

            return {
                "device_name": self.screen().name(),
                "device_id": self.extract_display_number(monitor_info["device"]) - 1,
                "device": monitor_info["device"],
            }

        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to get monitor handle: {e}")
            return None

    def get_brightness(self):
        monitor_info = self.get_monitor_handle()
        try:
            if DEBUG:
                logging.info(
                    f" device_id = {monitor_info['device_id']}, device {monitor_info['device']}, device_name {monitor_info['device_name']}"
                )
            brightness = sbc.get_brightness(display=monitor_info["device_id"])[0]
            return brightness
        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to get primary display brightness: {e}")
            return None

    def set_brightness(self, brightness: int, device_id: int) -> None:
        try:
            sbc.set_brightness(brightness, display=device_id)
            self._update_label()
        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to set laptop brightness: {e}")

    def update_brightness(self, increase: bool, decrease: bool) -> None:
        try:
            current = self.get_brightness()
            if current is None:
                return
            if increase:
                new_brightness = min(current + self._step, 100)
            elif decrease:
                new_brightness = max(current - self._step, 0)
            else:
                return

            monitor_info = self.get_monitor_handle()
            try:
                if not monitor_info:
                    return None

                self.set_brightness(new_brightness, monitor_info["device_id"])
            except Exception as e:
                if DEBUG:
                    logging.warning(f"Failed to set laptop brightness: {e}")

        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to update brightness: {e}")

    def get_brightness_icon(self, brightness: int):
        if self._auto_light:
            return self._auto_light_icon
        if 0 <= brightness <= 25:
            icon = self._brightness_icons[0]
        elif 26 <= brightness <= 50:
            icon = self._brightness_icons[1]
        elif 51 <= brightness <= 75:
            icon = self._brightness_icons[2]
        else:
            icon = self._brightness_icons[3]
        return icon

    def auto_light(self):
        current_time = datetime.now().time()
        monitor_info = self.get_monitor_handle()
        if not monitor_info:
            return
        # Handle midnight crossing
        if self._auto_light_night_start <= self._auto_light_night_end:
            is_night = self._auto_light_night_start <= current_time <= self._auto_light_night_end
        else:
            is_night = current_time >= self._auto_light_night_start or current_time <= self._auto_light_night_end
        new_mode = "night" if is_night else "day"
        # Only set brightness if mode changed
        if new_mode != self._current_mode:
            self._current_mode = new_mode
            if is_night:
                self.set_brightness(self._auto_light_night_level, monitor_info["device_id"])
            else:
                self.set_brightness(self._auto_light_day_level, monitor_info["device_id"])

    def check_brightness(self):
        brightness = self.get_brightness()
        if brightness is not None and brightness != self.current_brightness:
            self._update_label()
            self.current_brightness = brightness

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.update_brightness(increase=True, decrease=False)
        elif event.angleDelta().y() < 0:
            self.update_brightness(increase=False, decrease=True)

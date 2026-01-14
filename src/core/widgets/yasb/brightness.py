import re
from datetime import datetime

import win32api
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_progress_widget, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.brightness.service import BrightnessService
from core.validation.widgets.yasb.brightness import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


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
        progress_bar: dict = None,
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
        self._progress_bar = progress_bar

        self._service = BrightnessService()
        self._hmonitor = None
        self._current_brightness: int | None = None

        self.progress_widget = build_progress_widget(self, self._progress_bar)

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
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

        # Register with the service for brightness change notifications
        self._service.register_widget(self)

        # Request initial brightness
        QTimer.singleShot(10, self._request_brightness)

        if self._auto_light:
            self._auto_light_timer = QTimer()
            self._auto_light_timer.timeout.connect(self.auto_light)
            self._auto_light_timer.start(60000)
            QTimer.singleShot(1000, self.auto_light)

    def get_hmonitor(self) -> int | None:
        """Returns the monitor handle where this widget is displayed."""
        try:
            hwnd = int(self.winId())
            self._hmonitor = int(win32api.MonitorFromWindow(hwnd, 2))
            return self._hmonitor
        except Exception:
            return None

    def on_brightness_changed(self, brightness: int) -> None:
        """Updates the widget when brightness level changes."""
        self._current_brightness = brightness
        self._update_label()

    def _request_brightness(self) -> None:
        """Ask the service for current brightness level."""
        hmonitor = self.get_hmonitor()
        if hmonitor:
            self._service.get_brightness(hmonitor, self)

    def _set_brightness(self, value: int) -> None:
        """Change brightness to the given value."""
        hmonitor = self.get_hmonitor()
        if hmonitor:
            self._service.set_brightness(hmonitor, value)
            self._current_brightness = value
            self._update_label()

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
        current = self._current_brightness
        if current is None or not self._brightness_toggle_level:
            return
        levels = self._brightness_toggle_level
        next_levels = [lvl for lvl in levels if lvl > current]
        self._set_brightness(next_levels[0] if next_levels else levels[0])

    def _toggle_level_prev(self):
        current = self._current_brightness
        if current is None or not self._brightness_toggle_level:
            return
        levels = self._brightness_toggle_level
        prev_levels = [lvl for lvl in levels if lvl < current]
        self._set_brightness(prev_levels[-1] if prev_levels else levels[-1])

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

        percent = self._current_brightness

        if percent is None:
            if self._hide_unsupported:
                self.hide()
            return

        icon = self.get_brightness_icon(percent)
        if self._tooltip:
            set_tooltip(self, f"Brightness {percent}%")

        label_options = {"{icon}": icon, "{percent}": percent}

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            self.progress_widget.set_value(percent)

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
        hmonitor = self.get_hmonitor()
        if not hmonitor:
            return

        current = self._current_brightness
        if current is None:
            return

        self.dialog = PopupWidget(
            self,
            self._brightness_menu["blur"],
            self._brightness_menu["round_corners"],
            self._brightness_menu["round_corners_type"],
            self._brightness_menu["border_color"],
        )
        self.dialog.setProperty("class", "brightness-menu")

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setProperty("class", "brightness-slider")
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(current)

        self.brightness_slider.valueChanged.connect(self._on_slider_value_changed_if_not_dragging)
        self.brightness_slider.sliderReleased.connect(self._on_slider_released)

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

    def _on_slider_released(self):
        """Hide tooltip when slider is released"""
        self._on_slider_value_changed(self.brightness_slider.value())
        if hasattr(self, "_slider_tooltip") and self._slider_tooltip:
            self._slider_tooltip.hide()
            self._slider_tooltip = None

    def _get_slider_handle_geometry(self, slider):
        """Calculate the geometry for the slider handle position"""
        value = slider.value()
        slider_range = slider.maximum() - slider.minimum()
        if slider_range > 0:
            handle_pos = (value - slider.minimum()) / slider_range
            x_offset = int(slider.width() * handle_pos)

            widget_rect = slider.rect()
            widget_global_pos = slider.mapToGlobal(widget_rect.topLeft())
            widget_global_pos.setX(widget_global_pos.x() + x_offset)

            handle_geometry = QRect(widget_global_pos.x(), widget_global_pos.y(), 1, slider.height())
            return handle_geometry
        return None

    def _show_slider_tooltip(self, slider, value):
        """Show/update tooltip for slider during drag"""
        if not self._tooltip or not slider.isSliderDown():
            return

        if not hasattr(self, "_slider_tooltip") or not self._slider_tooltip:
            self._slider_tooltip = CustomToolTip()
            self._slider_tooltip._position = "top"
            handle_geometry = self._get_slider_handle_geometry(slider)
            if handle_geometry:
                self._slider_tooltip.label.setText(f"{value}%")
                self._slider_tooltip.adjustSize()
                self._slider_tooltip._base_pos = self._slider_tooltip._calculate_position(handle_geometry)
                self._slider_tooltip.move(self._slider_tooltip._base_pos.x(), self._slider_tooltip._base_pos.y())
                self._slider_tooltip.setWindowOpacity(1.0)
                self._slider_tooltip.show()
        else:
            handle_geometry = self._get_slider_handle_geometry(slider)
            if handle_geometry:
                self._slider_tooltip.label.setText(f"{value}%")
                self._slider_tooltip.adjustSize()
                base_pos = self._slider_tooltip._calculate_position(handle_geometry)
                self._slider_tooltip.move(base_pos.x(), base_pos.y())

    def _on_slider_value_changed_if_not_dragging(self, value):
        if self.brightness_slider.isSliderDown():
            self._show_slider_tooltip(self.brightness_slider, value)
        else:
            self._on_slider_value_changed(value)

    def _on_slider_value_changed(self, value):
        self._set_brightness(value)
        self._show_slider_tooltip(self.brightness_slider, value)

    def update_brightness(self, increase: bool, decrease: bool) -> None:
        current = self._current_brightness
        if current is None:
            return
        if increase:
            self._set_brightness(min(current + self._step, 100))
        elif decrease:
            self._set_brightness(max(current - self._step, 0))

    def get_brightness_icon(self, brightness: int):
        if self._auto_light:
            return self._auto_light_icon
        if 0 <= brightness <= 25:
            return self._brightness_icons[0]
        elif 26 <= brightness <= 50:
            return self._brightness_icons[1]
        elif 51 <= brightness <= 75:
            return self._brightness_icons[2]
        else:
            return self._brightness_icons[3]

    def auto_light(self):
        current_time = datetime.now().time()
        if self._auto_light_night_start <= self._auto_light_night_end:
            is_night = self._auto_light_night_start <= current_time <= self._auto_light_night_end
        else:
            is_night = current_time >= self._auto_light_night_start or current_time <= self._auto_light_night_end

        new_mode = "night" if is_night else "day"
        if new_mode != self._current_mode:
            self._current_mode = new_mode
            self._set_brightness(self._auto_light_night_level if is_night else self._auto_light_day_level)

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.update_brightness(increase=True, decrease=False)
        elif event.angleDelta().y() < 0:
            self.update_brightness(increase=False, decrease=True)

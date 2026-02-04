import re
from datetime import datetime

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_progress_widget, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.brightness.service import BrightnessService
from core.utils.win32.bindings.user32 import MONITOR_DEFAULTTONEAREST, user32
from core.validation.widgets.yasb.brightness import BrightnessConfig
from core.widgets.base import BaseWidget


class BrightnessWidget(BaseWidget):
    validation_schema = BrightnessConfig

    def __init__(self, config: BrightnessConfig):
        super().__init__(class_name="brightness-widget")
        self.config = config
        self._show_alt_label = False
        self._widgets: list[QLabel] = []
        self._widgets_alt: list[QLabel] = []

        # Current state
        self._hmonitor = None
        self.current_brightness = None
        self._auto_light_timer: QTimer | None = None
        self._initialized = False
        self._auto_light_started = False
        self._slider_tooltip = None
        self._current_mode = None

        # Get brightness service singleton
        self._service = BrightnessService.instance()
        self._service.brightness_changed.connect(self._on_brightness_changed)

        # Build UI
        self.progress_widget = build_progress_widget(self, self.config.progress_bar.model_dump())

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self.config.label, self.config.label_alt, self.config.label_shadow.model_dump())

        # Register callbacks
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_level_next", self._toggle_level_next)
        self.register_callback("toggle_level_prev", self._toggle_level_prev)
        self.register_callback("toggle_brightness_menu", self._toggle_brightness_menu)

        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

        self._hmonitor = None
        self._initialized = False
        self._auto_light_started = False
        self._slider_tooltip = None

    def _get_hmonitor(self) -> int | None:
        """Get the monitor handle for this widget."""
        try:
            hwnd = int(self.winId())
            return user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        except Exception:
            return None

    def showEvent(self, a0: QShowEvent | None):
        """Handle widget show event detect monitor and check support."""
        super().showEvent(a0)
        if not self._initialized:
            self._initialized = True
            self._hmonitor = self._get_hmonitor()
            # Check if monitor supports brightness
            if self._hmonitor:
                brightness = self._service.get_brightness(self._hmonitor)
                if brightness is None:
                    # Monitor doesn't support brightness control hide widget
                    self.hide()
                    return
                self.current_brightness = brightness
                self._update_label()

    def _on_brightness_changed(self, hmonitor: int, brightness: int | None):
        """Handle brightness change from service (thread-safe via signal)."""
        if hmonitor == self._hmonitor:
            # Start auto light timer once on first successful brightness read
            if brightness is not None and not self._auto_light_started and self.config.auto_light:
                self._auto_light_started = True
                self._auto_light_timer = QTimer()
                self._auto_light_timer.timeout.connect(self._check_auto_light)
                self._auto_light_timer.start(60000)
                self._check_auto_light()

            self.current_brightness = brightness
            self._update_label()

    def get_brightness(self) -> int | None:
        """Get current brightness (cached)."""
        if self._hmonitor is None:
            self._hmonitor = self._get_hmonitor()
        if self._hmonitor:
            return self._service.get_brightness(self._hmonitor)
        return None

    def set_brightness(self, value: int):
        """Set brightness."""
        if self._hmonitor is None:
            self._hmonitor = self._get_hmonitor()
        if self._hmonitor:
            self._service.set_brightness(self._hmonitor, value)
            self.current_brightness = value
            self._update_label()

    def _toggle_label(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_level_next(self):
        current = self.get_brightness()
        if current is None or not self.config.brightness_toggle_level:
            return
        levels = self.config.brightness_toggle_level
        next_levels = [level for level in levels if level > current]
        self.set_brightness(next_levels[0] if next_levels else levels[0])

    def _toggle_level_prev(self):
        current = self.get_brightness()
        if current is None or not self.config.brightness_toggle_level:
            return
        levels = self.config.brightness_toggle_level
        prev_levels = [level for level in levels if level < current]
        self.set_brightness(prev_levels[-1] if prev_levels else levels[-1])

    def _toggle_brightness_menu(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_brightness_menu()

    def _update_label(self):
        """Update the widget label with current brightness."""
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        percent = self.current_brightness
        if percent is None:
            self.hide()
            return

        # Show widget if it was hidden
        if not self.isVisible():
            self.show()

        icon = self._get_brightness_icon(percent)
        if self.config.tooltip:
            set_tooltip(self, f"Brightness {percent}%")

        label_options = {"{icon}": icon, "{percent}": percent}

        # Update progress bar
        if self.config.progress_bar.enabled and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                pos = 0 if self.config.progress_bar.position == "left" else self._widget_container_layout.count()
                self._widget_container_layout.insertWidget(pos, self.progress_widget)
            self.progress_widget.set_value(percent)

        # Update label widgets
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets):
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def _get_brightness_icon(self, brightness: int) -> str:
        """Get icon based on brightness level."""
        if self.config.auto_light:
            return self.config.auto_light_icon
        if brightness <= 25:
            return self.config.brightness_icons[0]
        elif brightness <= 50:
            return self.config.brightness_icons[1]
        elif brightness <= 75:
            return self.config.brightness_icons[2]
        return self.config.brightness_icons[3]

    def _show_brightness_menu(self):
        """Show brightness slider popup."""
        self.dialog = PopupWidget(
            self,
            self.config.brightness_menu.blur,
            self.config.brightness_menu.round_corners,
            self.config.brightness_menu.round_corners_type,
            self.config.brightness_menu.border_color,
        )
        self.dialog.setProperty("class", "brightness-menu")

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setProperty("class", "brightness-slider")
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)

        current = self.get_brightness()
        if current is not None:
            self.brightness_slider.setValue(current)

        self.brightness_slider.valueChanged.connect(self._on_slider_changed)
        self.brightness_slider.sliderReleased.connect(self._on_slider_released)

        layout.addWidget(self.brightness_slider)
        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.brightness_menu.alignment,
            direction=self.config.brightness_menu.direction,
            offset_left=self.config.brightness_menu.offset_left,
            offset_top=self.config.brightness_menu.offset_top,
        )
        self.dialog.show()

    def _on_slider_changed(self, value: int):
        """Handle slider value change."""
        self._show_slider_tooltip(value)
        if not self.brightness_slider.isSliderDown():
            self.set_brightness(value)

    def _on_slider_released(self):
        """Handle slider release hide tooltip and apply value."""
        if self._slider_tooltip:
            self._slider_tooltip.hide()
            self._slider_tooltip = None
        self.set_brightness(self.brightness_slider.value())

    def _show_slider_tooltip(self, value: int):
        """Show tooltip above slider handle during drag."""
        if not self.config.tooltip or not self.brightness_slider.isSliderDown():
            return

        # Calculate handle position
        slider = self.brightness_slider
        ratio = value / 100.0
        x_offset = int(slider.width() * ratio)
        global_pos = slider.mapToGlobal(slider.rect().topLeft())
        handle_rect = QRect(global_pos.x() + x_offset, global_pos.y(), 1, slider.height())

        if not self._slider_tooltip:
            self._slider_tooltip = CustomToolTip()
            self._slider_tooltip._position = "top"

        self._slider_tooltip.label.setText(f"{value}%")
        self._slider_tooltip.adjustSize()
        pos = self._slider_tooltip._calculate_position(handle_rect)
        self._slider_tooltip.move(pos.x(), pos.y())
        self._slider_tooltip.setWindowOpacity(1.0)
        self._slider_tooltip.show()

    def _check_auto_light(self):
        """Check and apply auto light settings."""
        current_time = datetime.now().time()
        start = self.config.auto_light_night_start_time
        end = self.config.auto_light_night_end_time

        # Handle midnight crossing
        if start <= end:
            is_night = start <= current_time <= end
        else:
            is_night = current_time >= start or current_time <= end

        new_mode = "night" if is_night else "day"
        if new_mode != self._current_mode:
            self._current_mode = new_mode
            level = self.config.auto_light_night_level if is_night else self.config.auto_light_day_level
            self.set_brightness(level)

    def wheelEvent(self, a0: QWheelEvent | None):
        """Handle mouse wheel for brightness adjustment."""
        if a0 is None:
            return

        current = self.get_brightness()
        if current is None:
            return

        if a0.angleDelta().y() > 0:
            new_value = min(current + self.config.scroll_step, 100)
        else:
            new_value = max(current - self.config.scroll_step, 0)

        self.set_brightness(new_value)

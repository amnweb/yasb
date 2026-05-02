import re
from datetime import datetime

from PyQt6.QtCore import QEvent, QRect, Qt, QTimer
from PyQt6.QtGui import QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QStyle, QStyleOptionSlider, QVBoxLayout

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import PopupWidget, build_progress_widget
from core.validation.widgets.yasb.brightness import BrightnessConfig
from core.widgets.base import BaseWidget
from core.widgets.services.brightness.service import BrightnessService


class BrightnessWidget(BaseWidget):
    validation_schema = BrightnessConfig

    def __init__(self, config: BrightnessConfig):
        super().__init__(class_name="brightness-widget")
        self.config = config
        self._show_alt_label = False
        self._widgets: list[QLabel] = []
        self._widgets_alt: list[QLabel] = []

        # Current state
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

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        # Register callbacks
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_level_next", self._toggle_level_next)
        self.register_callback("toggle_level_prev", self._toggle_level_prev)
        self.register_callback("toggle_brightness_menu", self._toggle_brightness_menu)

        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

    @property
    def _hmonitor(self) -> int | None:
        """Bar-resolved monitor handle (set by Bar after position)."""
        return self.monitor_hwnd

    def showEvent(self, a0: QShowEvent | None):
        """Handle widget show event detect monitor and check support."""
        super().showEvent(a0)
        if not self._initialized:
            self._initialized = True
            if self._hmonitor:
                brightness = self._service.get_brightness(self._hmonitor)
                if brightness is not None:
                    self.current_brightness = brightness
                    self._update_label()
                    return
            # No value yet
            self.hide()

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
        if self._hmonitor:
            return self._service.get_brightness(self._hmonitor)
        return None

    def set_brightness(self, value: int):
        """Set brightness."""
        if self._hmonitor:
            self._service.set_brightness(self._hmonitor, value)
            self.current_brightness = value
            self._update_label()

    def _toggle_label(self):
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
        """Show brightness/contrast slider popup with all monitors."""
        self.dialog = PopupWidget(
            self,
            self.config.brightness_menu.blur,
            self.config.brightness_menu.round_corners,
            self.config.brightness_menu.round_corners_type,
            self.config.brightness_menu.border_color,
        )
        self.dialog.setProperty("class", "brightness-menu")

        layout = QVBoxLayout(self.dialog)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        monitors = self._service.get_monitors()
        self._sliders: dict[str, QSlider] = {}
        self._slider_types: dict[str, str] = {}

        for idx, (hmonitor, name) in enumerate(monitors):
            self._add_monitor_section(layout, hmonitor, name, idx)

        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.brightness_menu.alignment,
            direction=self.config.brightness_menu.direction,
            offset_left=self.config.brightness_menu.offset_left,
            offset_top=self.config.brightness_menu.offset_top,
        )
        self.dialog.show()

    def _add_monitor_section(self, layout: QVBoxLayout, hmonitor: int, name: str, index: int = 0):
        """Add a monitor section with brightness and optional contrast sliders."""
        monitor_row = QFrame()
        monitor_row.setProperty("class", f"monitor-row monitor-{index}")
        monitor_layout = QVBoxLayout(monitor_row)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.setSpacing(0)

        title = QLabel(name)
        title.setProperty("class", "monitor-title")
        monitor_layout.addWidget(title)

        subtitle = self._service.get_monitor_subtitle(hmonitor, index)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("class", "monitor-subtitle")
            monitor_layout.addWidget(sub)

        sliders_group = QFrame()
        sliders_group.setProperty("class", "slider-rows")
        sliders_layout = QVBoxLayout(sliders_group)
        sliders_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout.setSpacing(0)

        bright_row_widget = QFrame()
        bright_row_widget.setProperty("class", "slider-row")
        bright_row = QHBoxLayout(bright_row_widget)
        bright_row.setContentsMargins(0, 0, 0, 0)
        bright_row.setSpacing(6)

        bright_icon = QLabel(self.config.brightness_menu.brightness_icon)
        bright_icon.setProperty("class", "slider-icon")
        bright_row.addWidget(bright_icon)

        bright_slider = QSlider(Qt.Orientation.Horizontal)
        bright_slider.setProperty("class", "brightness-slider")
        bright_slider.setMinimum(0)
        bright_slider.setMaximum(100)
        bright_slider.setMouseTracking(True)
        bright_slider.installEventFilter(self)
        brightness = self._service.get_brightness(hmonitor)
        if brightness is not None:
            bright_slider.setValue(brightness)

        key = f"brightness_{hmonitor}"
        self._sliders[key] = bright_slider
        self._slider_types[key] = "brightness"
        bright_slider.valueChanged.connect(lambda v, k=key: self._on_monitor_slider_changed(k, v))
        bright_slider.sliderReleased.connect(lambda k=key: self._on_monitor_slider_released(k))
        bright_row.addWidget(bright_slider, 1)

        sliders_layout.addWidget(bright_row_widget)

        if self._service.supports_contrast(hmonitor):
            contrast_row_widget = QFrame()
            contrast_row_widget.setProperty("class", "slider-row")
            contrast_row = QHBoxLayout(contrast_row_widget)
            contrast_row.setContentsMargins(0, 0, 0, 0)
            contrast_row.setSpacing(6)

            contrast_icon = QLabel(self.config.brightness_menu.contrast_icon)
            contrast_icon.setProperty("class", "slider-icon")
            contrast_row.addWidget(contrast_icon)

            contrast_slider = QSlider(Qt.Orientation.Horizontal)
            contrast_slider.setProperty("class", "contrast-slider")
            contrast_slider.setMinimum(0)
            contrast_slider.setMaximum(100)
            contrast_slider.setMouseTracking(True)
            contrast_slider.installEventFilter(self)
            current_contrast = self._service.get_contrast(hmonitor)
            if current_contrast is not None:
                contrast_slider.setValue(current_contrast)

            key = f"contrast_{hmonitor}"
            self._sliders[key] = contrast_slider
            self._slider_types[key] = "contrast"
            contrast_slider.valueChanged.connect(lambda v, k=key: self._on_monitor_slider_changed(k, v))
            contrast_slider.sliderReleased.connect(lambda k=key: self._on_monitor_slider_released(k))
            contrast_row.addWidget(contrast_slider, 1)

            sliders_layout.addWidget(contrast_row_widget)

        monitor_layout.addWidget(sliders_group)
        layout.addWidget(monitor_row)

    def _on_monitor_slider_changed(self, key: str, value: int):
        """Handle slider value change for brightness or contrast."""
        slider = self._sliders.get(key)
        if slider is None:
            return

        if slider.isSliderDown():
            self._show_slider_tooltip(value, slider)

        slider_type = self._slider_types.get(key)
        hmonitor = int(key.split("_", 1)[1])
        if slider_type == "brightness":
            self._service.set_brightness(hmonitor, value)
            if hmonitor == self._hmonitor:
                self.current_brightness = value
                self._update_label()
        elif slider_type == "contrast":
            self._service.set_contrast(hmonitor, value)

    def _on_monitor_slider_released(self, key: str):
        """Handle slider release — hide tooltip and apply value."""
        self._hide_slider_tooltip()

        slider = self._sliders.get(key)
        if not slider:
            return
        value = slider.value()
        slider_type = self._slider_types.get(key)
        hmonitor = int(key.split("_", 1)[1])

        if slider_type == "brightness":
            self._service.set_brightness(hmonitor, value)
            if hmonitor == self._hmonitor:
                self.current_brightness = value
                self._update_label()
        elif slider_type == "contrast":
            self._service.set_contrast(hmonitor, value)

    def _show_slider_tooltip(self, value: int, slider: QSlider = None):
        """Show tooltip above slider handle during drag or hover."""
        if not self.config.tooltip:
            return

        if slider is None:
            return

        ratio = slider.value() / 100.0
        x_offset = int(slider.width() * ratio)
        global_pos = slider.mapToGlobal(slider.rect().topLeft())
        handle_rect = QRect(global_pos.x() + x_offset, global_pos.y(), 1, slider.height())

        if not self._slider_tooltip:
            self._slider_tooltip = CustomToolTip()
            self._slider_tooltip._position = "top"

        self._slider_tooltip.label.setText(str(value))
        self._slider_tooltip.adjustSize()
        pos = self._slider_tooltip._calculate_position(handle_rect)
        self._slider_tooltip.move(pos.x(), pos.y())
        self._slider_tooltip.setWindowOpacity(1.0)
        self._slider_tooltip.show()

    def _hide_slider_tooltip(self):
        if self._slider_tooltip:
            self._slider_tooltip.hide()
            self._slider_tooltip = None

    @staticmethod
    def _is_over_slider_handle(slider: QSlider, pos) -> bool:
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle_rect = slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            slider,
        )
        return handle_rect.contains(pos)

    def eventFilter(self, obj, event):
        if isinstance(obj, QSlider) and self.config.tooltip:
            event_type = event.type()
            if event_type == QEvent.Type.MouseMove:
                pos = event.position().toPoint()
                if self._is_over_slider_handle(obj, pos):
                    self._show_slider_tooltip(obj.value(), obj)
                elif not obj.isSliderDown():
                    self._hide_slider_tooltip()
            elif event_type == QEvent.Type.Leave and not obj.isSliderDown():
                self._hide_slider_tooltip()
        return super().eventFilter(obj, event)

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

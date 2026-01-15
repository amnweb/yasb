import logging
import re

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import (
    PopupWidget,
    add_shadow,
    build_progress_widget,
    build_widget_label,
    is_valid_qobject,
    refresh_widget_style,
)
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.microphone.service import AudioInputService
from core.validation.widgets.yasb.microphone import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class MicrophoneWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        mute_text: str,
        tooltip: bool,
        scroll_step: int,
        icons: dict[str, str],
        mic_menu: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
    ):
        super().__init__(class_name=f"microphone-widget {class_name}")
        self.audio_endpoint = None
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._mute_text = mute_text
        self._tooltip = tooltip
        self._scroll_step = int(scroll_step) / 100
        self._icons = icons
        self._mic_menu = mic_menu
        self._padding = container_padding
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._progress_bar = progress_bar

        self.progress_widget = build_progress_widget(self, self._progress_bar)

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_mute", self.toggle_mute)
        self.register_callback("toggle_mic_menu", self.show_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._service = AudioInputService()
        self._service.register_widget(self)

        self.audio_endpoint = self._service.get_microphone_interface()
        self._update_label()

    def _reinitialize_microphone(self):
        """Update microphone interface reference after device change."""
        # Service already reinitialized, just update our reference
        self.audio_endpoint = self._service.get_microphone_interface()

        # Close dialog if open (device change means menu data is stale)
        if hasattr(self, "dialog") and is_valid_qobject(self.dialog):
            self.dialog.hide()
            # Only reopen menu if we still have a valid device
            if self.audio_endpoint is not None:
                try:
                    microphone = self._service.get_microphone()
                    if microphone:
                        self.show_menu()
                except Exception as e:
                    logging.debug(f"Cannot show microphone menu after device change: {e}")

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

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        # Handle no device case
        if self.audio_endpoint is None:
            min_icon = self._get_mic_icon()
            min_level = "No Device"
            mute_status = None
        else:
            try:
                mute_status = self.audio_endpoint.GetMute()
                mic_level = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
                min_icon = self._get_mic_icon()
                min_level = self._mute_text if mute_status == 1 else f"{mic_level}%"
            except Exception as e:
                logging.error(f"Failed to get microphone info: {e}")
                return

        label_options = {"{icon}": min_icon, "{level}": min_level}

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            numeric_value = int(re.search(r"\d+", min_level).group()) if re.search(r"\d+", min_level) else 0
            self.progress_widget.set_value(numeric_value)

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_muted_class(
                            active_widgets[widget_index], mute_status == 1 if mute_status is not None else False
                        )
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_muted_class(
                            active_widgets[widget_index], mute_status == 1 if mute_status is not None else False
                        )
                widget_index += 1

    def _update_slider_value(self):
        """Helper method to update slider value based on current microphone level"""
        if hasattr(self, "volume_slider") and self.audio_endpoint is not None:
            try:
                current_volume = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.setValue(current_volume)
            except:
                pass

    def _set_muted_class(self, widget, muted: bool):
        """Set or remove the 'muted' and 'no-device' classes on the widget."""
        current_class = widget.property("class") or ""
        classes = set(current_class.split())

        # Handle no-device class
        if self.audio_endpoint is None:
            classes.add("no-device")
        else:
            classes.discard("no-device")

        # Handle muted class
        if muted:
            classes.add("muted")
        else:
            classes.discard("muted")

        widget.setProperty("class", " ".join(classes))
        refresh_widget_style(widget)

    def _on_slider_released(self):
        """Hide tooltip when slider is released"""
        if hasattr(self, "_slider_tooltip") and self._slider_tooltip:
            self._slider_tooltip.hide()
            self._slider_tooltip = None

    def _show_slider_tooltip(self, slider, value):
        """Show tooltip above slider handle during drag."""
        if not self._tooltip or not slider.isSliderDown():
            return

        # Calculate handle position
        slider_range = slider.maximum() - slider.minimum()
        if slider_range <= 0:
            return
        ratio = (value - slider.minimum()) / slider_range
        x_offset = int(slider.width() * ratio)
        global_pos = slider.mapToGlobal(slider.rect().topLeft())
        handle_rect = QRect(global_pos.x() + x_offset, global_pos.y(), 1, slider.height())

        if not hasattr(self, "_slider_tooltip") or not self._slider_tooltip:
            self._slider_tooltip = CustomToolTip()
            self._slider_tooltip._position = "top"

        self._slider_tooltip.label.setText(f"{value}%")
        self._slider_tooltip.adjustSize()
        pos = self._slider_tooltip._calculate_position(handle_rect)
        self._slider_tooltip.move(pos.x(), pos.y())
        self._slider_tooltip.setWindowOpacity(1.0)
        self._slider_tooltip.show()

    def _get_mic_icon(self):
        """Get appropriate microphone icon based on mute status."""
        if self.audio_endpoint is None:
            if self._tooltip:
                set_tooltip(self, "No microphone device connected")
            return self._icons["muted"]

        current_mute_status = self.audio_endpoint.GetMute()
        current_level = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
        if current_mute_status == 1:
            mic_icon = self._icons["muted"]
            tooltip = f"Muted: Volume {current_level}%"
        else:
            mic_icon = self._icons["normal"]
            tooltip = f"Volume {current_level}%"
        if self._tooltip:
            set_tooltip(self, tooltip)
        return mic_icon

    def toggle_mute(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if self.audio_endpoint is None:
            return
        try:
            current_mute_status = self.audio_endpoint.GetMute()
            self.audio_endpoint.SetMute(not current_mute_status, None)
        except Exception as e:
            logging.error(f"Failed to toggle microphone mute: {e}")

    def _increase_volume(self):
        if self.audio_endpoint is None:
            return
        try:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + self._scroll_step, 1.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            if self.audio_endpoint.GetMute() and new_volume > 0.0:
                self.audio_endpoint.SetMute(False, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to increase microphone volume: {e}")

    def _decrease_volume(self):
        if self.audio_endpoint is None:
            return
        try:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - self._scroll_step, 0.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            if new_volume == 0.0:
                self.audio_endpoint.SetMute(True, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to decrease microphone volume: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if self.audio_endpoint is None:
            return
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()

    def show_menu(self):
        if self.audio_endpoint is None:
            return

        self.dialog = PopupWidget(
            self,
            self._mic_menu["blur"],
            self._mic_menu["round_corners"],
            self._mic_menu["round_corners_type"],
            self._mic_menu["border_color"],
        )
        self.dialog.setProperty("class", "microphone-menu")

        # Create vertical layout for the dialog
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create a container widget for device buttons
        self.container = QWidget()
        self.container.setProperty("class", "microphone-container")
        self.container_layout = QVBoxLayout()
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        # Get all microphone devices and create buttons if more than one
        self.devices = self._service.get_all_devices()
        if len(self.devices) > 1:
            current_device = self._service.get_microphone()
            current_device_id = current_device.id if current_device else None
            self.device_buttons = {}
            for device_id, device_name in self.devices:
                btn = QPushButton(device_name)
                if device_id == current_device_id:
                    btn.setProperty("class", "device selected")
                else:
                    btn.setProperty("class", "device")
                btn.setProperty("device_id", device_id)
                btn.clicked.connect(self._set_default_device)
                self.container_layout.addWidget(btn)
                self.device_buttons[device_id] = btn

            self.container.setLayout(self.container_layout)

        layout.addWidget(self.container)

        # Create global microphone volume section
        global_container = QFrame()
        global_container.setProperty("class", "system-volume-container")
        global_layout = QVBoxLayout()
        global_layout.setSpacing(0)
        global_layout.setContentsMargins(0, 0, 0, 0)

        # Slider row with toggle button
        slider_row = QHBoxLayout()
        slider_row.setSpacing(0)
        slider_row.setContentsMargins(0, 0, 0, 0)

        # System microphone slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setProperty("class", "volume-slider")
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        try:
            current_volume = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
            self.volume_slider.setValue(current_volume)
        except Exception:
            self.volume_slider.setValue(0)
        self.volume_slider.valueChanged.connect(self._on_slider_value_changed)
        self.volume_slider.sliderReleased.connect(self._on_slider_released)
        slider_row.addWidget(self.volume_slider)

        global_layout.addLayout(slider_row)
        global_container.setLayout(global_layout)
        layout.addWidget(global_container)

        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._mic_menu["alignment"],
            direction=self._mic_menu["direction"],
            offset_left=self._mic_menu["offset_left"],
            offset_top=self._mic_menu["offset_top"],
        )
        self.dialog.show()

    def _set_default_device(self):
        """Handle device button click to set new default microphone."""
        sender_btn = self.sender()
        device_id = sender_btn.property("device_id")

        # Unselect all buttons first
        for btn in self.device_buttons.values():
            btn.setProperty("class", "device")
            refresh_widget_style(btn)

        # Select clicked button
        sender_btn.setProperty("class", "device selected")
        refresh_widget_style(sender_btn)

        # Set the default device (this will trigger device change callback)
        self._service.set_default_device(device_id)

    def _on_slider_value_changed(self, value):
        if self.audio_endpoint is not None:
            try:
                self.audio_endpoint.SetMasterVolumeLevelScalar(value / 100, None)
                # Show tooltip while actively dragging
                if hasattr(self, "volume_slider"):
                    self._show_slider_tooltip(self.volume_slider, value)
            except Exception as e:
                logging.error(f"Failed to set microphone volume: {e}")

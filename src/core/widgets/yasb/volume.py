import ctypes
import logging
import re

from PIL import Image
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent
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
from core.utils.widgets.volume.service import AudioOutputService
from core.utils.win32.app_icons import get_process_icon
from core.utils.win32.utilities import get_app_name_from_pid
from core.validation.widgets.yasb.volume import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class VolumeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        mute_text: str,
        tooltip: bool,
        scroll_step: int,
        slider_beep: bool,
        volume_icons: list[str],
        audio_menu: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
    ):
        super().__init__(class_name=f"volume-widget {class_name}")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._mute_text = mute_text
        self._tooltip = tooltip
        self._scroll_step = int(scroll_step) / 100
        self._slider_beep = slider_beep
        self._audio_menu = audio_menu
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self.volume = None
        self._volume_icons = volume_icons
        self._progress_bar = progress_bar
        self._icon_cache = {}
        self._dpi = 1.0

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
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_mute", self.toggle_mute)
        self.register_callback("toggle_volume_menu", self._toggle_volume_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._service = AudioOutputService()
        self._service.register_widget(self)

        self.volume = self._service.get_volume_interface()
        self._update_label()

    def _reinitialize_audio(self):
        """Update volume interface reference after device change."""
        # Service already reinitialized, just update our reference
        self.volume = self._service.get_volume_interface()

        # Close dialog if open (device change means menu data is stale)
        if hasattr(self, "dialog") and is_valid_qobject(self.dialog):
            self.dialog.hide()
            # Only reopen menu if we still have a valid device and speakers available
            if self.volume is not None:
                try:
                    speakers = self._service.get_speakers()
                    if speakers:
                        self.show_volume_menu()
                except Exception as e:
                    logging.debug(f"Cannot show volume menu after device change: {e}")

        self._update_label()

    def _toggle_volume_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_volume_menu()

    def _on_slider_released(self):
        # Hide tooltip when slider is released
        if hasattr(self, "_slider_tooltip") and self._slider_tooltip:
            self._slider_tooltip.hide()
            self._slider_tooltip = None
        if self._slider_beep:
            # Play a beep sound when slider is released
            try:
                ctypes.windll.user32.MessageBeep(0)
            except Exception as e:
                logging.debug(f"Failed to play volume sound: {e}")

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

    def _on_slider_value_changed(self, value):
        if self.volume is not None:
            try:
                self.volume.SetMasterVolumeLevelScalar(value / 100, None)
                # Show tooltip while actively dragging
                if hasattr(self, "volume_slider"):
                    self._show_slider_tooltip(self.volume_slider, value)
            except Exception as e:
                logging.error(f"Failed to set volume: {e}")

    def _set_app_volume(self, volume_interface, value, slider=None):
        """Set volume for a specific application"""
        try:
            volume_interface.SetMasterVolume(value / 100, None)
            # Show tooltip while actively dragging
            if slider:
                self._show_slider_tooltip(slider, value)
        except Exception as e:
            logging.error(f"Failed to set application volume: {e}")

    def _toggle_app_mute(self, volume_interface, icon_label, slider, pid):
        """Toggle mute state for a specific application"""
        try:
            current_mute = volume_interface.GetMute()
            new_mute = not current_mute
            volume_interface.SetMute(new_mute, None)
            # Update icon and slider state
            self._update_app_mute_state(icon_label, slider, new_mute, pid)
        except Exception as e:
            logging.error(f"Failed to toggle application mute: {e}")

    def _update_app_mute_state(self, icon_label, slider, is_muted, pid):
        """Update the visual state of an app's icon and slider based on mute status"""
        try:
            # Get the original icon
            app_icon = self._get_process_icon_pixmap(pid, icon_size=16, force_grayscale=is_muted)
            if app_icon:
                icon_label.setPixmap(app_icon)

            # Enable/disable the slider
            slider.setEnabled(not is_muted)
        except Exception as e:
            logging.error(f"Failed to update app mute state: {e}")

    def _toggle_app_volumes(self):
        """Toggle the visibility of application volume sliders with animation"""
        if not hasattr(self, "app_volumes_container") or not hasattr(self, "app_volumes_expanded"):
            return

        # Toggle the expanded state
        self.app_volumes_expanded = not self.app_volumes_expanded

        if self.app_volumes_expanded:
            # Show container first
            self.app_volumes_container.show()
            content_height = self.app_volumes_container.sizeHint().height()
            target_height = content_height
            current_height = 0
            self.app_toggle_btn.setText(self._audio_menu["app_icons"]["toggle_up"])
            self.app_toggle_btn.setProperty("class", "toggle-apps expanded")
            if self._tooltip:
                set_tooltip(self.app_toggle_btn, "Collapse application volumes")
        else:
            target_height = 0
            current_height = self.app_volumes_container.height()
            self.app_toggle_btn.setText(self._audio_menu["app_icons"]["toggle_down"])
            self.app_toggle_btn.setProperty("class", "toggle-apps")
            if self._tooltip:
                set_tooltip(self.app_toggle_btn, "Expand application volumes")

        refresh_widget_style(self.app_toggle_btn)

        # Stop any existing animation
        if (
            hasattr(self, "app_volume_animation")
            and self.app_volume_animation.state() == QPropertyAnimation.State.Running
        ):
            self.app_volume_animation.stop()

        # Set the starting height immediately before animation
        self.app_volumes_container.setMaximumHeight(current_height)

        # Create animation
        self.app_volume_animation = QPropertyAnimation(self.app_volumes_container, b"maximumHeight")
        self.app_volume_animation.setDuration(200)
        self.app_volume_animation.setStartValue(current_height)
        self.app_volume_animation.setEndValue(target_height)
        self.app_volume_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Update dialog size during animation
        self.app_volume_animation.valueChanged.connect(self._resize_dialog)

        # Hide container after animation completes if collapsing
        if not self.app_volumes_expanded:
            self.app_volume_animation.finished.connect(lambda: self.app_volumes_container.hide())

        self.app_volume_animation.start()

    def _resize_dialog(self):
        """Resize the dialog to fit its content during animation"""
        if hasattr(self, "dialog"):
            self.dialog.adjustSize()

    def _update_slider_value(self):
        """Helper method to update slider value based on current volume"""
        if hasattr(self, "volume_slider") and self.volume is not None:
            try:
                current_volume = round(self.volume.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.setValue(current_volume)
            except:
                pass

    def _format_session_label(self, name: str) -> str:
        """Format session label by removing file extensions and truncating if necessary"""
        name = name.removesuffix(".exe").replace(".", " ").title()
        return name if len(name) <= 23 else f"{name[:20]}..."

    def _get_process_icon_pixmap(self, pid: int, icon_size: int = 16, force_grayscale: bool = False) -> QPixmap | None:
        """Get icon for a process and convert to QPixmap with DPI-aware caching"""
        try:
            # Create cache key with PID, icon_size, DPI, and grayscale state
            cache_key = (pid, icon_size, self._dpi, force_grayscale)

            if cache_key in self._icon_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                # Get current DPI
                self._dpi = self.screen().devicePixelRatio()
                icon_img = get_process_icon(pid)
                if icon_img:
                    # Resize and convert to RGBA with DPI scaling
                    scaled_size = int(icon_size * self._dpi)
                    icon_img = icon_img.resize((scaled_size, scaled_size), Image.LANCZOS)
                    icon_img = icon_img.convert("RGBA")

                    # Apply grayscale if muted
                    if force_grayscale:
                        # Convert to grayscale while preserving alpha channel
                        grayscale = icon_img.convert("L")
                        icon_img.paste(grayscale, (0, 0), icon_img)

                    # Cache the resized image
                    self._icon_cache[cache_key] = icon_img

            if not icon_img:
                return None

            # Convert to QPixmap
            data = icon_img.tobytes("raw", "RGBA")
            qimage = QImage(data, icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            pixmap.setDevicePixelRatio(self._dpi)
            return pixmap
        except Exception as e:
            logging.debug(f"Failed to get icon pixmap for PID {pid}: {e}")

        return None

    def _update_device_buttons(self, active_device_id):
        # Update classes for all device buttons
        for device_id, btn in self.device_buttons.items():
            if device_id == active_device_id:
                btn.setProperty("class", "device selected")
            else:
                btn.setProperty("class", "device")
            refresh_widget_style(btn)

    def _set_default_device(self):
        """Set default audio device using pycaw's built-in method"""
        sender = self.sender()
        device_id = sender.property("device_id")

        if self._service.set_default_device(device_id):
            self._update_slider_value()
            self._update_device_buttons(device_id)
            self._update_label()

    def show_volume_menu(self):
        if self.volume is None:
            return

        self.dialog = PopupWidget(
            self,
            self._audio_menu["blur"],
            self._audio_menu["round_corners"],
            self._audio_menu["round_corners_type"],
            self._audio_menu["border_color"],
        )
        self.dialog.setProperty("class", "audio-menu")

        # Create vertical layout for the dialog
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create a container widget and layout
        self.container = QWidget()
        self.container.setProperty("class", "audio-container")
        self.container_layout = QVBoxLayout()
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        self.devices = self._service.get_all_devices()
        if len(self.devices) > 1:
            current_device = self._service.get_speakers()
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

        # Create global volume section (at the top)
        global_container = QFrame()
        global_container.setProperty("class", "system-volume-container")
        global_layout = QVBoxLayout()
        global_layout.setSpacing(0)
        global_layout.setContentsMargins(0, 0, 0, 0)

        # Slider row with toggle button
        slider_row = QHBoxLayout()
        slider_row.setSpacing(0)
        slider_row.setContentsMargins(0, 0, 0, 0)

        # System volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setProperty("class", "volume-slider")
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)

        # Set current volume
        try:
            current_volume = round(self.volume.GetMasterVolumeLevelScalar() * 100)
            self.volume_slider.setValue(current_volume)
        except:
            self.volume_slider.setValue(0)

        # Connect slider value change to volume control
        self.volume_slider.valueChanged.connect(self._on_slider_value_changed)
        # Connect slider release to hide tooltip and optionally beep
        self.volume_slider.sliderReleased.connect(self._on_slider_released)

        slider_row.addWidget(self.volume_slider)

        audio_sessions = []
        if self._audio_menu["show_apps"]:
            # Get active audio sessions directly from service
            audio_sessions = self._service.get_active_audio_sessions(
                get_app_name_callback=get_app_name_from_pid,
                format_name_callback=self._format_session_label,
            )
            # Add app toggle button on the right (only if there are audio sessions)
            if audio_sessions:
                self.app_toggle_btn = QPushButton(self._audio_menu["app_icons"]["toggle_down"])
                self.app_toggle_btn.setProperty("class", "toggle-apps")
                self.app_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self.app_toggle_btn.clicked.connect(lambda: self._toggle_app_volumes())
                if self._tooltip:
                    set_tooltip(self.app_toggle_btn, "Expand application volumes")
                slider_row.addWidget(self.app_toggle_btn)

        global_layout.addLayout(slider_row)
        global_container.setLayout(global_layout)
        layout.addWidget(global_container)

        # Create per-application volume sliders section
        if audio_sessions and self._audio_menu["show_apps"]:
            self.app_volumes_container = QFrame()
            self.app_volumes_container.setProperty("class", "apps-container")
            app_volumes_layout = QVBoxLayout()
            app_volumes_layout.setSpacing(0)
            app_volumes_layout.setContentsMargins(0, 0, 0, 0)

            for session_info in audio_sessions:
                app_container = QFrame()
                app_container.setProperty("class", "app-volume")
                app_layout = QVBoxLayout()
                app_layout.setSpacing(0)
                app_layout.setContentsMargins(0, 0, 0, 0)

                display_name = session_info.get("app_name", self._format_session_label(session_info["name"]))
                if self._audio_menu["show_app_labels"]:
                    app_label = QLabel(display_name)
                    app_label.setProperty("class", "app-label")
                    app_layout.addWidget(app_label)

                slider_layout = QHBoxLayout()
                slider_layout.setSpacing(0)
                slider_layout.setContentsMargins(0, 0, 0, 0)

                try:
                    is_muted = session_info["volume_interface"].GetMute()
                except:
                    is_muted = False

                if self._audio_menu["show_app_icons"]:
                    icon_frame = QFrame()
                    icon_frame.setContentsMargins(0, 0, 0, 0)
                    icon_frame.setProperty("class", "app-icon-container")
                    icon_frame.setCursor(Qt.CursorShape.PointingHandCursor)
                    if self._tooltip:
                        set_tooltip(icon_frame, display_name, delay=800, position="top")

                    icon_frame_layout = QHBoxLayout()
                    icon_frame_layout.setContentsMargins(0, 0, 0, 0)
                    icon_frame_layout.setSpacing(0)
                    icon_frame.setLayout(icon_frame_layout)

                    icon_label = QLabel()
                    icon_label.setProperty("class", "app-icon")
                    icon_label.setFixedSize(16, 16)

                    # Try to get the app icon (grayscale if muted)
                    app_icon = self._get_process_icon_pixmap(
                        session_info["pid"], icon_size=16, force_grayscale=is_muted
                    )
                    if app_icon:
                        icon_label.setPixmap(app_icon)

                    icon_frame_layout.addWidget(icon_label)
                    slider_layout.addWidget(icon_frame)

                # Application volume slider
                app_slider = QSlider(Qt.Orientation.Horizontal)
                app_slider.setProperty("class", "app-slider")
                app_slider.setMinimum(0)
                app_slider.setMaximum(100)

                try:
                    app_volume = int(session_info["volume_interface"].GetMasterVolume() * 100)
                    app_slider.setValue(app_volume)
                except:
                    app_slider.setValue(100)
                # Disable slider if muted
                app_slider.setEnabled(not is_muted)

                # Connect to change app volume
                app_slider.valueChanged.connect(
                    lambda value,
                    vol_interface=session_info["volume_interface"],
                    slider=app_slider: self._set_app_volume(vol_interface, value, slider)
                )
                # Connect slider release to hide tooltip
                app_slider.sliderReleased.connect(self._on_slider_released)

                if self._audio_menu["show_app_icons"]:
                    # Make icon frame clickable to toggle mute
                    icon_frame.mousePressEvent = lambda event, vol_interface=session_info[
                        "volume_interface"
                    ], icon=icon_label, slider=app_slider, pid=session_info["pid"]: self._toggle_app_mute(
                        vol_interface, icon, slider, pid
                    )

                slider_layout.addWidget(app_slider)
                app_layout.addLayout(slider_layout)
                app_container.setLayout(app_layout)
                app_volumes_layout.addWidget(app_container)

            self.app_volumes_container.setLayout(app_volumes_layout)

            # Initially hide the app volumes
            self.app_volumes_container.setMaximumHeight(0)
            self.app_volumes_container.hide()
            layout.addWidget(self.app_volumes_container)

            # Store expanded state
            self.app_volumes_expanded = False
        self.dialog.setLayout(layout)

        # Position the dialog
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._audio_menu["alignment"],
            direction=self._audio_menu["direction"],
            offset_left=self._audio_menu["offset_left"],
            offset_top=self._audio_menu["offset_top"],
        )
        self.dialog.show()
        # Automatically expand app volumes if configured
        if audio_sessions and self._audio_menu["show_apps_expanded"] and self._audio_menu["show_apps"]:
            self._toggle_app_volumes()

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

        if self.volume is None:
            mute_status, icon_volume, level_volume = None, self._volume_icons[0], "No Device"
            set_tooltip(self, "No audio device connected.")
        else:
            try:
                mute_status = self.volume.GetMute()
                icon_volume = self._get_volume_icon()
                level_volume = (
                    self._mute_text if mute_status == 1 else f"{round(self.volume.GetMasterVolumeLevelScalar() * 100)}%"
                )
            except Exception as e:
                logging.error(f"Failed to get volume info: {e}")
                mute_status, icon_volume, level_volume = None, "", "No Device"

        label_options = {"{icon}": icon_volume, "{level}": level_volume}

        if self._progress_bar["enabled"] and self.progress_widget and self.volume is not None:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            numeric_value = int(re.search(r"\d+", level_volume).group()) if re.search(r"\d+", level_volume) else 0
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
                        self._set_device_state_classes(active_widgets[widget_index], mute_status == 1)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_device_state_classes(active_widgets[widget_index], mute_status == 1)
                widget_index += 1

    def _set_device_state_classes(self, widget, muted: bool):
        """Set or remove the 'muted' and 'no-device' classes on the widget."""
        current_class = widget.property("class") or ""
        classes = set(current_class.split())

        # Handle no-device class
        if self.volume is None:
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

    def _get_volume_icon(self):
        current_mute_status = self.volume.GetMute()
        current_volume_level = round(self.volume.GetMasterVolumeLevelScalar() * 100)
        if self._tooltip:
            set_tooltip(self, f"Volume {current_volume_level}% {'(Muted)' if current_mute_status == 1 else ''}")
        if current_mute_status == 1:
            volume_icon = self._volume_icons[0]
        elif 0 <= current_volume_level < 11:
            volume_icon = self._volume_icons[1]
        elif 11 <= current_volume_level < 30:
            volume_icon = self._volume_icons[2]
        elif 30 <= current_volume_level < 60:
            volume_icon = self._volume_icons[3]
        else:
            volume_icon = self._volume_icons[4]
        return volume_icon

    def _increase_volume(self):
        if self.volume is None:
            return
        try:
            current_volume = self.volume.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + self._scroll_step, 1.0)
            self.volume.SetMasterVolumeLevelScalar(new_volume, None)
            if self.volume.GetMute() and new_volume > 0.0:
                self.volume.SetMute(False, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to increase volume: {e}")

    def _decrease_volume(self):
        if self.volume is None:
            return
        try:
            current_volume = self.volume.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - self._scroll_step, 0.0)
            self.volume.SetMasterVolumeLevelScalar(new_volume, None)
            if new_volume == 0.0:
                self.volume.SetMute(True, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to decrease volume: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if self.volume is None:
            return
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()

    def toggle_mute(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if self.volume is None:
            return
        try:
            current_mute_status = self.volume.GetMute()
            self.volume.SetMute(not current_mute_status, None)
            self._update_label()
        except Exception as e:
            logging.error(f"Failed to toggle mute: {e}")

import ctypes
import logging
from typing import Any, Optional

import comtypes
from PIL import Image, ImageChops
from PIL.ImageDraw import ImageDraw
from PIL.ImageQt import ImageQt
from pycaw.pycaw import AudioUtilities
from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QWheelEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QSlider, QVBoxLayout
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackInfo

from core.utils.utilities import PopupWidget, ScrollingLabel, add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.media.aumid_process import get_process_name_for_aumid
from core.utils.widgets.media.media import WindowsMedia
from core.utils.widgets.media.source_apps import (
    get_source_app_class_name,
    get_source_app_display_name,
    get_source_app_mapping,
)
from core.utils.win32.app_aumid import (
    ERROR_INSUFFICIENT_BUFFER,
    PROCESS_QUERY_LIMITED_INFORMATION,
    CloseHandle,
    GetApplicationUserModelId,
    OpenProcess,
)
from core.validation.widgets.yasb.media import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


class MediaWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    _playback_info_signal = QtCore.pyqtSignal(GlobalSystemMediaTransportControlsSessionPlaybackInfo)
    _media_info_signal = QtCore.pyqtSignal(object)
    _session_status_signal = QtCore.pyqtSignal(bool)
    _popup_play_button = None
    _popup_next_label = None
    _popup_prev_label = None
    _timeline_info_signal = QtCore.pyqtSignal(object)

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        hide_empty: bool,
        callbacks: dict[str, str],
        max_field_size: dict[str, int],
        show_thumbnail: bool,
        controls_only: bool,
        controls_left: bool,
        controls_hide: bool,
        thumbnail_alpha: int,
        thumbnail_padding: int,
        thumbnail_corner_radius: int,
        thumbnail_edge_fade: bool,
        symmetric_corner_radius: bool,
        icons: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        media_menu: dict[str, Any],
        media_menu_icons: dict[str, str],
        scrolling_label: dict[str, Any],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"media-widget {class_name}")
        self._label_content = label
        self._label_alt_content = label_alt

        self._max_field_size = max_field_size
        self._show_thumbnail = show_thumbnail
        self._thumbnail_alpha = thumbnail_alpha
        self._media_button_icons = icons
        self._controls_only = controls_only
        self._controls_left = controls_left
        self._controls_hide = controls_hide
        self._thumbnail_padding = thumbnail_padding
        self._thumbnail_corner_radius = thumbnail_corner_radius
        self._thumbnail_edge_fade = thumbnail_edge_fade
        self._symmetric_corner_radius = symmetric_corner_radius
        self._hide_empty = hide_empty
        self._animation = animation
        self._padding = container_padding
        self._menu_config = media_menu
        self._menu_config_icons = media_menu_icons
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._scrolling_label = scrolling_label
        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        if self._hide_empty:
            self.hide()
        # Make a grid box to overlay the text and thumbnail
        self.thumbnail_box = QGridLayout()

        if self._controls_left:
            self._prev_label, self._play_label, self._next_label = self._create_media_buttons()
            if not controls_only:
                self._widget_container_layout.addLayout(self.thumbnail_box)
        else:
            if not controls_only:
                self._widget_container_layout.addLayout(self.thumbnail_box)
            self._prev_label, self._play_label, self._next_label = self._create_media_buttons()

        # Label
        if self._scrolling_label["enabled"]:
            self._label = ScrollingLabel(
                self,
                max_width=self._max_field_size["label"],
                options=self._scrolling_label,
            )
        else:
            self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        add_shadow(self._label, self._label_shadow)

        # Label Alt
        if self._scrolling_label["enabled"]:
            self._label_alt = ScrollingLabel(
                self,
                max_width=self._max_field_size["label_alt"],
                options=self._scrolling_label,
            )
        else:
            self._label_alt = QLabel(self)
        self._label_alt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        add_shadow(self._label_alt, self._label_shadow)

        self._thumbnail_label = QLabel(self)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")

        self.thumbnail_box.addWidget(self._thumbnail_label, 0, 0)
        self.thumbnail_box.addWidget(self._label, 0, 0)
        self.thumbnail_box.addWidget(self._label_alt, 0, 0)

        # Get media manager
        self.media = WindowsMedia()

        if self._controls_only:
            # Initial hide labels and thumbnail
            self._label.hide()
            self._label_alt.hide()
            self._thumbnail_label.hide()

        # Set configure signals and register them als callbacks
        self._playback_info_signal.connect(self._on_playback_info_changed)
        self.media.subscribe(
            lambda playback_info: self._playback_info_signal.emit(playback_info)
            if hasattr(self, "_playback_info_signal")
            else None,
            "playback_info",
        )
        self._media_info_signal.connect(self._on_media_properties_changed)
        self.media.subscribe(
            lambda media_info: self._media_info_signal.emit(media_info)
            if hasattr(self, "_media_info_signal")
            else None,
            "media_info",
        )
        self._session_status_signal.connect(self._on_session_status_changed)
        self.media.subscribe(
            lambda session_status: self._session_status_signal.emit(session_status)
            if hasattr(self, "_session_status_signal")
            else None,
            "session_status",
        )
        self._timeline_info_signal.connect(self._on_timeline_properties_changed)
        self.media.subscribe(
            lambda timeline_info: self._timeline_info_signal.emit(timeline_info)
            if hasattr(self, "_timeline_info_signal")
            else None,
            "timeline_info",
        )
        self.media.subscribe(
            lambda timeline_info: self._update_interpolated_position(timeline_info)
            if hasattr(self, "_label")
            else None,
            "timeline_interpolated",
        )

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.register_callback("toggle_media_menu", self._toggle_media_menu)
        if not self._controls_only:
            self.register_callback("toggle_play_pause", self._toggle_play_pause)
            self.register_callback("toggle_label", self._toggle_label)
            self._label.show()

        self._label_alt.hide()
        self._show_alt_label = False

        # Force media update to detect running session
        self.timer.singleShot(0, self.media.force_update)

        # Initialize tracking variables
        self._last_position = 0
        self._last_update_time = 0
        self._is_playing = False
        self._app_volume_slider = None
        self._app_volume_session = None
        self._app_mute_button = None
        self._app_is_muted = False

    def _toggle_media_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_menu()

    def show_menu(self):
        self._dialog = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )

        self._dialog.setProperty("class", "media-menu")

        # Create main layout for the popup dialog
        main_layout = QVBoxLayout(self._dialog)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)

        # Try to get current media info and thumbnail
        media_info = self.media._media_info

        if media_info is not None and (
            ("title" in media_info and media_info["title"] is not None)
            or ("artist" in media_info and media_info["artist"] is not None)
        ):
            # Create thumbnail label
            self._popup_thumbnail_label = QLabel()
            self._popup_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._popup_thumbnail_label.setProperty("class", "thumbnail")
            self._popup_thumbnail_label.setContentsMargins(0, 0, 0, 0)
            self._popup_thumbnail_label.setFixedSize(
                self._menu_config["thumbnail_size"], self._menu_config["thumbnail_size"]
            )
            try:
                # Use thumbnail if available, otherwise create a default one
                if media_info["thumbnail"] is not None:
                    popup_pixmap = self._create_thumbnail_for_popup(media_info["thumbnail"])
                else:
                    # Create default thumbnail
                    popup_pixmap = self._create_empty_thumbnail()

                if popup_pixmap:
                    self._popup_thumbnail_label.setPixmap(popup_pixmap)
                    content_layout.addWidget(self._popup_thumbnail_label, alignment=Qt.AlignmentFlag.AlignTop)

                # Create layout for text information (title, artist, slider, controls)
                text_layout = QVBoxLayout()
                text_layout.setContentsMargins(0, 0, 0, 0)
                text_layout.setSpacing(0)
                text_layout.setProperty("class", "text-layout")

                title_text = (
                    self._format_max_field_size(media_info["title"], "popup_title")
                    if media_info["title"] is not None
                    else "Unknown Title"
                )
                self._popup_title_label = QLabel(title_text)
                self._popup_title_label.setContentsMargins(0, 0, 0, 0)
                self._popup_title_label.setProperty("class", "title")
                self._popup_title_label.setWordWrap(True)
                self._popup_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

                artist_text = (
                    self._format_max_field_size(media_info["artist"], "popup_artist")
                    if media_info["artist"] is not None
                    else "Unknown Artist"
                )
                self._popup_artist_label = QLabel(artist_text)
                self._popup_artist_label.setContentsMargins(0, 0, 0, 0)
                self._popup_artist_label.setProperty("class", "artist")
                self._popup_artist_label.setWordWrap(True)
                self._popup_artist_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
                text_layout.addWidget(self._popup_title_label, alignment=Qt.AlignmentFlag.AlignTop)
                text_layout.addWidget(self._popup_artist_label, alignment=Qt.AlignmentFlag.AlignTop)

                # Add control buttons directly below the slider in the text layout
                control_layout = QHBoxLayout()
                control_layout.setSpacing(0)

                # Create clickable buttons using the same method as main widget
                prev_button = ClickableLabel(self)
                prev_button.setProperty("class", "btn prev")
                prev_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                prev_button.setText(self._menu_config_icons["prev_track"])
                prev_button.data = self.media.prev
                self._popup_prev_label = prev_button

                play_button = ClickableLabel(self)
                play_button.setProperty("class", "btn play")
                play_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                play_icon = self._menu_config_icons["pause" if self._is_playing else "play"]
                play_button.setText(play_icon)
                play_button.data = self.media.play_pause
                self._popup_play_button = play_button

                next_button = ClickableLabel(self)
                next_button.setProperty("class", "btn next")
                next_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                next_button.setText(self._menu_config_icons["next_track"])
                next_button.data = self.media.next
                self._popup_next_label = next_button

                control_layout.addWidget(prev_button)
                control_layout.addWidget(play_button)
                control_layout.addWidget(next_button)

                control_layout.addStretch(1)

                source_name, source_class_name = self._get_source_app_name(media_info)
                if source_name is not None and self._menu_config["show_source"]:
                    self._popup_source_label = QLabel(source_name)
                    self._popup_source_label.setContentsMargins(0, 0, 0, 0)
                    self._popup_source_label.setProperty("class", f"source {source_class_name}")
                    self._popup_source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    control_layout.addWidget(self._popup_source_label, 0, Qt.AlignmentFlag.AlignVCenter)

                # Add control layout to the text layout
                text_layout.addLayout(control_layout)

                # Add the text layout to the top layout
                content_layout.addLayout(text_layout)

                # Per-app vertical volume slider
                if self._menu_config["show_volume_slider"]:
                    try:
                        self._vol_container = QFrame()
                        self._vol_container.setProperty("class", "app-volume-container")
                        vol_layout = QVBoxLayout(self._vol_container)
                        vol_layout.setContentsMargins(0, 0, 0, 0)
                        vol_layout.setSpacing(0)

                        self._app_volume_slider = QSlider(Qt.Orientation.Vertical)
                        self._app_volume_slider.setProperty("class", "volume-slider")
                        self._app_volume_slider.setMinimum(0)
                        self._app_volume_slider.setMaximum(100)
                        self._app_volume_slider.setCursor(Qt.CursorShape.PointingHandCursor)
                        self._app_volume_slider.valueChanged.connect(self._on_app_volume_slider_changed)

                        vol_layout.addWidget(self._app_volume_slider, 0, Qt.AlignmentFlag.AlignCenter)

                        # Add mute/unmute button below the volume slider
                        self._app_mute_button = ClickableLabel(self)
                        self._app_mute_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        self._app_mute_button.setProperty("class", "mute-button")
                        self._app_mute_button.setCursor(Qt.CursorShape.PointingHandCursor)
                        self._app_mute_button.data = self._toggle_app_mute

                        vol_layout.addWidget(self._app_mute_button, 0, Qt.AlignmentFlag.AlignCenter)
                        content_layout.addWidget(self._vol_container, 0, Qt.AlignmentFlag.AlignRight)

                        # Bind slider to the current media app session and set initial value
                        self._bind_app_volume_session()
                        self._update_app_volume_slider()
                        self._update_app_mute_button()
                    except Exception as e:
                        logging.error(f"MediaWidget: Error creating app volume slider: {e}")

            except Exception as e:
                logging.error(f"MediaWidget: Error setting thumbnail in menu: {e}")
        else:
            # No media playing message
            no_media_label = QLabel("No media playing")
            no_media_label.setProperty("class", "no-media")
            no_media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(no_media_label)

        # Add top layout to main layout
        main_layout.addLayout(content_layout)

        # Create horizontal layout for slider and time labels
        self._time_slider_container = QFrame()
        self._time_slider_container.setProperty("class", "media-timeline-container")
        self._time_slider_container.setContentsMargins(0, 0, 0, 0)

        # Use a vertical layout for the container instead of horizontal
        time_slider_layout = QVBoxLayout(self._time_slider_container)
        time_slider_layout.setContentsMargins(0, 0, 0, 0)
        time_slider_layout.setSpacing(0)  # Add spacing between slider and time labels

        # Create and configure the slider
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setProperty("class", "progress-slider")
        self._progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._progress_slider.setMinimum(0)
        self._progress_slider.setMaximum(1000)  # We use 1000 for better precision

        # Create a horizontal layout for the time labels
        time_labels_layout = QHBoxLayout()
        time_labels_layout.setContentsMargins(0, 0, 0, 0)
        time_labels_layout.setSpacing(0)

        # Create time labels for current and total time
        self._popup_current_time_label = QLabel("00:00")
        self._popup_current_time_label.setProperty("class", "playback-time current")
        self._popup_current_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._popup_total_time_label = QLabel("00:00")
        self._popup_total_time_label.setProperty("class", "playback-time total")
        self._popup_total_time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Initialize with current times if available
        if hasattr(self, "_last_position") and hasattr(self, "_duration"):
            self._popup_current_time_label.setText(self._format_time(self._last_position))
            self._popup_total_time_label.setText(self._format_time(self._duration))

        # Add time labels to the horizontal layout with stretch to push them apart
        time_labels_layout.addWidget(self._popup_current_time_label)
        time_labels_layout.addStretch(1)  # This pushes the labels to opposite sides
        time_labels_layout.addWidget(self._popup_total_time_label)

        # Add the time labels layout to the main vertical layout
        time_slider_layout.addLayout(time_labels_layout)
        time_slider_layout.addWidget(self._progress_slider)

        # Add the time-slider layout to the main layout instead of just the slider
        main_layout.addWidget(self._time_slider_container)

        # Initialize slider position
        if hasattr(self, "_last_position") and hasattr(self, "_duration") and self._duration > 0:
            percent = min(1000, int((self._last_position / self._duration) * 1000))
            self._progress_slider.setValue(percent)
        else:
            self._progress_slider.setValue(0)

        # Connect slider events
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.valueChanged.connect(self._on_slider_value_changed)

        # Initialize seeking flag
        self._seeking = False

        if not self.media.is_seek_supported():
            self._time_slider_container.setVisible(False)
            QTimer.singleShot(0, lambda: self._dialog.adjustSize())

        self._dialog.adjustSize()
        self._dialog.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._update_popup_menu_buttons()
        self._dialog.show()

        # Create and install the filter
        self._wheel_filter = WheelEventFilter(self)
        self._dialog.installEventFilter(self._wheel_filter)

        if self._menu_config["show_volume_slider"]:
            self._update_app_volume_slider()
            self._update_app_mute_button()

    def _get_source_app_name(self, media_info):
        """Get formatted source app name from media info or session."""
        source_name = None

        # First try from media_info
        if media_info and "source_app" in media_info and media_info["source_app"]:
            source_app = media_info["source_app"]
            # Direct lookup using the imported function
            source_name = get_source_app_display_name(source_app)
            if source_name is None and DEBUG:
                # Log when app is found but not in our list
                logging.debug(f"Unknown source app in media_info: '{source_app}' - consider adding to source_apps.py")

        # If not found, try to get source name from session
        if source_name is None:
            try:
                if hasattr(self.media, "_current_session") and self.media._current_session:
                    source_app = self.media._current_session.source_app_user_model_id
                    if source_app:
                        # Direct lookup using the imported function
                        source_name = get_source_app_display_name(source_app)
                        if source_name is None and DEBUG:
                            # Log when session app is found but not in our list
                            logging.debug(
                                f"Unknown source app in session: '{source_app}' - consider adding to source_apps.py"
                            )
            except Exception as e:
                if DEBUG:
                    logging.debug(f"Error getting media source: {e}")

        # Return the source name and its CSS class name (or None, None if not found)
        if source_name:
            return source_name, get_source_app_class_name(source_name)
        else:
            return None, None

    def _update_popup_menu_buttons(self):
        try:
            is_playing = self._is_playing
            play_icon = self._menu_config_icons["pause" if is_playing else "play"]

            # Get control states directly from playback info, not from main UI buttons
            try:
                playback_info = self.media._playback_info
                is_prev_enabled = playback_info.controls.is_previous_enabled
                is_next_enabled = playback_info.controls.is_next_enabled
                is_play_enabled = playback_info.controls.is_play_pause_toggle_enabled
            except (AttributeError, Exception):
                # Default to enabled if there's an error getting control states
                is_prev_enabled = True
                is_next_enabled = True
                is_play_enabled = True

            # Update popup button states
            if self._popup_play_button:
                self._popup_play_button.setText(play_icon)
                self._popup_play_button.setProperty("class", f"btn play {'disabled' if not is_play_enabled else ''}")
                self._popup_play_button.setCursor(
                    Qt.CursorShape.PointingHandCursor if is_play_enabled else Qt.CursorShape.PointingHandCursor
                )
                self._popup_play_button.setStyleSheet("")

            if self._popup_prev_label:
                self._popup_prev_label.setProperty("class", f"btn prev {'disabled' if not is_prev_enabled else ''}")
                self._popup_prev_label.setCursor(
                    Qt.CursorShape.PointingHandCursor if is_prev_enabled else Qt.CursorShape.PointingHandCursor
                )
                self._popup_prev_label.setStyleSheet("")

            if self._popup_next_label:
                self._popup_next_label.setProperty("class", f"btn next {'disabled' if not is_next_enabled else ''}")
                self._popup_next_label.setCursor(
                    Qt.CursorShape.PointingHandCursor if is_next_enabled else Qt.CursorShape.PointingHandCursor
                )
                self._popup_next_label.setStyleSheet("")
        except Exception as e:
            logging.error(f"MediaWidget: Error initializing popup buttons: {e}")

    def _format_time(self, seconds):
        """Format seconds as HH:MM:SS or MM:SS depending on duration."""
        # Extract hours, minutes, and seconds
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        # Format differently based on whether there are hours or not
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:01d}:{seconds:02d}"

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label

        if self._show_alt_label:
            self._label.hide()
            self._label_alt.show()
        else:
            self._label.show()
            self._label_alt.hide()
        # Force an update on the media info when toggling the label
        self.media.force_update()

    def _toggle_play_pause(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        WindowsMedia().play_pause()

    def _on_timeline_properties_changed(self, timeline_props):
        """Handle timeline property updates."""
        if not timeline_props:
            return

        try:
            # Get position and duration in seconds
            position_sec = timeline_props.position.total_seconds()
            duration_sec = timeline_props.end_time.total_seconds()
            # Update individual time labels if they exist
            try:
                if hasattr(self, "_popup_current_time_label") and self._popup_current_time_label:
                    self._popup_current_time_label.setText(self._format_time(position_sec))

                if hasattr(self, "_popup_total_time_label") and self._popup_total_time_label:
                    self._popup_total_time_label.setText(self._format_time(duration_sec))
            except RuntimeError:
                # Labels were deleted when popup closed
                self._popup_current_time_label = None
                self._popup_total_time_label = None

            # Store the official position and current time for interpolation
            self._last_position = timeline_props.position.total_seconds()
            self._last_update_time = QtCore.QDateTime.currentMSecsSinceEpoch()
            self._duration = timeline_props.end_time.total_seconds()

        except Exception as e:
            logging.error(f"Error updating timeline: {e}")

    def _update_interpolated_position(self, timeline_data):
        try:
            # Skip updates if user is currently seeking or dialog isn't visible
            if not (hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible()):
                return
            if self._seeking:
                return
            position = timeline_data["position"]
            duration = timeline_data["duration"]

            # Update UI with estimated position
            if hasattr(self, "_popup_current_time_label") and self._popup_current_time_label:
                position_str = self._format_time(position)
                self._popup_current_time_label.setText(position_str)

            # Smoother slider updates - only update if the difference is significant
            if hasattr(self, "_progress_slider") and self._progress_slider and duration > 0:
                # Calculate percentage position
                new_percent = min(1000, int((position / duration) * 1000))
                current_percent = self._progress_slider.value()

                # Only update if position changed by at least 0.5%
                # This prevents tiny movements that make the slider appear jumpy
                if abs(new_percent - current_percent) >= 5:
                    self._progress_slider.setValue(new_percent)

        except RuntimeError:
            # The label or progress bar has been deleted (dialog closed)
            # Clear references to prevent future errors
            if hasattr(self, "_popup_current_time_label"):
                self._popup_current_time_label = None
            if hasattr(self, "_progress_slider"):
                self._progress_slider = None
        except Exception as e:
            logging.error(f"Error updating interpolated position: {e}")

    @QtCore.pyqtSlot(bool)
    def _on_session_status_changed(self, has_session: bool):
        active_label = self._label_alt if self._show_alt_label else self._label

        if has_session:
            # If media is not None, we show the frame
            self.show()

            # If we do not only have controls, make sure the label is shown
            if not self._controls_only:
                active_label.show()

        else:
            # Hide thumbnail and label fields
            self._thumbnail_label.hide()
            active_label.hide()
            active_label.setText("")
            if not self._controls_hide:
                if self._play_label is not None:
                    self._play_label.setText(self._media_button_icons["play"])
                    self._play_label.setProperty("class", "btn play disabled")
                    self._play_label.setStyleSheet("")

                if self._prev_label is not None:
                    self._prev_label.setProperty("class", "btn prev disabled")
                    self._prev_label.setStyleSheet("")

                if self._next_label is not None:
                    self._next_label.setProperty("class", "btn next disabled")
                    self._next_label.setStyleSheet("")

            # If we want to hide the widget when no music is playing, hide it!
            if self._hide_empty:
                self.hide()

    @QtCore.pyqtSlot(GlobalSystemMediaTransportControlsSessionPlaybackInfo)
    def _on_playback_info_changed(self, playback_info: GlobalSystemMediaTransportControlsSessionPlaybackInfo):
        # Set play-pause state icon
        is_playing = playback_info.playback_status == 4
        is_prev_enabled = playback_info.controls.is_previous_enabled
        is_play_enabled = playback_info.controls.is_play_pause_toggle_enabled
        is_next_enabled = playback_info.controls.is_next_enabled
        self._is_playing = is_playing

        if not self._controls_hide:
            play_icon = self._media_button_icons["pause" if is_playing else "play"]
            # Update main widget button
            self._play_label.setText(play_icon)

            self._prev_label.setProperty("class", f"btn prev {'disabled' if not is_prev_enabled else ''}")
            self._prev_label.setCursor(
                Qt.CursorShape.PointingHandCursor if is_prev_enabled else Qt.CursorShape.PointingHandCursor
            )

            self._play_label.setProperty("class", f"btn play {'disabled' if not is_play_enabled else ''}")
            self._play_label.setCursor(
                Qt.CursorShape.PointingHandCursor if is_play_enabled else Qt.CursorShape.PointingHandCursor
            )

            self._next_label.setProperty("class", f"btn next {'disabled' if not is_next_enabled else ''}")
            self._next_label.setCursor(
                Qt.CursorShape.PointingHandCursor if is_next_enabled else Qt.CursorShape.PointingHandCursor
            )

            self._prev_label.setStyleSheet("")
            self._play_label.setStyleSheet("")
            self._next_label.setStyleSheet("")

        # Update popup if it's currently open
        try:
            if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                play_icon_popup = self._menu_config_icons["pause" if is_playing else "play"]
                if self._popup_play_button is not None:
                    self._popup_play_button.setText(play_icon_popup)
                    self._popup_play_button.setProperty(
                        "class", f"btn play {'disabled' if not is_play_enabled else ''}"
                    )
                    self._popup_play_button.setCursor(
                        Qt.CursorShape.PointingHandCursor if is_play_enabled else Qt.CursorShape.PointingHandCursor
                    )
                    self._popup_play_button.setStyleSheet("")

                if self._popup_prev_label is not None:
                    self._popup_prev_label.setProperty("class", f"btn prev {'disabled' if not is_prev_enabled else ''}")
                    self._popup_prev_label.setCursor(
                        Qt.CursorShape.PointingHandCursor if is_prev_enabled else Qt.CursorShape.PointingHandCursor
                    )
                    self._popup_prev_label.setStyleSheet("")

                if self._popup_next_label is not None:
                    self._popup_next_label.setProperty("class", f"btn next {'disabled' if not is_next_enabled else ''}")
                    self._popup_next_label.setCursor(
                        Qt.CursorShape.PointingHandCursor if is_next_enabled else Qt.CursorShape.PointingHandCursor
                    )
                    self._popup_next_label.setStyleSheet("")
        except RuntimeError:
            self._popup_play_button = None
            self._popup_prev_label = None
            self._popup_next_label = None
        except Exception as e:
            logging.error(f"MediaWidget: Error updating popup button: {e}")
            self._popup_play_button = None
            self._popup_prev_label = None
            self._popup_next_label = None

    @QtCore.pyqtSlot(object)  # None or dict
    def _on_media_properties_changed(self, media_info: Optional[dict[str, Any]]):
        try:
            if (
                hasattr(self, "_dialog")
                and self._dialog is not None
                and self._dialog.isVisible()
                and media_info is not None
            ):
                try:
                    if (
                        hasattr(self, "_popup_title_label")
                        and hasattr(self, "_popup_artist_label")
                        and hasattr(self, "_popup_thumbnail_label")
                    ):
                        self._popup_title_label.setText(self._format_max_field_size(media_info["title"], "popup_title"))
                        self._popup_artist_label.setText(
                            self._format_max_field_size(media_info["artist"], "popup_artist")
                        )

                        if media_info["thumbnail"] is not None:
                            popup_pixmap = self._create_thumbnail_for_popup(media_info["thumbnail"])
                        else:
                            popup_pixmap = self._create_empty_thumbnail()
                        self._popup_thumbnail_label.setPixmap(popup_pixmap)

                    if hasattr(self, "_popup_source_label"):
                        source_name, source_class_name = self._get_source_app_name(media_info)
                        if source_name is not None:
                            self._popup_source_label.setText(source_name)
                            self._popup_source_label.setProperty("class", f"source {source_class_name}")
                            self._popup_source_label.style().unpolish(self._popup_source_label)
                            self._popup_source_label.style().polish(self._popup_source_label)

                except Exception as e:
                    logging.error(f"Error updating popup content: {e}")
        except RuntimeError:
            pass
        except Exception as e:
            logging.error(f"MediaWidget: Error updating popup content: {e}")

        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        # If we only have controls, stop update here
        if self._controls_only:
            return

        if self._max_field_size["truncate_whole_label"]:
            try:
                formatted_info = {
                    k: self._format_max_field_size(v, f"field_{k}") if isinstance(v, str) else v
                    for k, v in media_info.items()
                }
                format_label_content = active_label_content.format(**formatted_info)
                format_label_content = self._format_max_field_size(format_label_content)
            except Exception as e:
                logging.error(f"MediaWidget: Error formatting label: {e}")
                # Try to at least show the title if available
                if media_info and "title" in media_info and media_info["title"]:
                    format_label_content = self._format_max_field_size(media_info["title"])
                else:
                    format_label_content = "No media"
        else:
            format_label_content = active_label_content.format(
                **{k: self._format_max_field_size(v) if isinstance(v, str) else v for k, v in media_info.items()}
            )
        # Format the label
        active_label.setText(format_label_content)

        # If we don't want the thumbnail, stop here
        if not self._show_thumbnail:
            return

        # If no media in session, hide thumbnail and stop here
        if media_info["thumbnail"] is None:
            self._thumbnail_label.hide()
            return
        # Only update the thumbnail if the title/artist changes or if we did a toggle (resize)
        try:
            if media_info["thumbnail"] is not None and media_info["title"]:
                thumbnail = self._crop_thumbnail(media_info["thumbnail"], active_label.sizeHint().width())
                pixmap = QPixmap.fromImage(ImageQt(thumbnail))
                self._thumbnail_label.setPixmap(pixmap)

        except Exception as e:
            logging.error(f"MediaWidget: Error setting thumbnail: {e}")
            self._thumbnail_label.hide()
        else:
            self._thumbnail_label.show()

    def _create_empty_thumbnail(self):
        """Create a default thumbnail with an eighth note icon."""
        try:
            size = self._menu_config["thumbnail_size"]
            corner_radius = self._menu_config["thumbnail_corner_radius"]
            # Create base image with dark background
            large_size = size * 2  # Create at higher resolution for better quality
            large_img = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 255))
            draw = ImageDraw(large_img)

            # Use white color for the note
            note_color = (255, 255, 255, 255)

            # Scale all elements relative to image size
            center_x = large_size // 2
            center_y = large_size // 2

            # Calculate note head dimensions - make it large like in the image
            head_radius = int(large_size * 0.14)  # Note head is about 44% of width

            # Calculate position of the note head (centered horizontally, lower half vertically)
            head_x = center_x - int(large_size * 0.1)  # Slightly left of center
            head_y = center_y + int(large_size * 0.12)  # Lower half

            # Calculate stem dimensions
            stem_width = int(large_size * 0.05)
            stem_height = int(large_size * 0.4)

            # Calculate flag dimensions
            flag_width = int(large_size * 0.15)
            flag_height = int(large_size * 0.3)

            # Draw the note stem (vertical line)
            stem_x = head_x + head_radius - stem_width  # Stem attaches to right side of note head
            stem_top_y = head_y - stem_height
            draw.rectangle(
                [
                    (stem_x, stem_top_y),  # Top-left
                    (stem_x + stem_width, head_y),  # Bottom-right
                ],
                fill=note_color,
            )

            # Draw the note head (circle)
            draw.ellipse(
                [(head_x - head_radius, head_y - head_radius), (head_x + head_radius, head_y + head_radius)],
                fill=note_color,
            )

            draw.rectangle(
                [
                    (stem_x + stem_width - 1, stem_top_y),
                    (stem_x + stem_width + flag_width, stem_top_y + flag_height // 3),
                ],
                fill=note_color,
            )

            # Resize down to target size with high quality anti-aliasing
            img = large_img.resize((size, size), Image.LANCZOS)

            # Add rounded corners
            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw(mask)
            mask_draw.rounded_rectangle([(0, 0), (size, size)], corner_radius, fill=150)

            # Apply mask for rounded corners
            img.putalpha(mask)

            return QPixmap.fromImage(ImageQt(img))

        except Exception as e:
            logging.error(f"Error creating default thumbnail: {e}")
            return None

    def _create_thumbnail_for_popup(self, img):
        """Process image thumbnail into a square with rounded corners for popup display."""
        try:
            square_size = self._menu_config["thumbnail_size"]
            # Increase corner radius for more visible rounded corners (25% instead of 15%)
            corner_radius = self._menu_config["thumbnail_corner_radius"]

            # Calculate aspect ratio
            aspect = img.width / img.height

            # First resize maintaining aspect ratio to cover the square
            if aspect > 1:  # Wider than tall
                new_height = square_size
                new_width = int(square_size * aspect)
            else:  # Taller than wide
                new_width = square_size
                new_height = int(square_size / aspect)

            # Resize with high-quality resampling
            resized = img.resize((new_width, new_height), Image.LANCZOS)

            # Crop to square
            if resized.width >= square_size and resized.height >= square_size:
                left = (resized.width - square_size) // 2
                top = (resized.height - square_size) // 2
                square_img = resized.crop((left, top, left + square_size, top + square_size))
            else:
                square_img = resized.resize((square_size, square_size), Image.LANCZOS)

            # Ensure image is RGBA
            if square_img.mode != "RGBA":
                square_img = square_img.convert("RGBA")

            # Create much higher-resolution mask for better anti-aliasing (12x size)
            scale = 4  # Significantly increased for smoother corners
            hr_size = square_size * scale
            hr_radius = corner_radius * scale

            # Create the mask
            mask = Image.new("L", (hr_size, hr_size), color=0)
            draw = ImageDraw(mask)

            # Draw rounded rectangle with smoother corners
            draw.rounded_rectangle([(0, 0), (hr_size, hr_size)], radius=hr_radius, fill=255)

            # Resize mask back down with high-quality anti-aliasing
            mask = mask.resize((square_size, square_size), Image.LANCZOS)

            # Apply the mask to create rounded corners
            square_img.putalpha(mask)

            # Convert to QPixmap
            return QPixmap.fromImage(ImageQt(square_img))
        except Exception as e:
            logging.error(f"Error creating square thumbnail: {e}")
            return None

    def _crop_thumbnail(self, thumbnail: Image.Image, active_label_width: int) -> Image.Image:
        """Process an image thumbnail for proper display."""
        # Calculate dimensions while respecting container padding
        available_width = active_label_width

        if not self._scrolling_label["enabled"]:
            available_width = available_width + self._thumbnail_padding
        # Preserve aspect ratio during resize
        aspect_ratio = thumbnail.width / thumbnail.height
        new_height = int(available_width / aspect_ratio)

        # Resize with high-quality resampling
        thumbnail = thumbnail.resize((available_width, new_height), Image.LANCZOS)

        # Crop vertically to fit widget height
        available_height = max(1, int(self._widget_container.contentsRect().height()))
        if thumbnail.height > available_height:
            y1 = (thumbnail.height - available_height) // 2
            thumbnail = thumbnail.crop((0, y1, thumbnail.width, y1 + available_height))

        # Apply base transparency
        if thumbnail.mode != "RGBA":
            thumbnail = thumbnail.convert("RGBA")

        # Create base alpha channel filled with the thumbnail alpha value
        base_alpha = Image.new("L", thumbnail.size, color=self._thumbnail_alpha)

        # Apply effects based on priorities
        if self._thumbnail_edge_fade:
            # If edge fade is enabled, use it without corner radius
            base_alpha = self._apply_edge_fade(base_alpha)
        elif self._thumbnail_corner_radius > 0:
            # Only apply corner radius if edge fade is disabled
            base_alpha = self._create_corner_mask(thumbnail.size, base_alpha)

        # Apply final alpha channel
        thumbnail.putalpha(base_alpha)
        return thumbnail

    def _create_corner_mask(self, image_size: tuple, base_mask: Image) -> Image:
        """Create a rounded corner mask compatible with the base alpha mask."""
        # Determine which corners to round
        corners = (False, True, True, False) if self._controls_left else (True, False, False, True)
        if self._symmetric_corner_radius:
            corners = (True, True, True, True)

        # Use a higher resolution for better antialiasing
        scale_factor = 2
        hr_size = (image_size[0] * scale_factor, image_size[1] * scale_factor)
        hr_radius = self._thumbnail_corner_radius * scale_factor

        # Create the high-resolution mask
        corner_mask = Image.new("L", hr_size, color=0)
        painter = ImageDraw(corner_mask)

        try:
            # Draw rounded rectangle
            painter.rounded_rectangle(
                [0, 0, hr_size[0] - 1, hr_size[1] - 1], hr_radius, self._thumbnail_alpha, None, 0, corners=corners
            )
        except Exception as e:
            logging.error(f"Error creating corner mask, return default thumb: {e}")
            return base_mask

        # Scale back down with antialiasing
        corner_mask = corner_mask.resize(image_size, Image.LANCZOS)

        return corner_mask

    def _apply_edge_fade(self, alpha_mask: Image) -> Image:
        """Apply edge fade effect to an alpha mask."""

        width, height = alpha_mask.size
        fade_width = int(width * 0.3)
        fade_mask = Image.new("L", (width, height), color=255)

        # Create gradient arrays for better performance
        left_gradient = [int(255 * (x / fade_width)) for x in range(fade_width)]
        right_gradient = [int(255 * ((width - x) / fade_width)) for x in range(width - fade_width, width)]

        # Apply gradients
        for x, alpha in enumerate(left_gradient):
            line = Image.new("L", (1, height), color=alpha)
            fade_mask.paste(line, (x, 0))

        for i, x in enumerate(range(width - fade_width, width)):
            line = Image.new("L", (1, height), color=right_gradient[i])
            fade_mask.paste(line, (x, 0))

        # Use ImageChops.darker instead of multiply to preserve corner transparency
        return ImageChops.darker(alpha_mask, fade_mask)

    def _format_max_field_size(self, text: str, field_type="default"):
        if field_type == "popup_title":
            max_size = self._menu_config["max_title_size"]
        elif field_type == "popup_artist":
            max_size = self._menu_config["max_artist_size"]
        else:
            # If we are using scrolling labels, return the original text without formatting
            if self._scrolling_label["enabled"]:
                return text
            max_size = self._max_field_size["label_alt" if self._show_alt_label else "label"]

        if len(text) > max_size:
            return text[: max_size - 3] + "..."
        else:
            return text

    def _create_media_button(self, icon, action):
        if not self._controls_hide:
            label = ClickableLabel(self)
            label.setProperty("class", "btn disabled")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setText(icon)
            label.data = action
            self._widget_container_layout.addWidget(label)
            return label

    def _create_media_buttons(self):
        return (
            self._create_media_button(self._media_button_icons["prev_track"], WindowsMedia().prev),
            self._create_media_button(self._media_button_icons["play"], WindowsMedia().play_pause),
            self._create_media_button(self._media_button_icons["next_track"], WindowsMedia().next),
        )

    def execute_code(self, func):
        try:
            func()
        except Exception as e:
            logging.error(f"Error executing code: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.media.switch_session(+1)  # Next
        elif event.angleDelta().y() < 0:
            self.media.switch_session(-1)  # Prev

    def _on_slider_pressed(self):
        # User started dragging, stop automatic updates
        self._seeking = True

    def _on_slider_released(self):
        # User finished dragging, perform seek operation
        value = self._progress_slider.value()
        if hasattr(self, "_duration") and self._duration > 0:
            # Convert percentage to seconds
            position = (value / 1000.0) * self._duration
            try:
                # Seek to the position
                self.media.seek_to_position(position)
            except Exception as e:
                logging.error(f"Error seeking to position: {e}")
        # Resume automatic updates
        self._seeking = False

    def _on_slider_value_changed(self, value):
        # Only process value changes from user interaction
        if not self._seeking:
            return

        # Update time labels to reflect potential new position
        if hasattr(self, "_duration") and self._duration > 0:
            position = (value / 1000.0) * self._duration
            position_str = self._format_time(position)
            duration_str = self._format_time(self._duration)

            # Update both time labels
            self._popup_current_time_label.setText(position_str)
            self._popup_total_time_label.setText(duration_str)

    def _get_current_app_identifier(self) -> tuple[Optional[str], Optional[str]]:
        """Get the AUMID of the current media app."""
        aumid = None

        # Try to get AUMID from current session
        try:
            if hasattr(self.media, "_current_session") and self.media._current_session:
                aumid = self.media._current_session.source_app_user_model_id
        except Exception:
            pass

        # Try to get AUMID from media info
        try:
            media_info = getattr(self.media, "_media_info", None)
            if media_info and media_info.get("source_app"):
                aumid = media_info.get("source_app") or aumid
        except Exception:
            pass

        return aumid

    def _get_process_aumid(self, pid: int) -> Optional[str]:
        """Get AUMID for a process using GetApplicationUserModelId."""
        if GetApplicationUserModelId is None:
            return None

        try:
            hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not hProcess:
                return None

            try:
                length = ctypes.c_uint32(0)
                # First call to get buffer size
                if GetApplicationUserModelId(hProcess, ctypes.byref(length), None) == ERROR_INSUFFICIENT_BUFFER:
                    buf = ctypes.create_unicode_buffer(length.value)
                    if GetApplicationUserModelId(hProcess, ctypes.byref(length), buf) == 0:
                        return buf.value
            finally:
                CloseHandle(hProcess)
        except Exception:
            pass

        return None

    def _match_session_by_mapping(self, sessions, aumid: str):
        """Match session using source app mapping."""
        if not aumid:
            return None

        mapping = get_source_app_mapping(aumid)
        if not mapping:
            return None

        process_name = mapping.get("process")
        if process_name:
            for session in sessions:
                try:
                    proc = getattr(session, "Process", None)
                    if proc and proc.name().lower() == process_name.lower():
                        return session
                except Exception:
                    continue

        return None

    def _match_session_by_aumid(self, sessions, aumid: str):
        """Match session by process AUMID."""
        target_aumid = aumid.lower()
        for session in sessions:
            try:
                proc = getattr(session, "Process", None)
                if proc and proc.pid:
                    process_aumid = self._get_process_aumid(int(proc.pid))
                    if process_aumid and process_aumid.lower() == target_aumid:
                        return session
            except Exception:
                continue
        return None

    def _match_session_by_executable(self, sessions, identifier: str):
        """Match session by executable name."""
        if not identifier.endswith(".exe"):
            return None

        exe_name = identifier.lower()
        for session in sessions:
            try:
                proc = getattr(session, "Process", None)
                if proc and proc.name().lower() == exe_name:
                    return session
            except Exception:
                continue
        return None

    def _bind_app_volume_session(self):
        """Locate and bind the audio session corresponding to current media app."""
        self._app_volume_session = None
        aumid = self._get_current_app_identifier()
        identifier = (aumid or "").lower()

        try:
            comtypes.CoInitialize()
            sessions = AudioUtilities.GetAllSessions()
            candidate = None
            if aumid:
                candidate = self._match_session_by_mapping(sessions, aumid)

            if not candidate and aumid:
                candidate = self._match_session_by_aumid(sessions, aumid)

            if not candidate and identifier:
                candidate = self._match_session_by_executable(sessions, identifier)

            if not candidate and aumid:
                proc_name = get_process_name_for_aumid(aumid)
                if proc_name:
                    candidate = self._match_session_by_executable(sessions, proc_name)

            self._app_volume_session = candidate

        except Exception as e:
            logging.error(f"MediaWidget: Failed to bind app volume session: {e}")
            self._app_volume_session = None
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    def _get_volume_interface(self):
        """Get the SimpleAudioVolume interface for the current session."""
        if not self._app_volume_session:
            return None
        return getattr(self._app_volume_session, "SimpleAudioVolume", None)

    def _update_app_volume_slider(self):
        """Update slider value from bound app session volume."""
        if not self._app_volume_slider:
            return

        volume_interface = self._get_volume_interface()
        if not volume_interface:
            self._vol_container.hide()
            self._app_volume_slider.setEnabled(False)
            return

        try:
            raw_level = volume_interface.GetMasterVolume()
            level = int(round(float(raw_level) * 100))

            self._app_volume_slider.blockSignals(True)
            self._app_volume_slider.setValue(level)
            self._app_volume_slider.blockSignals(False)
            self._app_volume_slider.setEnabled(True)

        except Exception as e:
            logging.error(f"MediaWidget: Failed to read app volume: {e}")
            self._app_volume_slider.setEnabled(False)

    def _on_app_volume_slider_changed(self, value: int):
        """Set app session volume from slider."""
        volume_interface = self._get_volume_interface()
        if not volume_interface:
            return

        try:
            volume_interface.SetMasterVolume(float(value) / 100.0, None)

            # Unmute if volume is raised above 0
            if value > 0 and self._app_is_muted:
                self._app_is_muted = False
                self._update_app_mute_button()

        except Exception as e:
            logging.error(f"MediaWidget: Failed to set app volume: {e}")

    def _toggle_app_mute(self):
        """Toggle mute state for the current app."""
        volume_interface = self._get_volume_interface()
        if not volume_interface:
            return

        try:
            # Get current mute state (default to False if failed)
            current_mute = False
            try:
                current_mute = bool(volume_interface.GetMute())
            except Exception:
                pass

            # Toggle mute state
            new_mute = not current_mute
            volume_interface.SetMute(new_mute, None)
            self._app_is_muted = new_mute

            self._update_app_mute_button()

        except Exception as e:
            logging.error(f"MediaWidget: Failed to toggle app mute: {e}")

    def _update_app_mute_button(self):
        """Update the mute button icon based on current mute state."""
        if not self._app_mute_button:
            return

        volume_interface = self._get_volume_interface()
        if not volume_interface:
            self._app_mute_button.setEnabled(False)
            return

        try:
            is_muted = volume_interface.GetMute()
            self._app_is_muted = is_muted

            icon_key = "unmute" if is_muted else "mute"
            self._app_mute_button.setText(self._menu_config_icons[icon_key])
            self._app_mute_button.setProperty("class", f"{icon_key}-button")
            self._app_mute_button.setEnabled(True)
            self._app_mute_button.style().unpolish(self._app_mute_button)
            self._app_mute_button.style().polish(self._app_mute_button)

        except Exception as e:
            logging.error(f"MediaWidget: Failed to update mute button: {e}")
            self._app_mute_button.setEnabled(False)


class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.data:
            if self.parent_widget._animation["enabled"]:
                AnimationManager.animate(
                    self, self.parent_widget._animation["type"], self.parent_widget._animation["duration"]
                )
            self.parent_widget.execute_code(self.data)


class WheelEventFilter(QtCore.QObject):
    """
    Install event filter to capture wheel events in the popup to handle wheel events for media session switching.
    This class is used to capture wheel events and switch media sessions accordingly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_widget = parent

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Wheel:
            if not self.media_widget._dialog.geometry().contains(event.globalPosition().toPoint()):
                return False

            if hasattr(self.media_widget, "_app_volume_slider") and self.media_widget._app_volume_slider:
                slider_global_rect = QtCore.QRect(
                    self.media_widget._app_volume_slider.mapToGlobal(QtCore.QPoint(0, 0)),
                    self.media_widget._app_volume_slider.size(),
                )
                if slider_global_rect.contains(event.globalPosition().toPoint()):
                    return False

            old_session = getattr(self.media_widget.media, "_current_session", None)
            if event.angleDelta().y() > 0:
                self.media_widget.media.switch_session(+1)
            elif event.angleDelta().y() < 0:
                self.media_widget.media.switch_session(-1)
            new_session = getattr(self.media_widget.media, "_current_session", None)
            if new_session != old_session:
                self.media_widget._dialog.hide()
                self.media_widget.show_menu()
            return True
        return False

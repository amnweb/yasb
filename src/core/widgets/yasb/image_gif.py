import os
import re

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QImageReader, QMovie
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.utils.utilities import add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.image_gif import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ImageGifWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    _instances: list["ImageGifWidget"] = []
    _shared_timer: QTimer | None = None

    def __init__(
        self,
        label: str,
        label_alt: str,
        file_path: str,
        width: int,
        height: int,
        speed: int,
        keep_aspect_ratio: bool,
        animation: dict[str, str],
        update_interval: int = 0,
        callbacks: dict = None,
        container_padding: dict = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
        **kwargs,
    ):
        super().__init__(class_name="image-gif-widget", **kwargs)
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._update_interval = update_interval
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._speed = speed
        self._keep_aspect_ratio = keep_aspect_ratio
        self._animation = animation
        self._file_path = file_path
        self._width = width
        self._height = height

        self._movie_label = QLabel()
        self._movie_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._movie = QMovie()

        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        # Add the container to the main widget layout
        self._widget_container_layout.addWidget(self._movie_label)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, None)

        self._setup()

        # Callbacks
        self.callback_left = callbacks.get("on_left", "do_nothing")
        self.callback_right = callbacks.get("on_right", "do_nothing")
        self.callback_middle = callbacks.get("on_middle", "do_nothing")

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("pause_gif", self._pause_gif)

        if self not in ImageGifWidget._instances:
            ImageGifWidget._instances.append(self)

        if update_interval > 0 and ImageGifWidget._shared_timer is None:
            ImageGifWidget._shared_timer = QTimer(self)
            ImageGifWidget._shared_timer.setInterval(update_interval)
            ImageGifWidget._shared_timer.timeout.connect(self._update_label)
            ImageGifWidget._shared_timer.start()

        self._update_label()

    def _setup(self):
        """Image/Gif setup"""
        file_path = self._file_path

        if not file_path or not os.path.exists(file_path):
            self._show_error_placeholder()
            return

        try:
            if self._movie:
                self._movie.stop()
                self._movie.deleteLater()

            self._movie = QMovie(file_path)

            if self._width or self._height:
                self._movie.setScaledSize(self._get_scaled_size())

            self._movie.setSpeed(self._speed)

            self._movie_label.setMovie(self._movie)
            self._movie.start()

        except Exception as e:
            print(f"Error when loading file : {file_path}: {e}")
            self._show_error_placeholder()

    def _show_error_placeholder(self):
        """Display error when file could not be loaded."""
        self._movie_label.setText("Error loading file")

    def _toggle_label(self):
        AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _pause_gif(self):
        if self._movie:
            if self._movie.state() == QMovie.MovieState.Paused:
                self._movie.setPaused(False)
            else:
                self._movie.setPaused(True)

    def _get_scaled_size(self):
        """Get correct size for displaying image/gif."""
        if not self._movie:
            return QSize(self._width, self._height)

        reader = QImageReader(self._file_path)
        size = reader.size()

        target_width = self._width
        target_height = self._height

        if self._keep_aspect_ratio:
            return size.scaled(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            return size.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio)

    def _update_label(self):
        """Update label using current playback speed and file path."""
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        label_options = {
            "{speed}": self._speed,
            "{file_path}": self._file_path,
            "{file_name}": os.path.basename(self._file_path),
        }

        for part in label_parts:
            part = part.strip()
            for fmt_str, value in label_options.items():
                part = part.replace(fmt_str, str(value))

            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1

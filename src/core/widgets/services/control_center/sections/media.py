import io
import logging
import os
from collections.abc import Callable
from typing import Any

from PIL import Image
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QMouseEvent, QPainter, QPainterPath, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.utils.qobject import is_valid_qobject
from core.utils.utilities import ElidedLabel, refresh_widget_style
from core.widgets.services.media.media import SessionState, WindowsMedia
from settings import SCRIPT_PATH

logger = logging.getLogger("media_section")


class _MediaButton(QLabel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data: Callable[[], Any] | None = None

    def mouseReleaseEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton and self.data is not None:
            try:
                self.data()
            except Exception as e:
                logger.error("Error executing media control: %s", e)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)


class MediaSectionWidget(QFrame):
    """Section containing media playback controls and track information."""

    def __init__(self, parent: QWidget, config: object):
        super().__init__(parent)
        self.config = config
        self.setProperty("class", "section media")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.hide()

        self._media = WindowsMedia()

        self._current_app_id: str = ""
        self._current_title: str = ""
        self._current_artist: str = ""
        self._current_is_playing: bool | None = None

        self._cached_thumb: tuple[int, QPixmap] | None = None
        self._empty_thumb: QPixmap | None = self._build_empty_thumbnail()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content = QFrame(self)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._thumbnail_label = QLabel(content)
        self._thumbnail_label.setProperty("class", "thumbnail")
        self._thumbnail_label.setFixedSize(config.thumbnail_size, config.thumbnail_size)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        track_info = QFrame(content)
        track_info.setProperty("class", "track-info")
        track_info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        track_layout = QVBoxLayout(track_info)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)

        self._title_label = ElidedLabel("", track_info)
        self._title_label.setProperty("class", "title")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._artist_label = ElidedLabel("", track_info)
        self._artist_label.setProperty("class", "subtext")
        self._artist_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        track_layout.addWidget(self._title_label)
        track_layout.addWidget(self._artist_label)
        track_layout.addStretch(1)

        controls_frame = QFrame(content)
        controls_frame.setProperty("class", "controls")
        controls_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        self._prev_btn = _MediaButton(controls_frame)
        self._prev_btn.setProperty("class", "button prev")
        self._prev_btn.setText(config.icons.prev_track)
        self._prev_btn.data = self._media.prev

        self._play_btn = _MediaButton(controls_frame)
        self._play_btn.setProperty("class", "button play")
        self._play_btn.data = self._media.play_pause

        self._next_btn = _MediaButton(controls_frame)
        self._next_btn.setProperty("class", "button next")
        self._next_btn.setText(config.icons.next_track)
        self._next_btn.data = self._media.next

        controls_layout.addWidget(self._prev_btn)
        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._next_btn)

        content_layout.addWidget(self._thumbnail_label)
        content_layout.addWidget(track_info, 1)
        content_layout.addWidget(controls_frame)

        layout.addWidget(content)

        self._media.current_session_changed.connect(self._on_current_session_changed)
        self._media.media_properties_changed.connect(self._on_media_properties_changed)
        self._media.playback_info_changed.connect(self._on_playback_info_changed)
        self.destroyed.connect(self._disconnect_media_signals)

    def _disconnect_media_signals(self):
        try:
            self._media.current_session_changed.disconnect(self._on_current_session_changed)
            self._media.media_properties_changed.disconnect(self._on_media_properties_changed)
            self._media.playback_info_changed.disconnect(self._on_playback_info_changed)
        except Exception:
            pass

    @pyqtSlot()
    def _on_current_session_changed(self):
        self._sync_ui(force_thumbnail=True)

    @pyqtSlot()
    def _on_media_properties_changed(self):
        self._sync_ui(force_thumbnail=True)

    @pyqtSlot()
    def _on_playback_info_changed(self):
        self._update_controls()

    def refresh_state(self) -> None:
        self._sync_ui(force_thumbnail=True)

    def _sync_ui(self, force_thumbnail: bool = False):
        if not is_valid_qobject(self):
            return
        session = self._media.current_session
        if session is None:
            if self._current_app_id:
                self._current_app_id = ""
                self._current_title = ""
                self._current_artist = ""
                self._current_is_playing = None
                self.hide()
            return

        if not self._current_app_id:
            self.show()

        app_id = session.app_id
        session_changed = app_id != self._current_app_id
        self._current_app_id = app_id

        title = session.title or "Unknown Title"
        artist = session.artist or "Unknown Artist"
        if title != self._current_title:
            self._current_title = title
            self._title_label.setText(title)
        if artist != self._current_artist:
            self._current_artist = artist
            self._artist_label.setText(artist)

        if session_changed or force_thumbnail:
            self._apply_thumbnail(session.thumbnail)

        self._update_controls_from(session)

    def _apply_thumbnail(self, image: Image.Image | None):
        if not is_valid_qobject(self._thumbnail_label):
            return

        if image is None:
            if self._empty_thumb is not None:
                self._thumbnail_label.setPixmap(self._empty_thumb)
            else:
                self._thumbnail_label.clear()
            self._cached_thumb = None
            return

        img_id = id(image)
        if self._cached_thumb is not None and self._cached_thumb[0] == img_id:
            return

        try:
            pixmap = self._render_thumbnail(image)
            self._cached_thumb = (img_id, pixmap)
            self._thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            logger.error("Error creating media thumbnail: %s", e)
            self._cached_thumb = None
            self._thumbnail_label.clear()

    def _render_thumbnail(self, image: Image.Image) -> QPixmap:
        size = self.config.thumbnail_size
        radius = self.config.thumbnail_radius

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        w, h = image.size
        if w > h:
            left = (w - h) // 2
            image = image.crop((left, 0, left + h, h))
        elif h > w:
            top = (h - w) // 2
            image = image.crop((0, top, w, top + w))

        resized = image.resize((size, size), Image.LANCZOS)

        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        source = QPixmap()
        if not source.loadFromData(buf.getvalue()):
            return QPixmap(size, size)

        if radius <= 0:
            return source
        return self._apply_rounded_corners(source, size, radius)

    def _build_empty_thumbnail(self) -> QPixmap | None:
        try:
            icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
            if not os.path.exists(icon_path):
                return None
            size = self.config.thumbnail_size
            radius = self.config.thumbnail_radius

            with Image.open(icon_path) as image:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                resized = image.resize((size, size), Image.LANCZOS)
                buf = io.BytesIO()
                resized.save(buf, format="PNG")
                source = QPixmap()
                if not source.loadFromData(buf.getvalue()):
                    return QPixmap(size, size)

            if radius <= 0:
                return source
            return self._apply_rounded_corners(source, size, radius)
        except Exception as e:
            logger.error("Error creating default media thumbnail: %s", e)
            return None

    def _apply_rounded_corners(self, source: QPixmap, size: int, radius: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, source)
        painter.end()
        return pixmap

    def _update_controls(self):
        session = self._media.current_session
        if session is not None:
            self._update_controls_from(session)

    def _update_controls_from(self, session: SessionState):
        if not is_valid_qobject(self._play_btn):
            return

        is_playing = session.is_playing
        if is_playing != self._current_is_playing:
            self._current_is_playing = is_playing
            self._play_btn.setText(self.config.icons.pause if is_playing else self.config.icons.play)

        if session.playback_ready:
            self._prev_btn.setEnabled(session.controls_prev_enabled)
            self._play_btn.setEnabled(session.controls_play_enabled)
            self._next_btn.setEnabled(session.controls_next_enabled)
        else:
            self._prev_btn.setEnabled(True)
            self._play_btn.setEnabled(True)
            self._next_btn.setEnabled(True)

        for btn in (self._prev_btn, self._play_btn, self._next_btn):
            old_class = btn.property("class") or ""
            classes = [c for c in old_class.split() if c != "disabled"]
            if not btn.isEnabled():
                classes.append("disabled")
            new_class = " ".join(classes)
            if new_class != old_class:
                btn.setProperty("class", new_class)
                refresh_widget_style(btn)

    def wheelEvent(self, event: QWheelEvent | None):
        if event is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self._media.switch_current_session(1 if delta > 0 else -1)
        event.accept()

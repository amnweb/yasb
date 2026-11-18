"""Compact native media popup with independently controlled Windows sessions."""

import asyncio
import math
from functools import partial
from typing import override

from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QEvent, QObject, QPoint, QSignalBlocker, Qt, QTimer
from PyQt6.QtGui import QHideEvent, QMouseEvent, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.utils.stat_popup import PinnablePopup
from core.utils.tooltip import set_tooltip
from core.validation.widgets.yasb.audio_visualizer import AudioVisualizerConfig
from core.validation.widgets.yasb.media import MediaWidgetConfig
from core.widgets.services.media.media import SessionState, WindowsMedia
from core.widgets.services.media.source_apps import resolve_source_app_name
from core.widgets.services.media.volume import AppVolumeController
from core.widgets.yasb.audio_visualizer import AudioVisualizerWidget

MAX_TIMELINE_DURATION = 604800


def time_text(seconds: float) -> str:
    seconds = max(0, int(seconds)) if math.isfinite(seconds) else 0
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours}:{minutes:02}:{seconds % 60:02}" if hours else f"{minutes}:{seconds % 60:02}"


def label(text: str, css_class: str) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setProperty("class", css_class)
    return widget


class MediaSessionCard(QFrame):
    def __init__(self, popup: MediaSessionsPopup, session_id: str, state: SessionState):
        super().__init__(popup)
        self.popup = popup
        self.session_id = session_id
        self.state = state
        self._thumbnail_identity: object = object()
        self._seeking = False
        self.setProperty("class", "media-session-card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        menu = popup.config.media_menu
        self.thumbnail = label("♫", "thumbnail")
        self.thumbnail.setFixedSize(menu.thumbnail_size, menu.thumbnail_size)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumbnail, 0, Qt.AlignmentFlag.AlignTop)

        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(2)
        heading = QHBoxLayout()
        self.title = label("", "title")
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        heading.addWidget(self.title, 1)
        self.visualizer: AudioVisualizerWidget | None = None
        if menu.show_visualizer:
            self.visualizer = AudioVisualizerWidget(
                AudioVisualizerConfig.model_validate(
                    {
                        "class_name": "media-visualizer",
                        "style": "bars",
                        "height": 20,
                        "mirror": True,
                        "channels": "stereo",
                        "smoothness": 80,
                        "framerate": 30,
                        "freq_min": 500,
                        "bars": {"count": 8, "width": 1, "gap": 4},
                    }
                )
            )
            set_tooltip(self.visualizer, "System audio")
            heading.addWidget(self.visualizer)
        details.addLayout(heading)
        self.artist = label("", "artist")
        self.artist.setMinimumWidth(0)
        self.artist.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        details.addWidget(self.artist)
        if menu.show_source:
            source = label((resolve_source_app_name(state.app_id) or state.app_id)[: menu.max_source_size], "source")
            details.addWidget(source)
        details.addSpacing(6)

        self.timeline = QFrame()
        self.timeline.setProperty("class", "media-timeline-container")
        timeline_layout = QVBoxLayout(self.timeline)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)
        times = QHBoxLayout()
        self.elapsed = label("0:00", "playback-time current")
        self.remaining = label("0:00", "playback-time total")
        times.addWidget(self.elapsed)
        times.addStretch()
        times.addWidget(self.remaining)
        timeline_layout.addLayout(times)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setProperty("class", "progress-slider")
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(self._begin_seek)
        self.progress.sliderReleased.connect(self._finish_seek)
        timeline_layout.addWidget(self.progress)
        details.addWidget(self.timeline)

        controls = QHBoxLayout()
        controls.setSpacing(4)
        icons = popup.config.media_menu_icons
        self.previous = self._button(icons.prev_track, "btn prev", "Previous track")
        self.play = self._button(icons.play, "btn play", "Play/pause")
        self.next_track = self._button(icons.next_track, "btn next", "Next track")
        for button, action in ((self.previous, "prev"), (self.play, "play_pause"), (self.next_track, "next")):
            button.clicked.connect(partial(self._command, action))
            controls.addWidget(button)
        controls.addStretch()
        self.mute = self._button(icons.unmute, "mute-button", "Mute application")
        self.mute.clicked.connect(self._toggle_mute)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setProperty("class", "volume-slider")
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(80)
        self.volume.valueChanged.connect(self._set_volume)
        set_tooltip(self.volume, "Application volume (shared by its media sessions)")
        self.volume_value = label("—", "volume-value")
        self.volume_value.setFixedWidth(34)
        for widget in (self.mute, self.volume, self.volume_value):
            widget.setVisible(menu.show_volume_slider)
            controls.addWidget(widget)
        details.addLayout(controls)
        layout.addLayout(details, 1)
        self.update_state(state)

    def _button(self, text: str, css_class: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("class", css_class)
        set_tooltip(button, tooltip)
        return button

    def close_overlays(self) -> None:
        pass

    def handle_pointer_press(self, global_position: QPoint) -> None:
        pass

    def dispose(self) -> None:
        self.close_overlays()

    def _command(self, action: str) -> None:
        self.popup.command(self.session_id, action)

    def _begin_seek(self) -> None:
        self._seeking = True

    def _finish_seek(self) -> None:
        self._seeking = False
        self.popup.command(self.session_id, "seek", self.progress.value() * self.state.duration / 1000)

    def _set_volume(self, level: int) -> None:
        self.popup.volumes.set_volume(self.state.app_id, level)
        self.popup.update_volumes()

    def _toggle_mute(self) -> None:
        self.popup.volumes.toggle_mute(self.state.app_id)
        self.popup.update_volumes()

    def update_volume(self) -> None:
        snapshot = self.popup.volumes.snapshot(self.state.app_id)
        enabled = snapshot is not None
        self.volume.setEnabled(enabled)
        self.mute.setEnabled(enabled)
        self.volume_value.setText(f"{snapshot[0]}%" if snapshot else "—")
        if snapshot:
            if not self.volume.isSliderDown():
                blocker = QSignalBlocker(self.volume)
                self.volume.setValue(snapshot[0])
                del blocker
            icons = self.popup.config.media_menu_icons
            self.mute.setText(icons.mute if snapshot[1] else icons.unmute)

    def update_state(self, state: SessionState) -> None:
        self.state = state
        menu = self.popup.config.media_menu
        title = state.title or "Unknown Title"
        self.title.setText(title[: menu.max_title_size] + "…" if len(title) > menu.max_title_size else title)
        set_tooltip(self.title, title)
        self.artist.setText(
            state.artist[: menu.max_artist_size] + "…" if len(state.artist) > menu.max_artist_size else state.artist
        )
        set_tooltip(self.artist, state.artist)
        self.previous.setEnabled(state.playback_ready and state.controls_prev_enabled)
        self.next_track.setEnabled(state.playback_ready and state.controls_next_enabled)
        self.play.setEnabled(state.playback_ready and state.controls_play_enabled)
        self.play.setText(
            self.popup.config.media_menu_icons.pause if state.is_playing else self.popup.config.media_menu_icons.play
        )
        self.timeline.setVisible(state.timeline_enabled and 0 < state.duration < MAX_TIMELINE_DURATION)
        self.elapsed.setText(time_text(state.current_pos))
        self.remaining.setText("−" + time_text(state.duration - state.current_pos))
        if not self._seeking and not self.progress.isSliderDown():
            self.progress.setValue(
                min(1000, max(0, int(state.current_pos / state.duration * 1000)))
                if state.duration > 0 and math.isfinite(state.duration) and math.isfinite(state.current_pos)
                else 0
            )
        if self.visualizer is not None:
            self.visualizer.setVisible(state.is_playing)
        if self._thumbnail_identity is not state.thumbnail:
            self._thumbnail_identity = state.thumbnail
            if state.thumbnail is None:
                self.thumbnail.clear()
                self.thumbnail.setText("♫")
            else:
                image = QPixmap.fromImage(ImageQt(state.thumbnail.convert("RGBA")))
                size = menu.thumbnail_size
                scaled = image.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                result = QPixmap(size, size)
                result.fill(Qt.GlobalColor.transparent)
                with QPainter(result) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addRoundedRect(0, 0, size, size, menu.thumbnail_corner_radius, menu.thumbnail_corner_radius)
                    painter.setClipPath(path)
                    painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
                self.thumbnail.setPixmap(result)


class MediaSessionsPopup(PinnablePopup):
    def __init__(self, parent: QWidget, media: WindowsMedia, config: MediaWidgetConfig):
        menu = config.media_menu
        super().__init__(parent, menu.blur, menu.round_corners, menu.round_corners_type, menu.border_color)
        self.media = media
        self.config = config
        self.cards: dict[str, MediaSessionCard] = {}
        self.volumes = AppVolumeController()
        self.setProperty("class", "media-menu native-media-menu")
        screen = parent.screen()
        self._panel_width = min(menu.width, screen.availableGeometry().width() - 24) if screen else menu.width
        self.setFixedWidth(self._panel_width)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = QFrame()
        self.header.setProperty("class", "header")
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(label("Media", "text"))
        header_layout.addStretch()
        if menu.pinnable:
            header_layout.addWidget(self.create_pin_button())
        layout.addWidget(self.header)
        self.sessions_scroll = QScrollArea()
        self.sessions_scroll.setProperty("class", "media-sessions-scroll")
        self.sessions_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sessions_scroll.setWidgetResizable(True)
        self.sessions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollbar = self.sessions_scroll.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.valueChanged.connect(self.close_overlays)
        viewport = self.sessions_scroll.viewport()
        if viewport is not None:
            viewport.setProperty("class", "media-sessions-viewport")
            viewport.setAutoFillBackground(False)
        self.content = QFrame()
        self.content.setProperty("class", "media-sessions")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.empty = label("No media playing", "no-media")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.empty)
        self.sessions_scroll.setWidget(self.content)
        layout.addWidget(self.sessions_scroll)
        media.media_data_changed.connect(self.refresh)
        media.media_properties_changed.connect(self.refresh)
        media.playback_info_changed.connect(self.refresh)
        self.volume_timer = QTimer(self)
        self.volume_timer.setInterval(2000)
        self.volume_timer.timeout.connect(self._refresh_volumes)
        self._last_sessions: dict[str, SessionState] = {}
        self.refresh(getattr(parent, "all_sessions", {}))
        self.volume_timer.start()

    def command(self, session_id: str, action: str, position: float | None = None) -> None:
        asyncio.get_running_loop().create_task(self.media.control_session(session_id, action, position))

    def refresh(self, sessions: dict[str, SessionState] | None = None) -> None:
        if sessions is not None:
            self._last_sessions = dict(sessions)
        if self._is_closing:
            return
        available = self._last_sessions
        if not self.config.media_menu.show_all_sessions:
            available = {key: state for key, state in available.items() if state.is_current}
        changed = set(available) != set(self.cards)
        for key in self.cards.keys() - available.keys():
            card = self.cards.pop(key)
            card.dispose()
            self.content_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        for key, state in available.items():
            if key not in self.cards:
                if self.config.media_menu.layout == "artwork":
                    from core.widgets.services.media.artwork import ArtworkMediaSessionCard

                    self.cards[key] = ArtworkMediaSessionCard(self, key, state)
                else:
                    self.cards[key] = MediaSessionCard(self, key, state)
                self.content_layout.addWidget(self.cards[key])
            else:
                self.cards[key].update_state(state)
        self.empty.setVisible(not self.cards)
        if changed:
            self._refresh_volumes()
        self._fit_content()

    def _fit_content(self) -> None:
        # Apply CSS first: a legacy media-menu min-width can otherwise replace
        # the fixed minimum width during polish and let adjustSize shrink us.
        self.ensurePolished()
        self.setFixedWidth(self._panel_width)
        self.content_layout.activate()
        screen = self.screen()
        available_height = screen.availableGeometry().height() - 80 if screen else self.config.media_menu.max_height
        max_height = min(self.config.media_menu.max_height, available_height)
        height = min(self.content_layout.sizeHint().height(), max_height - self.header.sizeHint().height() - 4)
        self.sessions_scroll.setFixedHeight(max(40, height))
        self.adjustSize()
        layout = self.layout()
        if layout is not None:
            layout.activate()

    def _refresh_volumes(self) -> None:
        if self.config.media_menu.show_volume_slider:
            self.volumes.refresh({card.state.app_id for card in self.cards.values()})
            self.update_volumes()

    def update_volumes(self) -> None:
        for card in self.cards.values():
            card.update_volume()

    def close_overlays(self) -> None:
        for card in self.cards.values():
            card.close_overlays()

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if isinstance(a1, QMouseEvent) and a1.type() == QEvent.Type.MouseButtonPress:
            for card in self.cards.values():
                card.handle_pointer_press(a1.globalPosition().toPoint())
        return super().eventFilter(a0, a1)

    @override
    def hideEvent(self, a0: QHideEvent | None) -> None:
        self.volume_timer.stop()
        self.close_overlays()
        super().hideEvent(a0)

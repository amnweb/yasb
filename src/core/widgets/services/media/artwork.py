"""Artwork-backed native media sessions with an in-panel volume dropdown."""

from typing import cast, override

from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap, QResizeEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QSlider, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.validation.widgets.yasb.audio_visualizer import AudioVisualizerConfig
from core.widgets.services.media.media import SessionState
from core.widgets.services.media.popup import MediaSessionCard, MediaSessionsPopup, label, time_text
from core.widgets.services.media.waves import WAVE_PALETTES, LayeredWaveCanvas, choose_wave_palette
from core.widgets.yasb.audio_visualizer import AudioVisualizerWidget


class ArtworkSurface(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setProperty("class", "media-artwork-surface")
        self.artwork: QPixmap | None = None
        self._scaled: QPixmap | None = None

    def set_artwork(self, artwork: QPixmap | None) -> None:
        self.artwork = artwork
        self._scaled = None
        self.update()

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        self._scaled = None
        super().resizeEvent(a0)

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(bounds, 24, 24)
            painter.setClipPath(path)
            painter.fillPath(path, QColor("#191919"))
            if self.artwork is not None:
                if self._scaled is None:
                    self._scaled = self.artwork.scaled(
                        self.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                painter.drawPixmap(
                    (self.width() - self._scaled.width()) // 2,
                    (self.height() - self._scaled.height()) // 2,
                    self._scaled,
                )
                painter.fillPath(path, QColor(0, 0, 0, 165))
            painter.setPen(QPen(QColor("#292929"), 1))
            painter.drawPath(path)


class ProgressWaveVisualizer(AudioVisualizerWidget):
    """Use the existing analyzer/canvas while allowing a full-width timeline wave."""

    def __init__(self, config: AudioVisualizerConfig):
        super().__init__(config)
        original = self._canvas
        self._canvas = LayeredWaveCanvas(original.width(), original.height())
        self._widget_container_layout.replaceWidget(original, self._canvas)
        original.hide()
        original.deleteLater()

    def set_palette(self, name: str) -> None:
        self._canvas.set_palette(name)

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        if hasattr(self, "_canvas"):
            self._canvas.setFixedWidth(max(8, self.width()))


class ProgressWave(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setProperty("class", "media-progress-wave")
        self.setFixedHeight(28)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._progress = 0
        self.clip = QFrame(self)
        self.clip.setProperty("class", "media-wave-clip")
        self.clip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.visualizer = ProgressWaveVisualizer(
            AudioVisualizerConfig.model_validate(
                {
                    "class_name": "media-wave-visualizer",
                    "style": "waves",
                    "height": 28,
                    "channels": "mono",
                    "mirror": False,
                    "smoothness": 80,
                    "framerate": 30,
                    "freq_min": 500,
                    "waves": {"width": 400},
                }
            )
        )
        self.visualizer.setParent(self.clip)
        self.visualizer.setMinimumWidth(0)
        self.visualizer.setMaximumWidth(16777215)
        set_tooltip(self, "System audio")

    def set_progress(self, value: int) -> None:
        self._progress = min(1000, max(0, value))
        self._fit()

    def set_palette(self, name: str) -> None:
        self.visualizer.set_palette(name)

    def _fit(self) -> None:
        played = round(self.width() * self._progress / 1000)
        self.clip.setVisible(played > 1)
        self.clip.setGeometry(0, 0, played, self.height())
        self.visualizer.setGeometry(0, 0, played, self.height())

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self._fit()


class WaveTrack(QFrame):
    """Overlay the wave baseline on the real slider groove, ending at its handle."""

    def __init__(self, progress: QSlider, wave: ProgressWave, parent: QWidget):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setProperty("class", "media-wave-track")
        self.progress = progress
        self.wave = wave
        wave.setParent(self)
        wave.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        progress.setParent(self)
        progress.raise_()
        progress.valueChanged.connect(self._on_progress)

    def _on_progress(self, value: int) -> None:
        self.wave.set_progress(value)
        self.fit_to_slider()

    def fit_to_slider(self) -> None:
        self.progress.setGeometry(0, 18, self.width(), 20)
        option = QStyleOptionSlider()
        option.initFrom(self.progress)
        option.orientation = Qt.Orientation.Horizontal
        option.minimum, option.maximum = self.progress.minimum(), self.progress.maximum()
        option.sliderValue = self.progress.value()
        style = self.progress.style()
        if style is None:
            return
        option.sliderPosition = option.minimum
        first = style.subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self.progress
        )
        option.sliderPosition = option.maximum
        last = style.subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self.progress
        )
        groove = style.subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self.progress
        )
        baseline = self.progress.y() + groove.center().y() + 1
        self.wave.setGeometry(
            first.center().x(),
            baseline - self.wave.height(),
            max(0, last.center().x() - first.center().x()),
            self.wave.height(),
        )

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self.fit_to_slider()


class ArtworkMediaSessionCard(MediaSessionCard):
    def __init__(self, popup: MediaSessionsPopup, session_id: str, state: SessionState):
        self._artwork_ready = False
        super().__init__(popup, session_id, state)
        self.setProperty("class", "media-session-card artwork-session-card")
        # Reuse all native controls and their session-specific callbacks.
        self._old_content = QWidget(self)
        old_layout = self.layout()
        if old_layout is not None:
            self._old_content.setLayout(old_layout)
        self._old_content.hide()
        if self.visualizer is not None:
            self.visualizer.hide()
            self.visualizer.deleteLater()
            self.visualizer = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 6, 16, 6)
        outer.setSpacing(0)
        self.surface = ArtworkSurface(self)
        self.surface.setMinimumHeight(196)
        outer.addWidget(self.surface)
        content = QVBoxLayout(self.surface)
        content.setContentsMargins(18, 18, 18, 16)
        content.setSpacing(0)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        heading.addStretch()
        icon = (
            "\uf1bc"
            if "spotify" in state.app_id.lower()
            else "\uf268"
            if "chrome" in state.app_id.lower()
            else "\uf001"
        )
        self.source_icon = label(icon, "media-source-icon")
        heading.addWidget(self.source_icon)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.title.setMaximumWidth(max(100, popup.config.media_menu.width - 150))
        heading.addWidget(self.title)
        heading.addStretch()
        content.addLayout(heading)
        content.addSpacing(12)

        timeline_layout = cast(QVBoxLayout, self.timeline.layout())
        times = timeline_layout.takeAt(0)
        timeline_layout.removeWidget(self.progress)
        self.wave = ProgressWave(self.timeline)
        self.wave_track = WaveTrack(self.progress, self.wave, self.timeline)
        timeline_layout.addWidget(self.wave_track)
        if times is not None and times.layout() is not None:
            timeline_layout.addLayout(cast(QHBoxLayout, times.layout()))
        content.addWidget(self.timeline)
        content.addSpacing(14)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.mute)
        controls.addStretch()
        for button in (self.previous, self.play, self.next_track):
            controls.addWidget(button)
        controls.addStretch()
        self.volume_button = self._button("\ue70d", "volume-dropdown-button", "Application volume")
        self.volume_button.setCheckable(True)
        self.volume_button.clicked.connect(self._toggle_volume_dropdown)
        self.volume_button.setVisible(popup.config.media_menu.show_volume_slider)
        controls.addWidget(self.volume_button)
        content.addLayout(controls)

        self.volume_dropdown = QFrame(popup)
        self.volume_dropdown.setProperty("class", "media-volume-dropdown")
        self.volume_dropdown.setFixedSize(198, 54)
        dropdown_layout = QHBoxLayout(self.volume_dropdown)
        dropdown_layout.setContentsMargins(14, 10, 14, 10)
        dropdown_layout.setSpacing(8)
        self.volume.setFixedWidth(120)
        dropdown_layout.addWidget(self.volume)
        dropdown_layout.addWidget(self.volume_value)
        self.volume_dropdown.hide()
        self._artwork_identity: object = object()
        self._artwork_ready = True
        self.update_state(state)

    @override
    def update_state(self, state: SessionState) -> None:
        super().update_state(state)
        if not self._artwork_ready:
            return
        text = f"{state.title or 'Unknown Title'} · {state.artist}" if state.artist else state.title or "Unknown Title"
        maximum = self.popup.config.media_menu.max_title_size
        self.title.setText(text[:maximum] + "…" if len(text) > maximum else text)
        set_tooltip(self.title, text)
        self.elapsed.setText(time_text(state.current_pos).zfill(5))
        self.remaining.setText(time_text(state.duration).zfill(5))
        self.wave.set_progress(self.progress.value())
        self.wave.visualizer.setVisible(state.is_playing and self.popup.config.media_menu.show_visualizer)
        if self._artwork_identity is not state.thumbnail:
            self._artwork_identity = state.thumbnail
            artwork = (
                QPixmap.fromImage(ImageQt(state.thumbnail.convert("RGBA"))) if state.thumbnail is not None else None
            )
            self.surface.set_artwork(artwork)
            self.palette_name = choose_wave_palette(state.thumbnail)
            self.wave.set_palette(self.palette_name)
            color = WAVE_PALETTES[self.palette_name]
            self.progress.setStyleSheet(
                f"QSlider::sub-page:horizontal {{ background-color: {color}; }}"
                f"QSlider::handle:horizontal {{ background-color: {color}; }}"
            )
            self.wave_track.fit_to_slider()

    @override
    def update_volume(self) -> None:
        super().update_volume()
        self.volume_button.setEnabled(self.volume.isEnabled())
        if not self.volume.isEnabled():
            self.close_overlays()

    def _toggle_volume_dropdown(self) -> None:
        was_visible = self.volume_dropdown.isVisible()
        self.popup.close_overlays()
        if was_visible:
            return
        anchor = self.volume_button.mapTo(self.popup, QPoint(0, self.volume_button.height()))
        x = min(
            self.popup.width() - self.volume_dropdown.width() - 8,
            max(8, anchor.x() + self.volume_button.width() - self.volume_dropdown.width()),
        )
        y = anchor.y() + 6
        if y + self.volume_dropdown.height() > self.popup.height() - 8:
            y = anchor.y() - self.volume_button.height() - self.volume_dropdown.height() - 6
        self.volume_dropdown.move(x, max(8, y))
        self.volume_dropdown.show()
        self.volume_dropdown.raise_()
        self.volume_button.setChecked(True)

    @override
    def close_overlays(self) -> None:
        self.volume_dropdown.hide()
        self.volume_button.setChecked(False)

    @override
    def handle_pointer_press(self, global_position: QPoint) -> None:
        if not self.volume_dropdown.isVisible():
            return
        for widget in (self.volume_dropdown, self.volume_button):
            if widget.rect().contains(widget.mapFromGlobal(global_position)):
                return
        self.close_overlays()

    @override
    def dispose(self) -> None:
        self.close_overlays()
        self.volume_dropdown.deleteLater()

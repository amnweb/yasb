"""Native YASB audio visualizer, event-driven WASAPI loopback capture."""

import logging
import time

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QHideEvent, QShowEvent

from core.validation.widgets.yasb.audio_visualizer import DEFAULT_COLORS, AudioVisualizerConfig
from core.widgets.base import BaseWidget
from core.widgets.services.audio_visualizer.loopback import AudioVisualizerCaptureService
from core.widgets.services.audio_visualizer.paint import AudioVizCanvas
from core.widgets.services.audio_visualizer.spectrum import (
    FFT_SIZE,
    SpectrumAnalyzer,
    layout_mono,
    layout_stereo,
)


def _sensitivity_mult(value: int) -> float:
    """Map config 0–100 (default 50 = 1.0*) to analyzer gain."""
    return max(0.1, min(2.0, value / 50.0))


def _wave_points(width: int) -> int:
    return max(4, min(128, width // 5))


def _resolve_edge_fade(edge_fade: int | list[int]) -> tuple[int, int]:
    # The config validator guarantees a list here is exactly [left, right].
    if isinstance(edge_fade, list):
        return int(edge_fade[0]), int(edge_fade[1])
    fade = int(edge_fade)
    return fade, fade


class _ReaderToken:
    """A widget's claim on the shared capture stream.

    Deliberately holds no reference to the widget, so it can be handed to the
    ``destroyed`` signal without keeping the widget alive.

    ``attach`` opens the claim (visible); ``set_visible`` follows the bar as it
    hides and shows, and only ``detach`` (on widget destruction) drops it.
    """

    __slots__ = ("_service", "_framerate", "_channels", "_attached", "_visible")

    def __init__(
        self,
        service: AudioVisualizerCaptureService,
        framerate: int,
        channels: frozenset[str],
    ) -> None:
        self._service = service
        self._framerate = framerate
        self._channels = channels
        self._attached = False
        self._visible = True

    def attach(self) -> None:
        if self._attached:
            return
        self._attached = True
        self._visible = True
        self._service.attach(self._framerate, self._channels)

    def detach(self) -> None:
        if not self._attached:
            return
        self._service.detach(self._framerate, self._channels, self._visible)
        self._attached = False
        self._visible = True

    def set_visible(self, visible: bool) -> None:
        if not self._attached or visible == self._visible:
            return
        self._visible = visible
        self._service.set_reader_visible(visible)


class AudioVisualizerWidget(BaseWidget):
    validation_schema = AudioVisualizerConfig

    def __init__(self, config: AudioVisualizerConfig) -> None:
        super().__init__(class_name=f"audio-visualizer-widget {config.class_name}".strip())
        self.config = config
        self._stereo = config.channels == "stereo"
        self._audio_active = False
        self._idle_hidden = False
        self._last_render_ns = 0
        self._frame_interval_ns = 1_000_000_000 // max(1, config.framerate)

        edge_left, edge_right = _resolve_edge_fade(config.edge_fade)

        self._init_container()
        colors = self._parse_colors(config.colors)
        smoothness = config.smoothness / 100.0
        sensitivity = _sensitivity_mult(config.sensitivity)

        columns, canvas_width, item_width, item_gap = self._resolve_style_metrics(config)
        if self._stereo:
            right_bands = max(2, columns // 2)
            left_bands = max(2, columns - right_bands)
        else:
            left_bands = right_bands = columns

        def make_analyzer(bands: int) -> SpectrumAnalyzer:
            return SpectrumAnalyzer(
                bands=bands,
                fft_size=FFT_SIZE,
                f_min=float(config.freq_min),
                f_max=float(config.freq_max),
                sensitivity=sensitivity,
                smoothness=smoothness,
                auto_gain=config.auto_gain,
            )

        self._analyzer_l = make_analyzer(left_bands)
        self._analyzer_r = make_analyzer(right_bands) if self._stereo else None

        self._canvas = AudioVizCanvas(
            style=config.style,
            height=config.height,
            columns=columns,
            canvas_width=canvas_width,
            item_width=item_width,
            item_gap=item_gap,
            gradient=config.gradient,
            mirror=config.mirror,
            stereo=self._stereo,
            colors=colors,
            edge_fade_left=edge_left,
            edge_fade_right=edge_right,
        )
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        self._widget_container_layout.addWidget(self._canvas)

        self._expanded_width = self.sizeHint().width()
        self._collapse_animation = QPropertyAnimation(self, b"maximumWidth", self)
        self._collapse_animation.setDuration(150)
        self._collapse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.callback_left = config.callbacks.on_left
        self.callback_middle = config.callbacks.on_middle
        self.callback_right = config.callbacks.on_right

        frame_ms = max(8, 1000 // max(1, config.framerate))
        self._fade_timer = QTimer(self)
        self._fade_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._fade_timer.setInterval(frame_ms)
        self._fade_timer.timeout.connect(self._on_fade_tick)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._hide_timer.setInterval(config.hide_idle_after)
        self._hide_timer.timeout.connect(self._hide_for_idle)

        # Tell the shared service which spectra to compute for us: both for
        # stereo, otherwise just the one the mono mix draws from.
        channels = frozenset({"left", "right"}) if self._stereo else frozenset({config.mono_option})

        self._service = AudioVisualizerCaptureService.instance()
        self._token = _ReaderToken(self._service, config.framerate, channels)
        token = self._token
        self.destroyed.connect(lambda *_: token.detach())

        self._service.frame_ready.connect(self._on_frame)
        self._service.audio_stopped.connect(self._on_audio_stopped)
        self._service.format_changed.connect(self._apply_sample_rate)
        self._apply_sample_rate(self._service.sample_rate)

        if config.hide_idle:
            # Start collapsed so the bar never reserves space for a silent
            # visualizer, but stay attached so the stream can wake us.
            self._idle_hidden = True
            self._apply_collapsed(True, animate=False)
            self._token.attach()

    def _apply_collapsed(self, collapsed: bool, *, animate: bool = True) -> None:
        """Collapse to zero width rather than ``hide()``, eased so the bar
        reflows smoothly instead of the widget popping in or out.

        A hidden widget stops receiving show/hide events, so it cannot tell
        when the bar itself is hidden and would keep the capture stream open
        forever. A zero-width widget stays visually gone but still gets the
        bar's show/hide events, so ``hideEvent`` can always release the stream.
        """
        target = 0 if collapsed else self._expanded_width
        if not animate:
            self._collapse_animation.stop()
            self.setMinimumWidth(0)
            self.setMaximumWidth(target)
            self.updateGeometry()
            return
        current = self.width()
        self._collapse_animation.stop()
        self.setMinimumWidth(0)
        self._collapse_animation.setStartValue(current)
        self._collapse_animation.setEndValue(target)
        self._collapse_animation.start()

    @staticmethod
    def _resolve_style_metrics(config: AudioVisualizerConfig) -> tuple[int, int, int, int]:
        if config.style == "waves":
            width = config.waves.width
            return _wave_points(width), width, 1, 0
        if config.style == "dots":
            d = config.dots
            return d.count, d.count * max(2, d.size + d.gap), d.size, d.gap
        b = config.bars
        return b.count, b.count * (b.width + b.gap), b.width, b.gap

    @staticmethod
    def _parse_colors(raw: list[str]) -> list[QColor]:
        colors: list[QColor] = []
        for hex_color in raw or DEFAULT_COLORS:
            c = QColor(hex_color)
            if c.isValid():
                colors.append(c)
            else:
                logging.error("Invalid audio visualizer color: %s", hex_color)
        return colors or [QColor(c) for c in DEFAULT_COLORS]

    def _apply_sample_rate(self, sample_rate: int) -> None:
        self._analyzer_l.set_sample_rate(sample_rate)
        if self._analyzer_r is not None:
            self._analyzer_r.set_sample_rate(sample_rate)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._token.attach()
        # Resume the shared stream. If the bar just blinked (auto-hide, a
        # maximised window) it was only frozen, so this costs nothing.
        self._token.set_visible(True)
        if self._idle_hidden:
            # The bar came back while we were idle-collapsed: stay collapsed
            # and wait for audio to expand us again.
            return
        if not self._service.is_active:
            self._reset_visual()
            if self.config.hide_idle:
                self._hide_timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        # The idle collapse never calls hide(), so any hide event here means
        # the bar, a monitor change or a minimise hid us. Freeze the shared
        # stream (it stays open, so a re-show resumes instantly). _idle_hidden
        # and the collapsed width are left as they are.
        self._fade_timer.stop()
        self._hide_timer.stop()
        self._audio_active = False
        self._reset_visual()
        self._token.set_visible(False)

    def _reset_visual(self) -> None:
        self._analyzer_l.reset()
        if self._analyzer_r is not None:
            self._analyzer_r.reset()
        self._canvas.reset()

    def _on_frame(self) -> None:
        if self._audio_active:
            if time.monotonic_ns() - self._last_render_ns < self._frame_interval_ns:
                return
        else:
            self._audio_active = True
            self._fade_timer.stop()
            self._hide_timer.stop()
            if self._idle_hidden:
                self._idle_hidden = False
                self._apply_collapsed(False)
        self._render()

    def _frame_delta(self) -> float:
        """Seconds since the last frame, so smoothing is framerate-independent."""
        now = time.monotonic_ns()
        previous = self._last_render_ns
        self._last_render_ns = now
        if not previous:
            return 1.0 / max(1, self.config.framerate)
        return (now - previous) / 1_000_000_000.0

    def _render(self) -> None:
        dt = self._frame_delta()
        magnitudes = self._service.magnitudes
        if self._stereo and self._analyzer_r is not None:
            samples = layout_stereo(
                self._analyzer_l.map_bands(magnitudes("left"), dt),
                self._analyzer_r.map_bands(magnitudes("right"), dt),
                self.config.reverse,
            )
        else:
            bands = self._analyzer_l.map_bands(magnitudes(self.config.mono_option), dt)
            samples = layout_mono(bands, self.config.reverse)
        self._canvas.set_samples(samples)

    def _on_audio_stopped(self) -> None:
        if not self._audio_active:
            return
        self._audio_active = False
        if self._idle_hidden:
            return
        # Walk the bars down to zero rather than leaving them frozen on the
        # last captured frame. The timer stops itself once they settle.
        self._fade_timer.start()
        if self.config.hide_idle:
            self._hide_timer.start()

    def _on_fade_tick(self) -> None:
        dt = self._frame_delta()
        left, moving = self._analyzer_l.decay(dt)
        if self._stereo and self._analyzer_r is not None:
            right, moving_r = self._analyzer_r.decay(dt)
            samples = layout_stereo(left, right, self.config.reverse)
            moving = moving or moving_r
        else:
            samples = layout_mono(left, self.config.reverse)
        self._canvas.set_samples(samples)
        if not moving:
            self._fade_timer.stop()

    def _hide_for_idle(self) -> None:
        if self._audio_active or self._idle_hidden:
            return
        self._fade_timer.stop()
        self._reset_visual()
        self._idle_hidden = True
        self._apply_collapsed(True)

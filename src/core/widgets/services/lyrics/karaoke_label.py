from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Any, Literal, cast, override

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PyQt6.QtCore import (
    pyqtProperty as _pyqtProperty,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import QLabel, QWidget

from core.widgets.services.lyrics.models import Word
from core.widgets.services.lyrics.note_icons import get_two_tone_colors, paint_two_tone_note

logger = logging.getLogger("core.widgets.services.lyrics.karaoke_label")

_pyqt_property = cast("Any", _pyqtProperty)


@dataclass
class _Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    alpha: int
    spark_type: str = "star"
    rotation: float = 0.0
    rot_speed: float = 0.0
    twinkle_freq: float = 24.0
    twinkle_phase: float = 0.0


class _LayerSnapshot:
    """Snapshot of a lyric line's render state for dual-layer transition rendering."""

    __slots__ = ("text", "words", "word_spans", "total_width", "wipe_x", "karaoke_enabled")

    def __init__(
        self,
        text: str,
        words: list[Word] | None,
        word_spans: list[tuple[float, float]],
        total_width: float,
        wipe_x: float,
        karaoke_enabled: bool,
    ):
        self.text = text
        self.words = words
        self.word_spans = word_spans
        self.total_width = total_width
        self.wipe_x = wipe_x
        self.karaoke_enabled = karaoke_enabled


class KaraokeLabel(QLabel):
    def __init__(self, parent: QWidget | None = None, default_text: str = ""):
        super().__init__(default_text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self._is_html_mode: bool = False

        self._words: list[Word] | None = None
        self._position_ms: int = 0
        self._is_active: bool = False
        self._is_painting: bool = False
        self._row_state: str = "upcoming"  # "upcoming", "active", "past"
        self._karaoke_enabled: bool = False
        self._display_text: str = default_text
        self._prefix: str = ""
        self._suffix: str = ""
        self._scale_factor: float = 1.0
        self._scale_anim: QVariantAnimation | None = None

        self._cue_dots_enabled: bool = False
        self._cue_progress: float = 0.0
        self._cue_is_searching: bool = False
        self._cue_prefix: str = "♪"
        self._cue_phase: float = 0.0

        self._break_visualizer_enabled: bool = False
        self._break_visualizer_style: str = "bars"
        self._break_visualizer_symmetry: bool = False
        self._karaoke_beat_glow_enabled: bool = True
        self._beat_sparks_enabled: bool = True
        self._beat_syllable_float_enabled: bool = True
        self._syllable_physics_enabled: bool = False
        self._break_wave_enabled: bool = False
        self._break_wave_progress: float = 0.0
        self._break_wave_remaining_sec: int = 0
        self._is_visualizer_active: bool = False
        self._is_notes_active: bool = False
        self._notes_progress: float = 0.0
        self._notes_animated: bool = True
        self._visualizer_samples: list[float] = []
        self._vis_bar_width: float = 3.0
        self._vis_bar_spacing: float = 2.0
        self._vis_bar_radius: float = 1.5
        self._vis_bar_height: int | None = None
        self._vis_min_bar_height: int | None = None
        self._vis_vertical_alignment: str = "middle"
        self._visualizer_progress: float = 0.0
        self._visualizer_prefix: str = "♪"
        self._bass_energy: float = 0.0

        self._sparks: list[_Spark] = []
        self._sparkle_style: str = "stars"
        self._sparkle_intensity: str = "subtle"
        self._last_spark_spawn_time: float = 0.0
        self._last_spark_tick_time: float = 0.0
        self._spark_timer_active: bool = False
        self._spark_armed: bool = True

        self._line_sparks_enabled: bool = True
        self._line_beat_glow_enabled: bool = True
        self._line_beat_bounce_enabled: bool = True
        self._line_start_ms: int = 0
        self._line_duration_ms: int = 0
        self._line_progress: float = 0.0

        self._word_spans: list[tuple[float, float]] = []  # (start_x, end_x)
        self._prefix_width: float = 0.0
        self._total_text_width: float = 0.0
        self._wipe_x: float = 0.0
        self._auto_scroll_offset: float = 0.0
        self._auto_scroll_enabled: bool = True
        self._active_word_index: int | None = None
        self._word_progress: float = 0.0

        self._secondary_text: str = ""
        self._secondary_words: list[Word] | None = None
        self._primary_text_width: float = 0.0
        self._secondary_base_x: float = 0.0
        self._secondary_text_width: float = 0.0
        self._secondary_word_spans: list[tuple[float, float]] = []
        self._secondary_wipe_x: float = 0.0
        self._secondary_active_word_index: int | None = None
        self._secondary_word_progress: float = 0.0

        self._sung_color: QColor | None = None
        self._upcoming_color: QColor | None = None
        self._glow_color: QColor | None = None

        self._album_color_mode: str | bool = False  # False, "effects_only", "full"
        self._target_album_color: QColor | None = None
        self._current_album_color: QColor | None = None
        self._album_secondary_color: QColor | None = None
        self._color_lerp_start_color: QColor | None = None
        self._color_lerp_start_time: float = 0.0
        self._color_lerp_duration: float = 0.45
        self._color_lerp_timer: QTimer | None = None

        self._transition_mode: str = "none"  # "none", "slide_up", "scale", "wipe"
        self._transition_duration_ms: int = 280
        self._transition_easing: str = "out_cubic"
        self._transition_progress: float = 1.0
        self._transition_anim: QPropertyAnimation | None = None
        self._outgoing_layer: _LayerSnapshot | None = None

    @property
    def wipe_x(self) -> float:
        return self._wipe_x

    @property
    def secondary_words(self) -> list[Word] | None:
        return self._secondary_words

    @property
    def total_width(self) -> float:
        return self._total_text_width

    @property
    def active_word_index(self) -> int | None:
        return self._active_word_index

    @property
    def word_progress(self) -> float:
        return self._word_progress

    @property
    def is_transitioning(self) -> bool:
        return (
            self._outgoing_layer is not None
            and self._transition_anim is not None
            and self._transition_anim.state() == QPropertyAnimation.State.Running
        )

    def _get_transition_progress(self) -> float:
        return self._transition_progress

    def _set_transition_progress(self, val: float) -> None:
        self._transition_progress = float(val)
        self.update()

    transition_progress: Any = _pyqt_property(float, _get_transition_progress, _set_transition_progress)

    def set_transition_config(
        self,
        mode: str = "none",
        duration_ms: int = 280,
        easing: str = "out_cubic",
    ) -> None:
        """Configures line change animation settings."""
        self._transition_mode = mode
        self._transition_duration_ms = max(0, duration_ms)
        self._transition_easing = easing

    def _get_scale_factor(self) -> float:
        return self._scale_factor

    def _set_scale_factor(self, value: float) -> None:
        self._scale_factor = float(value)
        self.update()

    scale_factor: Any = _pyqt_property(float, _get_scale_factor, _set_scale_factor)

    def animate_scale(self, target_scale: float, duration_ms: int = 280) -> None:
        if abs(self._scale_factor - target_scale) < 0.005:
            return
        if duration_ms <= 0:
            self._scale_factor = target_scale
            self.update()
            return

        if self._scale_anim and self._scale_anim.state() == QVariantAnimation.State.Running:
            self._scale_anim.stop()

        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setDuration(duration_ms)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.setStartValue(self._scale_factor)
        self._scale_anim.setEndValue(target_scale)
        self._scale_anim.valueChanged.connect(self._on_scale_anim_step)
        self._scale_anim.start()

    def _on_scale_anim_step(self, value: Any) -> None:
        self._scale_factor = float(value)
        self.update()

    def set_audio_reactive_config(
        self,
        break_visualizer: bool = False,
        break_visualizer_style: str = "bars",
        break_visualizer_symmetry: bool = False,
        karaoke_beat_glow: bool = True,
        sparkles: bool = True,
        beat_jump: bool = True,
        line_sparks: bool = True,
        line_beat_glow: bool = True,
        line_beat_bounce: bool = True,
    ) -> None:
        self._break_visualizer_enabled = break_visualizer
        self._break_visualizer_style = break_visualizer_style
        self._break_visualizer_symmetry = break_visualizer_symmetry
        self._karaoke_beat_glow_enabled = karaoke_beat_glow
        self._beat_sparks_enabled = sparkles
        self._beat_syllable_float_enabled = beat_jump
        self._sparkle_style = "stars"
        self._sparkle_intensity = "subtle"
        self._line_sparks_enabled = line_sparks
        self._line_beat_glow_enabled = line_beat_glow
        self._line_beat_bounce_enabled = line_beat_bounce

    def set_visualizer_style_options(
        self,
        bar_width: float = 3.0,
        bar_spacing: float = 2.0,
        bar_radius: float = 1.5,
        bar_height: int | None = None,
        min_bar_height: int | None = None,
        vertical_alignment: str = "middle",
    ) -> None:
        """Geometry for the break visualizer. Heights of None follow the font height."""
        self._vis_vertical_alignment = (
            vertical_alignment if vertical_alignment in ("top", "middle", "bottom") else "middle"
        )
        self._vis_bar_width = max(1.0, float(bar_width))
        self._vis_bar_spacing = max(0.0, float(bar_spacing))
        self._vis_bar_radius = max(0.0, float(bar_radius))
        self._vis_bar_height = bar_height
        self._vis_min_bar_height = min_bar_height
        self.update()

    def _effective_valign(self) -> str:
        """Vertical alignment in use. Mirrored styles and "none" always stay centred."""
        style = (self._break_visualizer_style or "bars").lower()
        if self._break_visualizer_symmetry or "mirrored" in style or style == "none":
            return "middle"
        return self._vis_vertical_alignment

    @staticmethod
    def _aligned_center(rect: QRect, item_h: float, valign: str, pad: float = 0.0) -> float:
        """Vertical centre for an item of ``item_h`` placed at the top, middle or bottom of ``rect``."""
        top = float(rect.top())
        height = float(rect.height())
        if valign == "top":
            return top + pad + item_h / 2.0
        if valign == "bottom":
            return top + height - pad - item_h / 2.0
        return top + height / 2.0

    def _visualizer_geometry(
        self, n_samples: int, is_waves: bool, max_span: float | None = None
    ) -> tuple[int, float, float, float, float]:
        """(count, bar_w, bar_gap, span, step). Shrinks to ``max_span`` when it would not fit."""
        bar_w = self._vis_bar_width
        gap = self._vis_bar_spacing
        if is_waves:
            n = max(4, min(32, n_samples))
            span = max(36.0, float(n - 1) * max(0.5, (bar_w + gap) * 0.9))
            if max_span is not None and 0.0 < max_span < span:
                span = max_span
            return n, bar_w, gap, span, span / float(max(1, n - 1))
        n = max(1, min(32, n_samples))
        span = float(n) * bar_w + float(n - 1) * gap
        if max_span is not None and 0.0 < max_span < span:
            f = max_span / span
            bar_w *= f
            gap *= f
            span = max_span
        return n, bar_w, gap, span, bar_w + gap

    def set_syllable_physics(self, enabled: bool) -> None:
        self._syllable_physics_enabled = enabled
        self.update()

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enables or disables horizontal auto-tracking pan when text exceeds widget width."""
        self._auto_scroll_enabled = enabled
        if not enabled:
            self._auto_scroll_offset = 0.0
        self.update()

    def set_break_visualizer_style(self, style: str, symmetry: bool = False) -> None:
        self._break_visualizer_style = style
        self._break_visualizer_symmetry = symmetry or ("mirrored" in style)

    def update_break_visualizer_samples(self, samples: list[float]) -> None:
        if self._break_visualizer_enabled and self._is_visualizer_active:
            self._visualizer_samples = samples
            self.update()

    def set_glow_color(self, color: QColor | str | None) -> None:
        if isinstance(color, str) and color:
            self._glow_color = QColor(color)
        elif isinstance(color, QColor) and color.isValid():
            self._glow_color = color
        else:
            self._glow_color = None
        self.update()

    def _get_glow_color(self) -> QColor:
        return self._glow_color or QColor()

    def _set_glow_color(self, color: QColor) -> None:
        self._glow_color = color if color.isValid() else None
        self.update()

    glow_color: Any = _pyqt_property(QColor, _get_glow_color, _set_glow_color)

    def set_album_color_mode(self, mode: str | bool) -> None:
        if isinstance(mode, str):
            clean = mode.lower().strip()
            if clean in ("effects", "effects_only"):
                self._album_color_mode = "effects_only"
            elif clean == "full":
                self._album_color_mode = "full"
            else:
                self._album_color_mode = False
        else:
            self._album_color_mode = "effects_only" if mode else False
        self.update()

    def set_album_art_color(self, color: QColor | tuple[int, int, int] | str | None) -> None:
        if not self._album_color_mode:
            self._current_album_color = None
            self._target_album_color = None
            if self._color_lerp_timer and self._color_lerp_timer.isActive():
                self._color_lerp_timer.stop()
            return

        target: QColor | None = None
        if isinstance(color, tuple) and len(color) >= 3:
            target = QColor(color[0], color[1], color[2])
        elif isinstance(color, str) and color:
            target = QColor(color)
        elif isinstance(color, QColor) and color.isValid():
            target = color

        if target is not None and not target.isValid():
            target = None

        if self._target_album_color == target:
            return

        self._target_album_color = target

        if self._current_album_color is None or target is None:
            self._current_album_color = target
            self.update()
            return

        self._color_lerp_start_color = QColor(self._current_album_color)
        self._color_lerp_start_time = time.monotonic()
        if self._color_lerp_timer is None:
            self._color_lerp_timer = QTimer(self)
            self._color_lerp_timer.setInterval(16)
            self._color_lerp_timer.timeout.connect(self._step_color_lerp)
        if not self._color_lerp_timer.isActive():
            self._color_lerp_timer.start()

    def _step_color_lerp(self) -> None:
        if not self._color_lerp_start_color or not self._target_album_color:
            if self._color_lerp_timer and self._color_lerp_timer.isActive():
                self._color_lerp_timer.stop()
            return

        now = time.monotonic()
        elapsed = now - self._color_lerp_start_time
        progress = min(1.0, max(0.0, elapsed / self._color_lerp_duration))

        t = 1.0 - (1.0 - progress) ** 3

        start = self._color_lerp_start_color
        target = self._target_album_color

        r = int(start.red() + (target.red() - start.red()) * t)
        g = int(start.green() + (target.green() - start.green()) * t)
        b = int(start.blue() + (target.blue() - start.blue()) * t)

        self._current_album_color = QColor(r, g, b)
        self.update()

        if progress >= 1.0:
            if self._color_lerp_timer and self._color_lerp_timer.isActive():
                self._color_lerp_timer.stop()
            self._current_album_color = self._target_album_color
            self._color_lerp_start_color = None

    def set_album_art_palette(
        self,
        primary: QColor | tuple[int, int, int] | str | None,
        secondary: QColor | tuple[int, int, int] | str | None = None,
    ) -> None:
        """Sets primary and secondary album art colors for two-tone palette theming."""
        self.set_album_art_color(primary)
        if isinstance(secondary, tuple) and len(secondary) >= 3:
            self._album_secondary_color = QColor(secondary[0], secondary[1], secondary[2])
        elif isinstance(secondary, str) and secondary:
            self._album_secondary_color = QColor(secondary)
        elif isinstance(secondary, QColor) and secondary.isValid():
            self._album_secondary_color = secondary
        else:
            self._album_secondary_color = None
        self.update()

    def set_bass_energy(self, val: float) -> None:
        if not (
            self._karaoke_beat_glow_enabled
            or self._beat_sparks_enabled
            or self._beat_syllable_float_enabled
            or getattr(self, "_beat_audio_rail_enabled", False)
            or self._line_sparks_enabled
            or self._line_beat_glow_enabled
            or self._line_beat_bounce_enabled
            or getattr(self, "_is_notes_active", False)
            or getattr(self, "_cue_dots_enabled", False)
        ):
            return
        clamped = max(0.0, min(1.0, val))
        energy_changed = abs(self._bass_energy - clamped) > 0.008
        prev_energy = self._bass_energy
        self._bass_energy = clamped

        primary_line_effects = self._karaoke_enabled and not self._words and bool(self._secondary_words)
        if (getattr(self, "_is_notes_active", False) or getattr(self, "_cue_dots_enabled", False)) and energy_changed:
            self.update()

        should_spawn_sparks = (self._beat_sparks_enabled and self._karaoke_enabled) or (
            self._line_sparks_enabled and (not self._karaoke_enabled or primary_line_effects) and self._is_active
        )
        if should_spawn_sparks:
            delta = clamped - prev_energy
            time.monotonic()
            if clamped < 0.16:
                self._spark_armed = True

            is_beat_onset = (self._spark_armed and clamped >= 0.22 and delta > 0.035) or (delta > 0.16)
            if is_beat_onset:
                if self._karaoke_enabled and not primary_line_effects:
                    self._maybe_spawn_sparks(clamped)
                else:
                    self._maybe_spawn_line_sparks(clamped)
                self._spark_armed = False

        if (energy_changed or self._sparks) and self._is_active:
            self.update()

    def _maybe_spawn_sparks(self, energy: float) -> None:
        has_wipe = (
            self._wipe_x > 0.0
            or (self._secondary_words and self._secondary_wipe_x > 0.0)
            or (self._active_word_index is not None)
        )
        if not (self._karaoke_enabled and self._is_active and has_wipe and self._total_text_width > 0.0):
            return
        now = time.monotonic()
        if now - self._last_spark_spawn_time < 0.045:
            return
        self._last_spark_spawn_time = now

        rect = self.contentsRect()
        visible_h = float(rect.height())
        fm = self.fontMetrics()
        ascent = float(fm.ascent())
        descent = float(fm.descent())
        y_baseline = float(rect.top()) + (visible_h + ascent - descent) / 2.0

        intensity_mult = 0.65  # subtle mode

        base_count = random.randint(5, 8) if energy >= 0.35 else random.randint(2, 4)
        num_sparks = max(1, int(round(base_count * intensity_mult)))

        for i in range(num_sparks):
            spark_type = (
                "star" if i == 0 else random.choices(["star", "diamond", "ember"], weights=[0.55, 0.25, 0.20])[0]
            )

            primary_w = self._primary_text_width if self._secondary_words else self._total_text_width
            is_sec_singing = (
                self._secondary_words
                and self._secondary_active_word_index is not None
                and self._secondary_word_progress < 1.0
            )
            is_prim_singing = self._words and self._active_word_index is not None and self._word_progress < 1.0

            if is_sec_singing:
                active_needle = self._secondary_base_x + self._secondary_wipe_x
            elif is_prim_singing:
                active_needle = self._wipe_x
            else:
                if self._secondary_words and self._secondary_wipe_x > 0.0:
                    active_needle = self._secondary_base_x + self._secondary_text_width
                else:
                    active_needle = primary_w

            active_needle = max(2.0, min(self._total_text_width, active_needle))
            if is_sec_singing or is_prim_singing:
                sx = active_needle + random.uniform(-2.5, 1.5)
            else:
                sx = active_needle + random.uniform(-4.0, 1.5)
            sx = max(2.0, min(self._total_text_width - 1.0, sx))
            sy = y_baseline - random.uniform(ascent * 0.15, ascent * 0.85)

            vy = -random.uniform(22.0, 48.0 + 38.0 * energy * intensity_mult)
            vx = random.uniform(-26.0, 10.0 + 12.0 * energy)
            max_life = random.uniform(0.40, 0.68)

            if spark_type == "star":
                size = random.uniform(2.4, 3.8 + 1.8 * energy * intensity_mult)
            elif spark_type == "diamond":
                size = random.uniform(2.0, 3.2 + 1.4 * energy * intensity_mult)
            else:  # "ember"
                size = random.uniform(1.2, 2.2 + 1.0 * energy * intensity_mult)

            alpha = int(random.uniform(215, 255))
            rotation = random.uniform(0.0, 90.0)
            rot_speed = random.uniform(-150.0, 150.0)
            twinkle_freq = random.uniform(18.0, 32.0)
            twinkle_phase = random.uniform(0.0, 6.283)

            self._sparks.append(
                _Spark(
                    x=sx,
                    y=sy,
                    vx=vx,
                    vy=vy,
                    life=0.0,
                    max_life=max_life,
                    size=size,
                    alpha=alpha,
                    spark_type=spark_type,
                    rotation=rotation,
                    rot_speed=rot_speed,
                    twinkle_freq=twinkle_freq,
                    twinkle_phase=twinkle_phase,
                )
            )

        if not self._spark_timer_active:
            self._spark_timer_active = True
            QTimer.singleShot(16, self._on_spark_timer)

    def _maybe_spawn_line_sparks(self, energy: float) -> None:
        if not (self._is_active and self._total_text_width > 0.0):
            return
        now = time.monotonic()
        if now - self._last_spark_spawn_time < 0.045:
            return
        self._last_spark_spawn_time = now

        rect = self.contentsRect()
        visible_h = float(rect.height())
        fm = self.fontMetrics()
        ascent = float(fm.ascent())
        descent = float(fm.descent())
        y_baseline = float(rect.top()) + (visible_h + ascent - descent) / 2.0

        intensity_mult = 0.65  # subtle mode

        base_count = random.randint(5, 8) if energy >= 0.35 else random.randint(2, 4)
        num_sparks = max(1, int(round(base_count * intensity_mult)))
        total_w = self._total_text_width

        for i in range(num_sparks):
            spark_type = (
                "star" if i == 0 else random.choices(["star", "diamond", "ember"], weights=[0.55, 0.25, 0.20])[0]
            )

            sx = random.uniform(4.0, max(8.0, total_w - 4.0))
            sy = y_baseline - random.uniform(ascent * 0.10, ascent * 0.88)

            vy = -random.uniform(22.0, 48.0 + 38.0 * energy * intensity_mult)
            vx = random.uniform(-18.0, 18.0)
            max_life = random.uniform(0.40, 0.68)

            if spark_type == "star":
                size = random.uniform(2.4, 3.8 + 1.8 * energy * intensity_mult)
            elif spark_type == "diamond":
                size = random.uniform(2.0, 3.2 + 1.4 * energy * intensity_mult)
            else:  # "ember"
                size = random.uniform(1.2, 2.2 + 1.0 * energy * intensity_mult)

            alpha = int(random.uniform(215, 255))
            rotation = random.uniform(0.0, 90.0)
            rot_speed = random.uniform(-150.0, 150.0)
            twinkle_freq = random.uniform(18.0, 32.0)
            twinkle_phase = random.uniform(0.0, 6.283)

            self._sparks.append(
                _Spark(
                    x=sx,
                    y=sy,
                    vx=vx,
                    vy=vy,
                    life=0.0,
                    max_life=max_life,
                    size=size,
                    alpha=alpha,
                    spark_type=spark_type,
                    rotation=rotation,
                    rot_speed=rot_speed,
                    twinkle_freq=twinkle_freq,
                    twinkle_phase=twinkle_phase,
                )
            )

        if not self._spark_timer_active:
            self._spark_timer_active = True
            QTimer.singleShot(16, self._on_spark_timer)

    def _on_spark_timer(self) -> None:
        self._spark_timer_active = False
        if self._sparks:
            self.update()

    def _update_sparks(self) -> None:
        if not self._sparks:
            return
        now = time.monotonic()
        if self._last_spark_tick_time <= 0.0:
            dt = 0.016
        else:
            dt = max(0.001, min(0.05, now - self._last_spark_tick_time))
        self._last_spark_tick_time = now

        gravity = 38.0
        alive: list[_Spark] = []
        for sp in self._sparks:
            sp.life += dt
            if sp.life < sp.max_life:
                sp.vx *= max(0.0, 1.0 - 1.8 * dt)
                sp.vy += gravity * dt
                sp.x += sp.vx * dt
                sp.y += sp.vy * dt
                sp.rotation += sp.rot_speed * dt
                alive.append(sp)
        self._sparks = alive

        if self._sparks and not self._spark_timer_active:
            self._spark_timer_active = True
            QTimer.singleShot(16, self._on_spark_timer)

    def set_break_visualizer(
        self,
        samples: list[float],
        progress: float = 0.0,
        prefix: str = "",
        state: str = "active",
        style: str | None = None,
    ) -> None:
        if self._transition_anim and self._transition_anim.state() == QPropertyAnimation.State.Running:
            self._transition_anim.stop()
        self._outgoing_layer = None
        self._transition_progress = 1.0

        if style is not None:
            self._break_visualizer_style = style
            if "mirrored" in style:
                self._break_visualizer_symmetry = True

        self._break_visualizer_enabled = True
        self._karaoke_enabled = False
        self._cue_dots_enabled = False
        self._is_notes_active = False
        self._is_visualizer_active = True
        self._visualizer_samples = samples or [0.2] * 6
        self._visualizer_progress = max(0.0, min(1.0, progress))
        self._visualizer_prefix = prefix
        self._row_state = state
        self._is_active = state != "past" and "paused" not in state

        txt = f"{prefix} ılılllı" if prefix else "ılılllı"
        self._display_text = txt
        self.setText(txt)

        fm = self.fontMetrics()
        font_h = float(fm.height())
        note_icon_w = max(14.0, font_h * 0.9)
        prefix_w = note_icon_w if prefix else 0.0
        cur_style = (self._break_visualizer_style or "bars").lower()
        is_waves = "waves" in cur_style
        bars_span = self._visualizer_geometry(len(self._visualizer_samples), is_waves)[3]
        dot_gap = max(8.0, font_h * 0.44)
        self._total_text_width = prefix_w + (dot_gap if prefix else 0.0) + bars_span
        self.update()

    def set_break_notes(
        self,
        progress: float = 0.0,
        state: str = "active",
        animated: bool = True,
    ) -> None:
        """Activates Apple Music style sequential 3-note vector fill [single, beamed, single] during instrumental breaks / preludes."""
        if self._transition_anim and self._transition_anim.state() == QPropertyAnimation.State.Running:
            self._transition_anim.stop()
        self._outgoing_layer = None
        self._transition_progress = 1.0

        self._karaoke_enabled = False
        self._cue_dots_enabled = False
        self._is_visualizer_active = False
        self._is_notes_active = True
        self._notes_animated = animated
        self._sparks.clear()
        self._notes_progress = max(0.0, min(1.0, progress))
        self._row_state = state
        self._is_active = state != "past" and "paused" not in state

        txt = "♪ ♫ ♪"
        self._display_text = txt
        self.setText(txt)

        fm = self.fontMetrics()
        font_h = float(fm.height())
        note_sz = max(14.0, font_h * 0.9)
        gap = max(8.0, font_h * 0.44)
        self._total_text_width = 3.0 * note_sz + 2.0 * gap
        self.update()

    def _should_start_transition(self, new_text: str) -> bool:
        if self._transition_mode == "none" or self._transition_duration_ms <= 0:
            return False
        if not self._display_text or not new_text:
            return False
        if (
            self._display_text == new_text
            and not self._cue_dots_enabled
            and not self._is_visualizer_active
            and not self._is_notes_active
        ):
            return False
        return True

    def _start_transition(self) -> None:
        if self._transition_anim and self._transition_anim.state() == QPropertyAnimation.State.Running:
            self._transition_anim.stop()

        self._sparks.clear()
        self._outgoing_layer = _LayerSnapshot(
            text=self._display_text,
            words=self._words,
            word_spans=list(self._word_spans),
            total_width=self._total_text_width,
            wipe_x=self._wipe_x,
            karaoke_enabled=self._karaoke_enabled,
        )

        self._transition_progress = 0.0

        if self._transition_anim is None:
            self._transition_anim = QPropertyAnimation(self, b"transition_progress", self)
            self._transition_anim.finished.connect(self._on_transition_finished)

        self._transition_anim.setDuration(self._transition_duration_ms)
        self._transition_anim.setStartValue(0.0)
        self._transition_anim.setEndValue(1.0)
        self._transition_anim.setEasingCurve(self._get_easing_curve(self._transition_easing))
        self._transition_anim.start()

    def _on_transition_finished(self) -> None:
        self._outgoing_layer = None
        self._transition_progress = 1.0
        self.update()

    @staticmethod
    def _get_easing_curve(easing_name: str) -> QEasingCurve.Type:
        curves = {
            "out_cubic": QEasingCurve.Type.OutCubic,
            "out_quad": QEasingCurve.Type.OutQuad,
            "out_back": QEasingCurve.Type.OutBack,
            "in_out_cubic": QEasingCurve.Type.InOutCubic,
            "in_out_quad": QEasingCurve.Type.InOutQuad,
            "out_bounce": QEasingCurve.Type.OutBounce,
            "in_cubic": QEasingCurve.Type.InCubic,
            "in_quad": QEasingCurve.Type.InQuad,
            "linear": QEasingCurve.Type.Linear,
        }
        key = str(easing_name).replace("-", "_").strip().lower()
        return curves.get(key, QEasingCurve.Type.OutCubic)

    def set_plain_text(
        self,
        text: str,
        state: str = "upcoming",
        start_ms: int = 0,
        duration_ms: int = 0,
        position_ms: int = 0,
    ) -> None:
        text_changed = (
            (self._display_text != text)
            or self._cue_dots_enabled
            or self._is_visualizer_active
            or self._is_notes_active
            or self._karaoke_enabled
        )
        if self._should_start_transition(text):
            self._start_transition()
        elif text_changed:
            self._sparks.clear()

        self._karaoke_enabled = False
        self._cue_dots_enabled = False
        self._is_visualizer_active = False
        self._is_notes_active = False
        self._words = None
        self._word_spans.clear()
        self._display_text = text
        self._row_state = state
        self._is_active = state == "active" or "active" in state or "synced" in state
        self._line_start_ms = start_ms
        self._line_duration_ms = max(0, duration_ms)
        self._position_ms = position_ms

        if self._line_duration_ms > 0 and position_ms >= start_ms:
            self._line_progress = max(0.0, min(1.0, (position_ms - start_ms) / self._line_duration_ms))
        else:
            self._line_progress = 0.0

        if text_changed:
            self._auto_scroll_offset = 0.0
            self.setText(text)
            fm = self.fontMetrics()
            self._total_text_width = float(fm.horizontalAdvance(text))
        self.update()

    def set_line_synced_data(
        self,
        text: str,
        start_ms: int = 0,
        duration_ms: int = 0,
        position_ms: int = 0,
        state: str = "active",
    ) -> None:
        self.set_plain_text(
            text=text,
            state=state,
            start_ms=start_ms,
            duration_ms=duration_ms,
            position_ms=position_ms,
        )

    def update_line_position(self, position_ms: int) -> None:
        """Update the line-synced light wave."""
        if self._karaoke_enabled or not self._is_active:
            return
        self._position_ms = position_ms
        if self._line_duration_ms > 0 and position_ms >= self._line_start_ms:
            old_p = self._line_progress
            new_p = max(0.0, min(1.0, (position_ms - self._line_start_ms) / self._line_duration_ms))
            if abs(new_p - old_p) > 0.005:
                self._line_progress = new_p
                self.update()

    def set_cue_dots(
        self,
        progress: float = 0.0,
        is_searching: bool = False,
        prefix: str = "",
        phase: float = 0.0,
        state: str = "active",
    ) -> None:
        if self._transition_anim and self._transition_anim.state() == QPropertyAnimation.State.Running:
            self._transition_anim.stop()
        self._outgoing_layer = None
        self._transition_progress = 1.0

        self._karaoke_enabled = False
        self._cue_dots_enabled = True
        self._is_visualizer_active = False
        self._is_notes_active = False
        self._sparks.clear()
        self._cue_progress = max(0.0, min(1.0, progress))
        self._cue_is_searching = is_searching
        self._cue_prefix = prefix
        self._cue_phase = phase
        self._row_state = state
        self._is_active = state != "past" and "paused" not in state

        if is_searching:
            txt = f"{prefix}..." if not prefix.endswith("...") else prefix
        else:
            txt = f"{prefix} • • •" if prefix else "• • •"
        self._display_text = txt
        self.setText(txt)
        fm = self.fontMetrics()
        font_h = float(fm.height())
        note_icon_w = max(14.0, font_h * 0.9)
        draw_prefix = prefix[:-3].strip() if (is_searching and prefix.endswith("...")) else prefix
        prefix_w = note_icon_w if draw_prefix else 0.0
        dot_gap = max(8.0, font_h * 0.44)
        dots_span = 2.0 * dot_gap
        self._total_text_width = prefix_w + (dot_gap if draw_prefix else 0.0) + dots_span
        self.update()

    def set_row_state(self, state: str) -> None:
        """Updates row state for popup display ('upcoming', 'active', 'past')."""
        if self._row_state == state:
            return
        self._row_state = state
        self._is_active = state == "active"
        if not self._karaoke_enabled:
            self.update()
            return

        if state == "past":
            self._wipe_x = self._total_text_width
            self._active_word_index = (len(self._words) - 1) if self._words else None
            self._word_progress = 1.0
            if self._secondary_words:
                self._secondary_wipe_x = self._secondary_text_width
                self._secondary_active_word_index = len(self._secondary_words) - 1
                self._secondary_word_progress = 1.0
        elif state == "upcoming":
            self._wipe_x = 0.0
            self._active_word_index = None
            self._word_progress = 0.0
            self._secondary_wipe_x = 0.0
            self._secondary_active_word_index = None
            self._secondary_word_progress = 0.0
        self.update()

    def set_karaoke_data(
        self,
        text: str,
        words: list[Word] | None,
        position_ms: int,
        is_active: bool = True,
        prefix: str = "",
        suffix: str = "",
        state: str = "active",
        secondary_text: str = "",
        secondary_words: list[Word] | None = None,
    ) -> None:
        """Updates the full karaoke line data and current playback position."""
        if not words and not secondary_words:
            self.set_plain_text(text, state=state)
            return

        if self._should_start_transition(text):
            self._start_transition()

        self._karaoke_enabled = True
        self._cue_dots_enabled = False
        self._is_visualizer_active = False
        self._is_notes_active = False
        self._words = words
        self._secondary_text = secondary_text
        self._secondary_words = secondary_words
        self._position_ms = position_ms
        self._is_active = is_active
        self._row_state = state
        self._prefix = prefix
        self._suffix = suffix

        self._display_text = text
        self.setText(text)
        self._recompute_layout()
        self._recompute_wipe()
        self.update()

    def _recompute_layout(self) -> None:
        """Computes pixel bounds for each word based on current font metrics."""
        fm = self.fontMetrics()
        self._word_spans.clear()
        self._secondary_word_spans.clear()

        self._prefix_width = float(fm.horizontalAdvance(self._prefix)) if self._prefix else 0.0

        if not self._words and not self._secondary_words:
            self._total_text_width = float(fm.horizontalAdvance(self._display_text))
            self._primary_text_width = self._total_text_width
            return

        lyric_body = self._display_text[len(self._prefix) :]
        if self._suffix and lyric_body.endswith(self._suffix):
            lyric_body = lyric_body[: -len(self._suffix)]

        sec_str = self._secondary_text.strip() if self._secondary_text else ""
        if sec_str and self._secondary_words and lyric_body.endswith(sec_str):
            primary_body = lyric_body[: -len(sec_str)].rstrip()
            sec_start_in_body = lyric_body.rfind(sec_str)
        else:
            primary_body = lyric_body
            sec_start_in_body = -1

        if self._words:
            pos = 0
            word_char_ranges: list[tuple[int, int]] = []
            for w in self._words:
                clean_w = w.text.strip()
                if not clean_w:
                    word_char_ranges.append((pos, pos))
                    continue
                idx = primary_body.find(clean_w, pos)
                if idx != -1:
                    end_idx = idx + len(clean_w)
                    word_char_ranges.append((idx, end_idx))
                    pos = end_idx
                else:
                    word_char_ranges.append((pos, pos + len(clean_w)))
                    pos += len(clean_w)

            for start_c, end_c in word_char_ranges:
                start_x = self._prefix_width + float(fm.horizontalAdvance(primary_body[:start_c]))
                end_x = self._prefix_width + float(fm.horizontalAdvance(primary_body[:end_c]))
                self._word_spans.append((start_x, end_x))

        self._primary_text_width = float(fm.horizontalAdvance(primary_body))

        if sec_start_in_body != -1 and self._secondary_words:
            self._secondary_base_x = self._prefix_width + float(fm.horizontalAdvance(lyric_body[:sec_start_in_body]))
            self._secondary_text_width = float(fm.horizontalAdvance(sec_str))

            pos = 0
            sec_ranges: list[tuple[int, int]] = []
            for sw in self._secondary_words:
                clean_sw = sw.text.strip()
                if not clean_sw:
                    sec_ranges.append((pos, pos))
                    continue
                idx = sec_str.find(clean_sw, pos)
                if idx != -1:
                    end_idx = idx + len(clean_sw)
                    sec_ranges.append((idx, end_idx))
                    pos = end_idx
                else:
                    sec_ranges.append((pos, pos + len(clean_sw)))
                    pos += len(clean_sw)

            for s_c, e_c in sec_ranges:
                start_x = float(fm.horizontalAdvance(sec_str[:s_c]))
                end_x = float(fm.horizontalAdvance(sec_str[:e_c]))
                self._secondary_word_spans.append((start_x, end_x))
        else:
            self._secondary_base_x = 0.0
            self._secondary_text_width = 0.0

        self._total_text_width = float(fm.horizontalAdvance(self._display_text))

    def _recompute_wipe(self) -> None:
        """Calculates exact wipe X coordinates for primary and secondary seekers."""
        if not self._words and not self._secondary_words:
            self._wipe_x = 0.0
            self._secondary_wipe_x = 0.0
            return

        primary_w = self._primary_text_width if self._secondary_words else self._total_text_width

        if self._row_state == "past":
            self._wipe_x = primary_w
            self._active_word_index = (len(self._words) - 1) if self._words else None
            self._word_progress = 1.0
            if self._secondary_words:
                self._secondary_wipe_x = self._secondary_text_width
                self._secondary_active_word_index = len(self._secondary_words) - 1
                self._secondary_word_progress = 1.0
            return

        if self._row_state == "upcoming" or not self._is_active:
            self._wipe_x = 0.0
            self._active_word_index = None
            self._word_progress = 0.0
            self._secondary_wipe_x = 0.0
            self._secondary_active_word_index = None
            self._secondary_word_progress = 0.0
            return

        pos_ms = self._position_ms

        if self._words and self._word_spans:
            first_w = self._words[0]
            last_w = self._words[-1]

            if pos_ms < first_w.start_ms:
                self._wipe_x = self._prefix_width
                self._active_word_index = None
                self._word_progress = 0.0
            elif pos_ms >= last_w.end_ms:
                self._wipe_x = primary_w
                self._active_word_index = len(self._words) - 1
                self._word_progress = 1.0
            else:
                found = False
                for idx, w in enumerate(self._words):
                    start_x, end_x = self._word_spans[idx]
                    if w.start_ms <= pos_ms <= w.end_ms:
                        span = max(1, w.end_ms - w.start_ms)
                        prog = max(0.0, min(1.0, (pos_ms - w.start_ms) / span))
                        if idx == len(self._words) - 1 and prog >= 0.98:
                            self._wipe_x = primary_w
                        else:
                            self._wipe_x = start_x + prog * (end_x - start_x)
                        self._active_word_index = idx
                        self._word_progress = prog
                        found = True
                        break
                    elif pos_ms < w.start_ms:
                        if idx > 0:
                            _, prev_end_x = self._word_spans[idx - 1]
                            self._wipe_x = prev_end_x
                            self._active_word_index = idx - 1
                            self._word_progress = 1.0
                        else:
                            self._wipe_x = self._prefix_width
                            self._active_word_index = None
                            self._word_progress = 0.0
                        found = True
                        break
                if not found:
                    self._wipe_x = primary_w
                    self._active_word_index = len(self._words) - 1
                    self._word_progress = 1.0
        else:
            # A line can have line-level timing on the primary text while only
            # a secondary/background lane has word timings. Keep the primary
            # line active instead of leaving it in the dim upcoming color.
            self._wipe_x = primary_w
            self._active_word_index = None
            self._word_progress = 0.0

        if self._secondary_words and self._secondary_word_spans:
            sec_w = self._secondary_text_width
            first_sw = self._secondary_words[0]
            last_sw = self._secondary_words[-1]

            if pos_ms < first_sw.start_ms:
                self._secondary_wipe_x = 0.0
                self._secondary_active_word_index = None
                self._secondary_word_progress = 0.0
            elif pos_ms >= last_sw.end_ms:
                self._secondary_wipe_x = sec_w
                self._secondary_active_word_index = len(self._secondary_words) - 1
                self._secondary_word_progress = 1.0
            else:
                found_sec = False
                for s_idx, sw in enumerate(self._secondary_words):
                    s_start_x, s_end_x = self._secondary_word_spans[s_idx]
                    if sw.start_ms <= pos_ms <= sw.end_ms:
                        span = max(1, sw.end_ms - sw.start_ms)
                        prog = max(0.0, min(1.0, (pos_ms - sw.start_ms) / span))
                        if s_idx == len(self._secondary_words) - 1 and prog >= 0.98:
                            self._secondary_wipe_x = sec_w
                        else:
                            self._secondary_wipe_x = s_start_x + prog * (s_end_x - s_start_x)
                        self._secondary_active_word_index = s_idx
                        self._secondary_word_progress = prog
                        found_sec = True
                        break
                    elif pos_ms < sw.start_ms:
                        if s_idx > 0:
                            _, prev_s_end = self._secondary_word_spans[s_idx - 1]
                            self._secondary_wipe_x = prev_s_end
                            self._secondary_active_word_index = s_idx - 1
                            self._secondary_word_progress = 1.0
                        else:
                            self._secondary_wipe_x = 0.0
                            self._secondary_active_word_index = None
                            self._secondary_word_progress = 0.0
                        found_sec = True
                        break
                if not found_sec:
                    self._secondary_wipe_x = sec_w
                    self._secondary_active_word_index = len(self._secondary_words) - 1
                    self._secondary_word_progress = 1.0
        else:
            self._secondary_wipe_x = 0.0
            self._secondary_active_word_index = None
            self._secondary_word_progress = 0.0

    @override
    def setText(self, a0: str | None) -> None:
        text = a0 or ""
        if "<span" in text or "<div" in text or "<p" in text or "<b" in text:
            self.setTextFormat(Qt.TextFormat.RichText)
            self._is_html_mode = True
        else:
            self._is_html_mode = False
        super().setText(text)

    @override
    def setFont(self, a0: QFont) -> None:
        super().setFont(a0)
        if getattr(self, "_display_text", None) or getattr(self, "_words", None):
            self._recompute_layout()
            self._recompute_wipe()

    @override
    def changeEvent(self, a0: QEvent | None) -> None:
        super().changeEvent(a0)
        if a0 and a0.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.PaletteChange,
        ):
            if getattr(self, "_display_text", None):
                self._recompute_layout()
                self._recompute_wipe()
                self.update()

    @override
    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height())

    @override
    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self._display_text) if getattr(self, "_display_text", None) else 0
        return QSize(w, fm.height())

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        if self._is_painting:
            return
        self._is_painting = True
        try:
            self._paint_event(a0)
        finally:
            self._is_painting = False

    def _paint_event(self, a0: QPaintEvent | None) -> None:
        if getattr(self, "_is_html_mode", False) or (
            not self._karaoke_enabled
            and not self._cue_dots_enabled
            and not self._break_visualizer_enabled
            and not getattr(self, "_is_notes_active", False)
            and not self._display_text
            and bool(self.text())
        ):
            super().paintEvent(a0)
            return

        if getattr(self, "_is_notes_active", False):
            self._paint_break_notes(a0)
            return

        if self._break_visualizer_enabled and self._is_visualizer_active:
            self._paint_break_visualizer(a0)
            return

        if getattr(self, "_break_wave_enabled", False):
            self._paint_break_wave(a0)
            return

        if self._cue_dots_enabled:
            self._paint_cue_dots(a0)
            return

        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        visible_w = float(rect.width())
        fm = self.fontMetrics()
        if self._display_text:
            real_text_w = float(fm.horizontalAdvance(self._display_text))
            if not self._karaoke_enabled or self._total_text_width <= 0.0:
                self._total_text_width = real_text_w
            else:
                self._total_text_width = max(self._total_text_width, real_text_w)
        total_w = self._total_text_width

        if self._beat_sparks_enabled or self._line_sparks_enabled:
            self._update_sparks()

        if self._auto_scroll_enabled and total_w > visible_w:
            if (
                self._secondary_words
                and self._secondary_active_word_index is not None
                and (self._active_word_index is None or self._word_progress >= 1.0)
            ):
                active_focus_x = self._secondary_base_x + self._secondary_wipe_x
            else:
                active_focus_x = self._wipe_x
            target_scroll = active_focus_x - (visible_w / 2.0)
            max_scroll = total_w - visible_w
            desired_scroll = max(0.0, min(float(max_scroll), float(target_scroll)))
            self._auto_scroll_offset += (desired_scroll - self._auto_scroll_offset) * 0.3
        else:
            self._auto_scroll_offset = 0.0

        is_transitioning = self.is_transitioning

        rect = QRectF(self.contentsRect())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        painter.setClipRect(rect.adjusted(0, -12, 0, 12))

        if is_transitioning and self._outgoing_layer is not None:
            p = self._transition_progress
            mode = self._transition_mode
            out_layer = self._outgoing_layer

            out_dx, out_dy, out_scale, out_opacity, out_clip = self._compute_layer_params(
                mode, p, is_incoming=False, rect=rect, total_w=out_layer.total_width
            )
            in_dx, in_dy, in_scale, in_opacity, in_clip = self._compute_layer_params(
                mode, p, is_incoming=True, rect=rect, total_w=self._total_text_width
            )

            if out_opacity > 0.001:
                self._paint_layer(
                    painter,
                    rect,
                    text=out_layer.text,
                    words=out_layer.words,
                    total_w=out_layer.total_width,
                    wipe_x=out_layer.wipe_x,
                    karaoke_enabled=out_layer.karaoke_enabled,
                    dx=out_dx,
                    dy=out_dy,
                    scale=out_scale,
                    opacity=out_opacity,
                    clip_rect=out_clip,
                )

            if in_opacity > 0.001:
                self._paint_layer(
                    painter,
                    rect,
                    text=self._display_text,
                    words=self._words,
                    total_w=self._total_text_width,
                    wipe_x=self._wipe_x,
                    karaoke_enabled=self._karaoke_enabled,
                    dx=in_dx,
                    dy=in_dy,
                    scale=in_scale,
                    opacity=in_opacity,
                    clip_rect=in_clip,
                )
        else:
            self._paint_layer(
                painter,
                rect,
                text=self._display_text,
                words=self._words,
                total_w=self._total_text_width,
                wipe_x=self._wipe_x,
                karaoke_enabled=self._karaoke_enabled,
                dx=0.0,
                dy=0.0,
                scale=self._scale_factor,
                opacity=1.0,
                clip_rect=None,
            )

        painter.end()

    def _paint_break_visualizer(self, a0: QPaintEvent | None) -> None:
        rect = self.contentsRect()
        visible_w = float(rect.width())
        visible_h = float(rect.height())
        fm = self.fontMetrics()

        prefix = self._visualizer_prefix
        font_h = float(fm.height())
        note_icon_size = max(14.0, font_h * 0.9)
        prefix_w = note_icon_size if prefix else 0.0
        y_center = float(rect.top()) + visible_h / 2.0

        fg_col = self.palette().color(self.foregroundRole())
        if fg_col.alpha() == 0 or (fg_col.red() == 0 and fg_col.green() == 0 and fg_col.blue() == 0):
            fg_col = QColor(255, 255, 255)

        if (
            self._album_color_mode in ("effects_only", "full")
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            active_col = self._current_album_color
        else:
            active_col = self._sung_color or fg_col

        dot_gap = max(8.0, font_h * 0.44)

        samples = self._visualizer_samples or [0.2] * 6
        style = (self._break_visualizer_style or "bars").lower()
        symmetry = self._break_visualizer_symmetry or ("mirrored" in style)
        is_waves = "waves" in style

        max_span = visible_w - prefix_w - (dot_gap if prefix else 0.0)
        count, bar_w, bar_gap, bars_span, wave_step = self._visualizer_geometry(len(samples), is_waves, max_span)
        n_pts = count if is_waves else 0
        n_bars = 0 if is_waves else count

        total_w = prefix_w + (dot_gap if prefix else 0.0) + bars_span

        valign = "middle" if symmetry else self._vis_vertical_alignment
        icon_cy = self._aligned_center(rect, note_icon_size, valign)

        align = self.alignment()
        if align & Qt.AlignmentFlag.AlignRight:
            start_x = float(rect.right()) - total_w
        elif align & Qt.AlignmentFlag.AlignHCenter:
            start_x = float(rect.left()) + max(0.0, (visible_w - total_w) / 2.0)
        else:
            start_x = float(rect.left())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        painter.setClipRect(rect)

        if prefix:
            s_col, f_col = get_two_tone_colors(active_col, self._album_secondary_color)
            icon_rect = QRectF(start_x, icon_cy - note_icon_size / 2.0, note_icon_size, note_icon_size)
            is_row_active = self._row_state != "past" and "paused" not in self._row_state
            paint_two_tone_note(
                painter,
                icon_rect,
                variant="beamed",
                stroke_color=s_col,
                fill_color=f_col,
                fill_opacity=0.35,
                opacity=1.0 if is_row_active else 0.5,
            )
            first_bar_x = start_x + prefix_w + dot_gap
        else:
            first_bar_x = start_x

        p = self._visualizer_progress
        if self._vis_min_bar_height is not None:
            min_h = float(self._vis_min_bar_height)
        else:
            min_h = max(3.0, font_h * 0.20)
        if self._vis_bar_height is not None:
            max_h = float(self._vis_bar_height)
        else:
            max_h = max(min_h + 4.0, font_h * 0.85)
        max_h = max(min(max_h, visible_h), min_h + 1.0)

        flip = valign == "top"
        region_h = min(max_h, visible_h)
        if valign == "top":
            region_top = float(rect.top())
        elif valign == "bottom":
            region_top = float(rect.top()) + visible_h - region_h
        else:
            region_top = float(rect.top()) + (visible_h - region_h) / 2.0
        y_base = region_top if flip else region_top + region_h

        drop_pulse = 0.0
        if p >= 0.95:
            drop_t = (p - 0.95) / 0.05
            drop_pulse = math.sin(drop_t * math.pi)

        painter.setPen(Qt.PenStyle.NoPen)

        if is_waves:
            step = wave_step
            pts_samples = samples[:n_pts] if len(samples) >= n_pts else samples + [0.2] * (n_pts - len(samples))
            wave_alpha = int(220 if drop_pulse > 0.0 else 185)
            wave_col = QColor(active_col.red(), active_col.green(), active_col.blue(), wave_alpha)

            if symmetry:
                top_points: list[QPointF] = []
                bot_points: list[QPointF] = []
                for i in range(n_pts):
                    amp = max(0.0, min(1.0, pts_samples[i]))
                    h = min_h + (max_h - min_h) * amp
                    if drop_pulse > 0.0:
                        h = max(min_h, h * (1.0 - 0.4 * drop_pulse) + max_h * 0.3 * drop_pulse)
                    cx = first_bar_x + float(i) * step
                    top_y = y_center - h / 2.0
                    bot_y = y_center + h / 2.0
                    top_points.append(QPointF(cx, top_y))
                    bot_points.append(QPointF(cx, bot_y))

                path = QPainterPath()
                path.moveTo(top_points[0].x(), y_center)
                path.lineTo(top_points[0])
                for pt in top_points[1:]:
                    path.lineTo(pt)
                for pt in reversed(bot_points):
                    path.lineTo(pt)
                path.closeSubpath()
                painter.setBrush(wave_col)
                painter.fillPath(path, wave_col)
            else:
                top_points = []
                for i in range(n_pts):
                    amp = max(0.0, min(1.0, pts_samples[i]))
                    h = min_h + (max_h - min_h) * amp
                    if drop_pulse > 0.0:
                        h = max(min_h, h * (1.0 - 0.4 * drop_pulse) + max_h * 0.3 * drop_pulse)
                    cx = first_bar_x + float(i) * step
                    top_y = y_base + h if flip else y_base - h
                    top_points.append(QPointF(cx, top_y))

                path = QPainterPath()
                path.moveTo(first_bar_x, y_base)
                path.lineTo(top_points[0])
                for pt in top_points[1:]:
                    path.lineTo(pt)
                path.lineTo(first_bar_x + bars_span, y_base)
                path.closeSubpath()
                painter.setBrush(wave_col)
                painter.fillPath(path, wave_col)
        else:
            for i in range(n_bars):
                amp = max(0.0, min(1.0, samples[i] if i < len(samples) else 0.2))
                h = min_h + (max_h - min_h) * amp
                if drop_pulse > 0.0:
                    h = max(min_h, h * (1.0 - 0.4 * drop_pulse) + max_h * 0.3 * drop_pulse)

                bar_x = first_bar_x + float(i) * (bar_w + bar_gap)
                if symmetry:
                    bar_y = y_center - h / 2.0
                else:
                    bar_y = y_base if flip else y_base - h

                alpha = int((0.45 + 0.55 * amp) * 255)
                if drop_pulse > 0.0:
                    alpha = min(255, int(alpha + drop_pulse * 40))

                bar_col = QColor(active_col.red(), active_col.green(), active_col.blue(), alpha)
                painter.setBrush(bar_col)
                radius = min(self._vis_bar_radius, bar_w / 2.0, h / 2.0)
                painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, h), radius, radius)

        painter.end()

    def _compute_layer_params(
        self,
        mode: str,
        p: float,
        is_incoming: bool,
        rect: QRectF,
        total_w: float,
    ) -> tuple[float, float, float, float, QRectF | None]:
        visible_w = float(rect.width())
        visible_h = float(rect.height())

        if mode == "slide_up":
            if is_incoming:
                dy = visible_h * 0.70 * (1.0 - p)
                opacity = max(0.0, min(1.0, p))
            else:
                dy = -visible_h * 0.70 * p
                opacity = max(0.0, min(1.0, 1.0 - p))
            return 0.0, dy, 1.0, opacity, None

        elif mode == "scale":
            if is_incoming:
                scale = 0.88 + 0.12 * p
                opacity = max(0.0, min(1.0, p))
            else:
                scale = max(0.0, 1.0 - 0.12 * p)
                opacity = max(0.0, min(1.0, 1.0 - p))
            return 0.0, 0.0, scale, opacity, None

        elif mode == "wipe":
            p_clamped = max(0.0, min(1.0, p))
            split_x = float(rect.left()) + visible_w * p_clamped
            if is_incoming:
                clip = QRectF(float(rect.left()), float(rect.top()), max(0.0, split_x - float(rect.left())), visible_h)
                return 0.0, 0.0, 1.0, 1.0, clip
            else:
                clip = QRectF(split_x, float(rect.top()), max(0.0, float(rect.right()) - split_x), visible_h)
                opacity = max(0.0, min(1.0, 1.0 - p_clamped * 0.25))
                return 0.0, 0.0, 1.0, opacity, clip

        opacity = 1.0 if is_incoming else 0.0
        return 0.0, 0.0, 1.0, opacity, None

    def _paint_layer(
        self,
        painter: QPainter,
        rect: QRectF,
        text: str,
        words: list[Word] | None,
        total_w: float,
        wipe_x: float,
        karaoke_enabled: bool,
        dx: float,
        dy: float,
        scale: float,
        opacity: float,
        clip_rect: QRectF | None,
    ) -> None:
        """Paints a single layer of text with transform, opacity, and karaoke/plain styling."""
        if not text:
            return

        visible_w = float(rect.width())
        visible_h = float(rect.height())
        fm = self.fontMetrics()
        real_text_w = float(fm.horizontalAdvance(text))
        if not karaoke_enabled or total_w <= 0.0:
            total_w = real_text_w
        else:
            total_w = max(total_w, real_text_w)

        align = self.alignment()
        if align & Qt.AlignmentFlag.AlignRight:
            base_x = float(rect.right()) - total_w
        elif align & Qt.AlignmentFlag.AlignHCenter:
            base_x = float(rect.left()) + max(0.0, (visible_w - total_w) / 2.0)
        else:
            base_x = float(rect.left())

        if self._auto_scroll_enabled and total_w > visible_w:
            base_x = float(rect.left()) - self._auto_scroll_offset

        ascent = float(fm.ascent())
        descent = float(fm.descent())
        y_baseline = float(rect.top()) + (visible_h + ascent - descent) / 2.0

        fg_col = self.palette().color(self.foregroundRole())
        if fg_col.alpha() == 0 or (fg_col.red() == 0 and fg_col.green() == 0 and fg_col.blue() == 0):
            fg_col = QColor(255, 255, 255)

        if (
            self._album_color_mode == "full"
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            active_col = self._current_album_color
        else:
            active_col = self._sung_color or fg_col

        upcoming_col = self._upcoming_color or QColor(
            active_col.red(),
            active_col.green(),
            active_col.blue(),
            max(40, int(active_col.alpha() * 0.35)),
        )

        audio_reactive = (
            self._karaoke_beat_glow_enabled
            or self._beat_sparks_enabled
            or self._beat_syllable_float_enabled
            or self._line_sparks_enabled
            or self._line_beat_glow_enabled
            or self._line_beat_bounce_enabled
        )
        energy = min(1.0, self._bass_energy * 1.35) if audio_reactive else 0.0
        mixed_line_mode = karaoke_enabled and not words and bool(self._secondary_words)
        if mixed_line_mode and self._line_beat_bounce_enabled and self._is_active:
            dy = -1.6 * energy

        painter.save()

        if clip_rect is not None:
            painter.setClipRect(clip_rect, Qt.ClipOperation.IntersectClip)

        painter.setOpacity(max(0.0, min(1.0, opacity)))

        eff_scale = scale
        if total_w > 0.0 and eff_scale > 1.0:
            max_allowed_w = max(10.0, visible_w - 6.0)
            if total_w * eff_scale > max_allowed_w:
                eff_scale = max(1.0, max_allowed_w / total_w)

        if dx != 0.0 or dy != 0.0 or eff_scale != 1.0:
            align = self.alignment()
            if align & Qt.AlignmentFlag.AlignRight:
                center_x = base_x + total_w
            elif align & Qt.AlignmentFlag.AlignLeft:
                center_x = base_x
            else:
                center_x = base_x + total_w / 2.0
            center_y = float(rect.top()) + visible_h / 2.0
            painter.translate(center_x + dx, center_y + dy)
            if eff_scale != 1.0:
                painter.scale(eff_scale, eff_scale)
            painter.translate(-center_x, -center_y)

        text_pos = QPointF(base_x, y_baseline)
        glow_base = self._resolve_glow_color(active_col)

        clip_top = float(rect.top()) - abs(dy) - 50.0
        clip_h = visible_h + abs(dy) * 2.0 + 100.0

        active_float_spans: list[tuple[float, float, float, float]] = []

        if karaoke_enabled:
            if (
                words
                and self._word_spans
                and self._active_word_index is not None
                and 0 <= self._active_word_index < len(words)
                and 0 <= self._active_word_index < len(self._word_spans)
            ):
                p_idx = self._active_word_index
                p_word = words[p_idx]
                is_last_word = p_idx == len(words) - 1
                is_word_active = (
                    self._word_progress < 1.0 and p_word.start_ms <= self._position_ms <= p_word.end_ms
                ) or (
                    is_last_word
                    and self._is_active
                    and self._row_state != "past"
                    and self._position_ms >= p_word.start_ms
                )

                if is_word_active:
                    p_float_dy = (-1.0 * energy) if (self._beat_syllable_float_enabled and energy > 0.08) else 0.0
                    p_wobble_scale = 1.0

                    if self._syllable_physics_enabled:
                        time_since_start = float(self._position_ms - p_word.start_ms)
                        if 0.0 <= time_since_start <= 750.0:
                            if time_since_start < 125.0:
                                w = time_since_start / 125.0
                            else:
                                w = max(0.0, 1.0 - (time_since_start - 125.0) / 625.0)
                            p_wobble_scale = 1.0 + (w * 0.025)

                    p_tot_dy = p_float_dy
                    p_s_x, p_e_x = self._word_spans[p_idx]
                    if (p_tot_dy != 0.0 or p_wobble_scale != 1.0) and p_e_x > p_s_x:
                        active_float_spans.append((p_s_x, p_e_x, p_tot_dy, p_wobble_scale))

            if (
                self._secondary_words
                and self._secondary_word_spans
                and self._secondary_active_word_index is not None
                and 0 <= self._secondary_active_word_index < len(self._secondary_words)
                and 0 <= self._secondary_active_word_index < len(self._secondary_word_spans)
            ):
                s_idx = self._secondary_active_word_index
                s_word = self._secondary_words[s_idx]
                is_sec_last_word = s_idx == len(self._secondary_words) - 1
                is_sec_active = (
                    self._secondary_word_progress < 1.0 and s_word.start_ms <= self._position_ms <= s_word.end_ms
                ) or (
                    is_sec_last_word
                    and self._is_active
                    and self._row_state != "past"
                    and self._position_ms >= s_word.start_ms
                )

                if is_sec_active:
                    s_float_dy = (-1.0 * energy) if (self._beat_syllable_float_enabled and energy > 0.08) else 0.0
                    s_wobble_scale = 1.0

                    if self._syllable_physics_enabled:
                        time_since_start = float(self._position_ms - s_word.start_ms)
                        if 0.0 <= time_since_start <= 750.0:
                            if time_since_start < 125.0:
                                w = time_since_start / 125.0
                            else:
                                w = max(0.0, 1.0 - (time_since_start - 125.0) / 625.0)
                            s_wobble_scale = 1.0 + (w * 0.025)

                    s_tot_dy = s_float_dy
                    rel_s_x, rel_e_x = self._secondary_word_spans[s_idx]
                    abs_s_x = self._secondary_base_x + rel_s_x
                    abs_e_x = self._secondary_base_x + rel_e_x
                    if (s_tot_dy != 0.0 or s_wobble_scale != 1.0) and abs_e_x > abs_s_x:
                        active_float_spans.append((abs_s_x, abs_e_x, s_tot_dy, s_wobble_scale))

        def _draw_text_strip(
            target_clip: QRectF | None,
            pen: QColor | QPen,
            strip_opacity: float = 1.0,
        ) -> None:
            painter.save()
            if target_clip is not None:
                painter.setClipRect(target_clip, Qt.ClipOperation.IntersectClip)
            if strip_opacity < 0.999:
                painter.setOpacity(max(0.0, min(1.0, opacity * strip_opacity)))
            painter.setPen(pen)

            if not active_float_spans:
                painter.drawText(text_pos, text)
                painter.restore()
                return

            sorted_spans = sorted(active_float_spans, key=lambda s: s[0])

            cur_x = 0.0
            for span_start_x, span_end_x, span_shift_y, span_wobble_scale in sorted_spans:
                if span_start_x > cur_x:
                    painter.save()
                    left_pad = 100.0 if cur_x == 0.0 else 0.0
                    painter.setClipRect(
                        QRectF(base_x + cur_x - left_pad, clip_top, (span_start_x - cur_x) + left_pad, clip_h),
                        Qt.ClipOperation.IntersectClip,
                    )
                    painter.drawText(text_pos, text)
                    painter.restore()

                painter.save()
                painter.setClipRect(
                    QRectF(base_x + span_start_x, clip_top, span_end_x - span_start_x, clip_h),
                    Qt.ClipOperation.IntersectClip,
                )
                if span_wobble_scale != 1.0:
                    s_cx = base_x + (span_start_x + span_end_x) / 2.0
                    s_cy = y_baseline + span_shift_y
                    painter.translate(s_cx, s_cy)
                    painter.scale(span_wobble_scale, span_wobble_scale)
                    painter.translate(-s_cx, -s_cy)
                painter.drawText(QPointF(base_x, y_baseline + span_shift_y), text)
                painter.restore()

                cur_x = max(cur_x, span_end_x)

            if cur_x < total_w:
                painter.save()
                painter.setClipRect(
                    QRectF(base_x + cur_x, clip_top, max(1.0, total_w - cur_x + 100.0), clip_h),
                    Qt.ClipOperation.IntersectClip,
                )
                painter.drawText(text_pos, text)
                painter.restore()

            painter.restore()

        if karaoke_enabled and (words or self._secondary_words):
            _draw_text_strip(target_clip=None, pen=upcoming_col)

            primary_w = self._primary_text_width if self._secondary_words else total_w

            if wipe_x > 0.0:
                is_prim_finished = wipe_x >= (primary_w - 0.5)
                solid_prim_w = (
                    (total_w + 50.0)
                    if (not self._secondary_words and is_prim_finished)
                    else (primary_w if is_prim_finished else wipe_x)
                )
                _draw_text_strip(
                    target_clip=QRectF(base_x, clip_top, solid_prim_w, clip_h),
                    pen=active_col,
                )

            if self._secondary_words and self._secondary_wipe_x > 0.0:
                sec_wipe = self._secondary_wipe_x
                is_sec_finished = sec_wipe >= (self._secondary_text_width - 0.5)
                solid_sec_w = (self._secondary_text_width + 50.0) if is_sec_finished else sec_wipe
                _draw_text_strip(
                    target_clip=QRectF(base_x + self._secondary_base_x, clip_top, solid_sec_w, clip_h),
                    pen=active_col,
                )

            if mixed_line_mode and self._line_beat_glow_enabled and energy > 0.03 and self._is_active:
                painter.save()
                painter.setClipRect(
                    QRectF(base_x, clip_top, primary_w, clip_h),
                    Qt.ClipOperation.IntersectClip,
                )
                aura_alpha = int(36 * energy)
                line_glow = QColor(glow_base.red(), glow_base.green(), glow_base.blue(), aura_alpha)
                painter.setPen(line_glow)
                for ox, oy in [(-1.5, 0), (1.5, 0), (0, -1.5), (0, 1.5)]:
                    painter.drawText(QPointF(text_pos.x() + ox, text_pos.y() + oy), text)
                painter.restore()

            if self._karaoke_beat_glow_enabled and energy > 0.03:
                flares_to_draw: list[tuple[float, float]] = []  # (needle_x, wipe_distance)
                if wipe_x > 0.0 and (self._active_word_index is not None and self._word_progress < 1.0):
                    flares_to_draw.append((base_x + min(wipe_x, primary_w), wipe_x))
                if (
                    self._secondary_words
                    and self._secondary_wipe_x > 0.0
                    and (self._secondary_active_word_index is not None and self._secondary_word_progress < 1.0)
                ):
                    flares_to_draw.append(
                        (
                            base_x + self._secondary_base_x + min(self._secondary_wipe_x, self._secondary_text_width),
                            self._secondary_wipe_x,
                        )
                    )

                # Hold the active line after the vocal track ends.
                if not flares_to_draw and self._is_active and total_w > 0.0:
                    is_prim_done = wipe_x >= (primary_w - 0.5)
                    is_sec_done = (not self._secondary_words) or (
                        self._secondary_wipe_x >= (self._secondary_text_width - 0.5)
                    )
                    if is_prim_done and is_sec_done:
                        parked_end_x = min(
                            total_w,
                            (self._secondary_base_x + self._secondary_text_width)
                            if self._secondary_words
                            else primary_w,
                        )
                        flares_to_draw.append((base_x + parked_end_x, parked_end_x))

                for needle_x, cur_w in flares_to_draw:
                    flare_w = min(cur_w, 16.0 + 12.0 * energy)

                    painter.save()
                    clip_flare = QRectF(needle_x - flare_w, clip_top, flare_w, clip_h)
                    painter.setClipRect(clip_flare, Qt.ClipOperation.IntersectClip)

                    grad = QLinearGradient(needle_x - flare_w, 0, needle_x, 0)
                    grad.setColorAt(0.0, QColor(glow_base.red(), glow_base.green(), glow_base.blue(), 0))
                    grad.setColorAt(0.7, QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(45 * energy)))
                    grad.setColorAt(
                        1.0, QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(130 * energy))
                    )

                    painter.fillRect(
                        QRectF(needle_x - flare_w, y_baseline - ascent * 0.85, flare_w, ascent + descent),
                        grad,
                    )

                    spark_alpha = int(140 * energy)
                    spark_col = QColor(
                        min(255, active_col.red() + int(40 * energy)),
                        min(255, active_col.green() + int(40 * energy)),
                        min(255, active_col.blue() + int(40 * energy)),
                        spark_alpha,
                    )
                    _draw_text_strip(target_clip=clip_flare, pen=spark_col)

                    beam_alpha = int(min(255, 60 + 195 * energy))
                    beam_col = QColor(glow_base.red(), glow_base.green(), glow_base.blue(), beam_alpha)
                    painter.setPen(QPen(beam_col, 1.2))
                    painter.drawLine(
                        QPointF(needle_x - 0.5, y_baseline - ascent * 0.70),
                        QPointF(needle_x - 0.5, y_baseline + descent * 0.40),
                    )

                    painter.restore()

            if self._beat_sparks_enabled and self._sparks:
                painter.save()
                clip_sparks = QRectF(base_x - 35.0, clip_top, total_w + 55.0, clip_h)
                painter.setClipRect(clip_sparks, Qt.ClipOperation.IntersectClip)

                for sp in self._sparks:
                    prog = max(0.0, min(1.0, sp.life / max(0.001, sp.max_life)))

                    if prog < 0.15:
                        scale = (prog / 0.15) * 1.15
                    elif prog < 0.60:
                        scale = 1.15 - 0.20 * ((prog - 0.15) / 0.45)
                    else:
                        scale = max(0.05, 0.95 * (1.0 - (prog - 0.60) / 0.40))

                    twinkle = 0.78 + 0.22 * math.sin(sp.life * sp.twinkle_freq + sp.twinkle_phase)
                    fade = 1.0 - (prog**1.3)
                    alpha = int(max(0, min(255, sp.alpha * fade * twinkle)))

                    if alpha <= 4 or scale <= 0.05:
                        continue

                    sp_col = QColor(glow_base.red(), glow_base.green(), glow_base.blue(), alpha)
                    core_col = QColor(255, 255, 255, min(255, int(alpha * 0.95)))

                    curr_x = base_x + sp.x
                    curr_y = sp.y
                    current_size = max(0.7, sp.size * scale)

                    if current_size >= 1.5:
                        halo_r = current_size * 2.2
                        halo_grad = QRadialGradient(curr_x, curr_y, halo_r)
                        halo_grad.setColorAt(
                            0.0,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(alpha * 0.35)),
                        )
                        halo_grad.setColorAt(
                            0.55,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(alpha * 0.12)),
                        )
                        halo_grad.setColorAt(
                            1.0,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), 0),
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(halo_grad))
                        painter.drawEllipse(QPointF(curr_x, curr_y), halo_r, halo_r)

                    if sp.spark_type == "star":
                        rv = current_size * 1.35
                        rh = current_size * 0.95
                        ri_diag = current_size * 0.24 * 0.7071

                        painter.save()
                        painter.translate(curr_x, curr_y)
                        if sp.rotation != 0.0:
                            painter.rotate(sp.rotation)

                        star_outer = QPolygonF(
                            [
                                QPointF(0.0, -rv),
                                QPointF(ri_diag, -ri_diag),
                                QPointF(rh, 0.0),
                                QPointF(ri_diag, ri_diag),
                                QPointF(0.0, rv),
                                QPointF(-ri_diag, ri_diag),
                                QPointF(-rh, 0.0),
                                QPointF(-ri_diag, -ri_diag),
                            ]
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawPolygon(star_outer)

                        if current_size > 1.2:
                            crv = rv * 0.45
                            crh = rh * 0.45
                            cri = ri_diag * 0.45
                            star_inner = QPolygonF(
                                [
                                    QPointF(0.0, -crv),
                                    QPointF(cri, -cri),
                                    QPointF(crh, 0.0),
                                    QPointF(cri, cri),
                                    QPointF(0.0, crv),
                                    QPointF(-cri, cri),
                                    QPointF(-crh, 0.0),
                                    QPointF(-cri, -cri),
                                ]
                            )
                            painter.setBrush(QBrush(core_col))
                            painter.drawPolygon(star_inner)

                        painter.restore()

                    elif sp.spark_type == "diamond":
                        rv = current_size * 1.2
                        rh = current_size * 0.55

                        painter.save()
                        painter.translate(curr_x, curr_y)
                        if sp.rotation != 0.0:
                            painter.rotate(sp.rotation)

                        diamond_outer = QPolygonF(
                            [
                                QPointF(0.0, -rv),
                                QPointF(rh, 0.0),
                                QPointF(0.0, rv),
                                QPointF(-rh, 0.0),
                            ]
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawPolygon(diamond_outer)

                        if current_size > 1.2:
                            diamond_inner = QPolygonF(
                                [
                                    QPointF(0.0, -rv * 0.45),
                                    QPointF(rh * 0.45, 0.0),
                                    QPointF(0.0, rv * 0.45),
                                    QPointF(-rh * 0.45, 0.0),
                                ]
                            )
                            painter.setBrush(QBrush(core_col))
                            painter.drawPolygon(diamond_inner)

                        painter.restore()

                    else:  # "ember"
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawEllipse(QPointF(curr_x, curr_y), current_size, current_size)

                        if current_size > 0.9:
                            painter.setBrush(QBrush(core_col))
                            painter.drawEllipse(
                                QPointF(curr_x, curr_y),
                                current_size * 0.45,
                                current_size * 0.45,
                            )

                painter.restore()

        else:
            bounce_dy = 0.0
            if self._line_beat_bounce_enabled and energy > 0.04 and self._is_active:
                bounce_dy = -1.6 * energy

            draw_text_pos = QPointF(text_pos.x(), text_pos.y() + bounce_dy)

            if self._line_beat_glow_enabled and energy > 0.03 and self._is_active:
                painter.save()
                aura_alpha_1 = int(36 * energy)
                painter.setPen(QPen(QColor(glow_base.red(), glow_base.green(), glow_base.blue(), aura_alpha_1)))
                for ox, oy in [(-1.5, 0), (1.5, 0), (0, -1.5), (0, 1.5)]:
                    painter.drawText(QPointF(draw_text_pos.x() + ox, draw_text_pos.y() + oy), text)

                aura_alpha_2 = int(72 * energy)
                painter.setPen(QPen(QColor(glow_base.red(), glow_base.green(), glow_base.blue(), aura_alpha_2)))
                for ox, oy in [(-0.8, -0.8), (0.8, 0.8), (-0.8, 0.8), (0.8, -0.8)]:
                    painter.drawText(QPointF(draw_text_pos.x() + ox, draw_text_pos.y() + oy), text)
                painter.restore()

            if self._line_beat_glow_enabled and energy > 0.03 and self._is_active:
                flash_boost = int(45 * energy)
                flash_col = QColor(
                    min(255, active_col.red() + flash_boost),
                    min(255, active_col.green() + flash_boost),
                    min(255, active_col.blue() + flash_boost),
                    active_col.alpha(),
                )
                painter.setPen(flash_col)
                painter.drawText(draw_text_pos, text)
            else:
                painter.setPen(active_col)
                painter.drawText(draw_text_pos, text)

            if self._line_sparks_enabled and self._sparks and self._is_active:
                painter.save()
                clip_sparks = QRectF(base_x - 35.0, clip_top, total_w + 70.0, clip_h)
                painter.setClipRect(clip_sparks, Qt.ClipOperation.IntersectClip)

                for sp in self._sparks:
                    prog = max(0.0, min(1.0, sp.life / max(0.001, sp.max_life)))

                    if prog < 0.15:
                        scale = (prog / 0.15) * 1.15
                    elif prog < 0.60:
                        scale = 1.15 - 0.20 * ((prog - 0.15) / 0.45)
                    else:
                        scale = max(0.05, 0.95 * (1.0 - (prog - 0.60) / 0.40))

                    twinkle = 0.78 + 0.22 * math.sin(sp.life * sp.twinkle_freq + sp.twinkle_phase)
                    fade = 1.0 - (prog**1.3)
                    alpha = int(max(0, min(255, sp.alpha * fade * twinkle)))

                    if alpha <= 4 or scale <= 0.05:
                        continue

                    sp_col = QColor(glow_base.red(), glow_base.green(), glow_base.blue(), alpha)
                    core_col = QColor(255, 255, 255, min(255, int(alpha * 0.95)))

                    curr_x = base_x + sp.x
                    curr_y = sp.y + bounce_dy
                    current_size = max(0.7, sp.size * scale)

                    if current_size >= 1.5:
                        halo_r = current_size * 2.2
                        halo_grad = QRadialGradient(curr_x, curr_y, halo_r)
                        halo_grad.setColorAt(
                            0.0,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(alpha * 0.35)),
                        )
                        halo_grad.setColorAt(
                            0.55,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), int(alpha * 0.12)),
                        )
                        halo_grad.setColorAt(
                            1.0,
                            QColor(glow_base.red(), glow_base.green(), glow_base.blue(), 0),
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(halo_grad))
                        painter.drawEllipse(QPointF(curr_x, curr_y), halo_r, halo_r)

                    if sp.spark_type == "star":
                        rv = current_size * 1.35
                        rh = current_size * 0.95
                        ri_diag = current_size * 0.24 * 0.7071

                        painter.save()
                        painter.translate(curr_x, curr_y)
                        if sp.rotation != 0.0:
                            painter.rotate(sp.rotation)

                        star_outer = QPolygonF(
                            [
                                QPointF(0.0, -rv),
                                QPointF(ri_diag, -ri_diag),
                                QPointF(rh, 0.0),
                                QPointF(ri_diag, ri_diag),
                                QPointF(0.0, rv),
                                QPointF(-ri_diag, ri_diag),
                                QPointF(-rh, 0.0),
                                QPointF(-ri_diag, -ri_diag),
                            ]
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawPolygon(star_outer)

                        if current_size > 1.2:
                            crv = rv * 0.45
                            crh = rh * 0.45
                            cri = ri_diag * 0.45
                            star_inner = QPolygonF(
                                [
                                    QPointF(0.0, -crv),
                                    QPointF(cri, -cri),
                                    QPointF(crh, 0.0),
                                    QPointF(cri, cri),
                                    QPointF(0.0, crv),
                                    QPointF(-cri, cri),
                                    QPointF(-crh, 0.0),
                                    QPointF(-cri, -cri),
                                ]
                            )
                            painter.setBrush(QBrush(core_col))
                            painter.drawPolygon(star_inner)
                        painter.restore()

                    elif sp.spark_type == "diamond":
                        rv = current_size * 1.2
                        rh = current_size * 0.55

                        painter.save()
                        painter.translate(curr_x, curr_y)
                        if sp.rotation != 0.0:
                            painter.rotate(sp.rotation)

                        diamond_outer = QPolygonF(
                            [
                                QPointF(0.0, -rv),
                                QPointF(rh, 0.0),
                                QPointF(0.0, rv),
                                QPointF(-rh, 0.0),
                            ]
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawPolygon(diamond_outer)

                        if current_size > 1.2:
                            diamond_inner = QPolygonF(
                                [
                                    QPointF(0.0, -rv * 0.45),
                                    QPointF(rh * 0.45, 0.0),
                                    QPointF(0.0, rv * 0.45),
                                    QPointF(-rh * 0.45, 0.0),
                                ]
                            )
                            painter.setBrush(QBrush(core_col))
                            painter.drawPolygon(diamond_inner)
                        painter.restore()

                    else:  # "ember"
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(sp_col))
                        painter.drawEllipse(QPointF(curr_x, curr_y), current_size, current_size)

                        if current_size > 0.9:
                            painter.setBrush(QBrush(core_col))
                            painter.drawEllipse(
                                QPointF(curr_x, curr_y),
                                current_size * 0.45,
                                current_size * 0.45,
                            )

                painter.restore()

        painter.restore()

    def _resolve_glow_color(self, active_col: QColor) -> QColor:
        """Resolves the best neon bloom color for audio-reactive text glow."""
        if (
            self._album_color_mode in ("effects_only", "full")
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            return self._current_album_color

        if self._glow_color is not None and self._glow_color.isValid():
            return self._glow_color

        _, s, _, _ = active_col.getHsv()
        if (s or 0) >= 40:
            return active_col

        hi = self.palette().color(self.palette().ColorRole.Highlight)
        if hi.isValid():
            _, hi_s, _, _ = hi.getHsv()
            if (hi_s or 0) >= 40:
                return hi

        return QColor(208, 171, 249)

    def _paint_break_wave(self, a0: QPaintEvent | None) -> None:
        """Paints a wavy countdown indicator for instrumental breaks."""
        rect = self.contentsRect()
        visible_w = float(rect.width())
        visible_h = float(rect.height())
        if visible_w <= 0 or visible_h <= 0:
            return

        y_mid = float(rect.top()) + visible_h / 2.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        painter.setClipRect(rect)

        fg_col = self.palette().color(self.foregroundRole())
        if fg_col.alpha() == 0 or (fg_col.red() == 0 and fg_col.green() == 0 and fg_col.blue() == 0):
            fg_col = QColor(255, 255, 255)

        if (
            self._album_color_mode in ("effects_only", "full")
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            accent_col = self._current_album_color
        else:
            accent_col = self._sung_color or fg_col

        dim_col = QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 60)

        sec_text = f"{self._break_wave_remaining_sec}s" if self._break_wave_remaining_sec > 0 else "♪"
        badge_font = QFont(self.font())
        badge_font.setBold(True)
        badge_font.setPointSizeF(max(8.0, badge_font.pointSizeF() - 1.0))
        painter.setFont(badge_font)
        badge_fm = QFontMetrics(badge_font)
        badge_w = float(badge_fm.horizontalAdvance(sec_text)) + 14.0
        badge_h = float(badge_fm.height()) + 2.0

        total_track_w = min(180.0, max(120.0, visible_w - 40.0))
        cx = float(rect.left()) + visible_w / 2.0
        badge_rect = QRectF(cx - badge_w / 2.0, y_mid - badge_h / 2.0, badge_w, badge_h)

        left_track_start = cx - total_track_w / 2.0
        left_track_end = badge_rect.left() - 6.0
        right_track_start = badge_rect.right() + 6.0
        right_track_end = cx + total_track_w / 2.0

        p = self._break_wave_progress
        wavelength = 14.0
        is_row_active = self._row_state != "past" and "paused" not in self._row_state
        amplitude = 3.2 if is_row_active else 1.5

        def build_wave(x1: float, x2: float) -> QPainterPath:
            path = QPainterPath()
            if x2 <= x1:
                return path
            path.moveTo(x1, y_mid)
            steps = int(max(4, (x2 - x1) / 2.0))
            for s in range(1, steps + 1):
                cur_x = x1 + (x2 - x1) * (s / steps)
                cur_y = y_mid + amplitude * math.sin((cur_x - left_track_start) / wavelength * 2.0 * math.pi)
                path.lineTo(cur_x, cur_y)
            return path

        left_path = build_wave(left_track_start, left_track_end)
        right_path = build_wave(right_track_start, right_track_end)

        painter.setPen(QPen(dim_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(left_path)
        painter.drawPath(right_path)

        if p > 0.001 and is_row_active:
            fill_x = left_track_start + total_track_w * p
            painter.save()
            painter.setClipRect(QRectF(left_track_start - 2.0, y_mid - 20.0, fill_x - left_track_start + 2.0, 40.0))
            painter.setPen(QPen(accent_col, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(left_path)
            painter.drawPath(right_path)
            painter.restore()

        pill_bg = QColor(255, 255, 255, 25) if is_row_active else QColor(255, 255, 255, 12)
        painter.setPen(QPen(dim_col, 1.0))
        painter.setBrush(QBrush(pill_bg))
        painter.drawRoundedRect(badge_rect, badge_h / 2.0, badge_h / 2.0)

        if sec_text == "♪":
            s_col, f_col = get_two_tone_colors(accent_col, self._album_secondary_color)
            icon_sz = min(badge_w, badge_h) * 0.72
            icon_rect = QRectF(cx - icon_sz / 2.0, y_mid - icon_sz / 2.0, icon_sz, icon_sz)
            paint_two_tone_note(
                painter,
                icon_rect,
                variant="single",
                stroke_color=s_col,
                fill_color=f_col,
                fill_opacity=0.35,
                opacity=1.0 if is_row_active else 0.5,
            )
        else:
            text_pen = QColor(255, 255, 255, 230) if is_row_active else dim_col
            painter.setPen(text_pen)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, sec_text)

    def _paint_cue_dots(self, a0: QPaintEvent | None) -> None:
        """Paints Apple Music style breathing / vocal cue dots."""
        rect = self.contentsRect()
        visible_w = float(rect.width())
        visible_h = float(rect.height())
        fm = self.fontMetrics()

        prefix = self._cue_prefix
        if self._cue_is_searching and prefix.endswith("..."):
            prefix = prefix[:-3].strip()
        font_h = float(fm.height())
        note_icon_size = max(14.0, font_h * 0.9)
        prefix_w = note_icon_size if prefix else 0.0
        y_center = float(rect.top()) + visible_h / 2.0

        fg_col = self.palette().color(self.foregroundRole())
        if fg_col.alpha() == 0 or (fg_col.red() == 0 and fg_col.green() == 0 and fg_col.blue() == 0):
            fg_col = QColor(255, 255, 255)

        if (
            self._album_color_mode in ("effects_only", "full")
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            active_col = self._current_album_color
        else:
            active_col = self._sung_color or fg_col

        base_r = max(2.2, font_h * 0.12)
        active_r = max(4.0, font_h * 0.24)
        dot_gap = max(8.5, font_h * 0.46)

        dots_span = 2.0 * dot_gap
        total_w = prefix_w + (dot_gap if prefix else 0.0) + dots_span

        row_h = max(note_icon_size if prefix else 0.0, 2.0 * active_r)
        y_center = self._aligned_center(rect, row_h, self._effective_valign(), pad=2.0)

        align = self.alignment()
        if align & Qt.AlignmentFlag.AlignRight:
            start_x = float(rect.right()) - total_w
        elif align & Qt.AlignmentFlag.AlignHCenter:
            start_x = float(rect.left()) + max(0.0, (visible_w - total_w) / 2.0)
        else:
            start_x = float(rect.left())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        painter.setClipRect(rect)

        if prefix:
            s_col, f_col = get_two_tone_colors(active_col, self._album_secondary_color)
            icon_rect = QRectF(start_x, y_center - note_icon_size / 2.0, note_icon_size, note_icon_size)
            is_row_active = self._row_state != "past" and "paused" not in self._row_state
            paint_two_tone_note(
                painter,
                icon_rect,
                variant="single",
                stroke_color=s_col,
                fill_color=f_col,
                fill_opacity=0.35,
                opacity=1.0 if is_row_active else 0.5,
            )
            first_dot_x = start_x + prefix_w + dot_gap
        else:
            first_dot_x = start_x

        p = self._cue_progress
        is_searching = self._cue_is_searching
        is_past = self._row_state == "past"

        for i in range(3):
            dot_x = first_dot_x + float(i) * dot_gap
            dot_y = y_center

            if is_searching:
                theta = (self._cue_phase * 2.0 * math.pi * 1.3) - (float(i) * 0.85)
                wave = (math.sin(theta) + 1.0) / 2.0
                s = wave * wave * (3.0 - 2.0 * wave)
                r = base_r + (active_r - base_r) * s
                alpha = 0.30 + 0.70 * s
                dot_y -= 1.6 * s
            else:
                w_start = float(i) * 0.33
                w_end = min(0.95, (float(i) + 1.0) * 0.33 if i < 2 else 0.95)

                if p < w_start:
                    s = 0.0
                elif p >= w_end:
                    s = 1.0
                else:
                    t = (p - w_start) / max(0.01, w_end - w_start)
                    s = t * t * (3.0 - 2.0 * t)

                r = base_r + (active_r - base_r) * s
                alpha = 0.30 + 0.70 * s

                bass = self._bass_energy
                if bass > 0.04 and not is_past:
                    kick_lift = 2.4 * bass * (0.6 + 0.4 * s)
                    dot_y -= kick_lift
                    r += active_r * 0.45 * bass * (0.6 + 0.4 * s)

                if p >= 0.95 and not is_past:
                    drop_t = (p - 0.95) / 0.05
                    drop_pulse = math.sin(drop_t * math.pi)
                    r += active_r * 0.28 * drop_pulse
                    alpha = min(1.0, alpha + 0.2 * drop_pulse)
                    dot_y -= 1.4 * drop_pulse

                if bass > 0.15 and not is_past and (s > 0.08 or p < 0.01):
                    halo_r = r * 2.6
                    bloom_alpha = int(110 * bass * (0.4 + 0.6 * s))
                    if bloom_alpha > 5:
                        halo_grad = QRadialGradient(QPointF(dot_x, dot_y), halo_r)
                        halo_grad.setColorAt(
                            0.0, QColor(active_col.red(), active_col.green(), active_col.blue(), bloom_alpha)
                        )
                        halo_grad.setColorAt(
                            0.5,
                            QColor(active_col.red(), active_col.green(), active_col.blue(), int(bloom_alpha * 0.35)),
                        )
                        halo_grad.setColorAt(1.0, QColor(active_col.red(), active_col.green(), active_col.blue(), 0))
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(halo_grad))
                        painter.drawEllipse(QPointF(dot_x, dot_y), halo_r, halo_r)

            if self._album_secondary_color:
                col1, col2 = get_two_tone_colors(active_col, self._album_secondary_color)
                t_dot = float(i) / 2.0
                d_r = int(col1.red() + (col2.red() - col1.red()) * t_dot)
                d_g = int(col1.green() + (col2.green() - col1.green()) * t_dot)
                d_b = int(col1.blue() + (col2.blue() - col1.blue()) * t_dot)
                dot_col = QColor(d_r, d_g, d_b, int(max(0.0, min(1.0, alpha)) * 255))
            else:
                dot_col = QColor(
                    active_col.red(),
                    active_col.green(),
                    active_col.blue(),
                    int(max(0.0, min(1.0, alpha)) * 255),
                )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot_col)
            painter.drawEllipse(QPointF(dot_x, dot_y), r, r)

        painter.end()

    def _paint_break_notes(self, a0: QPaintEvent | None) -> None:
        rect = self.contentsRect()
        visible_w = float(rect.width())
        visible_h = float(rect.height())
        if visible_w <= 0 or visible_h <= 0:
            return

        fm = self.fontMetrics()
        font_h = float(fm.height())
        note_sz = max(14.0, font_h * 0.9)
        gap = max(8.0, font_h * 0.44)
        total_w = 3.0 * note_sz + 2.0 * gap

        align = self.alignment()
        if align & Qt.AlignmentFlag.AlignRight:
            start_x = float(rect.right()) - total_w
        elif align & Qt.AlignmentFlag.AlignHCenter:
            start_x = float(rect.left()) + max(0.0, (visible_w - total_w) / 2.0)
        else:
            start_x = float(rect.left())

        start_y = self._aligned_center(rect, note_sz, self._effective_valign(), pad=4.0) - note_sz / 2.0

        fg_col = self.palette().color(self.foregroundRole())
        if fg_col.alpha() == 0 or (fg_col.red() == 0 and fg_col.green() == 0 and fg_col.blue() == 0):
            fg_col = QColor(255, 255, 255)

        if (
            self._album_color_mode in ("effects_only", "full")
            and self._current_album_color is not None
            and self._current_album_color.isValid()
        ):
            active_col = self._current_album_color
        else:
            active_col = self._sung_color or fg_col

        col1, col2 = get_two_tone_colors(active_col, self._album_secondary_color)
        variants: list[Literal["single", "beamed"]] = ["single", "beamed", "single"]

        ahead_stroke = QColor(255, 255, 255, 70)
        ahead_fill = QColor(255, 255, 255, 28)
        past_stroke = QColor(255, 255, 255, 45)
        past_fill = QColor(255, 255, 255, 20)

        p = self._notes_progress
        is_past = self._row_state == "past"
        anim_enabled = getattr(self, "_notes_animated", True)

        drop_pulse = 0.0
        if anim_enabled and p >= 0.95:
            drop_t = (p - 0.95) / 0.05
            drop_pulse = math.sin(drop_t * math.pi)

        bass = self._bass_energy if anim_enabled else 0.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(rect)

        for i in range(3):
            nx = start_x + float(i) * (note_sz + gap)
            ny = start_y
            note_p = max(0.0, min(1.0, p * 3.0 - float(i)))

            active_mult = 0.5 + 0.5 * note_p
            stagger = 1.0 if i == 0 else (1.15 if i == 1 else 0.9)
            cur_lift = -3.8 * bass * active_mult * stagger
            if drop_pulse > 0.0 and not is_past:
                cur_lift -= 1.8 * drop_pulse

            cur_ny = ny + cur_lift

            scale_pop = 1.0
            if bass > 0.04 and not is_past:
                scale_pop += 0.16 * bass * active_mult
            if drop_pulse > 0.0 and not is_past:
                scale_pop += 0.12 * drop_pulse

            if bass > 0.18 and note_p > 0.05 and not is_past:
                halo_sz = note_sz * 1.8 * scale_pop
                halo_cx = nx + note_sz / 2.0
                halo_cy = cur_ny + note_sz / 2.0
                halo_alpha = int(95 * bass * note_p)
                if halo_alpha > 5:
                    halo_grad = QRadialGradient(QPointF(halo_cx, halo_cy), halo_sz / 2.0)
                    halo_grad.setColorAt(0.0, QColor(col1.red(), col1.green(), col1.blue(), halo_alpha))
                    halo_grad.setColorAt(0.5, QColor(col1.red(), col1.green(), col1.blue(), int(halo_alpha * 0.35)))
                    halo_grad.setColorAt(1.0, QColor(col1.red(), col1.green(), col1.blue(), 0))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(halo_grad))
                    painter.drawEllipse(QPointF(halo_cx, halo_cy), halo_sz / 2.0, halo_sz / 2.0)

            note_rect = QRectF(nx, cur_ny, note_sz, note_sz)

            if is_past:
                paint_two_tone_note(
                    painter,
                    note_rect,
                    variant=variants[i],
                    stroke_color=past_stroke,
                    fill_color=past_fill,
                    fill_opacity=0.20,
                    opacity=0.45,
                )
            else:
                t = note_p * note_p * (3.0 - 2.0 * note_p)

                s_r = int(ahead_stroke.red() + (col1.red() - ahead_stroke.red()) * t)
                s_g = int(ahead_stroke.green() + (col1.green() - ahead_stroke.green()) * t)
                s_b = int(ahead_stroke.blue() + (col1.blue() - ahead_stroke.blue()) * t)
                s_a = int(ahead_stroke.alpha() + (col1.alpha() - ahead_stroke.alpha()) * t)
                cur_stroke = QColor(s_r, s_g, s_b, s_a)

                f_r = int(ahead_fill.red() + (col2.red() - ahead_fill.red()) * t)
                f_g = int(ahead_fill.green() + (col2.green() - ahead_fill.green()) * t)
                f_b = int(ahead_fill.blue() + (col2.blue() - ahead_fill.blue()) * t)
                f_a = int(ahead_fill.alpha() + (col2.alpha() - ahead_fill.alpha()) * t)
                cur_fill = QColor(f_r, f_g, f_b, f_a)

                fill_op = 0.20 + 0.25 * t
                op = 0.50 + 0.50 * t
                if drop_pulse > 0.0:
                    op = min(1.0, op + 0.2 * drop_pulse)

                if abs(scale_pop - 1.0) > 0.005:
                    painter.save()
                    cx = note_rect.center().x()
                    cy = note_rect.center().y()
                    painter.translate(cx, cy)
                    painter.scale(scale_pop, scale_pop)
                    painter.translate(-cx, -cy)
                    paint_two_tone_note(
                        painter,
                        note_rect,
                        variant=variants[i],
                        stroke_color=cur_stroke,
                        fill_color=cur_fill,
                        fill_opacity=fill_op,
                        opacity=op,
                    )
                    painter.restore()
                else:
                    paint_two_tone_note(
                        painter,
                        note_rect,
                        variant=variants[i],
                        stroke_color=cur_stroke,
                        fill_color=cur_fill,
                        fill_opacity=fill_op,
                        opacity=op,
                    )

        painter.end()

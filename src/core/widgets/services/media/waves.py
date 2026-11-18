"""Three inexpensive decorative wave layers, modulated by native audio samples."""

import colorsys
import math
import time
from typing import override

from PIL import Image
from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QHideEvent, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QShowEvent

from core.widgets.services.audio_visualizer.paint import AudioVizCanvas

WAVE_PALETTES = {
    "blue": "#379cff",
    "cyan": "#24d8d0",
    "orange": "#ed9900",
    "green": "#50bb75",
}
_HUES = {name: QColor(color).hsvHueF() for name, color in WAVE_PALETTES.items()}
WAVE_SPEED = 3.5


def choose_wave_palette(image: Image.Image | None) -> str:
    if image is None:
        return "blue"
    sample = image.convert("RGB").resize((16, 16))
    votes = dict.fromkeys(WAVE_PALETTES, 0.0)
    pixels = sample.tobytes()  # pyright: ignore[reportUnknownMemberType] - Pillow leaves encoder varargs untyped.
    for index in range(0, len(pixels), 3):
        red, green, blue = pixels[index : index + 3]
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        if saturation < 0.18 or value < 0.12:
            continue
        palette = min(_HUES, key=lambda name: min(abs(hue - _HUES[name]), 1 - abs(hue - _HUES[name])))
        votes[palette] += saturation * value
    return max(votes, key=lambda name: votes[name]) if any(votes.values()) else "blue"


def wave_profile(position: float, layer: int, phase: float, energy: float) -> float:
    """A smooth envelope tapers every layer to zero at the track's two ends."""
    if position <= 0 or position >= 1:
        return 0.0
    envelope = math.sin(math.pi * position) ** 1.3
    offset = phase + layer * 1.7
    crests = 0.58 + 0.23 * math.sin(2 * math.pi * position * 1.2 + offset)
    crests += 0.13 * math.sin(2 * math.pi * position * 2.6 - offset * 0.7)
    amplitude = (0.62 + 0.28 * min(1.0, max(0.0, energy))) * (1 - layer * 0.10)
    return min(1.0, max(0.0, envelope * crests * amplitude))


def _tint(color: QColor, white: float) -> QColor:
    return QColor(
        *(round(component + (255 - component) * white) for component in (color.red(), color.green(), color.blue()))
    )


class LayeredWaveCanvas(AudioVizCanvas):
    def __init__(self, width: int, height: int):
        super().__init__(
            style="waves",
            height=height,
            columns=80,
            canvas_width=width,
            item_width=1,
            item_gap=0,
            mirror=False,
            stereo=False,
            edge_fade_left=0,
            edge_fade_right=0,
        )
        self.palette_name = "blue"
        self._gradients: tuple[QLinearGradient, ...] = ()
        self._gradient_key: tuple[str, int] | None = None
        self._energy = 0.0
        self._target_energy = 0.0
        self._last_tick = time.monotonic()
        self._animation_timer = QTimer(self)
        self._animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._animate)

    @override
    def set_samples(self, samples: list[float]) -> None:
        self._target_energy = min(1.0, max(0.0, sum(samples) / max(1, len(samples))))
        self.samples = samples

    def _animate(self) -> None:
        now = time.monotonic()
        elapsed = min(0.1, max(0.0, now - self._last_tick))
        self._last_tick = now
        self._energy += (self._target_energy - self._energy) * (1 - math.exp(-elapsed / 0.06))
        self.update()

    @override
    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        self._last_tick = time.monotonic()
        self._animation_timer.start()

    @override
    def hideEvent(self, a0: QHideEvent | None) -> None:
        self._animation_timer.stop()
        super().hideEvent(a0)

    def set_palette(self, name: str) -> None:
        self.palette_name = name if name in WAVE_PALETTES else "blue"
        self._gradient_key = None
        self.update()

    def _brushes(self) -> tuple[QLinearGradient, ...]:
        key = (self.palette_name, self.height())
        if key != self._gradient_key:
            color = QColor(WAVE_PALETTES[self.palette_name])
            gradients: list[QLinearGradient] = []
            for layer in range(3):
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0, _tint(color, 0.90 - layer * 0.20))
                gradient.setColorAt(1, _tint(color, 0.60 - layer * 0.25))
                gradients.append(gradient)
            self._gradients = tuple(gradients)
            self._gradient_key = key
        return self._gradients

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        width, height = self.width(), self.height()
        if width < 2:
            return
        phase = time.monotonic() * WAVE_SPEED
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for layer, gradient in enumerate(self._brushes()):
                path = QPainterPath(QPointF(0, height))
                previous = QPointF(0, height)
                for index in range(1, 49):
                    position = index / 48
                    point = QPointF(position * width, height * (1 - wave_profile(position, layer, phase, self._energy)))
                    path.quadTo(previous, (previous + point) / 2)
                    previous = point
                path.lineTo(previous)
                path.lineTo(width, height)
                path.closeSubpath()
                painter.setOpacity(0.78 + layer * 0.10)
                painter.fillPath(path, gradient)

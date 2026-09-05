"""Paint surface for the audio visualizer.

Everything that depends only on geometry (column positions, edge-fade
opacities, the colour brush and the fade mask) is built once and reused, so a
frame costs no more than the fills it actually needs.
"""

import logging

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QFrame


class AudioVizCanvas(QFrame):
    """Fixed-size widget that paints spectrum samples."""

    def __init__(
        self,
        *,
        style: str,
        height: int,
        columns: int,
        canvas_width: int,
        item_width: int,
        item_gap: int,
        gradient: bool,
        mirror: bool,
        stereo: bool,
        colors: list[QColor],
        edge_fade_left: int,
        edge_fade_right: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.style_name = style
        self.item_width = max(1, item_width)
        self.item_gap = max(0, item_gap)
        self.gradient = gradient
        self.mirror = mirror
        self.stereo = stereo
        self.colors = colors
        self.edge_fade_left = max(0, edge_fade_left)
        self.edge_fade_right = max(0, edge_fade_right)
        self.faded = bool(self.edge_fade_left or self.edge_fade_right)
        self.samples: list[float] = [0.0] * columns

        self._paint_failed = False
        self._brush_cache: QColor | QLinearGradient | None = None
        self._column_cache: dict[int, tuple[list[int], list[float], list[QColor]]] = {}
        self._fade_mask: QLinearGradient | None = None
        self._layer: QPixmap | None = None
        self._layer_key: tuple[int, int, float] | None = None

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWidth(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedSize(max(8, canvas_width), max(4, height))

    def set_samples(self, samples: list[float]) -> None:
        if samples == self.samples:
            return  # nothing moved, so there is nothing to repaint
        self.samples = samples
        self.update()

    def reset(self) -> None:
        """Blank the surface immediately, without waiting for a fade-out."""
        self.set_samples([0.0] * len(self.samples))

    def paintEvent(self, _event) -> None:
        if not self.samples:
            return
        try:
            with QPainter(self) as painter:
                if self.style_name == "waves":
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    self._paint_waves(painter)
                elif self.style_name == "dots":
                    self._paint_dots(painter)
                else:
                    self._paint_bars(painter)
        except Exception:
            if not self._paint_failed:
                self._paint_failed = True
                logging.warning("Audio visualizer paint failed; suppressing further paint errors", exc_info=True)

    def _columns(self, count: int) -> tuple[list[int], list[float], list[QColor]]:
        """Left edge, edge-fade opacity and colour for each column."""
        cached = self._column_cache.get(count)
        if cached is not None:
            return cached

        width = self.width()
        if self.style_name == "dots":
            size = self.item_width
            pitch = max(self.item_width + self.item_gap, width // max(1, count))
            offset = (pitch - size) // 2
            xs = [i * pitch + offset for i in range(count)]
        else:
            step = self.item_width + self.item_gap
            start = self.item_gap // 2
            xs = [start + i * step for i in range(count)]

        centre = self.item_width / 2.0
        opacities = [self._fade_at(x + centre, width) for x in xs]
        palette = [self.colors[i % len(self.colors)] for i in range(count)]
        result = (xs, opacities, palette)
        self._column_cache[count] = result
        return result

    def _brush(self) -> QColor | QLinearGradient:
        if self._brush_cache is None:
            if self.gradient and len(self.colors) > 1:
                gradient = QLinearGradient(0, 1, 0, 0)
                gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                step = 1.0 / (len(self.colors) - 1)
                for i, color in enumerate(self.colors):
                    gradient.setColorAt(i * step, color)
                self._brush_cache = gradient
            else:
                self._brush_cache = self.colors[0]
        return self._brush_cache

    _FADE_STEPS = 16

    @staticmethod
    def _ease(t: float) -> float:
        return t * t * (3 - 2 * t)

    def _fade_at(self, x: float, width: float) -> float:
        left = self.edge_fade_left
        right = self.edge_fade_right
        if left <= 0 and right <= 0:
            return 1.0
        if left > 0 and right > 0:
            left = min(left, width / 2)
            right = min(right, width / 2)
        else:
            left = min(left, width) if left > 0 else 0
            right = min(right, width) if right > 0 else 0
        if left > 0 and x <= left:
            return self._ease(max(0.0, x / left))
        if right > 0 and x >= width - right:
            return self._ease(max(0.0, (width - x) / right))
        return 1.0

    def _fade_gradient(self) -> QLinearGradient:
        """Horizontal alpha ramp used to mask the wave fill in one pass."""
        if self._fade_mask is not None:
            return self._fade_mask

        width = float(self.width())
        left = self.edge_fade_left
        right = self.edge_fade_right
        if left > 0 and right > 0:
            left = min(left, width / 2)
            right = min(right, width / 2)
        else:
            left = min(left, width) if left > 0 else 0
            right = min(right, width) if right > 0 else 0

        opaque = QColor(255, 255, 255, 255)
        gradient = QLinearGradient(0.0, 0.0, width, 0.0)
        steps = self._FADE_STEPS
        if left > 0:
            for i in range(steps + 1):
                t = i / steps
                alpha = round(self._ease(t) * 255)
                gradient.setColorAt(t * left / width, QColor(255, 255, 255, alpha))
        else:
            gradient.setColorAt(0.0, opaque)
        if right > 0:
            for i in range(steps + 1):
                t = i / steps
                alpha = round(self._ease(t) * 255)
                gradient.setColorAt(1.0 - t * right / width, QColor(255, 255, 255, alpha))
        else:
            gradient.setColorAt(1.0, opaque)
        self._fade_mask = gradient
        return gradient

    def _masking_layer(self, ratio: float) -> QPixmap:
        """Scratch surface for compositing the wave fill with the fade mask."""
        key = (self.width(), self.height(), ratio)
        if self._layer_key != key or self._layer is None:
            layer = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
            layer.setDevicePixelRatio(ratio)
            self._layer = layer
            self._layer_key = key
        return self._layer

    @staticmethod
    def _clamp_sample(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _paint_bars(self, painter: QPainter) -> None:
        h = self.height()
        brush = self._brush()
        bar_w = self.item_width
        xs, opacities, _ = self._columns(len(self.samples))
        faded = self.faded
        mirror = self.mirror
        ratio = self.devicePixelRatioF()

        # Painting straight onto `painter` would let Qt's own logical->physical
        # transform round each bar's edges independently: at a fractional scale
        # (125%, 150%) a 1-2px bar can then land on a different physical width
        # per bar, even though every bar asks for the same width. Deriving every
        # bar's position from one fixed physical step (rather than rounding each
        # bar's logical position separately) keeps the gaps between bars just as
        # constant as the bars themselves.
        layer = self._masking_layer(ratio)
        layer.setDevicePixelRatio(1.0)
        layer.fill(Qt.GlobalColor.transparent)
        n = len(self.samples)
        bar_w_phys = max(1, round(bar_w * ratio))
        step_phys = round((xs[1] - xs[0]) * ratio) if n > 1 else 0
        start_phys = round(xs[0] * ratio) if n else 0
        h_phys = layer.height()
        with QPainter(layer) as lp:
            for i, sample in enumerate(self.samples):
                sample = self._clamp_sample(sample)
                bar_h = max(1, min(h, round(sample * h)))
                bar_h_phys = max(1, round(bar_h * ratio))
                y_phys = (h_phys - bar_h_phys) // 2 if mirror else h_phys - bar_h_phys
                if faded:
                    lp.setOpacity(opacities[i])
                x_phys = start_phys + i * step_phys
                lp.fillRect(QRect(x_phys, y_phys, bar_w_phys, bar_h_phys), brush)

        layer.setDevicePixelRatio(ratio)
        painter.drawPixmap(0, 0, layer)

    def _paint_dots(self, painter: QPainter) -> None:
        size = self.item_width
        pitch = size + self.item_gap
        h = self.height()
        slots = max(1, (h - size) // pitch + 1) if pitch > 0 else 1
        xs, opacities, palette = self._columns(len(self.samples))
        faded = self.faded
        mirror = self.mirror
        ratio = self.devicePixelRatioF()

        layer = self._masking_layer(ratio)
        layer.setDevicePixelRatio(1.0)
        layer.fill(Qt.GlobalColor.transparent)
        n = len(self.samples)
        size_phys = max(1, round(size * ratio))
        step_phys = round((xs[1] - xs[0]) * ratio) if n > 1 else 0
        start_phys = round(xs[0] * ratio) if n else 0
        v_pitch_phys = max(1, round(pitch * ratio))
        h_phys = layer.height()
        with QPainter(layer) as lp:
            lp.setPen(Qt.PenStyle.NoPen)
            for i, sample in enumerate(self.samples):
                sample = self._clamp_sample(sample)
                lit = max(1, min(slots, round(sample * slots)))
                if faded:
                    lp.setOpacity(opacities[i])
                x_phys = start_phys + i * step_phys
                color = palette[i]
                start = (slots - lit) // 2 if mirror else 0
                for s in range(start, start + lit):
                    y_phys = h_phys - size_phys - s * v_pitch_phys
                    if y_phys < 0:
                        break
                    lp.fillRect(QRect(x_phys, y_phys, size_phys, size_phys), color)

        layer.setDevicePixelRatio(ratio)
        painter.drawPixmap(0, 0, layer)

    def _paint_waves(self, painter: QPainter) -> None:
        samples = self.samples
        if len(samples) < 2:
            return

        w = float(self.width())
        h = self.height()
        brush = self._brush()

        if self.stereo and len(samples) >= 4:
            # The widget gives the left channel the larger half when the band
            # count is odd (right_bands = n // 2), so split there, not at n // 2.
            mid = len(samples) - len(samples) // 2
            half = w / 2.0
            path = self._wave_path(samples[:mid], 0.0, half, h)
            path.addPath(self._wave_path(samples[mid:], half, w - half, h))
        else:
            path = self._wave_path(samples, 0.0, w, h)

        if not self.faded:
            painter.fillPath(path, brush)
            return

        # Fill once into a scratch layer and knock the edges out with a cached
        # alpha ramp. Masking per column would cost one full path fill per pixel
        # of width.
        layer = self._masking_layer(self.devicePixelRatioF())
        layer.fill(Qt.GlobalColor.transparent)
        with QPainter(layer) as mask_painter:
            mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            mask_painter.fillPath(path, brush)
            mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            mask_painter.fillRect(0, 0, self.width(), h, self._fade_gradient())
        painter.drawPixmap(0, 0, layer)

    def _wave_path(self, samples: list[float], x0: float, width: float, height: int) -> QPainterPath:
        path = QPainterPath()
        if not samples:
            return path

        mirror = self.mirror
        centre = height / 2.0

        def edges(sample: float) -> tuple[float, float]:
            """(top, bottom) y for one sample: floor-anchored, or split around centre."""
            bar_h = max(1, min(height, round(self._clamp_sample(sample) * height)))
            if mirror:
                half = bar_h / 2.0
                return centre - half, centre + half
            return float(height - bar_h), float(height)

        n = len(samples)
        step = width / max(1, n)
        xs = [x0 + i * step + step / 2.0 for i in range(n)]
        tops = [edges(s)[0] for s in samples]

        top0, bottom0 = edges(samples[0])
        path.moveTo(x0, bottom0)
        path.lineTo(x0, top0)
        self._curve_through(path, xs, tops)

        top_last, bottom_last = edges(samples[-1])
        path.lineTo(x0 + width, top_last)
        path.lineTo(x0 + width, bottom_last)
        if mirror:
            # Floor-anchored waves close along the flat bottom edge for free
            # (closeSubpath draws straight back to (x0, height)); a mirrored
            # wave needs that bottom edge traced back the same way the top was.
            bottoms = [edges(s)[1] for s in samples]
            self._curve_through(path, list(reversed(xs)), list(reversed(bottoms)))
        path.closeSubpath()
        return path

    @staticmethod
    def _curve_through(path: QPainterPath, xs: list[float], ys: list[float]) -> None:
        n = len(xs)
        path.lineTo(xs[0], ys[0])
        for i in range(1, n):
            mid_x = (xs[i - 1] + xs[i]) / 2.0
            mid_y = (ys[i - 1] + ys[i]) / 2.0
            path.quadTo(xs[i - 1], ys[i - 1], mid_x, mid_y)
        path.lineTo(xs[-1], ys[-1])

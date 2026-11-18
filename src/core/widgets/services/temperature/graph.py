"""Native stat graph in Celsius, with time-positioned gaps for missing readings."""

import math
from typing import override

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from core.utils.stat_popup import GraphWidget
from core.validation.widgets.yasb.temperature import SensorThresholds
from core.widgets.services.temperature.libre import HistoryPoint


class TemperatureGraph(GraphWidget):
    def __init__(self, show_grid: bool = False):
        self._readings: tuple[HistoryPoint, ...] = ()
        self._now = 0.0
        self._seconds = 120
        self.minimum = 0.0
        self.maximum = 100.0
        super().__init__("temperature-graph", show_grid)
        self.set_fill_enabled(False)

    def set_readings(
        self, readings: tuple[HistoryPoint, ...], now: float, seconds: int, thresholds: SensorThresholds | None = None
    ) -> None:
        self._readings, self._now, self._seconds = readings, now, seconds
        values = [value for _, value in readings if value is not None]
        self.minimum = min(0.0, math.floor(min(values) / 20) * 20) if values else 0.0
        self.maximum = max(100.0, math.ceil(max(values) / 20) * 20) if values else 100.0
        bands: list[tuple[float, float, str]] = []
        if thresholds is not None:
            span = self.maximum - self.minimum
            warning = min(100.0, max(0.0, (thresholds.warning - self.minimum) / span * 100))
            critical = min(100.0, max(0.0, (thresholds.critical - self.minimum) / span * 100))
            bands = [(0, warning, "#4cc2ff"), (warning, critical, "#f9c859"), (critical, 100, "#e76060")]
        self.set_color_bands(bands)
        self._rebuild_paths()
        self.update()

    @override
    def _rebuild_paths(self) -> None:
        self._line_path = None
        self._fill_path = None
        if not self._readings:
            return
        path = QPainterPath()
        points: list[QPointF] = []
        pad = self.STROKE_WIDTH / 2
        start = self._now - self._seconds

        def append_segment() -> None:
            if len(points) >= 2:
                path.addPath(self._build_smooth_path(points))
            elif points:
                point = points[0]
                path.moveTo(max(0.0, point.x() - 1), point.y())
                path.lineTo(point)
            points.clear()

        for timestamp, value in self._readings:
            if timestamp < start:
                continue
            if value is None:
                append_segment()
                continue
            x = max(0.0, min(float(self.width()), (timestamp - start) / self._seconds * self.width()))
            fraction = (value - self.minimum) / (self.maximum - self.minimum)
            points.append(QPointF(x, pad + (self.height() - 2 * pad) * (1 - fraction)))
        append_segment()
        self._line_path = path
        self._fill_path = QPainterPath()

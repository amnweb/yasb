"""The day ribbon: one date's light, painted from the API's own solar moments.

The band is a horizontal gradient whose stops sit at the times the API actually
returned for this location on this date, so the band's proportions *are* the
day's: a brief dawn wash near the equator, a long one in a northern summer.  The
configured prayers are ticked onto it and the current moment gets a stem, which
puts "where am I in the day" in one glance rather than in a column of numbers.

Every colour and dimension arrives from the stylesheet as a ``-qproperty-``, so
the ribbon carries no appearance of its own (see docs/Styling.md).
"""

from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QFrame

from core.utils.widgets.prayer_times.schedule import DAWN, DAY, DUSK, NIGHT


@dataclass(frozen=True)
class RibbonMark:
    """A prayer ticked onto the band, positioned as a 0..1 fraction of the window."""

    at: float
    passed: bool


class DayRibbon(QFrame):
    """A single day's light as a gradient band, ticked with its prayers.

    The widget holds no schedule of its own: ``set_day`` hands it fractions the
    caller has already resolved against the ribbon's time window, which keeps every
    datetime decision in the Qt-free schedule module.
    """

    def __init__(self, parent: QFrame | None = None):
        super().__init__(parent)
        self._stops: list[tuple[float, str]] = []
        self._marks: list[RibbonMark] = []
        self._now: float | None = None

        # Fallbacks only; styles.css overrides every one of these through -qproperty-.
        self._night = QColor("#181825")
        self._dawn = QColor("#74c7ec")
        self._day = QColor("#f9e2af")
        self._dusk = QColor("#fab387")
        self._tick = QColor(255, 255, 255, 110)
        self._passed_tick = QColor(0, 0, 0, 70)
        self._now_color = QColor("#cdd6f4")

        self._band_height = 10
        self._tick_width = 2
        self._tick_height = 4
        self._now_radius = 3

    # ------------------------------------------------------------------
    # Stylesheet-facing properties
    # ------------------------------------------------------------------

    @pyqtProperty(QColor)
    def nightcolor(self) -> QColor:
        return self._night

    @nightcolor.setter
    def nightcolor(self, value: QColor) -> None:
        self._night = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def dawncolor(self) -> QColor:
        return self._dawn

    @dawncolor.setter
    def dawncolor(self, value: QColor) -> None:
        self._dawn = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def daycolor(self) -> QColor:
        return self._day

    @daycolor.setter
    def daycolor(self, value: QColor) -> None:
        self._day = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def duskcolor(self) -> QColor:
        return self._dusk

    @duskcolor.setter
    def duskcolor(self, value: QColor) -> None:
        self._dusk = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def tickcolor(self) -> QColor:
        return self._tick

    @tickcolor.setter
    def tickcolor(self, value: QColor) -> None:
        self._tick = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def passedtickcolor(self) -> QColor:
        return self._passed_tick

    @passedtickcolor.setter
    def passedtickcolor(self, value: QColor) -> None:
        self._passed_tick = QColor(value)
        self.update()

    @pyqtProperty(QColor)
    def nowcolor(self) -> QColor:
        return self._now_color

    @nowcolor.setter
    def nowcolor(self, value: QColor) -> None:
        self._now_color = QColor(value)
        self.update()

    @pyqtProperty(int)
    def bandheight(self) -> int:
        return self._band_height

    @bandheight.setter
    def bandheight(self, value: int) -> None:
        self._band_height = max(1, int(value))
        self.updateGeometry()
        self.update()

    @pyqtProperty(int)
    def tickwidth(self) -> int:
        return self._tick_width

    @tickwidth.setter
    def tickwidth(self, value: int) -> None:
        self._tick_width = max(0, int(value))
        self.update()

    @pyqtProperty(int)
    def tickheight(self) -> int:
        return self._tick_height

    @tickheight.setter
    def tickheight(self, value: int) -> None:
        self._tick_height = max(0, int(value))
        self.updateGeometry()
        self.update()

    @pyqtProperty(int)
    def nowradius(self) -> int:
        return self._now_radius

    @nowradius.setter
    def nowradius(self, value: int) -> None:
        self._now_radius = max(0, int(value))
        self.updateGeometry()
        self.update()

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def set_day(
        self,
        stops: list[tuple[float, str]],
        marks: list[RibbonMark],
        now: float | None,
    ) -> None:
        """Set the band's gradient stops, its prayer ticks and the current moment.

        All three are 0..1 fractions of the ribbon's window.  *now* is None when the
        current moment falls outside that window, which is what the popup shows on an
        evening it has already moved on to tomorrow's schedule.
        """
        self._stops = stops
        self._marks = marks
        self._now = now
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        # Room for the now cap above the band, the band, a breathing gap, and the tick
        # lane below it; the stylesheet can still set min-height and max-height on top.
        return QSize(0, self._now_radius + self._band_height + 3 + self._tick_height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return self.sizeHint()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _role_color(self, role: str) -> QColor:
        return {NIGHT: self._night, DAWN: self._dawn, DAY: self._day, DUSK: self._dusk}.get(role, self._night)

    def _band_brush(self, band: QRectF) -> QBrush:
        gradient = QLinearGradient(band.left(), 0.0, band.right(), 0.0)
        if not self._stops:
            gradient.setColorAt(0.0, self._night)
            gradient.setColorAt(1.0, self._night)
        else:
            for fraction, role in self._stops:
                gradient.setColorAt(min(max(fraction, 0.0), 1.0), self._role_color(role))
        return QBrush(gradient)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        rect = QRectF(self.rect())
        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        # The band's light runs unbroken and the prayers annotate it from a lane below.
        # Cutting the ticks through the band instead segmented it, and a day's light does
        # not come in segments; it also made the whole thing read as a progress bar.
        tick_lane = float(self._tick_height) if self._marks else 0.0
        band_height = min(float(self._band_height), max(rect.height() - tick_lane, 1.0))
        band_top = rect.top() + max((rect.height() - tick_lane - band_height) / 2, 0.0)
        band = QRectF(rect.left(), band_top, rect.width(), band_height)

        path = QPainterPath()
        path.addRoundedRect(band, band.height() / 2, band.height() / 2)
        painter.fillPath(path, self._band_brush(band))

        if self._tick_width > 0 and tick_lane > 0:
            lane_top = rect.bottom() - tick_lane
            for mark in self._marks:
                x = band.left() + min(max(mark.at, 0.0), 1.0) * band.width()
                x = min(max(x, band.left() + self._tick_width / 2), band.right() - self._tick_width / 2)
                notch = QRectF(x - self._tick_width / 2, lane_top, float(self._tick_width), tick_lane)
                notch_path = QPainterPath()
                notch_path.addRoundedRect(notch, self._tick_width / 2, self._tick_width / 2)
                painter.fillPath(notch_path, self._passed_tick if mark.passed else self._tick)

        if self._now is None:
            return
        # The stem is exactly a tick wide, so the current moment reads as one more mark on
        # the same scale rather than a control you could drag; the cap is what sets it apart.
        stem_width = float(max(self._tick_width, 1))
        x = band.left() + min(max(self._now, 0.0), 1.0) * band.width()
        # Keep the stem whole at either end of the window instead of half-clipping it.
        x = min(max(x, band.left() + stem_width / 2), band.right() - stem_width / 2)
        stem = QRectF(x - stem_width / 2, rect.top(), stem_width, rect.height())
        stem_path = QPainterPath()
        stem_path.addRoundedRect(stem, stem_width / 2, stem_width / 2)
        painter.fillPath(stem_path, self._now_color)
        if self._now_radius > 0:
            painter.setBrush(self._now_color)
            painter.drawEllipse(QPointF(x, band.top()), float(self._now_radius), float(self._now_radius))

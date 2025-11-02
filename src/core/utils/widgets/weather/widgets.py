from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, override

from PyQt6.QtCore import QPoint, QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QWidget

from core.utils.utilities import refresh_widget_style
from core.utils.widgets.weather.api import IconFetcher


class CurrentHourLineStyle(StrEnum):
    SOLID = "solid"
    DASH = "dash"
    DOT = "dot"
    DASH_DOT = "dashDot"
    DASH_DOT_DOT = "dashDotDot"

    def to_qt(self) -> Qt.PenStyle:
        if self == CurrentHourLineStyle.SOLID:
            return Qt.PenStyle.SolidLine
        elif self == CurrentHourLineStyle.DASH:
            return Qt.PenStyle.DashLine
        elif self == CurrentHourLineStyle.DOT:
            return Qt.PenStyle.DotLine
        elif self == CurrentHourLineStyle.DASH_DOT:
            return Qt.PenStyle.DashDotLine
        elif self == CurrentHourLineStyle.DASH_DOT_DOT:
            return Qt.PenStyle.DashDotDotLine
        else:
            raise ValueError(f"Unknown CurrentHourLineStyle: {self}")


@dataclass
class HourlyData:
    temp: int
    wind: float
    icon_url: str
    time: datetime


def quadratic_bezier_point(p0: QPointF, p1: QPointF, p2: QPointF, t: float) -> QPointF:
    """Calculate the point on a quadratic bezier curve at t."""
    x = (1 - t) ** 2 * p0.x() + 2 * (1 - t) * t * p1.x() + t**2 * p2.x()
    y = (1 - t) ** 2 * p0.y() + 2 * (1 - t) * t * p1.y() + t**2 * p2.y()
    return QPointF(x, y)


class ClickableWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            a0.accept()
        super().mousePressEvent(a0)

    @override
    def setProperty(self, name: str | None, value: Any) -> bool:
        super().setProperty(name, value)
        if name == "class":
            refresh_widget_style(self)
            self.update()
            return True
        return False


class HourlyTemperatureScrollArea(QScrollArea):
    """A QScrollArea that supports hand-drag scrolling."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAutoFillBackground(False)
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("QScrollArea{background: transparent;border: none;}")
        self._drag_active = False
        self._drag_start_pos = QPoint()
        self._scroll_start_pos = QPoint()

    @override
    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._drag_start_pos = a0.pos()
            hsb = self.horizontalScrollBar()
            vsb = self.verticalScrollBar()
            if hsb and vsb:
                self._scroll_start_pos = QPoint(hsb.value(), vsb.value())
                a0.accept()
        else:
            super().mousePressEvent(a0)

    @override
    def mouseMoveEvent(self, a0: QMouseEvent | None):
        if a0 and self._drag_active:
            delta = a0.pos() - self._drag_start_pos
            hsb = self.horizontalScrollBar()
            vsb = self.verticalScrollBar()
            if hsb:
                hsb.setValue(self._scroll_start_pos.x() - delta.x())
            if vsb:
                vsb.setValue(self._scroll_start_pos.y() - delta.y())
            a0.accept()
        else:
            super().mouseMoveEvent(a0)

    @override
    def mouseReleaseEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            a0.accept()
        else:
            super().mouseReleaseEvent(a0)

    @override
    def wheelEvent(self, a0: QWheelEvent | None):
        if a0 is not None:
            hsb = self.horizontalScrollBar()
            if hsb:
                hsb.setValue(hsb.value() - a0.angleDelta().y())
                a0.accept()
            else:
                super().wheelEvent(a0)
        else:
            super().wheelEvent(a0)


class HourlyTemperatureLineWidget(QFrame):
    """Widget for drawing the temperature line and current hour indicator."""

    def __init__(self, parent: QWidget | None = None, units: str = "metric", config: dict[str, Any] | None = None):
        super().__init__(parent)
        self.hourly_data: list[HourlyData] = []
        self.current_time: datetime | None = None
        self.current_idx: int | None = None

        self.config = config or {}
        self.units = units
        self.current_line_style = CurrentHourLineStyle(self.config.get("current_line_style", "dot"))
        self.hour_point_spacing: int = self.config.get("hourly_point_spacing", 76)

        self.icon_fetcher = IconFetcher.get_instance(self)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # We set this widget as transparent becuase the parent widget will handle the background color and border
        # Background color will be used as curve color in the paintEvent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

    def update_weather(
        self,
        data: list[HourlyData] | None,
        current_time: datetime | None = None,
    ):
        """Update the graph with new weather data and current hour."""
        self.current_time = current_time
        if self.current_time and data:
            self.current_idx = 1
            from_idx = self.current_time.hour - 1 if self.current_time.hour > 0 else 0
            to_idx = self.current_time.hour - 1 + 26
            self.hourly_data = data.copy()[from_idx:to_idx]
            if from_idx == 0:
                self.hourly_data.insert(0, data[0])
        elif data:
            self.current_idx = None
            self.hourly_data = data.copy()[:25]
            self.hourly_data.append(data[-1])
        n = len(self.hourly_data)
        min_width = int(self.hour_point_spacing * (n - 1))
        self.setMinimumWidth(abs(min_width))
        self.update()

    def _get_temp_range(self) -> tuple[float, float]:
        temps = [h.temp for h in self.hourly_data]
        return (min(temps), max(temps)) if temps else (0.0, 1.0)

    def _get_points(
        self,
        width: float,
        height: float,
        icon_size: QSize,
        painter: QPainter,
    ) -> list[QPointF]:
        font_metrics = painter.fontMetrics()
        bottom_padding = icon_size.height() // 2

        time_height = wind_height = font_metrics.height()
        icon_height = icon_size.height()

        bottom_content_height = time_height + wind_height + icon_height + bottom_padding

        graph_top = font_metrics.height() * 2
        graph_bottom = height - bottom_content_height
        graph_height = graph_bottom - graph_top

        temp_min, temp_max = self._get_temp_range()
        temp_range = temp_max - temp_min or 1
        x_step = self.hour_point_spacing if len(self.hourly_data) > 1 else width

        points: list[QPointF] = []
        for i, h in enumerate(self.hourly_data):
            norm = (h.temp - temp_min) / temp_range
            y = graph_bottom - norm * graph_height
            x = i * x_step
            points.append(QPointF(x, y))
        return points

    @override
    def paintEvent(self, a0: QPaintEvent | None):
        if len(self.hourly_data) < 2:
            return

        painter = QPainter(self)
        curve_color = painter.background().color()
        if self.config.get("icon_smoothing", False):
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing
                | QPainter.RenderHint.TextAntialiasing
                | QPainter.RenderHint.SmoothPixmapTransform
            )
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

        height = self.height()
        width = self.width()
        i_size = self.config.get("hourly_icon_size", 32)
        icon_size = QSize(i_size, i_size)
        points = self._get_points(width, height, icon_size, painter)

        text_wind_icon_height = 0

        default_pen = painter.pen()
        painter.setPen(default_pen)
        # First draw the time, wind and icon
        for i in range(1, len(self.hourly_data) - 1):
            x_offset = i * self.hour_point_spacing
            # Time text
            if self.current_idx is not None and i == self.current_idx:
                time_text = "Now"
            else:
                if self.config.get("time_format", "24h") == "24h":
                    time_text = self.hourly_data[i].time.strftime("%H:%M")
                else:
                    time_text = self.hourly_data[i].time.strftime("%I:%M %p")
            time_rect = painter.fontMetrics().boundingRect(time_text)
            time_x = x_offset - time_rect.width() / 2
            time_y = height - time_rect.height() / 2
            painter.drawText(QPointF(time_x, time_y), time_text)
            # Wind text
            wind_text = f"{self.hourly_data[i].wind} {'km/h' if self.units == 'metric' else 'mph'}"
            wind_rect = painter.fontMetrics().boundingRect(wind_text)
            wind_x = x_offset - wind_rect.width() / 2
            wind_y = time_y - wind_rect.height()
            painter.drawText(QPointF(wind_x, wind_y), wind_text)
            # Draw icon
            icon = self.icon_fetcher.get_icon(self.hourly_data[i].icon_url)
            pixmap = QPixmap.fromImage(QImage.fromData(icon))
            icon_x = x_offset - icon_size.width() / 2
            icon_y = wind_y - wind_rect.height() - icon_size.height()
            painter.drawPixmap(
                int(icon_x),
                int(icon_y),
                icon_size.width(),
                icon_size.height(),
                pixmap,
            )
            # Set temp, wind and icon combined height
            text_wind_icon_height = time_rect.height() + wind_rect.height() + icon_size.height()

        # Draw temperature curve
        temp_line_width = self.config.get("temp_line_width", 2)
        if temp_line_width > 0:
            line_pen = QPen(curve_color, temp_line_width)
            painter.setPen(line_pen)
            path = QPainterPath(points[0])
            for i in range(1, len(points)):
                # Curve path
                if i < len(points) - 1:
                    mid_x = (points[i].x() + points[i + 1].x()) / 2
                    mid_y = (points[i].y() + points[i + 1].y()) / 2
                    path.quadTo(points[i], QPointF(mid_x, mid_y))
                else:
                    path.lineTo(points[i])
            painter.drawPath(path)

        # Draw temperature text
        painter.setPen(default_pen)
        for i in range(1, len(self.hourly_data) - 1):
            x_offset = i * self.hour_point_spacing
            temp_text = f"{self.hourly_data[i].temp}{'°C' if self.units == 'metric' else '°F'}"
            temp_rect = painter.fontMetrics().boundingRect(temp_text)
            temp_x = x_offset - temp_rect.width() / 2
            # Text will be drawn above the curve
            if temp_line_width > 0:
                p0 = points[i - 1]
                p1 = points[i]
                p2 = points[i + 1]
                t = 0.5
                # NOTE: We calculate this point to average it with the actual temp point
                # because otherwise the temperature text will clip with the curve on some values
                custom_point = quadratic_bezier_point(p0, p1, p2, t)
                average_point = (custom_point + points[i]) / 2
                temp_y = average_point.y() - 15
            # Text will have an offset from top of the widget if no curve is drawn
            else:
                temp_y = temp_rect.height()
            painter.drawText(QPointF(temp_x, temp_y), temp_text)

        # Draw vertical line for current hour
        current_line_width = self.config.get("current_line_width", 1)
        if current_line_width > 0:
            vline_pen = QPen(
                QColor(self.config.get("current_line_color", "#8EAEE8")),
                self.config.get("current_line_width", 1),
                self.current_line_style.to_qt(),
            )
            painter.setPen(vline_pen)
            if self.current_idx is not None:
                line_x = points[self.current_idx].x()
                if temp_line_width > 0:
                    custom_point = quadratic_bezier_point(points[0], points[1], points[2], 0.5)
                    average_point = (custom_point + points[1]) / 2
                    line_from = average_point.y() + 10
                else:
                    temp_rect = painter.fontMetrics().boundingRect("20°C")
                    line_from = temp_rect.height() + 10
                line_to = height - text_wind_icon_height - 10

                painter.drawLine(
                    int(line_x),
                    int(line_from),
                    int(line_x),
                    int(line_to),
                )
        painter.end()

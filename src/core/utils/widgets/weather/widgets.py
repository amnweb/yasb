import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, cast, override

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QHideEvent,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QWidget

from core.utils.utilities import refresh_widget_style
from core.utils.widgets.weather.animation import WeatherAnimationManager
from core.utils.widgets.weather.api import IconFetcher
from core.utils.widgets.weather.utils import (
    ColorFetchWidget,
    copy_painter_state,
    create_path_from_points,
    find_point_and_percent,
)

BORDER_RADIUS_PATTERN = re.compile(
    r"\.hourly-container(?![-\w])(?:\:[-\w]+)*\s*(?:,[^{]*)?\{[^}]*?border-radius:\s*(\d+)(?:px)?[^}]*\}"
)


class CurrentHourLineStyle(StrEnum):
    SOLID = "solid"
    DASH = "dash"
    DOT = "dot"
    DASH_DOT = "dashDot"
    DASH_DOT_DOT = "dashDotDot"

    def to_qt(self) -> Qt.PenStyle:
        mapping = {
            CurrentHourLineStyle.SOLID: Qt.PenStyle.SolidLine,
            CurrentHourLineStyle.DASH: Qt.PenStyle.DashLine,
            CurrentHourLineStyle.DOT: Qt.PenStyle.DotLine,
            CurrentHourLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
            CurrentHourLineStyle.DASH_DOT_DOT: Qt.PenStyle.DashDotDotLine,
        }
        return mapping.get(self, Qt.PenStyle.NoPen)


@dataclass
class HourlyData:
    temp: int
    wind: float
    icon_url: str
    time: datetime
    chance_of_rain: int
    chance_of_snow: int
    humidity: int
    graph_point: QPointF = field(default_factory=QPointF)


class ClickableWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
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


class HourlyDataLineWidget(QFrame):
    """Unified widget for drawing temperature, rain, or snow data lines."""

    def __init__(
        self,
        parent: QWidget | None = None,
        units: str = "metric",
        config: dict[str, Any] | None = None,
        data_type: str = "temperature",
    ):
        super().__init__(parent)
        self.hourly_data: list[HourlyData] = []
        self.current_time: datetime | None = None
        self.current_idx: int | None = None
        self.data_type = data_type  # "temperature", "rain", or "snow"

        self.config = config or {}
        self.units = units
        self.current_line_style = CurrentHourLineStyle(self.config.get("current_line_style", "dot"))
        self.gradient_colors = (
            self.config["hourly_gradient"]["top_color"],
            self.config["hourly_gradient"]["bottom_color"],
        )
        self.hour_point_spacing: int = self.config.get("hourly_point_spacing", 76)
        self.temp_animation_style = self.config.get("temp_animation_style", "both")

        self.icon_fetcher = IconFetcher.get_instance(self)

        self.rain_colors = ColorFetchWidget(self, "hourly-rain-animation")
        self.snow_colors = ColorFetchWidget(self, "hourly-snow-animation")

        self.weather_animation_manager = WeatherAnimationManager(self, self.config)

        # BG and FG cached data
        self.icon_smoothing = self.config.get("icon_smoothing", True)
        self.bg_pixmap = QPixmap()
        self.fg_pixmap = QPixmap()
        self.path_curve = QPainterPath()
        self.path_points: list[QPointF] = []
        self.needs_update = False

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # We set this widget as transparent becuase the parent widget will handle the background color and border
        # Background color will be used as curve color in the paintEvent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        # Set initial CSS class
        self.set_data_type(data_type)
        self._border_radius = 0.0
        self._update_border_radius()

    def set_data_type(self, data_type: str):
        """Change the data type being displayed."""
        self.data_type = data_type
        # Update CSS class based on data type
        if data_type == "rain":
            self.setProperty("class", "hourly-data rain")
        elif data_type == "snow":
            self.setProperty("class", "hourly-data snow")
        else:
            self.setProperty("class", "hourly-data temperature")
        refresh_widget_style(self)
        self.force_update()

    def update_weather(
        self,
        data: list[HourlyData] | None,
        current_time: datetime | None = None,
    ):
        """Update the graph with new weather data and current hour."""
        self.current_time = current_time
        if self.config["weather_animation"]["enable_debug"]:
            from core.utils.widgets.weather.debug import generate_debug_data

            data = generate_debug_data(current_time, data)
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
        self.force_update()

    def _get_data_range(self) -> tuple[float, float]:
        """Get the range of data based on current data_type."""
        if self.data_type == "temperature":
            values = [h.temp for h in self.hourly_data]
            return (min(values), max(values)) if values else (0.0, 1.0)
        elif self.data_type == "rain":
            return (0.0, 100.0)
        elif self.data_type == "snow":
            return (0.0, 100.0)
        return (0.0, 1.0)

    def _get_points(
        self,
        width: float,
        height: float,
        icon_size: QSize,
    ) -> list[QPointF]:
        font_metrics = self.fontMetrics()
        bottom_padding = icon_size.height() // 2

        time_height = wind_height = font_metrics.height()
        icon_height = icon_size.height()

        bottom_content_height = time_height + wind_height + icon_height + bottom_padding

        graph_top = font_metrics.height() * 2
        graph_bottom = height - bottom_content_height
        graph_height = graph_bottom - graph_top

        data_min, data_max = self._get_data_range()
        data_range = data_max - data_min or 1
        x_step = self.hour_point_spacing if len(self.hourly_data) > 1 else width

        points: list[QPointF] = []
        for i, h in enumerate(self.hourly_data):
            if self.data_type == "temperature":
                value = h.temp
            elif self.data_type == "rain":
                value = h.chance_of_rain
            elif self.data_type == "snow":
                value = h.chance_of_snow
            else:
                value = 0
            norm = (value - data_min) / data_range
            y = graph_bottom - norm * graph_height
            x = i * x_step
            h.graph_point = QPointF(x, y)
            points.append(QPointF(x, y))
        return points

    def _prepare_cached_data(self, painter: QPainter):
        """
        Prepare cached data for drawing since we are calling paintEvent very often for weather animation
        This way paintEvent only needs to blit QPixmap data instead of re-rendering everything from scratch
        """
        # Draw background pixmap
        dpr = self.devicePixelRatio()
        height = self.height()
        width = self.width()
        self.bg_pixmap = QPixmap(int(width * dpr), int(height * dpr))
        self.bg_pixmap.setDevicePixelRatio(dpr)
        self.bg_pixmap.fill(Qt.GlobalColor.transparent)
        bg_painter = QPainter(self.bg_pixmap)
        copy_painter_state(painter, bg_painter)

        i_size = self.config.get("hourly_icon_size", 32)
        icon_size = QSize(i_size, i_size)
        points = self._get_points(width, height, icon_size)

        # Create the curve path first so we can use it for the gradient
        path = create_path_from_points(points)

        # Update the weather animation manager with the new data
        if self.config["weather_animation"]["enabled"]:
            rain_colors, snow_colors = self.rain_colors.get_colors(), self.snow_colors.get_colors()
            self.weather_animation_manager.update_data(
                self.hourly_data,
                path,
                self.data_type,
                {"rain": rain_colors, "snow": snow_colors},
            )

        # Draw gradient under the curve
        if self.config["hourly_gradient"]["enabled"]:
            gradient = QLinearGradient(0, 0, 0, height)
            gradient.setColorAt(0, QColor(self.gradient_colors[0]))
            gradient.setColorAt(1, QColor(self.gradient_colors[1]))

            fill_path = QPainterPath(path)
            fill_path.lineTo(points[-1].x(), height)
            fill_path.lineTo(points[0].x(), height)
            fill_path.closeSubpath()

            bg_painter.setBrush(QBrush(gradient))
            bg_painter.setPen(Qt.PenStyle.NoPen)
            bg_painter.drawPath(fill_path)

        bg_painter.end()

        # Draw foreground pixmap
        self.fg_pixmap = QPixmap(int(width * dpr), int(height * dpr))
        self.fg_pixmap.setDevicePixelRatio(dpr)
        self.fg_pixmap.fill(Qt.GlobalColor.transparent)
        fg_painter = QPainter(self.fg_pixmap)

        # Use default pen and brush
        copy_painter_state(painter, fg_painter)

        text_wind_icon_height = 0

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
            fg_painter.drawText(QPointF(time_x, time_y), time_text)
            # Data text (wind for temperature, humidity for rain/snow)
            if self.data_type == "temperature":
                data_text = f"{self.hourly_data[i].wind} {'km/h' if self.units == 'metric' else 'mph'}"
            elif self.data_type == "rain":
                data_text = f"{self.hourly_data[i].humidity}%"
            elif self.data_type == "snow":
                data_text = f"{self.hourly_data[i].humidity}%"
            else:
                data_text = ""
            data_rect = painter.fontMetrics().boundingRect(data_text)
            data_x = x_offset - data_rect.width() / 2
            data_y = time_y - data_rect.height()
            fg_painter.drawText(QPointF(data_x, data_y), data_text)
            # Draw icon
            icon = self.icon_fetcher.get_icon(self.hourly_data[i].icon_url)
            pixmap = QPixmap.fromImage(QImage.fromData(icon))
            icon_x = x_offset - icon_size.width() / 2
            icon_y = data_y - data_rect.height() - icon_size.height()
            fg_painter.drawPixmap(
                int(icon_x),
                int(icon_y),
                icon_size.width(),
                icon_size.height(),
                pixmap,
            )
            # Set combined height
            text_wind_icon_height = time_rect.height() + data_rect.height() + icon_size.height()

        # Draw temperature curve
        curve_color = painter.background().color()
        fg_painter.save()
        temp_line_width = self.config.get("temp_line_width", 2)
        if temp_line_width > 0:
            line_pen = QPen(curve_color, temp_line_width)
            fg_painter.setPen(line_pen)
            fg_painter.setBrush(Qt.BrushStyle.NoBrush)
            fg_painter.drawPath(path)
        fg_painter.restore()

        # Draw value text above curve
        for i in range(1, len(self.hourly_data) - 1):
            x_offset = i * self.hour_point_spacing
            if self.data_type == "temperature":
                value_text = f"{self.hourly_data[i].temp}{'°C' if self.units == 'metric' else '°F'}"
            elif self.data_type == "rain":
                value_text = f"{self.hourly_data[i].chance_of_rain}%"
            elif self.data_type == "snow":
                value_text = f"{self.hourly_data[i].chance_of_snow}%"
            else:
                value_text = ""
            value_rect = fg_painter.fontMetrics().boundingRect(value_text)
            value_x = x_offset - value_rect.width() / 2
            # Text will be drawn above the curve
            if temp_line_width > 0:
                point, _ = find_point_and_percent(path, points[i].x())
                value_y = point.y() - 15
            # Text will have an offset from top of the widget if no curve is drawn
            else:
                value_y = value_rect.height()
            fg_painter.drawText(QPointF(value_x, value_y), value_text)

        # Draw vertical line for current hour
        current_line_width = self.config.get("current_line_width", 1)
        if current_line_width > 0:
            vline_pen = QPen(
                QColor(self.config.get("current_line_color", "#8EAEE8")),
                self.config.get("current_line_width", 1),
                self.current_line_style.to_qt(),
            )
            fg_painter.setPen(vline_pen)
            if self.current_idx is not None:
                line_x = points[self.current_idx].x()
                if temp_line_width > 0:
                    point, _ = find_point_and_percent(path, points[1].x())
                    line_from = point.y() + 10
                else:
                    sample_rect = fg_painter.fontMetrics().boundingRect("100%")
                    line_from = sample_rect.height() + 10
                line_to = height - text_wind_icon_height - 10

                fg_painter.drawLine(
                    int(line_x),
                    int(line_from),
                    int(line_x),
                    int(line_to),
                )
        fg_painter.end()

        self.needs_update = False

    def force_update(self):
        """Force an update of the static content"""
        self._update_border_radius()
        self.needs_update = True
        self.update()

    def _update_border_radius(self):
        """
        Extract border-radius from the stylesheet for .hourly-container
        This is a bit of a hack because we can't get the computed border-radius otherwise
        """
        try:
            # Traverse up to find the stylesheet
            widget = self
            while widget:
                # Check if it has styleSheet method
                if hasattr(widget, "styleSheet") and (sheet := widget.styleSheet().strip()):
                    match = BORDER_RADIUS_PATTERN.search(sheet)
                    if match:
                        self._border_radius = float(match.group(1))
                        return
                widget = widget.parent()
        except Exception:
            pass

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        """Redraw static content on resize only"""
        self.force_update()
        super().resizeEvent(a0)

    @override
    def hideEvent(self, a0: QHideEvent | None) -> None:
        # Reset cached data
        self.bg_pixmap = QPixmap()
        self.fg_pixmap = QPixmap()
        self.path_curve = QPainterPath()
        self.path_points.clear()
        super().hideEvent(a0)

    @override
    def paintEvent(self, a0: QPaintEvent | None):
        if len(self.hourly_data) < 2:
            return
        painter = QPainter(self)
        if self.icon_smoothing:
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing
                | QPainter.RenderHint.TextAntialiasing
                | QPainter.RenderHint.SmoothPixmapTransform
            )
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        # Create clip rect based on parent widget size to avoid drawing outside of the parent border radius
        parent = cast(QWidget, self.parent())
        p_rect = parent.rect()
        tl = self.mapFromParent(p_rect.topLeft().toPointF())
        br = self.mapFromParent(p_rect.bottomRight().toPointF() - QPointF(-1.0, -1.0))
        parent_rect = QRectF(tl, br)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(parent_rect, self._border_radius, self._border_radius)
        painter.setClipPath(clip_path)

        # Prepare cached content if needed
        if self.bg_pixmap.isNull() or self.fg_pixmap.isNull() or self.needs_update:
            self._prepare_cached_data(painter)
        # Draw cached background
        painter.drawPixmap(0, 0, self.bg_pixmap)
        # Paint weahter animation effect.
        self.weather_animation_manager.paint_animation(painter, clip_path)
        # Draw cached foreground
        painter.drawPixmap(0, 0, self.fg_pixmap)

        painter.end()

from collections.abc import Iterable, Sequence
from typing import Protocol, override

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSignalBlocker, Qt
from PyQt6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style


class PinnablePopup(PopupWidget):
    """Popup that can be pinned to stay open and draggable when pinned."""

    def __init__(
        self,
        parent: QWidget,
        blur: bool = False,
        round_corners: bool = False,
        round_corners_type: str = "normal",
        border_color: str = "None",
    ):
        super().__init__(
            parent,
            blur=blur,
            round_corners=round_corners,
            round_corners_type=round_corners_type,
            border_color=border_color,
        )
        self.is_pinned = False
        self._drag_pos: QPoint | None = None
        self.graph: GraphWidget | None = None
        self.stat_labels: dict[str, QLabel] = {}
        self._pin_buttons: list[tuple[QPushButton, str, str]] = []
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

    def create_pin_button(self, pin_icon: str = "\ue718", unpin_icon: str = "\ue77a") -> QPushButton:
        button = QPushButton(pin_icon)
        button.setCheckable(True)
        button.setProperty("class", "pin-btn")
        self._pin_buttons.append((button, pin_icon, unpin_icon))
        button.toggled.connect(self.set_pinned)
        self.set_pinned(self.is_pinned)
        return button

    def set_pinned(self, pinned: bool) -> None:
        self.is_pinned = pinned
        for button, pin_icon, unpin_icon in self._pin_buttons:
            blocker = QSignalBlocker(button)
            button.setChecked(pinned)
            del blocker
            button.setText(unpin_icon if pinned else pin_icon)
            button.setProperty("class", "pin-btn pinned" if pinned else "pin-btn")
            set_tooltip(button, "Unpin this window" if pinned else "Pin this window")
            refresh_widget_style(button)

    @override
    def event(self, a0: QEvent | None) -> bool:
        if a0 is not None and a0.type() == QEvent.Type.WindowDeactivate:
            if self.is_pinned:
                return True
            self.hide_animated()
            return True
        return super().event(a0)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and self.is_pinned and a0.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = a0.globalPosition().toPoint() - self.frameGeometry().topLeft()
            a0.accept()
        else:
            super().mousePressEvent(a0)

    @override
    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if (
            a0 is not None
            and self.is_pinned
            and self._drag_pos is not None
            and a0.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(a0.globalPosition().toPoint() - self._drag_pos)
            a0.accept()
        else:
            super().mouseMoveEvent(a0)

    @override
    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and self.is_pinned and a0.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            a0.accept()
        else:
            super().mouseReleaseEvent(a0)

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if self.is_pinned:
            return False
        return super().eventFilter(a0, a1)

    @override
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if self.is_pinned:
            if a0 is not None:
                a0.accept()
            return
        super().closeEvent(a0)


class GraphWidget(QFrame):
    """Rolling area chart for percentage-based history data (0-100)."""

    STROKE_WIDTH = 2
    FILL_TOP_OPACITY = 100
    FILL_BOTTOM_OPACITY = 10
    SPLINE_TENSION = 0.2
    GRID_CELL_SIZE = 16

    def __init__(self, css_class: str = "graph", show_grid: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: list[float] = []
        self._line_path: QPainterPath | None = None
        self._fill_path: QPainterPath | None = None
        self._show_grid = show_grid
        self._fill_enabled = True
        self._color_bands: tuple[tuple[float, float, str], ...] = ()
        self.setMinimumHeight(20)
        self.setProperty("class", css_class)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Hidden style proxy its CSS 'color' drives grid line color
        self._grid_proxy = QFrame(self)
        self._grid_proxy.setProperty("class", f"{css_class}-grid")
        self._grid_proxy.setFixedSize(0, 0)

    def set_fill_enabled(self, enabled: bool) -> None:
        self._fill_enabled = enabled
        self.update()

    def set_color_bands(self, bands: Sequence[tuple[float, float, str]]) -> None:
        """Color the existing smooth stroke by height; other charts retain their CSS color."""
        self._color_bands = tuple(bands)
        self.update()

    def set_data(self, data: list[float]) -> None:
        self._data = data
        self._rebuild_paths()
        self.update()

    @override
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self._rebuild_paths()

    def _rebuild_paths(self) -> None:
        self._line_path = None
        self._fill_path = None
        if not self._data:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        pad = self.STROKE_WIDTH / 2
        chart_h = h - pad * 2
        n = len(self._data)
        x_step = w / (n - 1) if n > 1 else w
        pts: list[QPointF] = []
        for i, val in enumerate(self._data):
            frac = max(0.0, min(val / 100.0, 1.0))
            pts.append(QPointF(i * x_step, pad + chart_h * (1.0 - frac)))
        if len(pts) < 2:
            return
        line_path = self._build_smooth_path(pts)
        fill_path = QPainterPath()
        fill_path.moveTo(pts[0].x(), h)
        fill_path.lineTo(pts[0])
        fill_path.connectPath(line_path)
        fill_path.lineTo(pts[-1].x(), h)
        fill_path.closeSubpath()
        self._line_path = line_path
        self._fill_path = fill_path

    @staticmethod
    def _build_smooth_path(pts: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(pts[0])
        tension = GraphWidget.SPLINE_TENSION
        if tension == 0 or len(pts) == 2:
            for i in range(1, len(pts)):
                path.lineTo(pts[i])
            return path
        last = len(pts) - 1
        for i in range(last):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(last, i + 2)]
            cp1_x = p1.x() + (p2.x() - p0.x()) * tension
            cp1_y = p1.y() + (p2.y() - p0.y()) * tension
            cp2_x = p2.x() - (p3.x() - p1.x()) * tension
            cp2_y = p2.y() - (p3.y() - p1.y()) * tension
            lo = min(p1.y(), p2.y())
            hi = max(p1.y(), p2.y())
            cp1_y = max(lo, min(cp1_y, hi))
            cp2_y = max(lo, min(cp2_y, hi))
            path.cubicTo(cp1_x, cp1_y, cp2_x, cp2_y, p2.x(), p2.y())
        return path

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        if self._line_path is None or self._fill_path is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.ensurePolished()
        line_color = self.palette().color(self.foregroundRole())
        h = self.height()
        w = self.width()
        # Square grid (anchored to bottom-right so edges align cleanly)
        if self._show_grid:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            self._grid_proxy.ensurePolished()
            grid_color = self._grid_proxy.palette().color(self._grid_proxy.foregroundRole())
            if not grid_color.isValid() or grid_color == QColor(0, 0, 0):
                grid_color = QColor(line_color)
                grid_color.setAlpha(30)
            painter.setPen(QPen(grid_color, 1))
            cell = self.GRID_CELL_SIZE
            last_x = w - 1
            last_y = h - 1
            # Horizontal lines (bottom to top)
            y = last_y
            while y >= 0:
                painter.drawLine(0, int(y), last_x, int(y))
                y -= cell
            if int(y + cell) > 0:
                painter.drawLine(0, 0, last_x, 0)
            # Vertical lines (right to left)
            x = last_x
            while x >= 0:
                painter.drawLine(int(x), 0, int(x), last_y)
                x -= cell
            if int(x + cell) > 0:
                painter.drawLine(0, 0, 0, last_y)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The colored fill follows the same usage bands as the stroke, blending at thresholds.
        if self._fill_enabled:
            gradient = self._fill_gradient(line_color)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(self._fill_path)
        # Stroke line
        pen = QPen(line_color, self.STROKE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setJoinStyle(Qt.PenJoinStyle.BevelJoin)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if not self._color_bands:
            painter.setPen(pen)
            painter.drawPath(self._line_path)
        else:
            pad = self.STROKE_WIDTH / 2
            chart_h = h - pad * 2
            for lower, upper, color in self._color_bands:
                top = 0.0 if upper >= 100 else pad + chart_h * (1 - upper / 100)
                bottom = float(h) if lower <= 0 else pad + chart_h * (1 - lower / 100)
                painter.save()
                painter.setClipRect(QRectF(0, top, float(w), max(0.0, bottom - top)))
                pen.setColor(QColor(color))
                painter.setPen(pen)
                painter.drawPath(self._line_path)
                painter.restore()

    def _fill_gradient(self, fallback: QColor) -> QLinearGradient:
        gradient = QLinearGradient(0, 0, 0, self.height())
        stops: list[tuple[float, str]]
        if not self._color_bands:
            stops = [(0.0, fallback.name(QColor.NameFormat.HexArgb)), (1.0, fallback.name(QColor.NameFormat.HexArgb))]
        else:
            stops = [(0.0, self._color_bands[-1][2]), (1.0, self._color_bands[0][2])]
            pad = self.STROKE_WIDTH / 2
            height = max(1, self.height())
            chart_h = height - pad * 2
            for index in range(1, len(self._color_bands)):
                lower, upper, color = self._color_bands[index]
                previous_lower, _, previous_color = self._color_bands[index - 1]
                boundary = (pad + chart_h * (1 - lower / 100)) / height
                width = min(2.5, (upper - lower) / 2, (lower - previous_lower) / 2) * chart_h / height / 100
                stops.extend([(max(0.0, boundary - width), color), (min(1.0, boundary + width), previous_color)])
        for position, value in sorted(stops):
            color = QColor(value)
            color.setAlpha(round(self.FILL_TOP_OPACITY + (self.FILL_BOTTOM_OPACITY - self.FILL_TOP_OPACITY) * position))
            gradient.setColorAt(position, color)
        return gradient


class StatPopupMenuConfig(Protocol):
    @property
    def blur(self) -> bool: ...
    @property
    def round_corners(self) -> bool: ...
    @property
    def round_corners_type(self) -> str: ...
    @property
    def border_color(self) -> str: ...
    @property
    def alignment(self) -> str: ...
    @property
    def direction(self) -> str: ...
    @property
    def offset_left(self) -> int: ...
    @property
    def offset_top(self) -> int: ...
    @property
    def show_graph(self) -> bool: ...
    @property
    def show_graph_grid(self) -> bool: ...
    @property
    def pin_icon(self) -> str: ...
    @property
    def unpin_icon(self) -> str: ...


type StatRow = tuple[str | None, str, str, str | None, str, str]


def build_stat_popup(
    parent: QWidget,
    menu_config: StatPopupMenuConfig,
    popup_class_name: str,
    title: str,
    history: Iterable[float],
    stat_rows: Sequence[StatRow],
    graph_class: str = "graph",
    primary_stats: Sequence[str] = (),
) -> PinnablePopup:

    popup = PinnablePopup(
        parent,
        blur=menu_config.blur,
        round_corners=menu_config.round_corners,
        round_corners_type=menu_config.round_corners_type,
        border_color=menu_config.border_color,
    )
    popup.setProperty("class", popup_class_name)
    layout = QVBoxLayout(popup)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    header = QFrame()
    header.setProperty("class", "header")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(0)
    title_label = QLabel(title)
    title_label.setProperty("class", "text")
    header_layout.addWidget(title_label)
    header_layout.addStretch()

    pin_icon = menu_config.pin_icon
    unpin_icon = menu_config.unpin_icon
    pin_btn = popup.create_pin_button(pin_icon, unpin_icon)
    header_layout.addWidget(pin_btn)
    layout.addWidget(header)

    if menu_config.show_graph:
        graph_container = QFrame()
        graph_container.setProperty("class", "graph-container")
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(0)
        graph = GraphWidget(
            graph_class,
            show_grid=menu_config.show_graph_grid,
        )
        graph_layout.addWidget(graph)
        layout.addWidget(graph_container)
        popup.graph = graph
        history_values = list(history)
        if history_values:
            graph.set_data(history_values)

    stats_frame = QFrame()
    stats_frame.setProperty("class", "stats")
    grid = QGridLayout(stats_frame)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(0)

    stat_labels: dict[str, QLabel] = {}
    for i, (left_header, left_key, left_value, right_header, right_key, right_value) in enumerate(stat_rows):
        for col, (header_text, key, value, is_right) in enumerate(
            [
                (left_header, left_key, left_value, False),
                (right_header, right_key, right_value, True),
            ]
        ):
            if header_text is None:
                continue
            align = Qt.AlignmentFlag.AlignRight if is_right else Qt.AlignmentFlag.AlignLeft
            item = QFrame()
            primary_class = " primary" if key in primary_stats else ""
            item.setProperty("class", f"stat-item{primary_class}")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(0)
            header_label = QLabel(header_text)
            header_label.setProperty("class", f"stat-label{primary_class}")
            header_label.setAlignment(align)
            value_label = QLabel(value)
            value_label.setProperty("class", f"stat-value{primary_class}")
            value_label.setAlignment(align)
            item_layout.addWidget(header_label)
            item_layout.addWidget(value_label)
            grid.addWidget(item, i, col)
            stat_labels[key] = value_label

    layout.addWidget(stats_frame)
    popup.stat_labels = stat_labels

    popup.adjustSize()
    popup.setPosition(
        alignment=menu_config.alignment,
        direction=menu_config.direction,
        offset_left=menu_config.offset_left,
        offset_top=menu_config.offset_top,
    )
    return popup

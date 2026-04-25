from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style


class PinnablePopup(PopupWidget):
    """Popup that can be pinned to stay open and draggable when pinned."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_pinned = False
        self._drag_pos = None
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate:
            if self._is_pinned:
                return True
            self.hide_animated()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        if self._is_pinned and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_pinned and self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_pinned and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        if self._is_pinned:
            return False
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self._is_pinned:
            event.accept()
            return
        super().closeEvent(event)


class GraphWidget(QFrame):
    """Rolling area chart for percentage-based history data (0-100)."""

    STROKE_WIDTH = 2
    FILL_TOP_OPACITY = 100
    FILL_BOTTOM_OPACITY = 10
    SPLINE_TENSION = 0.2
    GRID_CELL_SIZE = 16

    def __init__(self, css_class="graph", show_grid=False, parent=None):
        super().__init__(parent)
        self._data: list[float] = []
        self._line_path: QPainterPath | None = None
        self._fill_path: QPainterPath | None = None
        self._show_grid = show_grid
        self.setMinimumHeight(20)
        self.setProperty("class", css_class)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Hidden style proxy its CSS 'color' drives grid line color
        self._grid_proxy = QFrame(self)
        self._grid_proxy.setProperty("class", f"{css_class}-grid")
        self._grid_proxy.setFixedSize(0, 0)

    def set_data(self, data: list[float]) -> None:
        self._data = data
        self._rebuild_paths()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
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
        pts = []
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._line_path is None:
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
        # Fill gradient
        gradient = QLinearGradient(0, 0, 0, h)
        fill_top = QColor(line_color)
        fill_top.setAlpha(self.FILL_TOP_OPACITY)
        fill_bottom = QColor(line_color)
        fill_bottom.setAlpha(self.FILL_BOTTOM_OPACITY)
        gradient.setColorAt(0, fill_top)
        gradient.setColorAt(1, fill_bottom)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(self._fill_path)
        # Stroke line
        pen = QPen(line_color, self.STROKE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setJoinStyle(Qt.PenJoinStyle.BevelJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._line_path)


def build_stat_popup(
    parent,
    menu_config,
    popup_class_name,
    title,
    history,
    stat_rows,
    graph_class="graph",
):

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
    pin_btn = QPushButton(pin_icon)
    pin_btn.setCheckable(True)
    pin_btn.setProperty("class", "pin-btn")
    set_tooltip(pin_btn, "Pin this window")

    def on_pin_toggled(checked: bool):
        pin_btn.setText(unpin_icon if checked else pin_icon)
        pin_btn.setProperty("class", "pin-btn pinned" if checked else "pin-btn")
        set_tooltip(pin_btn, "Pin this window" if not checked else "Unpin this window")
        refresh_widget_style(pin_btn)
        popup._is_pinned = checked

    pin_btn.toggled.connect(on_pin_toggled)
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
        popup._graph = graph
        if history:
            graph.set_data(list(history))
    else:
        popup._graph = None

    stats_frame = QFrame()
    stats_frame.setProperty("class", "stats")
    grid = QGridLayout(stats_frame)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(0)

    stat_labels = {}
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
            item.setProperty("class", "stat-item")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(0)
            header_label = QLabel(header_text)
            header_label.setProperty("class", "stat-label")
            header_label.setAlignment(align)
            value_label = QLabel(value)
            value_label.setProperty("class", "stat-value")
            value_label.setAlignment(align)
            item_layout.addWidget(header_label)
            item_layout.addWidget(value_label)
            grid.addWidget(item, i, col)
            stat_labels[key] = value_label

    layout.addWidget(stats_frame)
    popup._stat_labels = stat_labels

    popup.adjustSize()
    popup.setPosition(
        alignment=menu_config.alignment,
        direction=menu_config.direction,
        offset_left=menu_config.offset_left,
        offset_top=menu_config.offset_top,
    )
    return popup

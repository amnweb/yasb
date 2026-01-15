"""
GitHub Copilot Usage Widget for YASB.
Displays premium request usage data with a popup showing detailed statistics.
"""

import os
import re
from datetime import datetime, timezone

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.copilot.api import CopilotDataManager, CopilotUsageData
from core.validation.widgets.yasb.copilot import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ProgressBar(QFrame):
    """Progress bar widget."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = 0
        self._max_value = 100
        self._warning_threshold = -1
        self._critical_threshold = -1
        self._state = ""
        self._extra_class = ""

        self.setMinimumHeight(6)
        self.setMaximumHeight(8)
        self.setProperty("class", "progress-bar")

        # Fill bar inside track
        self._fill = QFrame(self)
        self._fill.setProperty("class", "fill")
        self._fill.setGeometry(0, 0, 0, self.height())

    def set_value(self, value: int, max_value: int = 100) -> None:
        self._value = min(value, max_value)
        self._max_value = max_value
        self._update_state()
        self._update_fill()

    def set_thresholds(self, warning: int, critical: int) -> None:
        self._warning_threshold = warning
        self._critical_threshold = critical
        self._update_state()

    def set_class(self, class_name: str) -> None:
        """Set an additional CSS class (e.g., 'model-0', 'model-1')."""
        self._extra_class = class_name
        self._apply_class()

    def _apply_class(self) -> None:
        parts = ["progress-bar"]
        if self._extra_class:
            parts.append(self._extra_class)
        if self._state:
            parts.append(self._state)
        self.setProperty("class", " ".join(parts))
        self.style().unpolish(self)
        self.style().polish(self)

    def _update_state(self) -> None:
        pct = (self._value / self._max_value * 100) if self._max_value > 0 else 0
        old_state = self._state
        if self._critical_threshold >= 0 and pct >= self._critical_threshold:
            self._state = "critical"
        elif self._warning_threshold >= 0 and pct >= self._warning_threshold:
            self._state = "warning"
        else:
            self._state = ""

        if old_state != self._state:
            self._apply_class()

    def _update_fill(self) -> None:
        pct = (self._value / self._max_value * 100) if self._max_value > 0 else 0
        fill_width = int(self.width() * min(pct, 100) / 100)
        # Minimum width = height to preserve rounded corners when fill is small
        if fill_width > 0:
            fill_width = max(fill_width, self.height())
        self._fill.setGeometry(0, 0, fill_width, self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_fill()


class UsageChartWidget(QFrame):
    """Daily usage line chart with tooltip on hover."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._points: list[QPointF] = []
        self._tooltip: CustomToolTip | None = None
        self._hovered_index = -1
        self._pad_top = 10  # Top padding for chart to avoid clipping peaks
        self.setMinimumHeight(80)
        self.setProperty("class", "usage-chart")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

    def set_data(self, data: list[dict]) -> None:
        self._data = data
        self._calculate_points()
        self.update()

    def _calculate_points(self) -> None:
        self._points = []
        if not self._data:
            return

        w, h = self.width(), self.height()
        pad_top = self._pad_top
        chart_h = h - pad_top  # Only top padding, bottom goes to edge
        max_val = max((d.get("requests", 0) for d in self._data), default=1) or 1
        n = len(self._data)
        x_step = w / (n - 1) if n > 1 else w

        for i, item in enumerate(self._data):
            x = i * x_step
            y = pad_top + chart_h - (item.get("requests", 0) / max_val * chart_h)
            self._points.append(QPointF(x, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._calculate_points()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._points:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get colors from CSS palette
        self.ensurePolished()
        palette = self.palette()
        line_color = palette.color(self.foregroundRole())

        h, pad_top = self.height(), self._pad_top
        line_path = self._create_smooth_path() if len(self._points) > 1 else QPainterPath()

        # Gradient fill using line color with transparency
        gradient = QLinearGradient(0, pad_top, 0, h)
        fill_color_top = QColor(line_color)
        fill_color_top.setAlpha(100)
        fill_color_bottom = QColor(line_color)
        fill_color_bottom.setAlpha(10)
        gradient.setColorAt(0, fill_color_top)
        gradient.setColorAt(1, fill_color_bottom)

        fill_path = QPainterPath()
        fill_path.moveTo(self._points[0].x(), h)
        fill_path.lineTo(self._points[0])
        if len(self._points) > 1:
            fill_path.connectPath(line_path)
        fill_path.lineTo(self._points[-1].x(), h)
        fill_path.closeSubpath()

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(fill_path)

        # Line
        if len(self._points) > 1:
            pen = QPen(line_color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

        # Hovered point
        if 0 <= self._hovered_index < len(self._points):
            painter.setBrush(line_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self._points[self._hovered_index], 4, 4)

    def mouseMoveEvent(self, event):
        if not self._points:
            return
        mouse_x = event.pos().x()
        closest_idx = min(range(len(self._points)), key=lambda i: abs(self._points[i].x() - mouse_x))
        min_dist = abs(self._points[closest_idx].x() - mouse_x)

        if min_dist < 30 and self._hovered_index != closest_idx:
            self._hovered_index = closest_idx
            self.update()
            self._show_tooltip(closest_idx)
        elif min_dist >= 30 and self._hovered_index != -1:
            self._hovered_index = -1
            self.update()
            self._hide_tooltip()

    def leaveEvent(self, event):
        self._hovered_index = -1
        self.update()
        self._hide_tooltip()

    def _show_tooltip(self, idx: int) -> None:
        if not (0 <= idx < len(self._data)):
            return
        item = self._data[idx]
        date_str = item.get("date", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            fmt = "%#d %b %Y" if os.name == "nt" else "%-d %b %Y"
            formatted = dt.strftime(fmt)
        except ValueError:
            formatted = date_str

        if not self._tooltip:
            self._tooltip = CustomToolTip()
            self._tooltip._position = "top"

        self._tooltip.label.setText(f"{formatted}\n{item.get('requests', 0)} requests")
        self._tooltip.adjustSize()
        pos = self.mapToGlobal(self._points[idx].toPoint())

        # Calculate tooltip position centered above the point
        tooltip_x = pos.x() - self._tooltip.width() // 2
        tooltip_y = pos.y() - self._tooltip.height() - 10

        # Clamp to screen bounds
        screen = QGuiApplication.screenAt(pos)
        if screen:
            screen_geo = screen.geometry()
            tooltip_x = max(screen_geo.left(), min(tooltip_x, screen_geo.right() - self._tooltip.width()))
            tooltip_y = max(screen_geo.top(), min(tooltip_y, screen_geo.bottom() - self._tooltip.height()))

        self._tooltip.move(tooltip_x, tooltip_y)
        self._tooltip.show()

    def _hide_tooltip(self) -> None:
        if self._tooltip:
            self._tooltip.hide()
            self._tooltip = None

    def _create_smooth_path(self) -> QPainterPath:
        path = QPainterPath()
        pts = self._points
        if len(pts) < 2:
            return path
        path.moveTo(pts[0])
        if len(pts) == 2:
            path.lineTo(pts[1])
            return path

        tension = 0.3
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
            cp1_x = p1.x() + (p2.x() - p0.x()) * tension
            cp1_y = p1.y() + (p2.y() - p0.y()) * tension
            cp2_x = p2.x() - (p3.x() - p1.x()) * tension
            cp2_y = p2.y() - (p3.y() - p1.y()) * tension
            path.cubicTo(cp1_x, cp1_y, cp2_x, cp2_y, p2.x(), p2.y())
        return path


class CopilotWidget(BaseWidget):
    """GitHub Copilot Usage Widget with shared instance support."""

    validation_schema = VALIDATION_SCHEMA
    _instances: list["CopilotWidget"] = []
    _shared_timer: QTimer | None = None
    _initialized = False

    def __init__(
        self,
        label: str,
        label_alt: str,
        token: str,
        plan: str,
        tooltip: bool,
        update_interval: int,
        icons: dict[str, str],
        thresholds: dict[str, int],
        menu: dict,
        animation: dict[str, str],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(timer_interval=None, class_name="copilot-widget")

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip_enabled = tooltip
        self._plan = plan
        self._chart_enabled = menu.get("chart", True)
        self._update_interval = update_interval
        self._icons = icons
        self._thresholds = thresholds
        self._menu_config = menu
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._menu: PopupWidget | None = None

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, label, label_alt, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_popup", self._toggle_popup)
        self.register_callback("refresh", lambda: CopilotDataManager.refresh())
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        # Register instance
        if self not in CopilotWidget._instances:
            CopilotWidget._instances.append(self)

        # Initialize shared resources once
        if not CopilotWidget._initialized:
            CopilotWidget._initialized = True
            token_val = token if token != "env" else os.getenv("YASB_COPILOT_TOKEN", "")
            CopilotDataManager.initialize(
                token=token_val, plan=plan, update_interval=update_interval, chart=self._chart_enabled
            )
            CopilotDataManager.register_callback(CopilotWidget._on_data_update)

            CopilotWidget._shared_timer = QTimer()
            CopilotWidget._shared_timer.timeout.connect(CopilotDataManager.refresh)
            CopilotWidget._shared_timer.start(update_interval * 1000)

        # Cleanup on destroy
        try:
            self.destroyed.connect(self._on_destroyed)
        except Exception:
            pass

        self._update_label()

    def _on_destroyed(self):
        if self in CopilotWidget._instances:
            CopilotWidget._instances.remove(self)
        if not CopilotWidget._instances and (timer := CopilotWidget._shared_timer):
            timer.stop()
            CopilotWidget._shared_timer = None
            CopilotWidget._initialized = False

    @classmethod
    def _on_data_update(cls, data: CopilotUsageData):
        for inst in cls._instances[:]:
            try:
                QTimer.singleShot(0, inst._update_label)
            except RuntimeError:
                cls._instances.remove(inst)

    def _toggle_popup(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_popup()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for w in self._widgets:
            w.setVisible(not self._show_alt_label)
        for w in self._widgets_alt:
            w.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        data = CopilotDataManager.get_data()
        used = data.total_requests
        allowance = data.allowance
        pct = (used * 100 // allowance) if allowance else 0

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = [p for p in re.split(r"(<span.*?>.*?</span>)", active_label) if p]

        label_options = {
            "{icon}": self._icons["copilot"],
            "{used}": str(used),
            "{allowance}": str(allowance),
            "{percentage}": str(pct),
            "{total_cost}": f"{data.total_cost:.2f}",
        }

        for i, part in enumerate(label_parts):
            if i >= len(active_widgets):
                break
            text = part
            for key, val in label_options.items():
                text = text.replace(key, val)
            if "<span" in text:
                text = re.sub(r"<span.*?>|</span>", "", text)
            active_widgets[i].setText(text)

        # Update tooltip and state classes
        state_class = (
            "critical"
            if pct >= self._thresholds["critical"]
            else "warning"
            if pct >= self._thresholds["warning"]
            else ""
        )
        tip = f"Error: {data.error}" if data.error else f"Copilot: {used}/{allowance} ({pct}%)"

        for widget in active_widgets:
            if self._tooltip_enabled:
                set_tooltip(widget, tip)
            classes = [c for c in widget.property("class").split() if c not in ("warning", "critical")]
            if state_class:
                classes.append(state_class)
            widget.setProperty("class", " ".join(classes))
            refresh_widget_style(widget)

    def _show_popup(self):
        data = CopilotDataManager.get_data()

        self._menu = PopupWidget(
            self,
            blur=self._menu_config["blur"],
            round_corners=self._menu_config["round_corners"],
            round_corners_type=self._menu_config["round_corners_type"],
            border_color=self._menu_config["border_color"],
        )
        self._menu.setProperty("class", "copilot-menu")

        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if data.plan_type in ("pro", "pro_plus"):
            layout.addWidget(self._create_header(data))

        if data.error:
            layout.addWidget(self._create_error_section(data.error))
        elif data.total_requests or data.requests_by_model:
            layout.addWidget(self._create_progress_section(data))
            layout.addWidget(self._create_spending_section(data))
            if data.requests_by_model:
                layout.addWidget(self._create_model_section(data))
            if self._chart_enabled and data.daily_usage:
                layout.addWidget(self._create_chart_section(data))
        else:
            self._create_empty_state(layout)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._menu.show()

    def _create_empty_state(self, layout: QVBoxLayout) -> None:
        icon_lbl = QLabel(self._icons["copilot"])
        icon_lbl.setProperty("class", "empty-icon")

        msg = QLabel("Loading usage data...")
        msg.setProperty("class", "empty-message")

        center = QVBoxLayout()
        center.addStretch()
        center.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        center.addWidget(msg, alignment=Qt.AlignmentFlag.AlignCenter)
        center.addStretch()
        layout.addLayout(center)

    def _create_header(self, data: CopilotUsageData) -> QLabel:
        plan_names = {"pro": "Pro", "pro_plus": "Pro+"}
        plan_name = plan_names.get(data.plan_type, "")
        header = QLabel(f"<span style='font-weight:bold'>GitHub</span> Copilot ({plan_name})")
        header.setProperty("class", "header")
        return header

    def _create_progress_section(self, data: CopilotUsageData) -> QFrame:
        section = QFrame(self._menu)
        section.setProperty("class", "section progress-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title row with reset date on right
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Premium Requests")
        title.setProperty("class", "section-title")
        title_row.addWidget(title)
        title_row.addStretch()

        now = datetime.now(timezone.utc)
        next_reset = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)
        reset_lbl = QLabel(f"Resets on {next_reset.strftime('%b %d')}")
        reset_lbl.setProperty("class", "reset-date")
        title_row.addWidget(reset_lbl)
        layout.addLayout(title_row)

        bar = ProgressBar()
        bar.setMinimumHeight(8)
        bar.set_value(data.total_requests, data.allowance)
        bar.set_thresholds(self._thresholds["warning"], self._thresholds["critical"])
        layout.addWidget(bar)

        stats = QHBoxLayout()
        stats.setContentsMargins(0, 2, 0, 0)
        pct = (data.total_requests * 100 // data.allowance) if data.allowance else 0

        used_lbl = QLabel(f"{data.total_requests} / {data.allowance}")
        used_lbl.setProperty("class", "usage-count")
        stats.addWidget(used_lbl)
        stats.addStretch()
        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setProperty("class", "usage-percent")
        stats.addWidget(pct_lbl)
        layout.addLayout(stats)

        return section

    def _create_spending_section(self, data: CopilotUsageData) -> QFrame:
        section = QFrame()
        section.setProperty("class", "section spending-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Spending This Month")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        overage = max(0, data.total_requests - data.allowance)

        layout.addWidget(self._stat_row("Included:", f"{min(data.total_requests, data.allowance)} requests"))
        layout.addWidget(self._stat_row("Overage:", f"{overage} requests (${overage * 0.04:.2f})"))
        total_row = self._stat_row("Total Cost:", f"${data.total_cost:.2f}")
        total_row.setProperty("class", "stat-row total")
        layout.addWidget(total_row)

        return section

    def _stat_row(self, label: str, value: str) -> QFrame:
        row = QFrame()
        row.setProperty("class", "stat-row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(0)

        lbl = QLabel(label)
        lbl.setProperty("class", "stat-label")
        layout.addWidget(lbl)
        layout.addStretch()
        val = QLabel(value)
        val.setProperty("class", "stat-value")
        layout.addWidget(val)

        return row

    def _create_model_section(self, data: CopilotUsageData) -> QFrame:
        section = QFrame()
        section.setProperty("class", "section model-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Usage by Model")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        max_count = max(data.requests_by_model.values(), default=1)
        sorted_models = sorted(data.requests_by_model.items(), key=lambda x: x[1], reverse=True)

        for i, (model, count) in enumerate(sorted_models[:5]):
            row = QFrame(self._menu)
            row.setProperty("class", "model-usage-row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setSpacing(0)

            name_lbl = QLabel(model)
            name_lbl.setProperty("class", "model-name")
            name_lbl.setFixedWidth(120)
            row_layout.addWidget(name_lbl)

            bar = ProgressBar()
            bar.set_value(count, max_count)
            bar.set_class(f"model-{i % 5}")
            row_layout.addWidget(bar, 1)

            count_lbl = QLabel(str(count))
            count_lbl.setProperty("class", "model-count")
            count_lbl.setFixedWidth(50)
            count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(count_lbl)

            layout.addWidget(row)

        return section

    def _create_chart_section(self, data: CopilotUsageData) -> QFrame:
        section = QFrame()
        section.setProperty("class", "section chart-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Daily Usage")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        chart = UsageChartWidget()
        chart.set_data(data.daily_usage)
        layout.addWidget(chart)

        return section

    def _create_error_section(self, error: str) -> QFrame:
        section = QFrame()
        section.setProperty("class", "section error-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        icon = QLabel(self._icons["error"])
        icon.setProperty("class", "error-icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        msg = QLabel(error)
        msg.setProperty("class", "error-message")
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        return section

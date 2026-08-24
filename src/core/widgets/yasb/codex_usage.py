import re
import time
from calendar import monthrange
from datetime import date, datetime
from math import log1p
from typing import Any

from PyQt6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QVBoxLayout,
)

from core.utils.qobject import is_valid_qobject
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, build_progress_widget, refresh_widget_style
from core.validation.widgets.yasb.codex_usage import CodexUsageConfig
from core.widgets.base import BaseWidget
from core.widgets.services.codex_usage.codex_api import CodexUsageService


class UsageBar(QFrame):
    """CSS-styleable progress track used by the details popup."""

    def __init__(self, value: float, level: str, parent: QFrame | None = None):
        super().__init__(parent)
        self._value = max(0.0, min(100.0, value))
        self.setProperty("class", f"progress {level}")
        self._fill = QFrame(self)
        self._fill.setProperty("class", "fill")

    def set_value(self, value: float, level: str) -> None:
        self._value = max(0.0, min(100.0, value))
        self.setProperty("class", f"progress {level}")
        refresh_widget_style(self, self._fill)
        self._update_fill()

    def _update_fill(self) -> None:
        fill_width = int(self.width() * self._value / 100)
        if fill_width > 0:
            fill_width = max(fill_width, self.height())
        self._fill.setGeometry(0, 0, fill_width, self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_fill()


class TokenBar(QFrame):
    """CSS-styleable horizontal bar for per-model token totals."""

    def __init__(self, parent: QFrame | None = None):
        super().__init__(parent)
        self.setProperty("class", "model-bar")
        self._ratio = 0.0
        self._fill = QFrame(self)
        self._fill.setProperty("class", "fill")

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._update_fill()

    def _update_fill(self) -> None:
        width = int(self.width() * self._ratio)
        if width > 0:
            width = max(width, self.height())
        self._fill.setGeometry(0, 0, width, self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_fill()


class RefreshButton(QPushButton):
    """Segoe Fluent refresh button with a lightweight rotation animation."""

    def __init__(self, icon: str, parent: QFrame | None = None):
        super().__init__(parent)
        self._icon = icon
        self._angle = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(360.0)
        self._animation.setDuration(720)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._set_angle)

    def _set_angle(self, value: Any) -> None:
        self._angle = float(value)
        self.update()

    def start_animation(self) -> None:
        if self._animation.state() != QVariantAnimation.State.Running:
            self._animation.start()

    def stop_animation(self) -> None:
        self._animation.stop()
        self._angle = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""

        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setBrush(self.palette().color(self.foregroundRole()))

        icon = QPainterPath()
        icon.addText(0, 0, self.font(), self._icon)
        icon.translate(-icon.boundingRect().center())
        painter.translate(QPointF(self.width() / 2, self.height() / 2))
        painter.rotate(self._angle)
        painter.drawPath(icon)


class CodexUsageWidget(BaseWidget):
    """Display remaining Codex subscription usage reported by Codex app-server."""

    validation_schema = CodexUsageConfig

    def __init__(self, config: CodexUsageConfig):
        super().__init__(class_name="codex-usage")
        self.config = config
        self._show_alt_label = False
        self._menu: PopupWidget | None = None
        self._section_widgets: dict[str, dict[str, Any]] = {}
        self._detail_widgets: dict[str, QLabel] = {}
        self._pages: dict[str, QFrame] = {}
        self._visible_pages: list[str] = []
        self._current_page = "overview"
        self._pager: QFrame | None = None
        self._page_stack: QStackedWidget | None = None
        self._page_navigation: QFrame | None = None
        self._page_previous: QPushButton | None = None
        self._page_next: QPushButton | None = None
        self._page_indicator: QLabel | None = None
        self._overview_tokens: QFrame | None = None
        self._overview_empty: QLabel | None = None
        self._token_widgets: dict[str, QLabel] = {}
        self._reset_credit_widgets: list[dict[str, Any]] = []
        self._reset_credits_count: QLabel | None = None
        self._reset_credits_empty: QLabel | None = None
        self._heatmap_cells: list[QFrame] = []
        self._heatmap_month = date.today().replace(day=1)
        self._heatmap_month_label: QLabel | None = None
        self._heatmap_previous: QPushButton | None = None
        self._heatmap_next: QPushButton | None = None
        self._heatmap_history_note: QLabel | None = None
        self._model_widgets: list[dict[str, Any]] = []
        self._refresh_button: RefreshButton | None = None
        self._refresh_status: QLabel | None = None
        self._refresh_pending = False
        self._refresh_feedback_timer = QTimer(self)
        self._refresh_feedback_timer.setSingleShot(True)
        self._refresh_feedback_timer.timeout.connect(self._hide_refresh_feedback)
        self._service_released = False

        self._service = CodexUsageService.get_instance(
            self.config.codex_path,
            self.config.update_interval,
            self.config.cache_ttl,
            self.config.timeout,
            self.config.show_token_usage,
        )
        self._data: dict[str, Any] = self._service.latest()

        self.progress_widget = build_progress_widget(self, self.config.progress_bar.model_dump())
        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)
        if self.progress_widget:
            position = 0 if self.config.progress_bar.position == "left" else self._widget_container_layout.count()
            self._widget_container_layout.insertWidget(position, self.progress_widget)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("refresh", self._refresh)
        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

        self._service.data_ready.connect(self._on_data)
        self.destroyed.connect(lambda *_: self._release_service())
        self._update_label()

    def closeEvent(self, event) -> None:
        self._release_service()
        super().closeEvent(event)

    def _release_service(self) -> None:
        if self._service_released:
            return
        self._service_released = True
        try:
            self._service.release()
        except RuntimeError:
            pass

    def _refresh(self) -> None:
        if is_valid_qobject(self._menu) and self._menu.isVisible() and is_valid_qobject(self._refresh_button):
            self._refresh_pending = True
            self._refresh_feedback_timer.stop()
            self._refresh_button.setEnabled(False)
            self._refresh_button.start_animation()
            self._set_refresh_feedback("Refreshing…", "busy")
        self._service.refresh_now()

    def _on_data(self, data: dict[str, Any]) -> None:
        self._data = data
        self._update_label()
        self._sync_menu()
        self._finish_refresh_feedback(not data.get("stale"))

    def _set_refresh_feedback(self, text: str, state: str) -> None:
        if not is_valid_qobject(self._refresh_status):
            return
        self._refresh_status.setText(text)
        self._refresh_status.setProperty("class", f"refresh-status {state}")
        self._refresh_status.setVisible(bool(text))
        refresh_widget_style(self._refresh_status)

    def _finish_refresh_feedback(self, success: bool) -> None:
        if not self._refresh_pending:
            return
        self._refresh_pending = False
        if is_valid_qobject(self._refresh_button):
            self._refresh_button.stop_animation()
            self._refresh_button.setEnabled(True)
        self._set_refresh_feedback(
            "Refresh successful" if success else "Refresh failed", "success" if success else "error"
        )
        self._refresh_feedback_timer.start(2200)

    def _hide_refresh_feedback(self) -> None:
        if is_valid_qobject(self._refresh_status):
            self._refresh_status.hide()

    def _window(self, name: str) -> dict[str, Any]:
        value = self._data.get(name)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _percent(value: Any) -> str:
        return str(round(value)) if isinstance(value, (int, float)) else "--"

    @staticmethod
    def _percent_value(value: Any) -> float:
        return float(value) if isinstance(value, (int, float)) else 0.0

    @staticmethod
    def _duration_name(minutes: Any, fallback: str) -> str:
        if not isinstance(minutes, (int, float)) or minutes <= 0:
            return fallback
        minutes = int(minutes)
        if minutes % 10080 == 0:
            return f"{minutes // 10080}w"
        if minutes % 1440 == 0:
            return f"{minutes // 1440}d"
        if minutes % 60 == 0:
            return f"{minutes // 60}h"
        return f"{minutes}m"

    @staticmethod
    def _fmt_reset(timestamp: Any) -> str:
        if not isinstance(timestamp, (int, float)):
            return "--"
        seconds = max(0, int(timestamp - time.time()))
        minutes = seconds // 60
        days, remainder = divmod(minutes, 1440)
        hours, minutes = divmod(remainder, 60)
        if days:
            return f"{days}d {hours}h"
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"

    @staticmethod
    def _fmt_reset_at(timestamp: Any) -> str:
        if not isinstance(timestamp, (int, float)):
            return "--"
        reset = datetime.fromtimestamp(timestamp)
        template = "%b %d, %H:%M" if reset.year == datetime.now().year else "%Y-%m-%d %H:%M"
        return reset.strftime(template)

    @staticmethod
    def _fmt_updated(timestamp: Any) -> str:
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            return "Never"
        seconds = max(0, int(time.time() - timestamp))
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _level_class(remaining: Any) -> str:
        if not isinstance(remaining, (int, float)):
            return "unknown"
        if remaining <= 20:
            return "critical"
        if remaining <= 50:
            return "low"
        return "good"

    def _format_values(self) -> dict[str, str]:
        primary = self._window("primary")
        secondary = self._window("secondary")
        return {
            "primary_remaining": self._percent(primary.get("remaining")),
            "secondary_remaining": self._percent(secondary.get("remaining")),
            "primary_used": self._percent(primary.get("used")),
            "secondary_used": self._percent(secondary.get("used")),
            "primary_window": self._duration_name(primary.get("duration_mins"), "primary"),
            "secondary_window": self._duration_name(secondary.get("duration_mins"), "secondary"),
            "primary_reset": self._fmt_reset(primary.get("resets_at")),
            "secondary_reset": self._fmt_reset(secondary.get("resets_at")),
            "plan": str(self._data.get("plan") or "--"),
            "credits": str(self._data.get("credits") if self._data.get("credits") is not None else "--"),
            "stale": self.config.stale_icon if self._data.get("stale") else "",
        }

    def _active_window(self) -> dict[str, Any]:
        name = "secondary" if self._show_alt_label else "primary"
        return self._window(name)

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        template = self.config.label_alt if self._show_alt_label else self.config.label
        values = self._format_values()
        parts = [part for part in re.split(r"(<span.*?>.*?</span>)", template) if part.strip()]

        for index, part in enumerate(parts):
            if index >= len(active_widgets):
                continue
            widget = active_widgets[index]
            text = re.sub(r"<span.*?>|</span>", "", part).strip() if "<span" in part else part.strip()
            try:
                rendered = text.format(**values)
            except KeyError, ValueError:
                rendered = text
            widget.setText(rendered)
            widget.setVisible(bool(rendered))

        active_window = self._active_window()
        if self.progress_widget:
            self.progress_widget.setVisible(bool(active_window))
            if active_window:
                self.progress_widget.set_value(self._percent_value(active_window.get("remaining")))

        if self.config.tooltip:
            primary = self._window("primary")
            secondary = self._window("secondary")
            lines = [
                f"Codex {self._duration_name(primary.get('duration_mins'), 'primary')}: "
                f"{self._percent(primary.get('remaining'))}% remaining "
                f"({self._percent(primary.get('used'))}% used)",
            ]
            if secondary:
                lines.append(
                    f"Codex {self._duration_name(secondary.get('duration_mins'), 'secondary')}: "
                    f"{self._percent(secondary.get('remaining'))}% remaining "
                    f"({self._percent(secondary.get('used'))}% used)"
                )
            if self._data.get("stale"):
                lines.append(f"Cached data: {self._data.get('error') or 'refresh pending'}")
            set_tooltip(self, "\n".join(lines))
        refresh_widget_style(*active_widgets)

    def _toggle_menu(self) -> None:
        if is_valid_qobject(self._menu) and self._menu.isVisible():
            self._menu.hide_animated()
            return
        self._show_menu()

    def _show_menu(self) -> None:
        if not is_valid_qobject(self._menu):
            self._build_menu()
        self._sync_menu()
        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()
        self._service.refresh_now()

    def _build_section(self, name: str, fallback_title: str) -> QFrame:
        section = QFrame()
        section.setProperty("class", f"section {name}")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(fallback_title)
        title.setProperty("class", "title")
        layout.addWidget(title)

        progress = UsageBar(0, "unknown")
        layout.addWidget(progress)

        stats = QFrame()
        stats.setProperty("class", "stats")
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(0)
        used = QLabel("--% used")
        used.setProperty("class", "used")
        stats_layout.addWidget(used)
        stats_layout.addStretch()
        remaining = QLabel("--% remaining")
        remaining.setProperty("class", "remaining unknown")
        stats_layout.addWidget(remaining)
        layout.addWidget(stats)

        timing = QFrame()
        timing.setProperty("class", "timing")
        timing_layout = QHBoxLayout(timing)
        timing_layout.setContentsMargins(0, 0, 0, 0)
        timing_layout.setSpacing(8)
        reset = QLabel("Reset unknown")
        reset.setProperty("class", "reset")
        timing_layout.addWidget(reset)
        timing_layout.addStretch()
        date = QLabel("--")
        date.setProperty("class", "date")
        timing_layout.addWidget(date)
        layout.addWidget(timing)
        self._section_widgets[name] = {
            "frame": section,
            "title": title,
            "progress": progress,
            "reset": reset,
            "used": used,
            "remaining": remaining,
            "date": date,
        }
        return section

    @staticmethod
    def _format_tokens(value: Any) -> str:
        if not isinstance(value, (int, float)):
            return "--"
        value = max(0, float(value))
        for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
            if value >= divisor:
                formatted = f"{value / divisor:.1f}".rstrip("0").rstrip(".")
                return f"{formatted}{suffix}"
        return str(round(value))

    @staticmethod
    def _fmt_credit_date(timestamp: Any, prefix: str) -> str:
        if not isinstance(timestamp, (int, float)):
            return "Does not expire" if prefix == "Expires" else ""
        value = datetime.fromtimestamp(timestamp)
        template = "%b %d" if value.year == datetime.now().year else "%b %d, %Y"
        return f"{prefix} {value.strftime(template)}"

    @staticmethod
    def _reset_credit_title(credit: dict[str, Any]) -> str:
        title = credit.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return "Full reset" if credit.get("reset_type") == "codexRateLimits" else "Usage reset"

    def _build_resets_page(self) -> QFrame:
        page = QFrame()
        page.setProperty("class", "page resets")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QFrame()
        header.setProperty("class", "reset-credits-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("Usage limit resets")
        title.setProperty("class", "section-title")
        header_layout.addWidget(title)
        header_layout.addStretch()
        count = QLabel("")
        count.setProperty("class", "reset-credits-count")
        header_layout.addWidget(count)
        self._reset_credits_count = count
        layout.addWidget(header)

        empty = QLabel("No reset credits available")
        empty.setProperty("class", "empty-state reset-credits-empty")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setVisible(False)
        self._reset_credits_empty = empty
        layout.addWidget(empty)

        for _ in range(3):
            card = QFrame()
            card.setProperty("class", "reset-credit-card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(2)
            card_title = QLabel("Full reset")
            card_title.setProperty("class", "reset-credit-title")
            card_layout.addWidget(card_title)
            expiration = QLabel("Expires --")
            expiration.setProperty("class", "reset-credit-expiration")
            card_layout.addWidget(expiration)
            card.setVisible(False)
            layout.addWidget(card)
            self._reset_credit_widgets.append({"frame": card, "title": card_title, "expiration": expiration})

        layout.addStretch()
        self._pages["resets"] = page
        return page

    def _build_models_page(self) -> QFrame:
        page = QFrame()
        page.setProperty("class", "page models")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("Models · 30 days")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        for index in range(5):
            row = QFrame()
            row.setProperty("class", f"model-row row-{index + 1}")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            name = QLabel("--")
            name.setProperty("class", "model-name")
            bar = TokenBar()
            value = QLabel("--")
            value.setProperty("class", "model-value")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(name)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(value)
            layout.addWidget(row)
            self._model_widgets.append({"row": row, "name": name, "bar": bar, "value": value})

        layout.addStretch()
        self._pages["models"] = page
        return page

    def _build_overview_page(self) -> QFrame:
        page = QFrame()
        page.setProperty("class", "page overview")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.config.menu.show_overview:
            tokens = QFrame()
            tokens.setProperty("class", "overview-tokens")
            tokens_layout = QVBoxLayout(tokens)
            tokens_layout.setContentsMargins(0, 0, 0, 0)
            tokens_layout.setSpacing(0)
            title = QLabel("Token totals")
            title.setProperty("class", "section-title")
            tokens_layout.addWidget(title)

            periods = QFrame()
            periods.setProperty("class", "periods")
            periods_layout = QGridLayout(periods)
            periods_layout.setContentsMargins(0, 0, 0, 0)
            periods_layout.setHorizontalSpacing(8)
            periods_layout.setVerticalSpacing(2)
            for column, (label, key) in enumerate(
                (("TODAY", "today"), ("7 DAYS", "week"), ("30 DAYS", "month"), ("YEAR", "year"))
            ):
                name = QLabel(label)
                name.setProperty("class", "period-name")
                name.setAlignment(Qt.AlignmentFlag.AlignCenter)
                value = QLabel("--")
                value.setProperty("class", "period-value")
                value.setAlignment(Qt.AlignmentFlag.AlignCenter)
                periods_layout.addWidget(name, 0, column)
                periods_layout.addWidget(value, 1, column)
                self._token_widgets[key] = value
            tokens_layout.addWidget(periods)
            self._overview_tokens = tokens
            layout.addWidget(tokens)

            empty = QLabel("Token history is unavailable")
            empty.setProperty("class", "empty-state")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setVisible(False)
            self._overview_empty = empty
            layout.addWidget(empty)

        if self.config.menu.show_details:
            layout.addWidget(self._build_details_section())

        layout.addStretch()
        self._pages["overview"] = page
        return page

    def _build_activity_page(self) -> QFrame:
        page = QFrame()
        page.setProperty("class", "page activity")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        activity_header = QFrame()
        activity_header.setProperty("class", "activity-header")
        activity_header_layout = QHBoxLayout(activity_header)
        activity_header_layout.setContentsMargins(0, 0, 0, 0)
        activity_header_layout.setSpacing(4)
        activity_title = QLabel("Activity")
        activity_title.setProperty("class", "activity-title")
        activity_header_layout.addWidget(activity_title)
        activity_header_layout.addStretch()
        previous = QPushButton(self.config.menu.previous_page_icon)
        previous.setProperty("class", "month-nav previous")
        previous.setAccessibleName("Previous month")
        set_tooltip(previous, "Previous month")
        previous.clicked.connect(lambda: self._change_heatmap_month(-1))
        activity_header_layout.addWidget(previous)
        self._heatmap_previous = previous
        month_label = QLabel("")
        month_label.setProperty("class", "month-label")
        month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        activity_header_layout.addWidget(month_label)
        self._heatmap_month_label = month_label
        next_button = QPushButton(self.config.menu.next_page_icon)
        next_button.setProperty("class", "month-nav next")
        next_button.setAccessibleName("Next month")
        set_tooltip(next_button, "Next month")
        next_button.clicked.connect(lambda: self._change_heatmap_month(1))
        activity_header_layout.addWidget(next_button)
        self._heatmap_next = next_button
        layout.addWidget(activity_header)

        heatmap = QFrame()
        heatmap.setProperty("class", "heatmap")
        heatmap_layout = QGridLayout(heatmap)
        heatmap_layout.setContentsMargins(0, 0, 0, 0)
        heatmap_layout.setHorizontalSpacing(4)
        heatmap_layout.setVerticalSpacing(4)
        heatmap_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        for column, weekday in enumerate(("M", "T", "W", "T", "F", "S", "S")):
            label = QLabel(weekday)
            label.setProperty("class", "weekday")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heatmap_layout.addWidget(label, 0, column)
        for index in range(42):
            cell = QFrame()
            cell.setProperty("class", "cell level-0")
            heatmap_layout.addWidget(cell, index // 7 + 1, index % 7)
            self._heatmap_cells.append(cell)
        layout.addWidget(heatmap)
        history_note = QLabel("")
        history_note.setProperty("class", "history-note")
        history_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        history_note.setWordWrap(True)
        history_note.setVisible(False)
        layout.addWidget(history_note)
        self._heatmap_history_note = history_note

        layout.addStretch()
        self._pages["activity"] = page
        return page

    @staticmethod
    def _shift_month(month: date, amount: int) -> date:
        month_index = month.year * 12 + month.month - 1 + amount
        return date(month_index // 12, month_index % 12 + 1, 1)

    def _change_heatmap_month(self, amount: int) -> None:
        self._heatmap_month = self._shift_month(self._heatmap_month, amount)
        self._sync_heatmap()

    def _sync_heatmap(self) -> None:
        tokens = self._data.get("tokens")
        if not isinstance(tokens, dict):
            return
        daily = tokens.get("daily") if isinstance(tokens.get("daily"), dict) else {}
        current_month = date.today().replace(day=1)
        earliest_navigation_month = self._shift_month(current_month, -11)
        try:
            history_start = date.fromisoformat(str(tokens.get("history_start")))
        except ValueError:
            history_start = date.today()
        self._heatmap_month = min(current_month, max(earliest_navigation_month, self._heatmap_month))
        if is_valid_qobject(self._heatmap_month_label):
            self._heatmap_month_label.setText(self._heatmap_month.strftime("%B %Y").upper())
        if is_valid_qobject(self._heatmap_previous):
            self._heatmap_previous.setEnabled(self._heatmap_month > earliest_navigation_month)
        if is_valid_qobject(self._heatmap_next):
            self._heatmap_next.setEnabled(self._heatmap_month < current_month)

        first_weekday, days_in_month = monthrange(self._heatmap_month.year, self._heatmap_month.month)
        month_end = date(self._heatmap_month.year, self._heatmap_month.month, days_in_month)
        has_local_history = month_end >= history_start
        if is_valid_qobject(self._heatmap_history_note):
            self._heatmap_history_note.setText("No local token history for this month")
            self._heatmap_history_note.setVisible(not has_local_history)
        month_values = [
            daily.get(date(self._heatmap_month.year, self._heatmap_month.month, day).isoformat(), 0)
            for day in range(1, days_in_month + 1)
        ]
        maximum = max((value for value in month_values if isinstance(value, (int, float))), default=0)
        today = date.today()
        for index, cell in enumerate(self._heatmap_cells):
            day = index - first_weekday + 1
            if day < 1 or day > days_in_month:
                cell.setProperty("class", "cell outside")
                set_tooltip(cell, "")
                continue
            cell_date = date(self._heatmap_month.year, self._heatmap_month.month, day)
            value = daily.get(cell_date.isoformat(), 0)
            if cell_date < history_start:
                level = "unavailable"
            elif cell_date > today:
                level = "future"
            elif not isinstance(value, (int, float)) or value <= 0 or maximum <= 0:
                level = "level-0"
            else:
                level = f"level-{max(1, min(4, round(log1p(value) / log1p(maximum) * 4)))}"
            cell.setProperty("class", f"cell {level}")
            tooltip = (
                f"{cell_date.isoformat()}: no local token history"
                if cell_date < history_start
                else f"{cell_date.isoformat()}: {self._format_tokens(value)} tokens"
            )
            set_tooltip(cell, tooltip)
        refresh_widget_style(*self._heatmap_cells)

    def _build_details_section(self) -> QFrame:
        section = QFrame()
        section.setProperty("class", "details")
        layout = QGridLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)

        rows = (
            ("Plan", "plan"),
            ("Credits", "credits"),
            ("Updated", "updated"),
            ("Status", "status"),
        )
        for row, (title, key) in enumerate(rows):
            name = QLabel(title)
            name.setProperty("class", "name")
            layout.addWidget(name, row, 0)
            value = QLabel("--")
            value.setProperty("class", f"value {key}")
            layout.addWidget(value, row, 1)
            self._detail_widgets[key] = value

        error = QLabel("")
        error.setProperty("class", "error")
        error.setWordWrap(True)
        layout.addWidget(error, len(rows), 0, 1, 2)
        self._detail_widgets["error"] = error
        return section

    def _build_pager(self) -> QFrame:
        pager = QFrame()
        pager.setProperty("class", "pager")
        pager_layout = QVBoxLayout(pager)
        pager_layout.setContentsMargins(0, 0, 0, 0)
        pager_layout.setSpacing(0)

        navigation = QFrame()
        navigation.setProperty("class", "page-nav")
        self._page_navigation = navigation
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(0)

        previous = QPushButton(self.config.menu.previous_page_icon)
        previous.setProperty("class", "page-button previous")
        previous.setAccessibleName("Previous Codex usage page")
        set_tooltip(previous, "Previous page")
        previous.clicked.connect(lambda: self._change_page(-1))
        navigation_layout.addWidget(previous)
        self._page_previous = previous

        indicator = QLabel("")
        indicator.setProperty("class", "page-indicator")
        indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation_layout.addWidget(indicator, 1)
        self._page_indicator = indicator

        next_button = QPushButton(self.config.menu.next_page_icon)
        next_button.setProperty("class", "page-button next")
        next_button.setAccessibleName("Next Codex usage page")
        set_tooltip(next_button, "Next page")
        next_button.clicked.connect(lambda: self._change_page(1))
        navigation_layout.addWidget(next_button)
        self._page_next = next_button
        pager_layout.addWidget(navigation)

        stack = QStackedWidget()
        stack.setProperty("class", "page-stack")
        # Fits the activity grid while keeping every page stable across Windows display scales.
        stack.setFixedHeight(220)
        self._page_stack = stack
        if self.config.menu.show_overview or self.config.menu.show_details:
            stack.addWidget(self._build_overview_page())
        if self.config.menu.show_resets:
            stack.addWidget(self._build_resets_page())
        if self.config.show_token_usage and self.config.menu.show_models:
            stack.addWidget(self._build_models_page())
        if self.config.show_token_usage and self.config.menu.show_activity:
            stack.addWidget(self._build_activity_page())
        pager_layout.addWidget(stack)

        self._pager = pager
        return pager

    def _change_page(self, amount: int) -> None:
        if self._current_page not in self._visible_pages:
            return
        index = self._visible_pages.index(self._current_page) + amount
        if 0 <= index < len(self._visible_pages):
            self._current_page = self._visible_pages[index]
            self._sync_pager()

    def _sync_pager(self) -> None:
        if not is_valid_qobject(self._pager) or not is_valid_qobject(self._page_stack):
            return
        tokens = self._data.get("tokens")
        has_tokens = self.config.show_token_usage and isinstance(tokens, dict)
        models = tokens.get("models") if has_tokens and isinstance(tokens.get("models"), dict) else {}
        daily = tokens.get("daily") if has_tokens and isinstance(tokens.get("daily"), dict) else {}
        reset_credits = self._data.get("reset_credits")

        if is_valid_qobject(self._overview_tokens):
            self._overview_tokens.setVisible(has_tokens)
        if is_valid_qobject(self._overview_empty):
            self._overview_empty.setVisible(not has_tokens)

        visible_pages: list[str] = []
        if "overview" in self._pages:
            visible_pages.append("overview")
        if "resets" in self._pages and isinstance(reset_credits, dict):
            visible_pages.append("resets")
        if "models" in self._pages and models:
            visible_pages.append("models")
        if "activity" in self._pages and daily:
            visible_pages.append("activity")
        self._visible_pages = visible_pages

        self._pager.setVisible(bool(visible_pages))
        if not visible_pages:
            return
        if self._current_page not in visible_pages:
            self._current_page = "overview" if "overview" in visible_pages else visible_pages[0]
        index = visible_pages.index(self._current_page)
        self._page_stack.setCurrentWidget(self._pages[self._current_page])

        show_navigation = len(visible_pages) > 1
        self._page_navigation.setVisible(show_navigation)
        if not show_navigation:
            return
        overview_title = "Overview" if self.config.menu.show_overview else "Details"
        titles = {"overview": overview_title, "resets": "Resets", "models": "Models", "activity": "Activity"}
        self._page_previous.setEnabled(index > 0)
        self._page_next.setEnabled(index < len(visible_pages) - 1)
        self._page_indicator.setText(f"{titles[self._current_page]}  ·  {index + 1} / {len(visible_pages)}")
        self._page_indicator.setAccessibleName(
            f"{titles[self._current_page]} page, {index + 1} of {len(visible_pages)}"
        )

    def _build_menu(self) -> None:
        self._menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
            persistent=True,
        )
        self._menu.setProperty("class", "codex-usage-menu")
        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Codex Usage")
        title.setProperty("class", "text")
        header_layout.addWidget(title)
        header_layout.addStretch()
        refresh_status = QLabel("")
        refresh_status.setProperty("class", "refresh-status")
        refresh_status.setVisible(False)
        header_layout.addWidget(refresh_status)
        self._refresh_status = refresh_status

        refresh = RefreshButton(self.config.menu.refresh_icon)
        refresh.setProperty("class", "refresh")
        refresh.setAccessibleName("Refresh Codex usage")
        set_tooltip(refresh, "Refresh now")
        refresh.clicked.connect(self._refresh)
        header_layout.addSpacing(6)
        header_layout.addWidget(refresh)
        self._refresh_button = refresh
        layout.addWidget(header)
        layout.addWidget(self._build_section("primary", "Primary"))
        layout.addWidget(self._build_section("secondary", "Secondary"))
        layout.addWidget(self._build_pager())

    def _sync_reset_credits(self) -> None:
        if not is_valid_qobject(self._reset_credits_count):
            return
        summary = self._data.get("reset_credits")
        if not isinstance(summary, dict):
            return
        available_count = summary.get("available_count")
        available_count = max(0, int(available_count)) if isinstance(available_count, (int, float)) else 0
        suffix = "credit" if available_count == 1 else "credits"
        self._reset_credits_count.setText(f"{available_count} {suffix}")

        credits = summary.get("credits")
        credit_items = [credit for credit in credits if isinstance(credit, dict)] if isinstance(credits, list) else []
        if is_valid_qobject(self._reset_credits_empty):
            if credits is None and available_count:
                message = f"{available_count} reset {suffix} available; details unavailable"
            else:
                message = "No reset credits available"
            self._reset_credits_empty.setText(message)
            self._reset_credits_empty.setVisible(not credit_items)

        for index, widgets in enumerate(self._reset_credit_widgets):
            visible = index < len(credit_items)
            widgets["frame"].setVisible(visible)
            if not visible:
                continue
            credit = credit_items[index]
            title = self._reset_credit_title(credit)
            expiration = self._fmt_credit_date(credit.get("expires_at"), "Expires")
            widgets["title"].setText(title)
            widgets["expiration"].setText(expiration)
            description = credit.get("description")
            tooltip = description.strip() if isinstance(description, str) and description.strip() else expiration
            granted = self._fmt_credit_date(credit.get("granted_at"), "Granted")
            if granted:
                tooltip = f"{tooltip}\n{granted}"
            widgets["frame"].setAccessibleName(f"{title}, {expiration}")
            set_tooltip(widgets["frame"], tooltip)

    def _sync_menu(self) -> None:
        if not is_valid_qobject(self._menu):
            return
        for name, fallback in (("primary", "Primary"), ("secondary", "Secondary")):
            widgets = self._section_widgets.get(name)
            if not widgets:
                continue
            window = self._window(name)
            widgets["frame"].setVisible(bool(window))
            if not window:
                continue
            remaining = window.get("remaining")
            level = self._level_class(remaining)
            duration = self._duration_name(window.get("duration_mins"), fallback)
            widgets["title"].setText(duration)
            widgets["progress"].set_value(self._percent_value(remaining), level)
            widgets["used"].setText(f"{self._percent(window.get('used'))}% used")
            widgets["remaining"].setText(f"{self._percent(remaining)}% remaining")
            widgets["remaining"].setProperty("class", f"remaining {level}")
            widgets["reset"].setText(f"Resets in {self._fmt_reset(window.get('resets_at'))}")
            widgets["date"].setText(self._fmt_reset_at(window.get("resets_at")))
            refresh_widget_style(widgets["remaining"])

        tokens = self._data.get("tokens")
        has_tokens = self.config.show_token_usage and isinstance(tokens, dict)
        if has_tokens:
            periods = tokens.get("periods") if isinstance(tokens.get("periods"), dict) else {}
            for name, widget in self._token_widgets.items():
                widget.setText(self._format_tokens(periods.get(name)))

            self._sync_heatmap()

            models = tokens.get("models") if isinstance(tokens.get("models"), dict) else {}
            model_items = [
                (model, value) for model, value in models.items() if isinstance(value, (int, float)) and value >= 0
            ][: len(self._model_widgets)]
            model_maximum = max((value for _, value in model_items), default=0)
            for index, widgets in enumerate(self._model_widgets):
                visible = index < len(model_items)
                widgets["row"].setVisible(visible)
                if not visible:
                    continue
                model, value = model_items[index]
                widgets["name"].setText(str(model))
                widgets["value"].setText(self._format_tokens(value))
                widgets["bar"].set_ratio(float(value) / model_maximum if model_maximum else 0)

        if self._detail_widgets:
            stale = bool(self._data.get("stale"))
            self._detail_widgets["plan"].setText(str(self._data.get("plan") or "--"))
            credits = self._data.get("credits")
            self._detail_widgets["credits"].setText(str(credits if credits is not None else "--"))
            self._detail_widgets["updated"].setText(self._fmt_updated(self._data.get("fetched_at")))
            self._detail_widgets["status"].setText("Cached" if stale else "Live")
            self._detail_widgets["status"].setProperty("class", f"value status {'stale' if stale else 'live'}")
            error = str(self._data.get("error") or "") if stale else ""
            self._detail_widgets["error"].setText(error)
            self._detail_widgets["error"].setVisible(bool(error))
            set_tooltip(self._detail_widgets["error"], error)
            refresh_widget_style(self._detail_widgets["status"], self._detail_widgets["error"])
        self._sync_reset_credits()
        self._sync_pager()

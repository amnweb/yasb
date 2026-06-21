import re
from datetime import UTC, datetime
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.utils.stat_popup import GraphWidget, PinnablePopup, create_pin_button
from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.claude_usage import ClaudeUsageConfig
from core.widgets.base import BaseWidget
from core.widgets.services.claude_usage.claude_api import ClaudeUsageService
from core.widgets.services.claude_usage.status import STATUS_LEVELS, ClaudeStatusService
from core.widgets.services.claude_usage.token_history import TokenHistoryService, summarize

_TOKEN_PERIODS: list[tuple[str, str]] = [
    ("session", "Session"),
    ("today", "Today"),
    ("week", "Week"),
    ("month", "Month"),
    ("year", "Year"),
]
_EMPTY_TOKEN_SUMMARY: dict[str, Any] = {
    "totals": {},
    "series_by_period": {},
    "models_by_period": {},
    "session_id": None,
}


class UsageBar(QFrame):
    """A rounded progress bar drawn as a track QFrame with a child `.fill` QFrame.

    Keeps the fill at least as wide as it is tall so the rounded corners are preserved at
    low values (the QProgressBar::chunk square-fill issue), and stays fully CSS-styleable.
    """

    def __init__(self, value: int, level: str, accent: str = "", parent: QFrame | None = None):
        super().__init__(parent)
        self._value = max(0, min(100, value))
        self.setProperty("class", " ".join(c for c in ("progress", level, accent) if c))
        self._fill = QFrame(self)
        self._fill.setProperty("class", "fill")

    def _update_fill(self) -> None:
        fill_width = int(self.width() * self._value / 100)
        if fill_width > 0:
            fill_width = max(fill_width, self.height())
        self._fill.setGeometry(0, 0, fill_width, self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_fill()


class ClaudeUsageWidget(BaseWidget):
    validation_schema = ClaudeUsageConfig

    # Shown via {stale} when Claude Code's OAuth token has expired (nf-fa-warning).
    STALE_ICON = ""

    def __init__(self, config: ClaudeUsageConfig):
        super().__init__(class_name="claude-usage")
        self.config = config
        self._show_alt_label = False
        self._menu: PinnablePopup | None = None
        self._usage_frames: list[QFrame] = []
        self._service_released = False

        self._service = ClaudeUsageService.get_instance(self.config.update_interval, self.config.cache_ttl)
        self._data: dict[str, Any] = self._service.latest()

        # Local token-history (optional): scans Claude Code's session transcripts off-thread.
        self._token_service: TokenHistoryService | None = None
        self._token_summary: dict[str, Any] = dict(_EMPTY_TOKEN_SUMMARY)
        self._selected_period = self.config.token_history.default_period
        self._period_buttons: dict[str, QPushButton] = {}
        self._token_total_label: QLabel | None = None
        self._token_graph: GraphWidget | None = None
        self._model_container: QFrame | None = None
        self._model_layout: QGridLayout | None = None
        if self.config.token_history.enabled:
            self._token_service = TokenHistoryService.get_instance(self.config.token_history.scan_interval)
            self._token_summary = self._summarize_tokens(self._token_service.latest())

        # Claude API status (optional): polls the public status page off-thread.
        self._status_service: ClaudeStatusService | None = None
        self._status: dict[str, Any] = {"indicator": "unknown", "description": ""}
        self._status_dot: QLabel | None = None
        self._status_text_label: QLabel | None = None
        if self.config.status.enabled:
            self._status_service = ClaudeStatusService.get_instance(self.config.status.poll_interval)
            self._status = self._status_service.latest()

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("refresh", self._refresh)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

        self._service.data_ready.connect(self._on_data)
        if self._token_service is not None:
            self._token_service.data_ready.connect(self._on_token_data)
        if self._status_service is not None:
            self._status_service.data_ready.connect(self._on_status_data)
        self.destroyed.connect(lambda *_: self._release_service())
        self._update_label()

    def _release_service(self) -> None:
        if getattr(self, "_service_released", False):
            return
        self._service_released = True
        try:
            self._service.release()
        except RuntimeError:
            pass
        if self._token_service is not None:
            try:
                self._token_service.release()
            except RuntimeError:
                pass
        if self._status_service is not None:
            try:
                self._status_service.release()
            except RuntimeError:
                pass

    def closeEvent(self, event):
        self._release_service()
        super().closeEvent(event)

    def _on_data(self, data: dict[str, Any]) -> None:
        self._data = data
        self._update_label()
        self._refresh_usage_sections()

    def _refresh(self) -> None:
        self._service.refresh_now()
        if self._status_service is not None:
            self._status_service.refresh_now()

    def _summarize_tokens(self, agg: dict[str, Any]) -> dict[str, Any]:
        th = self.config.token_history
        return summarize(agg, count_cache_read=th.count_cache_read, week_starts_on=th.week_starts_on)

    def _on_token_data(self, agg: dict[str, Any]) -> None:
        self._token_summary = self._summarize_tokens(agg)
        self._update_label()
        self._sync_token_section()

    def _on_status_data(self, data: dict[str, Any]) -> None:
        self._status = data
        self._update_label()
        self._sync_status()

    def _status_level(self) -> str:
        level = self._status.get("indicator")
        return level if level in STATUS_LEVELS else "unknown"

    def _build_status_row(self) -> QFrame:
        row = QFrame()
        row.setProperty("class", "status-row")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        self._status_dot = QLabel(self.config.status.icon)
        self._status_dot.setProperty("class", "dot")
        row_layout.addWidget(self._status_dot)
        self._status_text_label = QLabel("")
        self._status_text_label.setProperty("class", "status-text")
        row_layout.addWidget(self._status_text_label)
        row_layout.addStretch()
        self._sync_status()
        return row

    def _sync_status(self) -> None:
        """Update the menu status dot colour and description in place."""
        if self._status_dot is None:
            return
        try:
            self._status_dot.setProperty("class", f"dot {self._status_level()}")
            self._status_text_label.setText(self._status.get("description", "") or "Status unavailable")
            refresh_widget_style(self._status_dot, self._status_text_label)
        except RuntimeError:
            self._status_dot = None
            self._status_text_label = None

    @staticmethod
    def _fmt_tokens(value: Any) -> str:
        """Compact token count, e.g. '15K', '1.2M', '218M', '3.4B', '1T'; '--' when unknown."""
        if not isinstance(value, (int, float)):
            return "--"
        n = int(value)
        if n < 1000:
            return str(n)
        units = ("K", "M", "B", "T")
        magnitude = 0
        scaled = n / 1000.0
        # Rounding can lift a value to 1000 of its unit (999_999 -> "1000K"); carry it up instead.
        while round(scaled, 1) >= 1000 and magnitude < len(units) - 1:
            scaled /= 1000.0
            magnitude += 1
        return f"{scaled:.1f}".rstrip("0").rstrip(".") + units[magnitude]

    def _format_values(self) -> dict[str, str]:
        totals = self._token_summary.get("totals", {})
        return {
            "five_hour": self._pct(self._data.get("five")),
            "seven_day": self._pct(self._data.get("seven")),
            "five_hour_reset": self._fmt_reset(self._data.get("five_reset_iso")),
            "seven_day_reset": self._fmt_reset(self._data.get("seven_reset_iso")),
            "stale": self.STALE_ICON if self._data.get("token_expired") else "",
            "session_tokens": self._fmt_tokens(totals.get("session")),
            "today_tokens": self._fmt_tokens(totals.get("today")),
            "week_tokens": self._fmt_tokens(totals.get("week")),
            "month_tokens": self._fmt_tokens(totals.get("month")),
            "year_tokens": self._fmt_tokens(totals.get("year")),
            "status": self.config.status.icon if self.config.status.enabled else "",
            "status_text": self._status.get("description", "") if self.config.status.enabled else "",
        }

    @staticmethod
    def _pretty_model(model_id: str) -> str:
        """Display name derived from the id so new models need no upkeep: the name is the first
        word after the 'claude-' prefix and the version is the first two short (<=2 digit) groups
        (date stamps and a bracketed suffix are dropped). A '[fast]' tag, added when the request
        ran in fast mode, renders as a trailing 'Fast'. Non-Claude ids are returned unchanged."""
        lowered = model_id.lower()
        if not lowered.startswith("claude-"):
            return model_id
        is_fast = "[fast]" in lowered
        parts = lowered.split("[", 1)[0].removeprefix("claude-").split("-")
        name = next((p for p in parts if p.isalpha()), None)
        if name is None:
            return model_id
        nums = [p for p in parts if p.isdigit() and len(p) <= 2]
        label = f"{name.capitalize()} {'.'.join(nums[:2])}".rstrip()
        return f"{label} Fast" if is_fast else label

    @staticmethod
    def _pct(value: Any) -> str:
        return "--" if value is None else str(value)

    @staticmethod
    def _pct_decimal(raw: Any, rounded: Any) -> str:
        """One-decimal percentage ('28.0') from the raw value, falling back to the rounded one."""
        value = raw if isinstance(raw, (int, float)) else rounded
        return f"{value:.1f}" if isinstance(value, (int, float)) else "--"

    @staticmethod
    def _fmt_reset(iso: str | None) -> str:
        """Short time-until-reset: a countdown ('4h 14m') when under a day away,
        otherwise a local weekday + time ('Sat 6:00 AM')."""
        if not iso:
            return "--"
        try:
            target = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            seconds = int((target - datetime.now(UTC)).total_seconds())
            if seconds <= 0:
                return "0m"
            if seconds < 24 * 3600:
                hours, minutes = divmod(seconds // 60, 60)
                return f"{hours}h {minutes}m" if hours else f"{minutes}m"
            local = target.astimezone()
            hour12 = local.hour % 12 or 12
            ampm = "AM" if local.hour < 12 else "PM"
            return f"{local:%a} {hour12}:{local.minute:02d} {ampm}"
        except Exception:
            return "--"

    @staticmethod
    def _fmt_duration(iso: str | None) -> str:
        """Relative time-until-reset, e.g. '6d 21h', '4h 14m', '10m'; '--' when unknown."""
        if not iso:
            return "--"
        try:
            target = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            seconds = int((target - datetime.now(UTC)).total_seconds())
            if seconds <= 0:
                return "0m"
            minutes = seconds // 60
            days, rem = divmod(minutes, 1440)
            hours, mins = divmod(rem, 60)
            if days:
                return f"{days}d {hours}h"
            if hours:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        except Exception:
            return "--"

    @staticmethod
    def _fmt_weekday(iso: str | None, with_date: bool = False) -> str:
        """Absolute reset as a local weekday + time, e.g. 'Sat @ 6:00 AM'; '--' when unknown.

        With ``with_date`` the month/day is included ('Sat, Jun 13 @ 6:00 AM') so two windows
        resetting on the same weekday stay distinguishable.
        """
        if not iso:
            return "--"
        try:
            local = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
            hour12 = local.hour % 12 or 12
            ampm = "AM" if local.hour < 12 else "PM"
            day = f"{local:%a, %b} {local.day}" if with_date else f"{local:%a}"
            return f"{day} @ {hour12}:{local.minute:02d} {ampm}"
        except Exception:
            return "--"

    def _reset_phrase(self, iso: str | None, reset_format: str) -> str:
        """Reset line for the popup footer, phrased per the window's reset_format."""
        if reset_format == "absolute":
            value = self._fmt_weekday(iso, with_date=self.config.reset_show_date)
            return f"Resets on {value}" if value != "--" else "Reset time unknown"
        value = self._fmt_duration(iso)
        return f"Resets in {value}" if value != "--" else "Reset time unknown"

    @staticmethod
    def _fmt_reset_at(iso: str | None) -> str:
        """Absolute local reset timestamp, e.g. '6/7/2026, 5:50:00 AM'."""
        if not iso:
            return "--"
        try:
            local = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
            hour12 = local.hour % 12 or 12
            ampm = "AM" if local.hour < 12 else "PM"
            return f"{local.month}/{local.day}/{local.year}, {hour12}:{local.minute:02d}:{local.second:02d} {ampm}"
        except Exception:
            return "--"

    @staticmethod
    def _level_class(value: Any) -> str:
        if not isinstance(value, (int, float)):
            return "unknown"
        if value >= 80:
            return "high"
        if value >= 50:
            return "medium"
        return "low"

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_template = self.config.label_alt if self._show_alt_label else self.config.label
        values = self._format_values()
        # Skip whitespace-only parts so the widget/template indices stay aligned with
        # build_widget_label (which drops them); otherwise multi-<span> labels misalign.
        label_parts = [part for part in re.split(r"(<span.*?>.*?</span>)", active_template) if part.strip()]

        for index, part in enumerate(label_parts):
            if index >= len(active_widgets):
                continue
            current_widget = active_widgets[index]
            if "<span" in part and "</span>" in part:
                text = re.sub(r"<span.*?>|</span>", "", part).strip()
            else:
                text = part.strip()
            try:
                rendered = text.format(**values)
            except Exception:
                rendered = text
            current_widget.setText(rendered)
            # Hide the label when its placeholder renders empty (e.g. {stale} on a valid
            # token) so it does not leave a constant gap from its own margin/spacing.
            current_widget.setVisible(bool(rendered))
            if "{status}" in part:
                base = current_widget.property("class") or "status"
                base = " ".join(t for t in base.split() if t not in STATUS_LEVELS)
                current_widget.setProperty("class", f"{base} {self._status_level()}")
            if self.config.tooltip:
                tip = f"Claude usage — 5h: {values['five_hour']}% · 7d: {values['seven_day']}%"
                if self._data.get("token_expired"):
                    tip += "\nToken expired — run `claude -p` to refresh"
                set_tooltip(current_widget, tip)
        refresh_widget_style(*active_widgets)

    def _toggle_menu(self) -> None:
        self._build_menu()

    def _build_section(self, title: str, value: Any, raw: Any, reset_iso: str | None, reset_format: str) -> QFrame:
        level = self._level_class(value)
        frame = QFrame()
        frame.setProperty("class", "section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel(f"{title} Window")
        title_label.setProperty("class", "title")
        layout.addWidget(title_label)

        progress = UsageBar(int(value) if isinstance(value, (int, float)) else 0, level)
        layout.addWidget(progress)

        footer = QFrame()
        footer.setProperty("class", "footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)

        reset_label = QLabel(self._reset_phrase(reset_iso, reset_format))
        reset_label.setProperty("class", "reset")
        footer_layout.addWidget(reset_label)
        footer_layout.addStretch()

        percent_label = QLabel(f"{self._pct_decimal(raw, value)}%")
        percent_label.setProperty("class", f"percent {level}")
        footer_layout.addWidget(percent_label)

        layout.addWidget(footer)

        date_label = QLabel(self._fmt_reset_at(reset_iso))
        date_label.setProperty("class", "date")
        layout.addWidget(date_label)

        return frame

    def _build_token_section(self) -> QFrame:
        """Tokens section: a Session/Today/Week/Month/Year toggle, the selected total,
        and an optional usage graph for the selected period."""
        th = self.config.token_history
        frame = QFrame()
        frame.setProperty("class", "section tokens")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if th.show_models:
            self._model_container = QFrame()
            self._model_container.setProperty("class", "model-usage")
            container_layout = QVBoxLayout(self._model_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            model_title = QLabel("Models")
            model_title.setProperty("class", "title")
            container_layout.addWidget(model_title)
            rows = QFrame()
            rows.setProperty("class", "model-rows")
            self._model_layout = QGridLayout(rows)
            self._model_layout.setContentsMargins(0, 0, 0, 0)
            self._model_layout.setHorizontalSpacing(8)
            self._model_layout.setVerticalSpacing(4)
            self._model_layout.setColumnStretch(1, 1)
            container_layout.addWidget(rows)
            layout.addWidget(self._model_container)
        else:
            self._model_container = None
            self._model_layout = None

        title_label = QLabel("Tokens")
        title_label.setProperty("class", "title")
        layout.addWidget(title_label)

        toggle = QFrame()
        toggle.setProperty("class", "period-toggle")
        toggle_layout = QHBoxLayout(toggle)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)
        self._period_buttons = {}
        for key, text in _TOKEN_PERIODS:
            btn = QPushButton(text)
            btn.setProperty("class", "period-btn")
            btn.clicked.connect(lambda _=False, k=key: self._select_period(k))
            toggle_layout.addWidget(btn)
            self._period_buttons[key] = btn
        layout.addWidget(toggle)

        self._token_total_label = QLabel("--")
        self._token_total_label.setProperty("class", "token-total")
        layout.addWidget(self._token_total_label)

        if th.show_graph:
            graph_container = QFrame()
            graph_container.setProperty("class", "graph-container")
            graph_layout = QVBoxLayout(graph_container)
            graph_layout.setContentsMargins(0, 0, 0, 0)
            graph_layout.setSpacing(0)
            self._token_graph = GraphWidget("token-graph", show_grid=th.show_graph_grid)
            graph_layout.addWidget(self._token_graph)
            layout.addWidget(graph_container)
        else:
            self._token_graph = None

        self._sync_token_section()
        return frame

    def _select_period(self, period: str) -> None:
        self._selected_period = period
        self._sync_token_section()

    def _sync_token_section(self) -> None:
        """Refresh the token total, active toggle button, and graph in place."""
        if self._token_total_label is None:
            return
        totals = self._token_summary.get("totals", {})
        try:
            self._token_total_label.setText(self._fmt_tokens(totals.get(self._selected_period)))
            for key, btn in self._period_buttons.items():
                active = key == self._selected_period
                btn.setProperty("class", "period-btn active" if active else "period-btn")
                refresh_widget_style(btn)
            if self._token_graph is not None:
                series = self._token_summary.get("series_by_period", {}).get(self._selected_period, [])
                peak = max(series) if series else 0
                normalized = [(v / peak * 100.0) if peak else 0.0 for v in series]
                if len(normalized) == 1:
                    # Duplicate a lone sample so the graph draws a flat line rather than nothing.
                    normalized.append(normalized[0])
                self._token_graph.set_data(normalized)
            self._sync_model_rows()
            if self._menu is not None and self._menu.isVisible():
                # A period switch changes the model-row count. activate() refreshes the cached
                # size hint after the rebuild, and resize() (not adjustSize, which only grows a
                # visible window) makes the popup track its content both ways, so it neither
                # crams the taller periods nor stretches the shorter ones.
                self._menu_layout.activate()
                self._menu.resize(self._menu.sizeHint())
        except RuntimeError:
            # Popup (and its labels) was destroyed; references are stale until reopened.
            self._token_total_label = None
            self._token_graph = None
            self._period_buttons = {}

    def _sync_model_rows(self) -> None:
        """Rebuild the per-model bars for the selected period; hide the container when empty."""
        if self._model_layout is None:
            return
        try:
            while self._model_layout.count():
                item = self._model_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Detach now (not just deleteLater) so the popup's size hint reflects the new
                    # row count synchronously, letting the caller resize the popup correctly.
                    widget.setParent(None)
                    widget.deleteLater()
            models = self._token_summary.get("models_by_period", {}).get(self._selected_period, [])[:5]
            self._model_container.setVisible(bool(models))
            peak = models[0][1] if models else 0
            # A grid keeps the name and total columns the same width across rows (sized to their
            # widest cell at layout time), so the bar column lines up without measuring fonts.
            for index, (model_id, total) in enumerate(models):
                name = QLabel(self._pretty_model(model_id))
                name.setProperty("class", "model-name")
                bar = UsageBar(int(total / peak * 100) if peak else 0, "", accent=f"model-{index % 5}")
                total_label = QLabel(self._fmt_tokens(total))
                total_label.setProperty("class", "model-total")
                total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._model_layout.addWidget(name, index, 0)
                self._model_layout.addWidget(bar, index, 1)
                self._model_layout.addWidget(total_label, index, 2)
        except RuntimeError:
            self._model_container = None
            self._model_layout = None

    def _build_usage_frames(self) -> list[QFrame]:
        return [
            self._build_section(
                "5-Hour",
                self._data.get("five"),
                self._data.get("five_raw"),
                self._data.get("five_reset_iso"),
                self.config.five_hour_reset_format,
            ),
            self._build_section(
                "7-Day",
                self._data.get("seven"),
                self._data.get("seven_raw"),
                self._data.get("seven_reset_iso"),
                self.config.seven_day_reset_format,
            ),
        ]

    def _add_menu_sections(self, layout: QVBoxLayout) -> None:
        self._usage_frames = self._build_usage_frames()
        for frame in self._usage_frames:
            layout.addWidget(frame)
        if self.config.token_history.enabled:
            layout.addWidget(self._build_token_section())

    def _refresh_usage_sections(self) -> None:
        """Rebuild the 5h/7d sections in place when fresh usage data arrives while the popup is open.

        The token section keeps its own state and refreshes separately, so it stays put rather than
        being rebuilt, which would otherwise discard the graph and per-model rows on every poll.
        """
        menu = self._menu
        try:
            if menu is None or not menu.isVisible():
                return
            layout = self._menu_layout
            new_frames = self._build_usage_frames()
            for old, new in zip(self._usage_frames, new_frames):
                index = layout.indexOf(old)
                layout.removeWidget(old)
                old.hide()
                old.deleteLater()
                layout.insertWidget(index, new)
            self._usage_frames = new_frames
            menu.adjustSize()
        except RuntimeError:
            self._menu = None  # popup was already destroyed

    def _build_menu(self) -> None:
        self._menu = PinnablePopup(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self._menu.setProperty("class", "claude-usage-menu")

        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._menu_layout = layout

        header = QFrame()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        title_label = QLabel("Claude Usage")
        title_label.setProperty("class", "text")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        refresh_btn = QPushButton("\U000f0450")
        refresh_btn.setProperty("class", "refresh")
        set_tooltip(refresh_btn, "Refresh now")
        refresh_btn.clicked.connect(self._refresh)
        header_layout.addWidget(refresh_btn)

        pin_btn = create_pin_button(self._menu, self.config.menu.pin_icon, self.config.menu.unpin_icon)
        header_layout.addWidget(pin_btn)

        layout.addWidget(header)
        if self.config.status.enabled and self.config.status.show_in_menu:
            layout.addWidget(self._build_status_row())
        self._add_menu_sections(layout)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()

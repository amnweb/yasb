import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.utils.qobject import is_valid_qobject
from core.utils.stat_popup import GraphWidget
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.deepseek_usage import DeepSeekUsageConfig
from core.widgets.base import BaseWidget
from core.widgets.services.deepseek_usage.deepseek_api import DeepSeekUsageService, resolve_api_key
from core.widgets.services.deepseek_usage.spend_history import (
    budget_percent,
    empty_ledger,
    parse_amount,
    summarize,
)

_SPEND_PERIODS: list[tuple[str, str]] = [
    ("today", "Today"),
    ("week", "Week"),
    ("month", "Month"),
    ("year", "Year"),
]
_PERIOD_TITLES: dict[str, str] = {"today": "today", "week": "this week", "month": "this month", "year": "this year"}
# Symbols for the currencies /user/balance can report; anything else falls back to the bare number.
_CURRENCY_SYMBOLS: dict[str, str] = {"CNY": "¥", "USD": "$"}
_ERROR_MESSAGES: dict[str, str] = {
    "no_key": "No API key - set YASB_DEEPSEEK_API_KEY",
    "auth": "API key rejected - check it on platform.deepseek.com",
    "http": "DeepSeek returned an error - showing last known balance",
    "network": "DeepSeek unreachable - showing last known balance",
}
_EMPTY_SUMMARY: dict[str, Any] = {"totals": {}, "series_by_period": {}, "currency": ""}


class UsageBar(QFrame):
    """A rounded progress bar drawn as a track QFrame with a child `.fill` QFrame.

    Keeps the fill at least as wide as it is tall so the rounded corners are preserved at
    low values (the QProgressBar::chunk square-fill issue), and stays fully CSS-styleable.
    """

    # Must match the stylesheet min/max-height for this bar.
    TRACK_HEIGHT = 6

    def __init__(self, value: float, level: str, parent: QFrame | None = None):
        super().__init__(parent)
        self._value = max(0.0, min(100.0, value))
        self.setProperty("class", f"progress {level}")
        self._fill = QFrame(self)
        self._fill.setProperty("class", "fill")

    def set_value(self, value: float, level: str) -> None:
        """Update value and level class in place, so a refresh reuses the bar instead of
        rebuilding the section (rebuilding is what causes the popup to flicker)."""
        self._value = max(0.0, min(100.0, value))
        self.setProperty("class", f"progress {level}")
        refresh_widget_style(self)
        self._update_fill()

    def _track_height(self) -> int:
        """Height of the painted track.

        The stylesheet engine paints this frame's background at its styled height and
        centres it, but sets no Qt geometry - minimumHeight() stays 0 - so the widget keeps
        whatever height the layout gave it (routinely ~40px). Filling that drew the value as
        a slab standing proud of the track, so the height is pinned here instead.
        TRACK_HEIGHT must match the stylesheet's min/max-height for this bar.
        """
        return min(self.TRACK_HEIGHT, self.height()) if self.height() > 0 else self.TRACK_HEIGHT

    def _update_fill(self) -> None:
        height = self._track_height()
        fill_width = int(self.width() * self._value / 100)
        if fill_width > 0:
            fill_width = max(fill_width, height)
        # Centred to match the track behind it; the +1 rounds the half-pixel the same
        # way the stylesheet engine does, otherwise the fill sits 2px high.
        self._fill.setGeometry(0, max(0, (self.height() - height + 1) // 2), fill_width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_fill()


class DeepSeekUsageWidget(BaseWidget):
    validation_schema = DeepSeekUsageConfig

    def __init__(self, config: DeepSeekUsageConfig):
        super().__init__(class_name="deepseek-usage")
        self.config = config
        self._show_alt_label = False
        self._menu: PopupWidget | None = None
        self._service_released = False
        self._selected_period = self.config.spend_history.default_period

        # Popup references, kept so a data refresh updates them in place.
        self._balance_labels: dict[str, QLabel] = {}
        self._budget_bar: UsageBar | None = None
        self._budget_percent_label: QLabel | None = None
        self._budget_detail_label: QLabel | None = None
        self._period_buttons: dict[str, QPushButton] = {}
        self._spend_total_label: QLabel | None = None
        self._spend_graph: GraphWidget | None = None
        self._footer_label: QLabel | None = None

        self._service = DeepSeekUsageService.get_instance(
            self.config.update_interval,
            self.config.cache_ttl,
            resolve_api_key(self.config.api_key),
            self.config.currency,
            self.config.spend_history.count_granted_as_spend,
        )
        self._data: dict[str, Any] = self._service.latest()
        self._summary: dict[str, Any] = self._summarize(self._data.get("ledger"))

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("refresh", self._refresh)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

        self._service.data_ready.connect(self._on_data)
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

    def closeEvent(self, event):
        self._release_service()
        super().closeEvent(event)

    def _on_data(self, data: dict[str, Any]) -> None:
        self._data = data
        self._summary = self._summarize(data.get("ledger"))
        self._update_label()
        self._sync_balance_section()
        self._sync_budget_section()
        self._sync_spend_section()
        self._sync_footer()

    def _refresh(self) -> None:
        self._service.refresh_now()

    def _summarize(self, ledger: Any) -> dict[str, Any]:
        if not self.config.spend_history.enabled or not isinstance(ledger, dict):
            return dict(_EMPTY_SUMMARY)
        return summarize(ledger or empty_ledger(), week_starts_on=self.config.spend_history.week_starts_on)

    # -- formatting ----------------------------------------------------------

    def _symbol(self) -> str:
        if self.config.currency_symbol:
            return self.config.currency_symbol
        return _CURRENCY_SYMBOLS.get((self._data.get("currency") or "").upper(), "")

    def _fmt_money(self, value: Any, unknown: str = "--") -> str:
        """Format an amount with the account's currency symbol.

        ``None`` and blank values render as ``unknown`` rather than as zero: not knowing
        the balance and having no money left are very different things to show on a bar.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return unknown
        amount = value if isinstance(value, Decimal) else parse_amount(value)
        # Sign goes outside the symbol ("-¥17.50", not "¥-17.50"), which {budget_remaining}
        # hits whenever the budget is overspent.
        sign = "-" if amount < 0 else ""
        return f"{sign}{self._symbol()}{abs(amount):,.{self.config.decimal_places}f}"

    def _spend(self, period: str) -> Decimal | None:
        if not self.config.spend_history.enabled:
            return None
        return self._summary.get("totals", {}).get(period)

    def _budget_percent(self) -> float | None:
        budget = self.config.budget
        if not budget.enabled or not self.config.spend_history.enabled:
            return None
        spend = self._spend(budget.period)
        if spend is None:
            return None
        return budget_percent(spend, Decimal(str(budget.amount)))

    def _budget_remaining(self) -> Decimal | None:
        budget = self.config.budget
        spend = self._spend(budget.period)
        if not budget.enabled or spend is None:
            return None
        return Decimal(str(budget.amount)) - spend

    def _is_low(self) -> bool:
        """True when the balance is below the configured floor, or DeepSeek itself says
        the account can no longer make calls."""
        if self._data.get("available") is False:
            return True
        threshold = self.config.low_balance_threshold
        total = self._data.get("total")
        if threshold <= 0 or total is None:
            return False
        return parse_amount(total) < Decimal(str(threshold))

    @staticmethod
    def _level_class(percent: float | None) -> str:
        if percent is None:
            return "unknown"
        if percent >= 90:
            return "critical"
        if percent >= 75:
            return "high"
        if percent >= 50:
            return "medium"
        return "low"

    def _error_message(self) -> str:
        error = self._data.get("error")
        return _ERROR_MESSAGES.get(error, "") if error else ""

    @staticmethod
    def _fmt_updated(timestamp: Any) -> str:
        if not timestamp:
            return "never"
        try:
            moment = datetime.fromtimestamp(int(timestamp)).astimezone()
        except TypeError, ValueError, OSError:
            return "never"
        delta = int((datetime.now().astimezone() - moment).total_seconds())
        if delta < 60:
            return "just now"
        if delta < 3600:
            return f"{delta // 60}m ago"
        if delta < 86400:
            return f"{delta // 3600}h ago"
        return moment.strftime("%b %d")

    def _format_values(self) -> dict[str, str]:
        percent = self._budget_percent()
        remaining = self._budget_remaining()
        return {
            "balance": self._fmt_money(self._data.get("total")),
            "total": self._fmt_money(self._data.get("total")),
            "granted": self._fmt_money(self._data.get("granted")),
            "topped_up": self._fmt_money(self._data.get("topped_up")),
            "currency": self._data.get("currency") or "",
            "today_spend": self._fmt_money(self._spend("today")),
            "week_spend": self._fmt_money(self._spend("week")),
            "month_spend": self._fmt_money(self._spend("month")),
            "year_spend": self._fmt_money(self._spend("year")),
            "budget_used": "--" if percent is None else f"{percent:.0f}",
            "budget_amount": self._fmt_money(Decimal(str(self.config.budget.amount))),
            "budget_remaining": self._fmt_money(remaining),
            "low": self.config.low_icon if self._is_low() else "",
            "stale": self.config.stale_icon if self._data.get("error") else "",
        }

    def _tooltip_text(self, values: dict[str, str]) -> str:
        tip = f"DeepSeek balance - {values['balance']}"
        if self.config.spend_history.enabled:
            tip += f"\nSpent today: {values['today_spend']} · this month: {values['month_spend']}"
        percent = self._budget_percent()
        if percent is not None:
            tip += f"\nBudget ({self.config.budget.period}): {percent:.0f}% of {values['budget_amount']}"
        message = self._error_message()
        if message:
            tip += f"\n{message}"
        return tip

    # -- bar label -----------------------------------------------------------

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
            # Hide the label when its placeholder renders empty (e.g. {low} on a healthy
            # balance) so it does not leave a constant gap from its own margin/spacing.
            current_widget.setVisible(bool(rendered))
            if "{budget_used}" in part:
                base = current_widget.property("class") or "budget"
                base = " ".join(t for t in base.split() if t not in ("unknown", "low", "medium", "high", "critical"))
                current_widget.setProperty("class", f"{base} {self._level_class(self._budget_percent())}")
            if self.config.tooltip:
                set_tooltip(current_widget, self._tooltip_text(values))
        refresh_widget_style(*active_widgets)

    # -- popup ---------------------------------------------------------------

    def _toggle_menu(self) -> None:
        if is_valid_qobject(self._menu) and self._menu.isVisible():
            self._menu.hide_animated()
            return
        self._show_menu()

    def _show_menu(self) -> None:
        """Build the popup once and reuse it on every open, same as `claude_usage`.

        ``persistent=True`` keeps ``PopupWidget`` from tearing it down on hide, so reopening
        never redoes the widget-tree construction and layout pass.
        """
        if not is_valid_qobject(self._menu):
            self._build_menu()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()
        # The popup ignores refreshes while hidden (see the sync methods' isVisible() guard), so
        # push the latest data in now rather than showing whatever was true when it last closed.
        self._sync_balance_section()
        self._sync_budget_section()
        self._sync_spend_section()
        self._sync_footer()

    def _build_header_icon(self) -> QLabel | None:
        """The product mark at the left of the header, when a path is configured.

        Rendered as rich text rather than a QPixmap so the same <img> the bar label accepts
        works here, and a missing file degrades to an empty label instead of raising.
        """
        path = (self.config.menu.icon or "").strip()
        if not path:
            return None
        label = QLabel(f"<img src='{path}' width='22' height='22'>")
        label.setProperty("class", "app-icon")
        return label

    def _build_balance_section(self) -> QFrame:
        """The balance leads, the way the window percentage leads in the other two widgets.

        A prepaid account has no quota and no reset, so the hero is money rather than a
        percentage - but it is still the one number you open this panel to read. The chip that
        used to label it is gone: the caption underneath says what it is, which keeps chips
        meaning "section label" here as in the Claude and Codex popups.
        """
        frame = QFrame()
        frame.setProperty("class", "section balance hero")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        total_label = QLabel("--")
        total_label.setProperty("class", "hero-value")
        layout.addWidget(total_label, 0, Qt.AlignmentFlag.AlignLeft)
        self._balance_labels["total"] = total_label

        caption = QLabel("available to spend")
        caption.setProperty("class", "hero-caption")
        layout.addWidget(caption, 0, Qt.AlignmentFlag.AlignLeft)
        self._balance_labels["caption"] = caption

        if self.config.menu.show_breakdown:
            ledger = QFrame()
            ledger.setProperty("class", "ledger")
            ledger_layout = QVBoxLayout(ledger)
            ledger_layout.setContentsMargins(0, 0, 0, 0)
            ledger_layout.setSpacing(0)
            for key, caption_text in (("topped_up", "Topped up"), ("granted", "Granted")):
                row = QFrame()
                row.setProperty("class", "row")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(0)

                caption_label = QLabel(caption_text)
                caption_label.setProperty("class", "name")
                row_layout.addWidget(caption_label)
                row_layout.addStretch()

                value_label = QLabel("--")
                value_label.setProperty("class", "value")
                value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(value_label)
                self._balance_labels[key] = value_label
                ledger_layout.addWidget(row)
            layout.addWidget(ledger)

        return frame

    def _build_budget_section(self) -> QFrame:
        budget = self.config.budget
        frame = QFrame()
        frame.setProperty("class", "section budget")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel(f"Budget ({_PERIOD_TITLES.get(budget.period, budget.period)})")
        title_label.setProperty("class", "title")
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignLeft)

        percent = self._budget_percent()
        self._budget_bar = UsageBar(percent or 0.0, self._level_class(percent))
        layout.addWidget(self._budget_bar)

        footer = QFrame()
        footer.setProperty("class", "footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)

        self._budget_detail_label = QLabel("--")
        self._budget_detail_label.setProperty("class", "detail")
        footer_layout.addWidget(self._budget_detail_label)
        footer_layout.addStretch()

        self._budget_percent_label = QLabel("--")
        self._budget_percent_label.setProperty("class", "percent")
        footer_layout.addWidget(self._budget_percent_label)

        layout.addWidget(footer)
        return frame

    def _build_spend_section(self) -> QFrame:
        """Spend section: a Today/Week/Month/Year toggle, the selected total, and an
        optional graph of the selected period."""
        history = self.config.spend_history
        frame = QFrame()
        frame.setProperty("class", "section spend")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel("Spend")
        title_label.setProperty("class", "title")
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignLeft)

        toggle = QFrame()
        toggle.setProperty("class", "period-toggle")
        toggle_layout = QHBoxLayout(toggle)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)
        self._period_buttons = {}
        for key, text in _SPEND_PERIODS:
            button = QPushButton(text)
            button.setProperty("class", "period-btn")
            button.clicked.connect(lambda _=False, period=key: self._select_period(period))
            toggle_layout.addWidget(button)
            self._period_buttons[key] = button
        layout.addWidget(toggle)

        self._spend_total_label = QLabel("--")
        self._spend_total_label.setProperty("class", "spend-total")
        layout.addWidget(self._spend_total_label)

        if history.show_graph:
            graph_container = QFrame()
            graph_container.setProperty("class", "graph-container")
            graph_layout = QVBoxLayout(graph_container)
            graph_layout.setContentsMargins(0, 0, 0, 0)
            graph_layout.setSpacing(0)
            self._spend_graph = GraphWidget("spend-graph", show_grid=history.show_graph_grid)
            graph_layout.addWidget(self._spend_graph)
            layout.addWidget(graph_container)
        else:
            self._spend_graph = None

        return frame

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("class", "section status")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._footer_label = QLabel("")
        self._footer_label.setProperty("class", "updated")
        self._footer_label.setWordWrap(True)
        layout.addWidget(self._footer_label)
        return frame

    def _select_period(self, period: str) -> None:
        self._selected_period = period
        self._sync_spend_section()

    def _sync_balance_section(self) -> None:
        if not self._balance_labels:
            return
        try:
            if self._menu is None or not self._menu.isVisible():
                return
            total_label = self._balance_labels.get("total")
            if total_label is not None:
                total_label.setText(self._fmt_money(self._data.get("total")))
                total_label.setProperty("class", "hero-value low" if self._is_low() else "hero-value")
                refresh_widget_style(total_label)
            for key in ("topped_up", "granted"):
                label = self._balance_labels.get(key)
                if label is not None:
                    label.setText(self._fmt_money(self._data.get(key)))
        except RuntimeError:
            # Popup was destroyed; references are stale until it reopens.
            self._balance_labels = {}
            self._menu = None

    def _sync_budget_section(self) -> None:
        if self._budget_bar is None:
            return
        try:
            if self._menu is None or not self._menu.isVisible():
                return
            percent = self._budget_percent()
            level = self._level_class(percent)
            self._budget_bar.set_value(percent or 0.0, level)
            if self._budget_percent_label is not None:
                self._budget_percent_label.setText("--" if percent is None else f"{percent:.0f}%")
                self._budget_percent_label.setProperty("class", f"percent {level}")
                refresh_widget_style(self._budget_percent_label)
            if self._budget_detail_label is not None:
                spent = self._fmt_money(self._spend(self.config.budget.period))
                budget = self._fmt_money(Decimal(str(self.config.budget.amount)))
                self._budget_detail_label.setText(f"{spent} of {budget}")
        except RuntimeError:
            self._budget_bar = None
            self._budget_percent_label = None
            self._budget_detail_label = None

    def _sync_spend_section(self) -> None:
        """Refresh the spend total, active toggle button and graph in place."""
        if self._spend_total_label is None:
            return
        try:
            period = self._selected_period
            self._spend_total_label.setText(self._fmt_money(self._spend(period), unknown="--"))
            for key, button in self._period_buttons.items():
                active = key == period
                button.setProperty("class", "period-btn active" if active else "period-btn")
                refresh_widget_style(button)
            if self._spend_graph is not None:
                series = self._summary.get("series_by_period", {}).get(period, [])
                peak = max(series) if series else 0
                normalized = [(value / peak * 100.0) if peak else 0.0 for value in series]
                if len(normalized) == 1:
                    # Duplicate a lone sample so the graph draws a flat line rather than nothing.
                    normalized.append(normalized[0])
                self._spend_graph.set_data(normalized)
        except RuntimeError:
            # Popup (and its labels) was destroyed; references are stale until reopened.
            self._spend_total_label = None
            self._spend_graph = None
            self._period_buttons = {}

    def _sync_footer(self) -> None:
        if self._footer_label is None:
            return
        try:
            message = self._error_message()
            self._footer_label.setText(message or f"Updated {self._fmt_updated(self._data.get('fetched_at'))}")
            self._footer_label.setProperty("class", "updated error" if message else "updated")
            refresh_widget_style(self._footer_label)
        except RuntimeError:
            self._footer_label = None

    def _build_menu(self) -> None:
        self._menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
            persistent=True,
            pinnable=True,
        )
        self._menu.setProperty("class", "deepseek-usage-menu")

        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        app_icon = self._build_header_icon()
        if app_icon is not None:
            header_layout.addWidget(app_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel("DeepSeek Usage")
        title_label.setProperty("class", "text")
        header_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch()

        refresh_btn = QPushButton("\U000f0450")
        refresh_btn.setProperty("class", "refresh")
        set_tooltip(refresh_btn, "Refresh now")
        refresh_btn.clicked.connect(self._refresh)
        header_layout.addWidget(refresh_btn)

        pin_btn = QPushButton(self.config.menu.pin_icon)
        pin_btn.setCheckable(True)
        pin_btn.setProperty("class", "pin-btn")
        set_tooltip(pin_btn, "Pin this window")

        def on_pin_toggled(checked: bool) -> None:
            pin_btn.setText(self.config.menu.unpin_icon if checked else self.config.menu.pin_icon)
            pin_btn.setProperty("class", "pin-btn pinned" if checked else "pin-btn")
            set_tooltip(pin_btn, "Unpin this window" if checked else "Pin this window")
            refresh_widget_style(pin_btn)
            self._menu.set_pinned(checked)

        pin_btn.toggled.connect(on_pin_toggled)
        header_layout.addWidget(pin_btn)
        layout.addWidget(header)

        self._balance_labels = {}
        layout.addWidget(self._build_balance_section())
        if self.config.budget.enabled and self.config.spend_history.enabled:
            layout.addWidget(self._build_budget_section())
        if self.config.spend_history.enabled:
            layout.addWidget(self._build_spend_section())
        layout.addWidget(self._build_footer())
        # Surplus height pools here at the bottom rather than spreading as gaps between
        # sections, matching the Claude popup.
        layout.addStretch(1)

        self._menu.adjustSize()
        # Lock the width after the first layout so switching periods only changes the height,
        # keeping the bars a constant length between periods.
        self._menu.setFixedWidth(self._menu.width())

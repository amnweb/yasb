import re
from datetime import UTC, datetime
from typing import Any

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.claude_usage import ClaudeUsageConfig
from core.widgets.base import BaseWidget
from core.widgets.services.claude_usage.claude_api import ClaudeUsageService


class UsageBar(QFrame):
    """A rounded progress bar drawn as a track QFrame with a child `.fill` QFrame.

    Keeps the fill at least as wide as it is tall so the rounded corners are preserved at
    low values (the QProgressBar::chunk square-fill issue), and stays fully CSS-styleable.
    """

    def __init__(self, value: int, level: str, parent: QFrame | None = None):
        super().__init__(parent)
        self._value = max(0, min(100, value))
        self.setProperty("class", f"progress {level}")
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

    # Warning glyph (nf-fa-warning) shown via {stale} when the OAuth token has expired.
    STALE_ICON = ""

    def __init__(self, config: ClaudeUsageConfig):
        super().__init__(class_name="claude-usage")
        self.config = config
        self._show_alt_label = False
        self._menu: PopupWidget | None = None
        self._service_released = False

        self._service = ClaudeUsageService.get_instance(self.config.update_interval, self.config.cache_ttl)
        self._data: dict[str, Any] = self._service.latest()

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
        self._update_label()
        self._refresh_menu_sections()

    def _refresh(self) -> None:
        self._service.refresh_now()

    def _format_values(self) -> dict[str, str]:
        return {
            "five_hour": self._pct(self._data.get("five")),
            "seven_day": self._pct(self._data.get("seven")),
            "five_hour_reset": self._fmt_reset(self._data.get("five_reset_iso")),
            "seven_day_reset": self._fmt_reset(self._data.get("seven_reset_iso")),
            "stale": self.STALE_ICON if self._data.get("token_expired") else "",
        }

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
    def _fmt_weekday(iso: str | None) -> str:
        """Absolute reset as a local weekday + time, e.g. 'Sat 6:00 AM'; '--' when unknown."""
        if not iso:
            return "--"
        try:
            local = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
            hour12 = local.hour % 12 or 12
            ampm = "AM" if local.hour < 12 else "PM"
            return f"{local:%a} {hour12}:{local.minute:02d} {ampm}"
        except Exception:
            return "--"

    def _reset_phrase(self, iso: str | None) -> str:
        """Grammatical reset line for the popup, honoring ``reset_format``."""
        if self.config.reset_format == "absolute":
            value = self._fmt_weekday(iso)
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
            # Hide empty labels so an unused placeholder (e.g. {stale} when the token is
            # valid) doesn't leave a constant gap from its margin/spacing.
            current_widget.setVisible(bool(rendered))
            if self.config.tooltip:
                tip = f"Claude usage — 5h: {values['five_hour']}% · 7d: {values['seven_day']}%"
                if self._data.get("token_expired"):
                    tip += "\nToken expired — run `claude -p` to refresh"
                set_tooltip(current_widget, tip)
        refresh_widget_style(*active_widgets)

    def _toggle_menu(self) -> None:
        self._build_menu()

    def _build_section(self, title: str, value: Any, raw: Any, reset_iso: str | None) -> QFrame:
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

        reset_label = QLabel(self._reset_phrase(reset_iso))
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

    def _add_menu_sections(self, layout: QVBoxLayout) -> None:
        self._section_frames = [
            self._build_section(
                "5-Hour", self._data.get("five"), self._data.get("five_raw"), self._data.get("five_reset_iso")
            ),
            self._build_section(
                "7-Day", self._data.get("seven"), self._data.get("seven_raw"), self._data.get("seven_reset_iso")
            ),
        ]
        for frame in self._section_frames:
            layout.addWidget(frame)

    def _refresh_menu_sections(self) -> None:
        """Redraw the popup sections in place when fresh data arrives while it is open."""
        menu = self._menu
        try:
            if menu is None or not menu.isVisible():
                return
            layout = self._menu_layout
            for frame in getattr(self, "_section_frames", []):
                layout.removeWidget(frame)
                frame.hide()
                frame.deleteLater()
            self._add_menu_sections(layout)
            menu.adjustSize()
        except RuntimeError:
            self._menu = None  # popup was already destroyed

    def _build_menu(self) -> None:
        self._menu = PopupWidget(
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

        layout.addWidget(header)
        self._add_menu_sections(layout)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()

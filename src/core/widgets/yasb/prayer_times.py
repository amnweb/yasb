import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.prayer_times.api import PrayerTimesDataFetcher
from core.validation.widgets.yasb.prayer_times import PrayerTimesConfig
from core.widgets.base import BaseWidget

# Canonical ordering as returned by the Aladhan API.
ALL_PRAYER_NAMES = ["Imsak", "Fajr", "Sunrise", "Dhuhr", "Asr", "Sunset", "Maghrib", "Isha", "Midnight"]


class PrayerTimesWidget(BaseWidget):
    validation_schema = PrayerTimesConfig

    def __init__(self, config: PrayerTimesConfig):
        super().__init__(class_name=f"prayer-times-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._timings: dict[str, str] = {}
        self._hijri: dict[str, Any] = {}
        self._meta: dict[str, Any] = {}
        self._popup: PopupWidget | None = None
        self._popup_row_widgets: dict[str, dict[str, QLabel]] = {}
        self._loading: bool = True
        self._date_offset: int = 0
        self._current_date: str = datetime.now().strftime("%Y-%m-%d")
        self._widgets: list[QWidget] = []
        self._widgets_alt: list[QWidget] = []

        # --- Container ---
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, config.label, config.label_alt, config.label_shadow.model_dump())

        # --- Callbacks ---
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_card", self._toggle_card)
        self.register_callback("update_label", self._update_label)
        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

        # --- API fetcher ---
        self._fetcher = PrayerTimesDataFetcher(
            self,
            url_factory=self._build_api_url,
            timeout_ms=config.update_interval * 1000,
        )
        self._fetcher.finished.connect(self._on_data_received)
        self._fetcher.start()

        # --- Minute timer: re-render label + open popup ---
        self._minute_timer = QTimer(self)
        self._minute_timer.setInterval(60_000)
        self._minute_timer.timeout.connect(self._on_minute_tick)
        self._minute_timer.start()

        # --- Flash animation ---
        self._flash_anim = QVariantAnimation(self)
        self._flash_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._flash_anim.valueChanged.connect(self._on_flash_frame)
        self._flash_anim.finished.connect(self._on_flash_half_done)
        self._flash_stop_timer = QTimer(self)
        self._flash_stop_timer.setSingleShot(True)
        self._flash_stop_timer.timeout.connect(self._stop_flash)

        # Show loading placeholder immediately before first API response
        self._update_label()

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def _build_api_url(self) -> str:
        """Return the Aladhan timings URL for the target date (today or tomorrow)."""
        today = (datetime.now() + timedelta(days=self._date_offset)).strftime("%d-%m-%Y")
        params: dict[str, Any] = {
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "method": self.config.method,
            "school": self.config.school,
            "midnightMode": self.config.midnight_mode,
        }
        if self.config.tune:
            params["tune"] = self.config.tune
        if self.config.timezone:
            params["timezonestring"] = self.config.timezone
        if self.config.shafaq:
            params["shafaq"] = self.config.shafaq
        return f"https://api.aladhan.com/v1/timings/{today}?{urllib.parse.urlencode(params)}"

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------

    def _on_data_received(self, data: dict) -> None:
        if not data:
            return
        try:
            self._timings = data["data"]["timings"]
            self._hijri = data["data"]["date"]["hijri"]
            self._meta = data["data"].get("meta", {})
            self._loading = False
            self._update_label()
            # If today's prayers are all done and we haven't switched to tomorrow yet,
            # immediately re-fetch tomorrow's schedule.
            if self._date_offset == 0 and self._all_prayers_passed():
                self._date_offset = 1
                self._fetcher.make_request()
        except (KeyError, TypeError) as exc:
            logging.error(f"Prayer times widget: failed to parse API response: {exc}")

    def _on_minute_tick(self) -> None:
        # Reset to today when the calendar date changes (midnight rollover).
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._date_offset = 0
            self._fetcher.make_request()
            return
        self._update_label()
        if self.config.flash.enabled and self._check_prayer_time():
            self._start_flash()
        if self._popup is not None:
            try:
                self._refresh_popup_rows()
            except RuntimeError:
                self._popup = None

    def _all_prayers_passed(self) -> bool:
        """Return True if every prayer in prayers_to_show has already passed today (including grace period)."""
        prayers = self.config.prayers_to_show or ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        now = datetime.now()
        grace = timedelta(minutes=self.config.grace_period)
        for name in prayers:
            time_str = self._timings.get(name, "")
            if not time_str or time_str == "--:--":
                continue
            try:
                h, m = int(time_str[:2]), int(time_str[3:5])
                if now.replace(hour=h, minute=m, second=0, microsecond=0) + grace > now:
                    return False
            except ValueError, IndexError:
                continue
        return True

    # ------------------------------------------------------------------
    # Next prayer helpers
    # ------------------------------------------------------------------

    def _get_next_prayer(self) -> tuple[str, str]:
        """Return (prayer_name, time_str) for the current or next upcoming prayer.

        A prayer is considered 'current' for grace_period minutes after its time,
        so the label doesn't immediately jump to the next prayer when the time hits.
        """
        if not self._timings:
            return ("—", "--:--")
        prayers = self.config.prayers_to_show or ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        now = datetime.now()
        grace = timedelta(minutes=self.config.grace_period)
        target_date = now + timedelta(days=self._date_offset)
        for name in prayers:
            time_str = self._timings.get(name, "")
            if not time_str or time_str == "--:--":
                continue
            try:
                h, m = int(time_str[:2]), int(time_str[3:5])
                if target_date.replace(hour=h, minute=m, second=0, microsecond=0) + grace > now:
                    return (name, time_str)
            except ValueError, IndexError:
                continue
        first = prayers[0]
        return (first, self._timings.get(first, "--:--"))

    def _time_delta_text(self, time_str: str) -> str:
        """Return human-readable remaining/elapsed label for a prayer time string."""
        if not time_str or time_str == "--:--":
            return ""
        try:
            now = datetime.now()
            target_date = now + timedelta(days=self._date_offset)
            h, m = int(time_str[:2]), int(time_str[3:5])
            target = target_date.replace(hour=h, minute=m, second=0, microsecond=0)
            delta = target - now
            grace = timedelta(minutes=self.config.grace_period)
            if delta.total_seconds() < 0:
                # Within grace period: show how many minutes into the prayer we are
                if abs(delta) < grace:
                    elapsed_min = int(abs(delta).total_seconds() // 60)
                    return f"{elapsed_min}m ago"
                return "passed"
            total_min = int(delta.total_seconds() // 60)
            hours, mins = divmod(total_min, 60)
            if hours > 0:
                return f"in {hours}h {mins:02d}m"
            return f"in {mins}m"
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Label options dict
    # ------------------------------------------------------------------

    def _build_label_options(self) -> dict[str, str]:
        """Build the dict of {placeholder: value} for string substitution."""
        options: dict[str, str] = {}
        for name in ALL_PRAYER_NAMES:
            options[f"{{{name.lower()}}}"] = self._timings.get(name, "--:--")
        next_name, next_time = self._get_next_prayer()
        options["{next_prayer}"] = next_name
        options["{next_prayer_time}"] = next_time
        ic = self.config.icons
        icon_map = {
            "Fajr": ic.fajr,
            "Sunrise": ic.sunrise,
            "Dhuhr": ic.dhuhr,
            "Asr": ic.asr,
            "Sunset": ic.sunset,
            "Maghrib": ic.maghrib,
            "Isha": ic.isha,
            "Imsak": ic.imsak,
            "Midnight": ic.midnight,
        }
        options["{icon}"] = icon_map.get(next_name, ic.default)
        if self._hijri:
            options["{hijri_day}"] = self._hijri.get("day", "")
            options["{hijri_month}"] = self._hijri.get("month", {}).get("en", "")
            options["{hijri_year}"] = self._hijri.get("year", "")
            options["{hijri_date}"] = f"{options['{hijri_day}']} {options['{hijri_month}']} {options['{hijri_year}']}"
        else:
            for k in ("{hijri_day}", "{hijri_month}", "{hijri_year}", "{hijri_date}"):
                options[k] = ""
        return options

    # ------------------------------------------------------------------
    # Bar label update
    # ------------------------------------------------------------------

    def _update_label(self, update_class: bool = True) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_content = self.config.label_alt if self._show_alt_label else self.config.label
        if self._loading:
            for widget in active_widgets:
                if isinstance(widget, QLabel):
                    widget.setText("Loading...")
                    widget.setProperty("class", "label loading")
                    refresh_widget_style(widget)
            return
        label_options = self._build_label_options()
        label_parts = [p for p in re.split(r"(<span.*?>.*?</span>)", active_content) if p]
        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if not part or widget_index >= len(active_widgets):
                continue
            for placeholder, value in label_options.items():
                part = part.replace(placeholder, str(value))
            widget = active_widgets[widget_index]
            if not isinstance(widget, QLabel):
                widget_index += 1
                continue
            if "<span" in part and "</span>" in part:
                widget.setText(re.sub(r"<span.*?>|</span>", "", part).strip())
            else:
                widget.setText(part)
                if update_class:
                    base = "label alt" if self._show_alt_label else "label"
                    next_name = label_options.get("{next_prayer}", "").lower()
                    widget.setProperty("class", f"{base} {next_name}")
                    refresh_widget_style(widget)
            widget_index += 1

    # ------------------------------------------------------------------
    # Prayer-time flash
    # ------------------------------------------------------------------

    def _check_prayer_time(self) -> bool:
        """Return True if the current minute matches any prayer in prayers_to_show."""
        if not self._timings or self._loading:
            return False
        prayers = self.config.prayers_to_show or ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        now = datetime.now()
        for name in prayers:
            time_str = self._timings.get(name, "")
            if not time_str or time_str == "--:--":
                continue
            try:
                h, m = int(time_str[:2]), int(time_str[3:5])
                if now.hour == h and now.minute == m:
                    return True
            except ValueError, IndexError:
                continue
        return False

    def _start_flash(self) -> None:
        """Start a smooth ping-pong color animation for the configured duration."""
        if self._flash_stop_timer.isActive():
            return
        flash_cfg = self.config.flash
        self._flash_anim.stop()
        self._flash_anim.setDuration(flash_cfg.interval)
        self._flash_anim.setStartValue(QColor(flash_cfg.color_b))
        self._flash_anim.setEndValue(QColor(flash_cfg.color_a))
        self._flash_anim.start()
        # Set label to flash text class immediately
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        base = "label alt" if self._show_alt_label else "label"
        for widget in active_widgets:
            if isinstance(widget, QLabel):
                widget.setProperty("class", f"{base} flash")
                refresh_widget_style(widget)
        self._flash_stop_timer.start(flash_cfg.duration * 1000)

    def _on_flash_half_done(self) -> None:
        """Reverse the animation on each half-cycle to create a ping-pong effect."""
        if not self._flash_stop_timer.isActive():
            return
        start = self._flash_anim.startValue()
        end = self._flash_anim.endValue()
        self._flash_anim.setStartValue(end)
        self._flash_anim.setEndValue(start)
        self._flash_anim.start()

    def _on_flash_frame(self, color: QColor) -> None:
        """Apply interpolated background color to the entire widget container each frame."""
        hex_color = color.name()
        self._widget_container.setStyleSheet(f"background-color: {hex_color}; border-color: {hex_color};")

    def _stop_flash(self) -> None:
        """Stop the flash animation and restore all styles."""
        self._flash_anim.stop()
        self._widget_container.setStyleSheet("")
        self._update_label(update_class=True)

    # ------------------------------------------------------------------
    # Popup card
    # ------------------------------------------------------------------

    def _toggle_card(self) -> None:
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)  # type: ignore
        self._show_popup()

    def _show_popup(self) -> None:
        m = self.config.menu
        self._popup = PopupWidget(self, m.blur, m.round_corners, m.round_corners_type, m.border_color)
        self._popup.setProperty("class", "prayer-times-menu")
        self._popup_row_widgets = {}

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(8)

        mosque_icon = QLabel(self.config.icons.mosque)
        mosque_icon.setProperty("class", "mosque-icon")
        mosque_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        title_text = "Tomorrow's Prayers" if self._date_offset > 0 else "Prayer Times"
        title_lbl = QLabel(title_text)
        title_lbl.setProperty("class", "title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        header_layout.addWidget(mosque_icon)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        if self._hijri:
            month_en = self._hijri.get("month", {}).get("en", "")
            hijri_lbl = QLabel(f"{self._hijri.get('day', '')} {month_en} {self._hijri.get('year', '')} AH")
            hijri_lbl.setProperty("class", "hijri-date")
            hijri_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            header_layout.addWidget(hijri_lbl)

        layout.addWidget(header)

        # ── Loading placeholder ───────────────────────────────────────
        if self._loading:
            loading_lbl = QLabel("Fetching prayer times...")
            loading_lbl.setProperty("class", "loading-placeholder")
            loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(loading_lbl)
            self._popup.setLayout(layout)
            self._popup.adjustSize()
            self._popup.setPosition(
                alignment=m.alignment,
                direction=m.direction,
                offset_left=m.offset_left,
                offset_top=m.offset_top,
            )
            self._popup.show()
            return

        # ── Prayer rows ───────────────────────────────────────────────
        next_name, _ = self._get_next_prayer()
        prayers = self.config.prayers_to_show or ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        ic = self.config.icons
        icon_map = {
            "Fajr": ic.fajr,
            "Sunrise": ic.sunrise,
            "Dhuhr": ic.dhuhr,
            "Asr": ic.asr,
            "Sunset": ic.sunset,
            "Maghrib": ic.maghrib,
            "Isha": ic.isha,
            "Imsak": ic.imsak,
            "Midnight": ic.midnight,
        }

        rows_container = QWidget()
        rows_container.setProperty("class", "rows-container")
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        for name in prayers:
            time_str = self._timings.get(name, "--:--")
            delta_text = self._time_delta_text(time_str)
            is_next = name == next_name
            is_passed = delta_text == "passed"

            row = QFrame()
            row_class = "prayer-row"
            if is_next:
                row_class += " active"
            elif is_passed:
                row_class += " passed"
            row.setProperty("class", row_class)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 10, 16, 10)
            row_layout.setSpacing(10)

            icon_lbl = QLabel(icon_map.get(name, ic.default))
            icon_lbl.setProperty("class", "prayer-icon")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFixedWidth(32)

            name_lbl = QLabel(name)
            name_lbl.setProperty("class", "prayer-name")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_lbl.setFixedWidth(80)

            time_lbl = QLabel(time_str)
            time_lbl.setProperty("class", "prayer-time")
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            time_lbl.setFixedWidth(52)

            remaining_lbl = QLabel(delta_text)
            remaining_lbl.setProperty("class", "prayer-remaining")
            remaining_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

            row_layout.addWidget(icon_lbl)
            row_layout.addWidget(name_lbl)
            row_layout.addWidget(time_lbl)
            row_layout.addStretch()
            row_layout.addWidget(remaining_lbl)

            rows_layout.addWidget(row)
            self._popup_row_widgets[name] = {"row": row, "remaining": remaining_lbl}  # type: ignore

        layout.addWidget(rows_container)

        # ── Footer ────────────────────────────────────────────────────
        method_name = self._meta.get("method", {}).get("name", "")
        if method_name:
            footer = QWidget()
            footer.setProperty("class", "footer")
            footer_layout = QHBoxLayout(footer)
            footer_layout.setContentsMargins(16, 8, 16, 8)
            method_lbl = QLabel(method_name)
            method_lbl.setProperty("class", "method-name")
            method_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            footer_layout.addWidget(method_lbl)
            layout.addWidget(footer)

        self._popup.setLayout(layout)
        self._popup.adjustSize()
        self._popup.setPosition(
            alignment=m.alignment,
            direction=m.direction,
            offset_left=m.offset_left,
            offset_top=m.offset_top,
        )
        self._popup.show()

    def _refresh_popup_rows(self) -> None:
        """Update remaining-time labels and active/passed CSS classes every minute."""
        if not self._popup_row_widgets:
            return
        next_name, _ = self._get_next_prayer()
        for name, widgets in self._popup_row_widgets.items():
            row: QFrame = widgets["row"]  # type: ignore
            remaining_lbl: QLabel = widgets["remaining"]  # type: ignore
            time_str = self._timings.get(name, "--:--")
            delta_text = self._time_delta_text(time_str)
            remaining_lbl.setText(delta_text)
            row_class = "prayer-row"
            if name == next_name:
                row_class += " active"
            elif delta_text == "passed":
                row_class += " passed"
            row.setProperty("class", row_class)
            refresh_widget_style(row)
            refresh_widget_style(remaining_lbl)

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def _toggle_label(self) -> None:
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)  # type: ignore
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

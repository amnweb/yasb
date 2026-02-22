import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.prayer_times.api import PrayerTimesDataFetcher
from core.validation.widgets.yasb.prayer_times import PrayerTimesConfig
from core.widgets.base import BaseWidget

# Names returned by the Aladhan API – used for iteration and tooltip display.
ALL_PRAYER_NAMES = ["Imsak", "Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha", "Midnight"]


class PrayerTimesWidget(BaseWidget):
    validation_schema = PrayerTimesConfig

    def __init__(self, config: PrayerTimesConfig):
        super().__init__(class_name=f"prayer-times-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False

        # Cached data from the last successful API response
        self._timings: dict[str, str] = {}
        self._hijri: dict[str, Any] = {}

        # --- Container ---
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)

        # --- Labels ---
        self._widgets: list = []
        self._widgets_alt: list = []
        build_widget_label(self, config.label, config.label_alt, config.label_shadow.model_dump())

        # --- Callbacks ---
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

        # --- API fetcher (rebuilds URL with today's date on every call) ---
        self._fetcher = PrayerTimesDataFetcher(
            self,
            url_factory=self._build_api_url,
            timeout_ms=config.update_interval * 1000,
        )
        self._fetcher.finished.connect(self._on_data_received)
        self._fetcher.start()

        # --- Minute timer: re-render label so "next prayer" stays current ---
        self._minute_timer = QTimer(self)
        self._minute_timer.setInterval(60_000)
        self._minute_timer.timeout.connect(self._update_label)
        self._minute_timer.start()

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def _build_api_url(self) -> str:
        """Return the Aladhan timings URL for today's date."""
        today = datetime.now().strftime("%d-%m-%Y")
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
            self._update_label()
        except (KeyError, TypeError) as exc:
            logging.error(f"Prayer times widget: failed to parse API response: {exc}")

    # ------------------------------------------------------------------
    # Next prayer calculation
    # ------------------------------------------------------------------

    def _get_next_prayer(self) -> tuple[str, str]:
        """Return (prayer_name, time_str) for the next upcoming prayer in prayers_to_show."""
        if not self._timings:
            return ("—", "--:--")

        prayers = self.config.prayers_to_show or ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        now = datetime.now()

        for name in prayers:
            time_str = self._timings.get(name, "")
            if not time_str or time_str == "--:--":
                continue
            try:
                hour, minute = int(time_str[:2]), int(time_str[3:5])
                prayer_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if prayer_dt > now:
                    return (name, time_str)
            except ValueError, IndexError:
                continue

        # All prayers for today have passed – next is the first prayer (tomorrow)
        first_name = prayers[0]
        return (first_name, self._timings.get(first_name, "--:--"))

    # ------------------------------------------------------------------
    # Label data
    # ------------------------------------------------------------------

    def _build_label_options(self) -> dict[str, str]:
        """Build the dict of {placeholder: value} for string substitution."""
        options: dict[str, str] = {}

        # Individual prayer times (lower-case key matches placeholder name)
        for name in ALL_PRAYER_NAMES:
            options[f"{{{name.lower()}}}"] = self._timings.get(name, "--:--")

        # Next prayer
        next_name, next_time = self._get_next_prayer()
        options["{next_prayer}"] = next_name
        options["{next_prayer_time}"] = next_time

        # Icon from config
        icon_cfg = self.config.icons
        icon_map = {
            "Fajr": icon_cfg.fajr,
            "Sunrise": icon_cfg.sunrise,
            "Dhuhr": icon_cfg.dhuhr,
            "Asr": icon_cfg.asr,
            "Maghrib": icon_cfg.maghrib,
            "Isha": icon_cfg.isha,
            "Imsak": icon_cfg.imsak,
            "Midnight": icon_cfg.midnight,
        }
        options["{icon}"] = icon_map.get(next_name, icon_cfg.default)

        # Hijri date parts
        if self._hijri:
            options["{hijri_day}"] = self._hijri.get("day", "")
            options["{hijri_month}"] = self._hijri.get("month", {}).get("en", "")
            options["{hijri_year}"] = self._hijri.get("year", "")
            options["{hijri_date}"] = f"{options['{hijri_day}']} {options['{hijri_month}']} {options['{hijri_year}']}"
        else:
            for key in ("{hijri_day}", "{hijri_month}", "{hijri_year}", "{hijri_date}"):
                options[key] = ""

        return options

    # ------------------------------------------------------------------
    # Label update
    # ------------------------------------------------------------------

    def _update_label(self, update_class: bool = True) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_content = self.config.label_alt if self._show_alt_label else self.config.label

        label_options = self._build_label_options()

        label_parts = re.split(r"(<span.*?>.*?</span>)", active_content)
        label_parts = [p for p in label_parts if p]

        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if not part or widget_index >= len(active_widgets):
                continue

            # Apply all substitutions
            for placeholder, value in label_options.items():
                part = part.replace(placeholder, str(value))

            widget = active_widgets[widget_index]
            if not isinstance(widget, QLabel):
                widget_index += 1
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                widget.setText(icon)
            else:
                widget.setText(part)
                if update_class:
                    next_name = label_options.get("{next_prayer}", "").lower()
                    base = "label alt" if self._show_alt_label else "label"
                    widget.setProperty("class", f"{base} {next_name}")
                    refresh_widget_style(widget)

            widget_index += 1

        # Tooltip: show all prayer times
        if self.config.tooltip and self._timings:
            self._update_tooltip()

    def _update_tooltip(self) -> None:
        """Set a tooltip on each label widget showing all prayer times."""
        prayers = self.config.prayers_to_show or ALL_PRAYER_NAMES
        lines = [f"{name}: {self._timings.get(name, '--:--')}" for name in prayers]
        if self._hijri:
            month = self._hijri.get("month", {}).get("en", "")
            lines.append(f"\n{self._hijri.get('day', '')} {month} {self._hijri.get('year', '')} AH")
        tooltip_text = "\n".join(lines)

        all_widgets = (self._widgets or []) + (self._widgets_alt or [])
        for widget in all_widgets:
            set_tooltip(widget, tooltip_text)

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

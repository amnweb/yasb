import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.widgets.prayer_times.api import PrayerTimesDataFetcher
from core.utils.widgets.prayer_times.ribbon import DayRibbon, RibbonMark
from core.utils.widgets.prayer_times.schedule import (
    ALL_PRAYER_NAMES,
    SOLAR_NAMES,
    PrayerTime,
    build_schedule,
    day_window,
    format_countdown,
    format_delta,
    format_span,
    light_stops,
    parse_gregorian_date,
    previous_entry,
    progress_fraction,
    shift_days,
)
from core.validation.widgets.yasb.prayer_times import PrayerTimesConfig
from core.widgets.base import BaseWidget

_DEFAULT_PRAYERS: list[str] = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
_DELTA_PASSED = "passed"

# A prayer moment older than this is treated as stale rather than "just happened",
# so waking from sleep does not fire a burst of flashes for prayers long past.
_FLASH_STALE_AFTER = timedelta(minutes=2)

# Resolution of the hero progress bar; a minute is well under one step of a prayer-to-prayer span.
_PROGRESS_STEPS = 1000


class PrayerTimesWidget(BaseWidget):
    """Widget that displays Islamic prayer times sourced from the Aladhan API.

    Renders the next upcoming prayer on the bar, supports an alternate label
    for a quick all-prayer overview, and opens a popup card with individual
    prayer rows and Hijri date information.  A configurable flash animation
    fires at the exact minute of each prayer.

    The API returns bare ``HH:MM`` strings in the *location's* timezone, so all
    times are resolved to absolute local moments (see ``prayer_times.schedule``)
    before any comparison against the current time.
    """

    validation_schema = PrayerTimesConfig

    def __init__(self, config: PrayerTimesConfig):
        super().__init__(class_name=f"prayer-times-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._timings: dict[str, str] = {}
        self._hijri: dict[str, Any] = {}
        self._meta: dict[str, Any] = {}
        self._schedule: list[PrayerTime] = []
        self._solar: dict[str, PrayerTime] = {}
        self._base_date = None
        self._tz_name: str | None = None
        self._popup: PopupWidget | None = None
        self._popup_layout: QVBoxLayout | None = None
        self._popup_key: tuple | None = None
        self._popup_hero: dict[str, QWidget] = {}
        self._popup_ribbon: dict[str, QWidget] = {}
        self._popup_row_widgets: dict[str, dict[str, QWidget]] = {}
        self._loading: bool = True
        self._date_offset: int = 0
        self._current_date: str = datetime.now().strftime("%Y-%m-%d")
        self._last_flash_check = self._now()

        self._init_container()
        self.build_widget_label(config.label, config.label_alt)
        # Remember each label's configured class before any state class is layered
        # on top, so icon spans keep their own class rather than inheriting "label".
        for label in (*self._widgets, *self._widgets_alt):
            label.setProperty("base_class", label.property("class") or "")

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

        # --- Minute timer: re-render label, fire flash, refresh popup ---
        # Aligned to the wall clock so a drifting timer cannot skip the minute
        # a prayer falls on.
        self._minute_timer = QTimer(self)
        self._minute_timer.setInterval(60_000)
        self._minute_timer.timeout.connect(self._on_minute_tick)
        now = datetime.now()
        ms_to_next_minute = (60 - now.second) * 1000 - now.microsecond // 1000
        QTimer.singleShot(max(ms_to_next_minute, 0), self._start_minute_timer)

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

        # Trigger flash immediately for debugging
        if config.flash.enabled and config.flash.debug:
            QTimer.singleShot(500, self._start_flash)

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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        """Return the current moment as a timezone-aware local datetime."""
        return datetime.now().astimezone()

    @property
    def _prayers(self) -> list[str]:
        """Return the configured list of prayers to show, falling back to defaults."""
        return self.config.prayers_to_show or _DEFAULT_PRAYERS

    @property
    def _grace(self) -> timedelta:
        return timedelta(minutes=self.config.grace_period)

    @property
    def _icon_map(self) -> dict[str, str]:
        """Return a mapping from prayer name to its configured icon character."""
        ic = self.config.icons
        return {
            "Fajr": ic.fajr,
            "Sunrise": ic.sunrise,
            "Dhuhr": ic.dhuhr,
            "Asr": ic.asr,
            "Sunset": ic.sunset,
            "Maghrib": ic.maghrib,
            "Isha": ic.isha,
            "Imsak": ic.imsak,
            "Midnight": ic.midnight,
            "Firstthird": ic.firstthird,
            "Lastthird": ic.lastthird,
        }

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------

    def _on_data_received(self, data: dict) -> None:
        if not data:
            return
        try:
            payload = data["data"]
            self._timings = payload["timings"]
            self._hijri = payload["date"]["hijri"]
            self._meta = payload.get("meta", {})
            self._tz_name = self._meta.get("timezone") or None
            # Anchor to the date the API actually answered for, not a locally
            # computed one, so a slow response near midnight cannot mis-date it.
            self._base_date = parse_gregorian_date(payload.get("date", {}).get("gregorian", {}).get("date"))
            if self._base_date is None:
                self._base_date = (datetime.now() + timedelta(days=self._date_offset)).date()
            self._rebuild_schedule()
            self._loading = False
            self._update_label()
            self._sync_popup()
            # If today's prayers are all done and we haven't switched to tomorrow yet,
            # immediately re-fetch tomorrow's schedule.
            if self._date_offset == 0 and self._all_prayers_passed():
                self._date_offset = 1
                self._fetcher.make_request()
        except (KeyError, TypeError) as exc:
            logging.error("Prayer times widget: failed to parse API response: %s", exc)

    def _rebuild_schedule(self) -> None:
        """Resolve the raw API timings into absolute, chronologically sorted local moments."""
        if not self._timings or self._base_date is None:
            self._schedule = []
            self._solar = {}
            return
        self._schedule = build_schedule(self._timings, self._base_date, self._tz_name, self._prayers)
        # The day is lit the same whether or not Sunrise is one of the prayers on show,
        # so the ribbon's light is resolved from the full response, not from _prayers.
        self._solar = {
            entry.name: entry for entry in build_schedule(self._timings, self._base_date, self._tz_name, SOLAR_NAMES)
        }

    def _start_minute_timer(self) -> None:
        self._minute_timer.start()
        self._on_minute_tick()

    def _on_minute_tick(self) -> None:
        # Reset to today when the calendar date changes (midnight rollover).
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._date_offset = 0
            self._fetcher.make_request()
            # Fall through rather than returning: the schedule holds absolute
            # moments, so it stays renderable until the response lands.
        self._update_label()
        if self.config.flash.enabled and self._flash_is_due():
            self._start_flash()
        self._sync_popup()

    def _all_prayers_passed(self) -> bool:
        """Return True if every configured prayer has passed, grace period included."""
        if not self._schedule:
            return False
        now = self._now()
        return all(entry.at + self._grace <= now for entry in self._schedule)

    # ------------------------------------------------------------------
    # Next prayer helpers
    # ------------------------------------------------------------------

    def _next_entry(self) -> PrayerTime | None:
        """Return the current or next upcoming prayer, or None if nothing is loaded.

        A prayer is considered 'current' for grace_period minutes after its time,
        so the label doesn't immediately jump to the next prayer when the time hits.

        Once the whole day has passed, the first prayer comes back rolled onto tomorrow.
        Returning it unrolled read as a moment that had already gone by, which is how the
        popup came to announce a prayer 'started 1076m ago' late in the evening. The widget
        re-fetches tomorrow's schedule at that point anyway; this is what it shows while
        that request is in flight, or if it never lands.
        """
        if not self._schedule:
            return None
        now = self._now()
        grace = self._grace
        for entry in self._schedule:
            if entry.at + grace > now:
                return entry
        return shift_days(self._schedule[0], 1)

    def _get_next_prayer(self) -> tuple[str, str]:
        """Return (prayer_name, time_str) for the current or next upcoming prayer."""
        entry = self._next_entry()
        if entry is None:
            return ("—", "--:--")
        return (entry.name, entry.time_str)

    def _time_delta_text(self, entry: PrayerTime) -> str:
        """Return human-readable remaining/elapsed label for a prayer moment."""
        return format_delta(entry.at, self._now(), self._grace, _DELTA_PASSED)

    def _row_delta_text(self, entry: PrayerTime, upcoming: PrayerTime | None) -> str:
        """Return the delta for a row, counting from *upcoming* when this is the row it names.

        Late in the evening every prayer in the day has gone by and the next one is the first
        prayer again, on tomorrow. The row was reading its own moment, so it came up both
        highlighted as next and marked as done; now it counts down to the same moment the hero
        above it does.
        """
        if upcoming is not None and entry.name == upcoming.name:
            return self._time_delta_text(upcoming)
        return self._time_delta_text(entry)

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
        options["{icon}"] = self._icon_map.get(next_name, self.config.icons.default)
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

    def _label_class(self, base: str, *states: str) -> str:
        """Compose a bar label's class: its configured class, any state classes, and ``flash`` while the glow runs."""
        flashing = ("flash",) if self._flash_stop_timer.isActive() else ()
        return " ".join(part for part in (base, *states, *flashing) if part)

    def _update_label(self, update_class: bool = True) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_content = self.config.label_alt if self._show_alt_label else self.config.label
        if self._loading:
            for widget in active_widgets:
                if not isinstance(widget, QLabel):
                    continue
                base = widget.property("base_class") or ""
                # Leave icon span text alone; only text labels get the placeholder.
                if "label" in base.split():
                    widget.setText("Loading...")
                    widget.setProperty("class", self._label_class(base, "loading"))
                else:
                    widget.setProperty("class", self._label_class(base))
                refresh_widget_style(widget)
            return
        label_options = self._build_label_options()
        label_parts = [p for p in re.split(r"(<span.*?>.*?</span>)", active_content) if p]
        next_name = label_options.get("{next_prayer}", "")
        # Guard against the "—" placeholder becoming a CSS class.
        prayer_class = next_name.lower() if next_name.isalpha() else ""
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
                # Every label keeps its configured class and additionally carries the
                # current prayer, so icons and text can be tinted per time of day.
                base = widget.property("base_class") or ""
                widget.setProperty("class", self._label_class(base, prayer_class))
                refresh_widget_style(widget)
            widget_index += 1
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        """Update the hover tooltip with a summary of today's (or tomorrow's) prayer times."""
        if not self.config.tooltip or not self._schedule:
            return
        next_name, _ = self._get_next_prayer()
        label = "Tomorrow" if self._date_offset > 0 else "Today"
        lines: list[str] = [f"<strong>{label}'s Prayers</strong>"]
        for entry in self._schedule:
            marker = " ◀" if entry.name == next_name else ""
            lines.append(f"{entry.name}: {entry.time_str}{marker}")
        set_tooltip(self, "<br>".join(lines))

    # ------------------------------------------------------------------
    # Prayer-time flash
    # ------------------------------------------------------------------

    def _flash_is_due(self) -> bool:
        """Return True if a prayer moment fell inside the window since the last check.

        Comparing against the previous check rather than the current wall-clock
        minute keeps this correct when the timer drifts or the machine sleeps.
        """
        now = self._now()
        previous = self._last_flash_check
        self._last_flash_check = now
        if self._loading or not self._schedule:
            return False
        return any(previous < entry.at <= now and now - entry.at <= _FLASH_STALE_AFTER for entry in self._schedule)

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
        # A running stop timer is what makes _label_class layer `flash` onto every label,
        # so it must be started before the labels are re-rendered.
        self._flash_stop_timer.start(flash_cfg.duration * 1000)
        self._update_label()

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
        # Stopping the timer first is what drops `flash` from the re-rendered labels.
        self._flash_stop_timer.stop()
        self._flash_anim.stop()
        self._widget_container.setStyleSheet("")
        self._update_label()

    # ------------------------------------------------------------------
    # Popup card
    # ------------------------------------------------------------------

    def _toggle_card(self) -> None:
        self._show_popup()

    def _show_popup(self) -> None:
        m = self.config.menu
        popup = PopupWidget(self, m.blur, m.round_corners, m.round_corners_type, m.border_color)
        popup.setProperty("class", "prayer-times-menu")

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._fill_popup(layout)

        popup.adjustSize()
        popup.setPosition(
            alignment=m.alignment,
            direction=m.direction,
            offset_left=m.offset_left,
            offset_top=m.offset_top,
        )
        popup.show()

        if popup.isVisible():
            self._popup = popup
        else:
            # PopupWidget.show() found one already open for this parent and
            # toggled it closed instead. This instance was never shown, so it
            # would never delete itself - drop it rather than leak it.
            popup.deleteLater()
            self._forget_popup()

    def _forget_popup(self) -> None:
        """Drop references to a popup that is gone or was never shown."""
        self._popup = None
        self._popup_layout = None
        self._popup_key = None
        self._popup_hero = {}
        self._popup_row_widgets = {}

    def _sync_popup(self) -> None:
        """Refresh the open popup, or drop stale references if it has closed."""
        if self._popup is None:
            return
        try:
            if not self._popup.isVisible():
                self._forget_popup()
                return
            self._refresh_popup()
        except RuntimeError:
            # Underlying C++ object already deleted.
            self._forget_popup()

    def _popup_state_key(self) -> tuple:
        """Everything the popup's structure depends on; when it changes the popup is rebuilt."""
        return (
            self._loading,
            self._base_date,
            self._now().date(),
            tuple(entry.name for entry in self._schedule),
            bool(self._hijri),
        )

    def _fill_popup(self, layout: QVBoxLayout) -> None:
        """Build every popup section into *layout*, replacing whatever it held before."""
        while layout.count():
            old = layout.takeAt(0).widget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()
        self._popup_layout = layout
        self._popup_key = self._popup_state_key()
        self._popup_hero = {}
        self._popup_ribbon = {}
        self._popup_row_widgets = {}

        layout.addWidget(self._build_popup_header())
        if self._loading or not self._schedule:
            text = "Fetching prayer times..." if self._loading else "No prayer times available"
            placeholder = QLabel(text)
            placeholder.setProperty("class", "loading-placeholder")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(placeholder)
            return

        ribbon = self._build_popup_ribbon()
        if ribbon is not None:
            layout.addWidget(ribbon)
        layout.addWidget(self._build_popup_hero())
        layout.addWidget(self._build_popup_rows())
        footer = self._build_popup_footer()
        if footer is not None:
            layout.addWidget(footer)

    def _refresh_popup(self) -> None:
        """Rebuild the popup when the day or prayer list changed, otherwise update it in place."""
        if self._popup_layout is None:
            return
        if self._popup_state_key() != self._popup_key:
            self._fill_popup(self._popup_layout)
            if self._popup is not None:
                self._popup.adjustSize()
            return
        self._refresh_popup_ribbon()
        self._refresh_popup_hero()
        self._refresh_popup_rows()

    def _gregorian_text(self) -> str:
        """Return the schedule's gregorian date, prefixed with Today/Tomorrow when it is one of those."""
        day = self._base_date
        text = f"{day:%A} {day.day} {day:%B}"
        relative = {0: "Today", 1: "Tomorrow"}.get((day - self._now().date()).days)
        return f"{relative}, {text}" if relative else text

    def _build_popup_header(self) -> QFrame:
        """Build the header: mosque icon and title on the left, Hijri and Gregorian dates on the right."""
        header = QFrame()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        mosque_icon = QLabel(self.config.icons.mosque)
        mosque_icon.setProperty("class", "mosque-icon")
        title_lbl = QLabel("Prayer times")
        title_lbl.setProperty("class", "title")
        header_layout.addWidget(mosque_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(title_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch()

        dates_layout = QVBoxLayout()
        dates_layout.setContentsMargins(0, 0, 0, 0)
        dates_layout.setSpacing(0)
        if self._hijri:
            month_en = self._hijri.get("month", {}).get("en", "")
            hijri_lbl = QLabel(f"{self._hijri.get('day', '')} {month_en} {self._hijri.get('year', '')} AH")
            hijri_lbl.setProperty("class", "hijri-date")
            hijri_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            dates_layout.addWidget(hijri_lbl)
        if self._base_date is not None:
            gregorian_lbl = QLabel(self._gregorian_text())
            gregorian_lbl.setProperty("class", "gregorian-date")
            gregorian_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            dates_layout.addWidget(gregorian_lbl)
        header_layout.addLayout(dates_layout)

        return header

    # ------------------------------------------------------------------
    # Day ribbon
    # ------------------------------------------------------------------

    def _build_popup_ribbon(self) -> QFrame | None:
        """Build the day ribbon: this date's own light, ticked with its prayers.

        Returns None when the response carried no sunrise or sunset, since without them
        there is no daylight to draw and a flat band would say nothing the rows do not.
        """
        if self._base_date is None or "Sunrise" not in self._solar:
            return None
        if not (set(self._solar) & {"Sunset", "Maghrib"}):
            return None

        section = QFrame()
        section.setProperty("class", "day")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        ribbon = DayRibbon()
        ribbon.setProperty("class", "day-ribbon")
        section_layout.addWidget(ribbon)

        # Glyph and time are separate labels rather than one string: a Nerd Font icon and
        # a UI-font time need different families and their own gap, which one QLabel cannot
        # give them.  Same split the bar labels use.
        captions_layout = QHBoxLayout()
        captions_layout.setContentsMargins(0, 0, 0, 0)
        captions_layout.setSpacing(0)
        sunrise_icon = QLabel(self._icon_map.get("Sunrise", ""))
        sunrise_icon.setProperty("class", "day-icon sunrise")
        sunrise_lbl = QLabel()
        sunrise_lbl.setProperty("class", "day-sunrise")
        daylight_lbl = QLabel()
        daylight_lbl.setProperty("class", "day-length")
        daylight_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sunset_lbl = QLabel()
        sunset_lbl.setProperty("class", "day-sunset")
        sunset_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        sunset_icon = QLabel(self._icon_map.get("Sunset", ""))
        sunset_icon.setProperty("class", "day-icon sunset")
        captions_layout.addWidget(sunrise_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        captions_layout.addWidget(sunrise_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        captions_layout.addStretch()
        captions_layout.addWidget(daylight_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        captions_layout.addStretch()
        captions_layout.addWidget(sunset_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        captions_layout.addWidget(sunset_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        section_layout.addLayout(captions_layout)

        self._popup_ribbon = {
            "frame": section,
            "ribbon": ribbon,
            "sunrise-icon": sunrise_icon,
            "sunrise": sunrise_lbl,
            "daylight": daylight_lbl,
            "sunset": sunset_lbl,
            "sunset-icon": sunset_icon,
        }
        self._refresh_popup_ribbon()
        return section

    def _refresh_popup_ribbon(self) -> None:
        """Move the ribbon's now stem and re-mark the prayers it has gone past."""
        parts = self._popup_ribbon
        if not parts or self._base_date is None:
            return
        now = self._now()
        start, end = day_window(self._base_date, self._tz_name, self._schedule)
        span = (end - start).total_seconds()
        if span <= 0:
            return

        def fraction(moment) -> float:
            return (moment - start).total_seconds() / span

        marks = [RibbonMark(at=fraction(entry.at), passed=entry.at <= now) for entry in self._schedule]
        # The stem is dropped rather than pinned to an edge once the popup has moved on to
        # tomorrow's schedule: this band is not the day the clock is in.
        position = fraction(now)
        ribbon: DayRibbon = parts["ribbon"]  # type: ignore[assignment]
        ribbon.set_day(light_stops(self._solar, start, end), marks, position if 0.0 <= position <= 1.0 else None)

        sunrise = self._solar.get("Sunrise")
        sunset = self._solar.get("Sunset") or self._solar.get("Maghrib")
        if sunrise is not None:
            parts["sunrise"].setText(sunrise.time_str)  # type: ignore[attr-defined]
        if sunset is not None:
            parts["sunset"].setText(sunset.time_str)  # type: ignore[attr-defined]
        if sunrise is not None and sunset is not None:
            length = format_span(sunrise.at, sunset.at)
            parts["daylight"].setText(f"{length} of daylight" if length else "")  # type: ignore[attr-defined]
        refresh_widget_style(*parts.values())

    def _build_popup_hero(self) -> QFrame:
        """Build the hero block: the current or next prayer, its countdown and progress since the previous one."""
        hero = QFrame()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(0)

        head_layout = QHBoxLayout()
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(0)
        icon_lbl = QLabel()
        icon_lbl.setProperty("class", "hero-icon")
        name_lbl = QLabel()
        name_lbl.setProperty("class", "hero-name")
        head_layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        head_layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        head_layout.addStretch()
        hero_layout.addLayout(head_layout)

        countdown_lbl = QLabel()
        countdown_lbl.setProperty("class", "hero-countdown")
        hero_layout.addWidget(countdown_lbl)

        progress = QProgressBar()
        progress.setProperty("class", "hero-progress")
        progress.setRange(0, _PROGRESS_STEPS)
        progress.setTextVisible(False)
        hero_layout.addWidget(progress)

        captions_layout = QHBoxLayout()
        captions_layout.setContentsMargins(0, 0, 0, 0)
        captions_layout.setSpacing(0)
        from_lbl = QLabel()
        from_lbl.setProperty("class", "hero-from")
        to_lbl = QLabel()
        to_lbl.setProperty("class", "hero-to")
        to_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        captions_layout.addWidget(from_lbl)
        captions_layout.addStretch()
        captions_layout.addWidget(to_lbl)
        hero_layout.addLayout(captions_layout)

        self._popup_hero = {
            "frame": hero,
            "icon": icon_lbl,
            "name": name_lbl,
            "countdown": countdown_lbl,
            "progress": progress,
            "from": from_lbl,
            "to": to_lbl,
        }
        self._refresh_popup_hero()
        return hero

    def _refresh_popup_hero(self) -> None:
        """Fill the hero widgets from the current or next prayer."""
        hero = self._popup_hero
        entry = self._next_entry()
        if not hero or entry is None:
            return
        now = self._now()
        previous = previous_entry(self._schedule, entry)
        # The frame carries the prayer name so CSS can tint the whole block per time of day,
        # and `now` for the one window the whole widget exists for: the prayer that has just
        # been called and is still inside its grace period.
        state = " now" if self._is_live(entry) else ""
        hero["frame"].setProperty("class", f"hero {entry.name.lower()}{state}")
        hero["icon"].setText(self._icon_map.get(entry.name, self.config.icons.default))
        hero["name"].setText(entry.name)
        hero["countdown"].setText(format_countdown(entry.at, now))
        hero["progress"].setValue(round(progress_fraction(previous.at, entry.at, now) * _PROGRESS_STEPS))
        hero["from"].setText(f"{previous.name} {previous.time_str}")
        hero["to"].setText(entry.time_str)
        refresh_widget_style(*hero.values())

    def _is_live(self, entry: PrayerTime) -> bool:
        """Return True while *entry* is the prayer that has been called and is still in grace."""
        now = self._now()
        return entry.at <= now < entry.at + self._grace

    def _row_class(self, entry: PrayerTime, next_name: str, delta_text: str) -> str:
        """Return a row's CSS class: its prayer name plus 'active', 'now' or 'passed' where those apply."""
        row_class = f"prayer-row {entry.name.lower()}"
        if entry.name == next_name:
            return f"{row_class} active now" if self._is_live(entry) else f"{row_class} active"
        if delta_text == _DELTA_PASSED:
            return f"{row_class} passed"
        return row_class

    def _remaining_slot(self, delta_text: str) -> tuple[str, str, Qt.AlignmentFlag]:
        """Return the (text, class, alignment) for a row's right-hand slot.

        A prayer that is done is marked once, not labelled: stacking the word 'passed' down
        four rows turned the column into noise and left no room for the one countdown that
        is actually live.

        The mark is centred rather than right-aligned, and that is load-bearing. Qt measures
        a label with the font family the stylesheet asked for; where that name is not the
        installed one it falls back to a font whose advance for the glyph is narrower than
        the ink the real font then paints, and a right-aligned glyph gets sliced down the
        middle. Centring leaves the overhang somewhere to go whatever the machine has
        installed, which is not something a widget shipped to other people can assume.
        """
        if delta_text == _DELTA_PASSED:
            return self.config.icons.done, "prayer-remaining done", Qt.AlignmentFlag.AlignCenter
        return delta_text, "prayer-remaining", Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight

    def _build_popup_rows(self) -> QFrame:
        """Build the prayer rows container, recording row widgets for later refresh."""
        icon_map = self._icon_map
        ic = self.config.icons
        upcoming = self._next_entry()
        next_name, _ = self._get_next_prayer()

        rows_container = QFrame()
        rows_container.setProperty("class", "rows-container")
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        for entry in self._schedule:
            delta_text = self._row_delta_text(entry, upcoming)

            row = QFrame()
            row.setProperty("class", self._row_class(entry, next_name, delta_text))
            row_layout = QHBoxLayout(row)
            # All spacing/sizing is left to CSS so the popup stays themeable.
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            icon_lbl = QLabel(icon_map.get(entry.name, ic.default))
            icon_lbl.setProperty("class", "prayer-icon")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            name_lbl = QLabel(entry.name)
            name_lbl.setProperty("class", "prayer-name")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            time_lbl = QLabel(entry.time_str)
            time_lbl.setProperty("class", "prayer-time")
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            remaining_text, remaining_class, remaining_align = self._remaining_slot(delta_text)
            remaining_lbl = QLabel(remaining_text)
            remaining_lbl.setProperty("class", remaining_class)
            remaining_lbl.setAlignment(remaining_align)

            row_layout.addWidget(icon_lbl)
            row_layout.addWidget(name_lbl)
            row_layout.addWidget(time_lbl)
            row_layout.addStretch()
            row_layout.addWidget(remaining_lbl)

            rows_layout.addWidget(row)
            self._popup_row_widgets[entry.name] = {
                "row": row,
                "icon": icon_lbl,
                "name": name_lbl,
                "time": time_lbl,
                "remaining": remaining_lbl,
            }

        return rows_container

    def _build_popup_footer(self) -> QFrame | None:
        """Build the footer with the calculation method and timezone, or None when neither is known."""
        method_name = self._meta.get("method", {}).get("name", "")
        if not (method_name or self._tz_name):
            return None
        footer = QFrame()
        footer.setProperty("class", "footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)
        if method_name:
            method_lbl = QLabel(method_name)
            method_lbl.setProperty("class", "method-name")
            footer_layout.addWidget(method_lbl)
        footer_layout.addStretch()
        if self._tz_name:
            timezone_lbl = QLabel(self._tz_name)
            timezone_lbl.setProperty("class", "timezone")
            timezone_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            footer_layout.addWidget(timezone_lbl)
        return footer

    def _refresh_popup_rows(self) -> None:
        """Update remaining-time labels and active/passed CSS classes every minute."""
        if not self._popup_row_widgets:
            return
        upcoming = self._next_entry()
        next_name, _ = self._get_next_prayer()
        for entry in self._schedule:
            widgets = self._popup_row_widgets.get(entry.name)
            if widgets is None:
                continue
            row: QFrame = widgets["row"]  # type: ignore[assignment]
            remaining_lbl: QLabel = widgets["remaining"]  # type: ignore[assignment]
            delta_text = self._row_delta_text(entry, upcoming)
            remaining_text, remaining_class, remaining_align = self._remaining_slot(delta_text)
            remaining_lbl.setText(remaining_text)
            remaining_lbl.setProperty("class", remaining_class)
            remaining_lbl.setAlignment(remaining_align)
            row.setProperty("class", self._row_class(entry, next_name, delta_text))
            # Descendant rules such as `.prayer-row.active .prayer-name` only re-apply once the
            # children are repolished as well, not just the row whose class changed.
            refresh_widget_style(*widgets.values())

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

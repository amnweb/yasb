import json
import locale
import logging
import os
import re
import winsound
from collections.abc import Iterator, Mapping
from datetime import date, datetime, timedelta
from functools import partial
from itertools import cycle
from types import ModuleType
from typing import NotRequired, TypedDict, cast, override
from zoneinfo import ZoneInfo, available_timezones

from PyQt6.QtCore import QDate, QLocale, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QPainter, QPalette, QShowEvent
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCalendarWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.tooltip import set_tooltip, show_tooltip_now
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.win32.backdrop import enable_blur
from core.utils.win32.utils import apply_qmenu_style
from core.validation.widgets.yasb.clock import ClockConfig
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH


class _HolidaysCache(TypedDict):
    module: ModuleType | None
    supported_countries: set[str] | None
    country_holidays: dict[str, Mapping[date, str]]


class Alarm(TypedDict):
    time: str
    days: NotRequired[list[int]]
    enabled: NotRequired[bool]
    title: NotRequired[str]


class SnoozedAlarm(TypedDict):
    alarm: Alarm
    snooze_until: datetime


type LocaleSetting = tuple[str | None, str | None]

_holidays_cache: _HolidaysCache = {"module": None, "supported_countries": None, "country_holidays": {}}
NOTIFICATION_SOUND = os.path.join(SCRIPT_PATH, "assets", "sound", "notification02.wav")


class ClockWidgetSharedState:
    """Shared state shared between all clock widget instances."""

    _instance: ClockWidgetSharedState | None = None
    _initialized: bool

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
        return cls._instance

    def __init__(self):
        """Initialize the shared state (only runs once for the singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self._widget_instances: list[ClockWidget] = []
        self.alarms: list[Alarm] = []
        self.snoozed_alarms: list[SnoozedAlarm] = []
        self._triggered_alarms: set[int] = set()
        self._last_check_minute: str | None = None
        self._startup_minute = datetime.now().strftime("%H:%M")
        self.timer_seconds_remaining = 0
        self.timer_active = False
        self._alarms_file = os.path.join(HOME_CONFIGURATION_DIR, "alarms.json")
        self._load_alarms()

    def register_widget(self, widget: ClockWidget) -> None:
        """Register a widget instance and start timer if this is first."""
        if widget not in self._widget_instances:
            self._widget_instances.append(widget)

            if len(self._widget_instances) == 1:
                widget.start_timer()

            def update_widget():
                try:
                    widget.update_label()
                    widget.update_tooltip()
                except Exception:
                    pass

            QTimer.singleShot(0, update_widget)

    def unregister_widget(self, widget: ClockWidget) -> None:
        """Remove a widget instance from the shared list."""
        if widget in self._widget_instances:
            self._widget_instances.remove(widget)

    def on_timer_tick(self):
        """Called on each timer tick: update timer, handle snoozes and alarms."""
        if self.timer_active:
            if self.timer_seconds_remaining == 0:
                self._timer_finished()
            elif self.timer_seconds_remaining > 0:
                self.timer_seconds_remaining -= 1

        for snoozed in self.snoozed_alarms[:]:
            snooze_until = snoozed["snooze_until"]
            if datetime.now() >= snooze_until:
                alarm = snoozed["alarm"]
                self.snoozed_alarms.remove(snoozed)
                self._trigger_alarm(alarm)

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        minute_changed = False
        if self._last_check_minute != current_time:
            self._last_check_minute = current_time
            self._triggered_alarms.clear()
            self._check_alarms()
            minute_changed = True

        self.notify_all_widgets(update_tooltip=minute_changed)

    def _check_alarms(self):
        """Check alarms and trigger any that should fire at the current minute."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.weekday()

        for idx, alarm in enumerate(self.alarms):
            if not alarm.get("enabled", True):
                continue

            if idx in self._triggered_alarms:
                continue

            if current_time == self._startup_minute:
                continue

            if alarm["time"] == current_time:
                days = alarm.get("days", [])
                if not days or len(days) == 7 or current_day in days:
                    self._triggered_alarms.add(idx)
                    self._trigger_alarm(alarm)

    def _trigger_alarm(self, alarm: Alarm) -> None:
        """Trigger an alarm on the first registered widget (UI action)."""
        if self._widget_instances:
            try:
                self._widget_instances[0].trigger_alarm(alarm)
            except Exception:
                pass

    def _timer_finished(self):
        """Handle the shared timer finishing: stop active timer and play sound."""
        self.timer_active = False
        self.timer_seconds_remaining = 0
        if self._widget_instances:
            try:
                self._widget_instances[0].play_sound()
            except Exception:
                pass

    def notify_all_widgets(self, update_tooltip: bool = False) -> None:
        """Notify all registered widgets to refresh label and optional tooltip."""
        for widget in self._widget_instances[:]:
            try:
                widget.update_label()
                if update_tooltip:
                    widget.update_tooltip()
            except Exception:
                pass

    def _load_alarms(self):
        """Load alarms from disk into shared state, if the file exists."""
        try:
            if os.path.exists(self._alarms_file):
                with open(self._alarms_file, encoding="utf-8") as f:
                    self.alarms = json.load(f)
        except Exception as e:
            logging.error("Error loading alarms: %s", e)
            self.alarms = []

    def save_alarms(self):
        """Persist alarms to disk in a tidy JSON format."""
        try:
            json_str = json.dumps(self.alarms, indent=2, ensure_ascii=False)
            json_str = re.sub(
                r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]",
                lambda m: "[" + m.group(1).replace("\n", "").replace(" ", "") + "]",
                json_str,
            )
            with open(self._alarms_file, "w", encoding="utf-8") as f:
                f.write(json_str)
        except Exception as e:
            logging.error("Error saving alarms: %s", e)


class FormattedSpinBox(QSpinBox):
    @override
    def textFromValue(self, v: int) -> str:
        """Format numeric value with two digits (e.g. 3 -> '03')."""
        return f"{v:02d}"

    def __init__(self, parent: QWidget | None = None):
        """Create the formatted spin box and make the line edit read-only."""
        super().__init__(parent)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)

    @override
    def showEvent(self, e: QShowEvent | None) -> None:
        """Adjust selection colors after the widget is shown so colors match."""
        super().showEvent(e)
        line_edit = self.lineEdit()
        if line_edit is None:
            return
        current_color = self.palette().color(self.foregroundRole())
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                selection-background-color: transparent;
                selection-color: {current_color.name()};
            }}
        """)


def _get_holidays_module() -> ModuleType:
    """Lazily import the `holidays` module and cache supported countries."""
    import importlib

    module = _holidays_cache["module"]
    if module is None:
        module = importlib.import_module("holidays")
        _holidays_cache["module"] = module
        _holidays_cache["supported_countries"] = set(module.list_supported_countries())
    return module


def _supported_country(country_code: str | None) -> str | None:
    supported = _holidays_cache["supported_countries"]
    if supported is None or not country_code:
        return None
    country = country_code.upper()
    if re.fullmatch(r"[A-Z]{2}", country) and country in supported:
        return country
    return None


def _get_cached_country_holidays(country: str, year: int, subdivision: str | None = None) -> Mapping[date, str]:
    """Return cached holidays for a country/year, loading if needed."""
    cache_key = f"{country}_{year}_{subdivision}"
    if cache_key not in _holidays_cache["country_holidays"]:
        holidays_module = _get_holidays_module()
        try:
            _holidays_cache["country_holidays"][cache_key] = holidays_module.country_holidays(
                country, years=[year], subdiv=subdivision
            )
        except Exception:
            _holidays_cache["country_holidays"][cache_key] = {}
    return _holidays_cache["country_holidays"][cache_key]


class CustomCalendar(QCalendarWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        timezone: str | None = None,
        country_code: str | None = None,
        subdivision: str | None = None,
        show_holidays: bool = True,
        holiday_color: str | None = None,
        locale_name: str = "",
    ):
        """Calendar widget with optional holiday highlighting by country."""
        super().__init__(parent)
        self.timezone = timezone
        self.country_code = country_code
        self.subdivision = subdivision
        self.show_holidays = show_holidays
        self.holiday_color = holiday_color
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setNavigationBarVisible(False)
        self.setAutoFillBackground(False)
        self._holidays: set[date] = set()
        self._current_year: int | None = None
        format = self.weekdayTextFormat(Qt.DayOfWeek.Monday)
        for day in range(Qt.DayOfWeek.Monday.value, Qt.DayOfWeek.Sunday.value + 1):
            self.setWeekdayTextFormat(Qt.DayOfWeek(day), format)

        table_view = self.findChild(QTableView)
        if table_view:
            table_view.setProperty("class", "calendar-table")
            palette = table_view.palette()
            palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
            palette.setColor(QPalette.ColorRole.HighlightedText, palette.color(QPalette.ColorRole.Text))
            table_view.setPalette(palette)

        if locale_name:
            self.setLocale(QLocale(locale_name))

        self.update_calendar_display()
        self._update_holidays_for_year(self.selectedDate().year())
        self.currentPageChanged.connect(self._on_page_changed)

    def _update_holidays_for_year(self, year: int) -> None:
        """Update the holiday cache for the given year (if supported)."""
        self._holidays = set()
        self._current_year = year
        country = _supported_country(self.country_code)
        if not country:
            return
        h = _get_cached_country_holidays(country, year, self.subdivision)
        self._holidays = set(h.keys())

    def _on_page_changed(self, year: int, month: int) -> None:
        """When calendar page changes, refresh holidays if year changed."""
        if year != self._current_year:
            self._update_holidays_for_year(year)

    @override
    def paintCell(self, painter: QPainter | None, rect: QRect, date: QDate | date) -> None:
        """Custom paint for cells; draw holiday dates in holiday_color."""
        qdate = date if isinstance(date, QDate) else QDate(date.year, date.month, date.day)
        if qdate < self.minimumDate() or qdate > self.maximumDate():
            return
        pydate = qdate.toPyDate()
        is_holiday = self.show_holidays and pydate in self._holidays
        if is_holiday and painter is not None:
            is_selected = qdate == self.selectedDate()
            if is_selected:
                painter.save()
                super().paintCell(painter, rect, date)
                painter.restore()
            else:
                painter.save()
                painter.setPen(QColor(self.holiday_color))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))
                painter.restore()
        else:
            super().paintCell(painter, rect, date)

    def update_calendar_display(self):
        """Set the calendar selected date according to the configured timezone."""
        if self.timezone:
            datetime_now = datetime.now(ZoneInfo(self.timezone))
        else:
            datetime_now = datetime.now().astimezone()
        self.setSelectedDate(QDate(datetime_now.year, datetime_now.month, datetime_now.day))


class ClockWidget(BaseWidget):
    validation_schema = ClockConfig

    def __init__(self, config: ClockConfig):
        super().__init__(config.update_interval, class_name=f"clock-widget {config.class_name}")
        self.config = config
        self._locale = self.config.locale
        self._tooltip = self.config.tooltip
        self._active_tz: str | None = None
        self._timezones_list = self._validate_timezones(self.config.timezones if self.config.timezones else [None])
        self._timezones: Iterator[str | None] = cycle(self._timezones_list)
        self._active_datetime_format_str = ""
        self._active_datetime_format: str | None = None
        self._label_content = self.config.label
        self._calendar = self.config.calendar
        self._label_alt_content = self.config.label_alt
        self._icons = self.config.icons or {}
        self._alarm_icons = self.config.alarm_icons
        self._current_hour: str | None = None
        self._current_minute: str | None = None
        self._previous_alarm_state = False
        self._timer_visible = False
        self._country_code = self.config.calendar.country_code or self.get_country_code()
        self._subdivision = self.config.calendar.subdivision
        self._init_container()
        self.build_widget_label(self._label_content, self._label_alt_content)

        self._timer_label = QLabel()
        self._timer_label.setProperty("class", "label timer")
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_label.hide()
        self._widget_container_layout.addWidget(self._timer_label)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self.update_label)
        self.register_callback("next_timezone", self._next_timezone)
        self.register_callback("toggle_calendar", self._toggle_calendar)
        self.register_callback("context_menu", self._show_context_menu)
        self.register_callback("timer_tick", self._on_timer_tick)
        self.register_callback("toggle_timer", self._show_timer_dialog)
        self.register_callback("toggle_alarm", self._show_alarm_dialog)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_timer = "timer_tick"

        self._show_alt_label = False

        self._shared_state = ClockWidgetSharedState()
        self._shared_state.register_widget(self)

        self._next_timezone()
        self.update_label()

        if self.config.calendar.show_holidays:
            QTimer.singleShot(0, _get_holidays_module)

    def _on_timer_tick(self):
        """Forward a timer tick event into the shared state handler."""
        self._shared_state.on_timer_tick()

    def _validate_timezones(self, timezones: list[str] | list[None]) -> list[str | None]:
        """Validate provided timezone strings and return the valid ones."""
        valid_timezones: list[str | None] = []
        available = available_timezones()
        for tz in timezones:
            if tz is None:
                # None means use system local timezone
                valid_timezones.append(None)
            elif tz in available:
                valid_timezones.append(tz)
            else:
                logging.warning(
                    "Invalid timezone '%s' ignored. Use format like 'America/New_York' or 'Europe/London'",
                    tz,
                )

        if not valid_timezones:
            logging.warning("No valid timezones found, using system local timezone")
            valid_timezones = [None]

        return valid_timezones

    def _toggle_calendar(self):
        self.show_calendar()

    def _toggle_label(self):
        """Toggle between primary and alternate label layouts."""
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self.update_label()

    def _get_icon_for_hour(self, hour: int) -> str:
        """Return the icon string for a given hour (with fallback for PM)."""
        key = f"clock_{hour:02d}"
        icon = self._icons.get(key)
        if icon is None and 13 <= hour <= 23:
            fallback_key = f"clock_{hour - 12:02d}"
            icon = self._icons.get(fallback_key, "")
        return icon or ""

    def _set_locale_context(self) -> tuple[LocaleSetting | None, LocaleSetting | None]:
        """Temporarily set LC_TIME (and LC_CTYPE when possible) to the widget's
        configured locale and return the previous settings so they can be
        restored later. Returns (org_locale_time, org_locale_ctype).
        """
        if not self._locale:
            return None, None

        org_locale_time = locale.getlocale(locale.LC_TIME)
        org_locale_ctype: LocaleSetting | None
        try:
            org_locale_ctype = locale.getlocale(locale.LC_CTYPE)
        except locale.Error:
            org_locale_ctype = None

        try:
            locale.setlocale(locale.LC_TIME, self._locale)
            try:
                locale.setlocale(locale.LC_CTYPE, self._locale)
            except locale.Error:
                pass
        except locale.Error:
            pass

        return org_locale_time, org_locale_ctype

    def _restore_locale_context(
        self, org_locale_time: LocaleSetting | None, org_locale_ctype: LocaleSetting | None
    ) -> None:
        """Restore previously saved locale values if they exist."""
        if org_locale_time is None:
            return

        locale.setlocale(locale.LC_TIME, org_locale_time)
        if org_locale_ctype:
            try:
                locale.setlocale(locale.LC_CTYPE, org_locale_ctype)
            except locale.Error:
                pass

    def update_label(self):
        # Choose which label set to update (primary or alternate)
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        now = datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
        current_hour = f"{now.hour:02d}"
        current_minute = f"{now.minute:02d}"
        hour_changed = self._current_hour != current_hour
        minute_changed = self._current_minute != current_minute
        if hour_changed:
            self._current_hour = current_hour
        if minute_changed:
            self._current_minute = current_minute

        # Temporarily switch locale so strftime outputs are localized
        org_locale_time, org_locale_ctype = self._set_locale_context()

        timer_active = self._shared_state.timer_active and self._shared_state.timer_seconds_remaining >= 0
        if timer_active:
            self._timer_label.setText(self._format_timer_display())

            alt_class = " alt" if self._show_alt_label else ""
            timer_class = f"label{alt_class} timer"
            if self._timer_label.property("class") != timer_class:
                self._timer_label.setProperty("class", timer_class)
                refresh_widget_style(self._timer_label)

            if not self._timer_visible:
                self._timer_label.show()
                self._timer_visible = True

        else:
            if self._timer_visible:
                self._timer_label.hide()
                self._timer_visible = False

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets):
                alt_class = " alt" if self._show_alt_label else ""
                current_class = active_widgets[widget_index].property("class")
                if "<span" in part and "</span>" in part:
                    icon_placeholder = re.sub(r"<span.*?>|</span>", "", part).strip()
                    if icon_placeholder == "{icon}":
                        icon = self._get_icon_for_hour(now.hour)
                        if active_widgets[widget_index].text() != icon:
                            active_widgets[widget_index].setText(icon)

                        new_class = f"icon{alt_class} clock_{current_hour}"
                        if current_class != new_class:
                            active_widgets[widget_index].setProperty("class", new_class)
                            refresh_widget_style(active_widgets[widget_index])
                    elif icon_placeholder == "{alarm}":
                        if self._shared_state.snoozed_alarms:
                            active_widgets[widget_index].setText(self.config.alarm_icons.snooze)
                            new_class = f"icon{alt_class} alarm snooze"
                            if current_class != new_class:
                                active_widgets[widget_index].setProperty("class", new_class)
                                refresh_widget_style(active_widgets[widget_index])
                            active_widgets[widget_index].setVisible(True)
                        elif self._has_enabled_alarms():
                            active_widgets[widget_index].setText(self.config.alarm_icons.enabled)
                            new_class = f"icon{alt_class} alarm"
                            if current_class != new_class:
                                active_widgets[widget_index].setProperty("class", new_class)
                                refresh_widget_style(active_widgets[widget_index])
                            active_widgets[widget_index].setVisible(True)
                        else:
                            active_widgets[widget_index].setText("")
                            active_widgets[widget_index].setVisible(False)

                    else:
                        active_widgets[widget_index].setText(icon_placeholder)
                else:
                    has_alarm = "{alarm}" in part and (self._shared_state.snoozed_alarms or self._has_enabled_alarms())

                    if "{icon}" in part:
                        icon = self._get_icon_for_hour(now.hour)
                        part = part.replace("{icon}", icon)

                    if "{alarm}" in part:
                        if self._shared_state.snoozed_alarms:
                            part = part.replace("{alarm}", self.config.alarm_icons.snooze)
                        elif self._has_enabled_alarms():
                            part = part.replace("{alarm}", self.config.alarm_icons.enabled)
                        else:
                            part = part.replace("{alarm}", "")
                    format_label_content = part
                    datetime_format_search = re.search(r"\{(.*)}", part)
                    if datetime_format_search:
                        try:
                            format_label_content = part.replace(
                                datetime_format_search.group(), now.strftime(datetime_format_search.group(1))
                            )
                        except Exception:
                            format_label_content = part

                    active_widgets[widget_index].setText(format_label_content)

                    if has_alarm:
                        if self._shared_state.snoozed_alarms:
                            new_class = f"label{alt_class} alarm snooze"
                        else:
                            new_class = f"label{alt_class} alarm"
                    else:
                        new_class = f"label{alt_class} clock_{current_hour}"

                    if current_class != new_class:
                        active_widgets[widget_index].setProperty("class", new_class)
                        refresh_widget_style(active_widgets[widget_index])

                    self._previous_alarm_state = has_alarm
                widget_index += 1

        self._restore_locale_context(org_locale_time, org_locale_ctype)

    def update_tooltip(self):
        if self._tooltip:
            try:
                now = datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
                org_locale_time, org_locale_ctype = self._set_locale_context()
                date_str = now.strftime("%A, %d %B %Y")
                day_abbr = now.strftime("%a")
                time_str = now.strftime("%H:%M")
                self._restore_locale_context(org_locale_time, org_locale_ctype)
                tz_display = self._active_tz.replace("_", " ") if self._active_tz else "Local time"
                tooltip_text = f"{date_str}\n\n{day_abbr} {time_str} ({tz_display})"

                if self._has_enabled_alarms():
                    alarm_info = self._get_alarms_tooltip()
                    tooltip_text += f"\n\n{alarm_info}"

                set_tooltip(self, tooltip_text)
            except Exception as e:
                logging.error("Error updating tooltip for timezone '%s': %s", self._active_tz, e)

    def _next_timezone(self):
        """Rotate to the next timezone in the configured list."""
        try:
            self._active_tz = next(self._timezones)
            if self._active_tz:
                ZoneInfo(self._active_tz)  # Validate timezone
            self.update_tooltip()
            self.update_label()
            if self._tooltip:
                show_tooltip_now(self)
        except Exception as e:
            logging.error("Error switching to timezone '%s': %s", self._active_tz, e)
            self._active_tz = None
            self.update_tooltip()
            self.update_label()

    def update_month_label(self, year: int, month: int) -> None:
        """Update the month label shown on the calendar popup."""
        qlocale = QLocale(self._locale) if self._locale else QLocale.system()
        new_month = qlocale.monthName(month)
        self.month_label.setText(new_month)
        if self.year_label:
            self.year_label.setText(str(year))

        selected_day = self.calendar.selectedDate().day()
        days_in_month = QDate(year, month, 1).daysInMonth()
        if selected_day > days_in_month:
            selected_day = days_in_month

        newDate = QDate(year, month, selected_day)
        self.day_label.setText(qlocale.dayName(newDate.dayOfWeek()))
        self.date_label.setText(newDate.toString("d"))

    def update_selected_date(self, date: QDate):
        """Refresh labels when a date in the calendar is selected."""
        qlocale = QLocale(self._locale) if self._locale else QLocale.system()
        self.day_label.setText(qlocale.dayName(date.dayOfWeek()))
        self.month_label.setText(qlocale.monthName(date.month()))
        if self.year_label:
            self.year_label.setText(str(date.year()))
        self.date_label.setText(date.toString("d"))
        if self.config.calendar.show_week_numbers:
            self.update_week_label(date)
        if self.config.calendar.show_holidays:
            self.update_holiday_label(date)

    def update_week_label(self, qdate: QDate):
        """Set the week number label for the given QDate."""
        week_number = qdate.weekNumber()[0]
        self.week_label.setText(f"Week {week_number}")

    def update_holiday_label(self, qdate: QDate):
        """Show holiday name for the selected date, if available for country."""
        country = _supported_country(self._country_code)
        if not country:
            self.holiday_label.setText("")
            return
        h = _get_cached_country_holidays(country, qdate.year(), self._subdivision)
        dt = date(qdate.year(), qdate.month(), qdate.day())
        holiday_name = h.get(dt)
        if holiday_name:
            self.holiday_label.setText(holiday_name)
        else:
            self.holiday_label.setText("")

    def get_country_code(self) -> str | None:
        """Try to detect the user's country code from Windows geo APIs."""
        if not self.config.calendar.show_holidays:
            return None
        import ctypes

        try:
            GetUserGeoID = ctypes.windll.kernel32.GetUserGeoID
            geo_id = GetUserGeoID(16)
            buf = ctypes.create_unicode_buffer(3)
            GetGeoInfoW = ctypes.windll.kernel32.GetGeoInfoW
            result = GetGeoInfoW(geo_id, 4, buf, len(buf), 0)
            country_code: str = buf.value if result else ""
            if country_code:
                return country_code
        except Exception:
            pass

        return None

    def show_calendar(self):
        """Build and show the calendar popup (includes optional extended UI)."""
        self._yasb_calendar = PopupWidget(
            self,
            self.config.calendar.blur,
            self.config.calendar.round_corners,
            self.config.calendar.round_corners_type,
            self.config.calendar.border_color,
        )
        self._yasb_calendar.setProperty("class", "clock-popup calendar")

        # Create main layout
        layout = QHBoxLayout()
        layout.setProperty("class", "calendar-layout")
        self._yasb_calendar.setLayout(layout)

        # Left side: Today Date
        date_layout = QVBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(0)
        date_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        datetime_now = datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
        qlocale = QLocale(self._locale) if self._locale else QLocale.system()

        self.day_label = QLabel(
            qlocale.dayName(QDate(datetime_now.year, datetime_now.month, datetime_now.day).dayOfWeek())
        )
        self.day_label.setProperty("class", "day-label")
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.day_label)

        self.month_label = QLabel(qlocale.monthName(datetime_now.month))
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setProperty("class", "month-label")
        date_layout.addWidget(self.month_label)

        self.year_label = None
        if self.config.calendar.show_years:
            self.year_label = QLabel(str(datetime_now.year))
            self.year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.year_label.setProperty("class", "year-label")
            date_layout.addWidget(self.year_label)

        self.date_label = QLabel(str(datetime_now.day))
        self.date_label.setProperty("class", "date-label")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.date_label)

        if self.config.calendar.show_week_numbers:
            week_number = QDate(datetime_now.year, datetime_now.month, datetime_now.day).weekNumber()[0]
            self.week_label = QLabel(f"Week {week_number}")
            self.week_label.setProperty("class", "week-label")
            self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_layout.addWidget(self.week_label)
            self.update_week_label(QDate(datetime_now.year, datetime_now.month, datetime_now.day))
        if self.config.calendar.show_holidays:
            self.holiday_label = QLabel("")
            self.holiday_label.setProperty("class", "holiday-label")
            self.holiday_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.holiday_label.setWordWrap(True)
            date_layout.addWidget(self.holiday_label)
            self.update_holiday_label(QDate(datetime_now.year, datetime_now.month, datetime_now.day))

        layout.addLayout(date_layout)

        self.calendar = CustomCalendar(
            self,
            self._active_tz,
            self._country_code,
            subdivision=self._subdivision,
            show_holidays=self.config.calendar.show_holidays,
            holiday_color=self.config.calendar.holiday_color,
            locale_name=self._locale,
        )
        self.calendar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.calendar.currentPageChanged.connect(self.update_month_label)
        self.calendar.clicked.connect(self.update_selected_date)

        layout.addWidget(self.calendar)

        if self.config.calendar.extended:
            actions_layout = QVBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            right_frame = QFrame()
            right_frame.setProperty("class", "extended-container")
            right_frame.setLayout(actions_layout)

            alarm_btn = QPushButton("Set Alarm")
            alarm_btn.setProperty("class", "button alarm small")

            timer_btn = QPushButton("Set Timer")
            timer_btn.setProperty("class", "button timer small")

            def on_alarm_clicked():
                try:
                    self._yasb_calendar.close()
                except Exception:
                    pass
                self._show_alarm_dialog()

            def on_timer_clicked():
                try:
                    self._yasb_calendar.close()
                except Exception:
                    pass
                self._show_timer_dialog()

            alarm_btn.clicked.connect(on_alarm_clicked)
            timer_btn.clicked.connect(on_timer_clicked)

            actions_layout.addWidget(alarm_btn)
            actions_layout.addWidget(timer_btn)

            holidays_label = QLabel("Upcoming holidays")
            holidays_label.setProperty("class", "upcoming-events-header")
            holidays_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            actions_layout.addWidget(holidays_label)

            upcoming_widgets: list[QLabel] = []
            for _ in range(4):
                lbl = QLabel("")
                lbl.setProperty("class", "upcoming-events-item")
                lbl.setWordWrap(False)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
                actions_layout.addWidget(lbl)
                upcoming_widgets.append(lbl)

            try:
                if self.config.calendar.show_holidays:
                    country = _supported_country(self._country_code)

                    if country:
                        today_dt = (
                            datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
                        ).date()
                        holidays: dict[date, str] = {}
                        for y in (today_dt.year, today_dt.year + 1):
                            holidays.update(_get_cached_country_holidays(country, y, self._subdivision))

                        upcoming = sorted(((d, n) for d, n in holidays.items() if d >= today_dt), key=lambda x: x[0])
                        qlocale = QLocale(self._locale) if self._locale else QLocale.system()
                        for idx, (d, name) in enumerate(upcoming[:4]):
                            qdate = QDate(d.year, d.month, d.day)
                            day_month = f"{qdate.day():02d}.{qdate.month():02d}"
                            max_len = 20
                            display_name = name if len(name) <= max_len else name[: max_len - 3].rstrip() + "..."
                            upcoming_widgets[idx].setText(f"{day_month}: {display_name}")
                            set_tooltip(upcoming_widgets[idx], name, position="top")

            except Exception:
                pass

            layout.addWidget(right_frame)

        self._yasb_calendar.adjustSize()

        self._yasb_calendar.setPosition(
            alignment=self.config.calendar.alignment,
            direction=self.config.calendar.direction,
            offset_left=self.config.calendar.offset_left,
            offset_top=self.config.calendar.offset_top,
        )

        self._yasb_calendar.show()

    def _show_context_menu(self):
        """Build and display the context menu for the clock widget."""
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")
        if len(self._timezones_list) > 1:
            tz_menu = QMenu("Timezones", menu)
            apply_qmenu_style(tz_menu)
            tz_menu.setProperty("class", "context-menu submenu")

            for tz in self._timezones_list:
                tz_display = tz.replace("_", " ") if tz else "Local time"
                tz_action = QAction(tz_display, tz_menu)
                tz_menu.addAction(tz_action)
                tz_action.triggered.connect(partial(self._set_timezone, tz))

            menu.addMenu(tz_menu)
            menu.addSeparator()

        if self._shared_state.timer_active:
            cancel_timer_action = QAction("Cancel Timer", menu)
            menu.addAction(cancel_timer_action)
            cancel_timer_action.triggered.connect(lambda: self._cancel_timer())
        else:
            set_timer_action = QAction("Set Timer", menu)
            menu.addAction(set_timer_action)
            set_timer_action.triggered.connect(lambda: self._show_timer_dialog())

        menu.addSeparator()

        set_alarm_action = QAction("Set Alarm", menu)
        menu.addAction(set_alarm_action)
        set_alarm_action.triggered.connect(lambda: self._show_alarm_dialog())

        if self._shared_state.alarms:
            menu.addSeparator()
            alarms_label = QAction("Alarms", menu)
            menu.addAction(alarms_label)
            alarms_label.setEnabled(False)

            for alarm in self._shared_state.alarms:
                alarm_text = self._format_alarm_text(alarm)
                alarm_action = QAction(alarm_text, menu)
                menu.addAction(alarm_action)
                alarm_action.triggered.connect(partial(self._show_alarm_dialog, alarm))

        margin = 6
        menu_size = menu.sizeHint()

        bar_widget = self.window()
        bar_top_left = bar_widget.mapToGlobal(bar_widget.rect().topLeft()) if bar_widget else QPoint(0, 0)
        bar_height = bar_widget.height() if bar_widget else 0

        button_center = self.mapToGlobal(self.rect().center())
        new_x = button_center.x() - menu_size.width() / 2

        bar_alignment: object = getattr(bar_widget, "alignment", None) if bar_widget else None
        bar_position = (
            cast(dict[str, object], bar_alignment).get("position") if isinstance(bar_alignment, dict) else None
        )
        if bar_position == "top":
            new_y = bar_top_left.y() + bar_height + margin
        else:
            new_y = bar_top_left.y() - menu_size.height() - margin
        pos = QPoint(int(new_x), int(new_y))

        menu.popup(pos)
        menu.activateWindow()

    def _set_timezone(self, timezone: str | None, checked: bool = False) -> None:
        """Make the supplied timezone the active one (and rotate the list)."""
        self._timezones = cycle([timezone] + [tz for tz in self._timezones_list if tz != timezone])
        self._next_timezone()

    def _format_alarm_text(self, alarm: Alarm) -> str:
        """Return a short textual representation of an alarm for menus."""
        time_str = alarm["time"]
        days = alarm.get("days", [])

        if not days or len(days) == 7:
            days_str = "Every day"
        elif len(days) == 1:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            days_str = day_names[days[0]]
        else:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            days_str = ", ".join([day_names[d] for d in sorted(days)])

        enabled_str = (
            f"{self.config.alarm_icons.enabled} "
            if alarm.get("enabled", True)
            else f"{self.config.alarm_icons.disabled} "
        )
        return f"{enabled_str} {time_str} ({days_str})"

    def _has_enabled_alarms(self) -> bool:
        """Return True if there are any enabled or snoozed alarms."""
        return (
            any(alarm.get("enabled", True) for alarm in self._shared_state.alarms)
            or len(self._shared_state.snoozed_alarms) > 0
        )

    def _get_alarms_tooltip(self) -> str:
        """Build the multi-line tooltip text describing active and snoozed alarms."""
        enabled_alarms = [alarm for alarm in self._shared_state.alarms if alarm.get("enabled", True)]

        if self._shared_state.snoozed_alarms and not enabled_alarms:
            if len(self._shared_state.snoozed_alarms) == 1:
                snooze_time = self._shared_state.snoozed_alarms[0]["snooze_until"].strftime("%H:%M:%S")
                return f"Snoozed alarm returns at {snooze_time}"
            else:
                return f"{len(self._shared_state.snoozed_alarms)} snoozed alarms"

        if not enabled_alarms:
            return "No active alarms"

        tooltip_lines = ["Active Alarms"]
        for alarm in enabled_alarms:
            time_str = alarm["time"]
            days = alarm.get("days", [])

            if not days or len(days) == 7:
                days_str = "Every day"
            elif len(days) == 1:
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                days_str = day_names[days[0]]
            else:
                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                days_str = ", ".join([day_names[d] for d in sorted(days)])

            tooltip_lines.append(f"{time_str} - {days_str}")

        if self._shared_state.snoozed_alarms:
            for snoozed in self._shared_state.snoozed_alarms:
                snooze_time = snoozed["snooze_until"].strftime("%H:%M:%S")
                tooltip_lines.append(f"Snoozed alarm returns at {snooze_time}")

        return "\n".join(tooltip_lines)

    def _create_dialog_popup(self, class_name: str) -> PopupWidget:
        """Create a configured PopupWidget used for dialogs (timer/alarm)."""
        popup = PopupWidget(
            self,
            self.config.calendar.blur,
            self.config.calendar.round_corners,
            self.config.calendar.round_corners_type,
            self.config.calendar.border_color,
        )
        popup.setProperty("class", f"clock-popup {class_name}")
        return popup

    def _create_time_grid(
        self,
        label1_text: str,
        label2_text: str,
        spin1_range: tuple[int, int],
        spin2_range: tuple[int, int],
        spin1_value: int | None = None,
        spin2_value: int | None = None,
    ) -> tuple[QHBoxLayout, FormattedSpinBox, FormattedSpinBox]:
        """Create a small hour/minute (or minute/second) grid and return spins."""
        time_grid = QGridLayout()
        time_grid.setContentsMargins(0, 0, 0, 0)
        time_grid.setHorizontalSpacing(0)
        time_grid.setVerticalSpacing(0)

        label1 = QLabel(label1_text)
        label1.setAlignment(Qt.AlignmentFlag.AlignRight)
        label1.setProperty("class", "clock-label-timer")
        time_grid.addWidget(label1, 0, 0)

        label2 = QLabel(label2_text)
        label2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label2.setProperty("class", "clock-label-timer")
        time_grid.addWidget(label2, 0, 2)

        spin1 = FormattedSpinBox()
        spin1.setRange(*spin1_range)
        spin1.setAlignment(Qt.AlignmentFlag.AlignRight)
        spin1.setProperty("class", "clock-input-time")
        spin1.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin1.setWrapping(True)
        if spin1_value is not None:
            spin1.setValue(spin1_value)
        time_grid.addWidget(spin1, 1, 0)

        colon_label = QLabel(":")
        colon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        colon_label.setProperty("class", "clock-input-time colon")
        time_grid.addWidget(colon_label, 1, 1)

        spin2 = FormattedSpinBox()
        spin2.setRange(*spin2_range)
        spin2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        spin2.setProperty("class", "clock-input-time")
        spin2.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin2.setWrapping(True)
        if spin2_value is not None:
            spin2.setValue(spin2_value)
        time_grid.addWidget(spin2, 1, 2)

        grid_wrapper = QHBoxLayout()
        grid_wrapper.addStretch()
        grid_wrapper.addLayout(time_grid)
        grid_wrapper.addStretch()

        return grid_wrapper, spin1, spin2

    def _create_footer_container(self, buttons: list[QPushButton]) -> QFrame:
        """Create a footer container for dialog buttons (Save/Cancel/Delete)."""
        footer_frame = QFrame()
        footer_frame.setProperty("class", "clock-popup-footer")
        button_layout = QHBoxLayout(footer_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)

        for btn in buttons:
            button_layout.addWidget(btn)
            if btn.text() == "Delete":
                button_layout.addStretch(1)

        return footer_frame

    def _show_alarm_dialog(self, alarm: Alarm | None = None, checked: bool = False) -> None:
        """Show the alarm editor dialog; if alarm is given, edit it."""
        is_edit_mode = alarm is not None

        popup = self._create_dialog_popup(class_name="alarm")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        popup.setLayout(layout)

        container_frame = QFrame()
        container_frame.setProperty("class", "clock-popup-container")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)

        if alarm is not None:
            hour, minute = map(int, alarm["time"].split(":"))
        else:
            now = datetime.now()
            hour, minute = now.hour, now.minute

        grid_wrapper, hour_spin, minute_spin = self._create_time_grid("Hour", "Minute", (0, 23), (0, 59), hour, minute)
        container_layout.addLayout(grid_wrapper)

        days_layout = QHBoxLayout()
        day_buttons: list[QPushButton] = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(day_names):
            btn = QPushButton(day)
            btn.setCheckable(True)
            btn.setProperty("class", "button day")
            if alarm is not None:
                btn.setChecked(i in alarm.get("days", []))
            day_buttons.append(btn)
            days_layout.addWidget(btn)
        container_layout.addLayout(days_layout)

        if not is_edit_mode:
            try:
                today_idx = datetime.now().weekday()
                for i, btn in enumerate(day_buttons):
                    btn.setChecked(i == today_idx)
            except Exception:
                pass

        quick_layout = QHBoxLayout()
        quick_options = [
            ("Today", "today"),
            ("Every day", "everyday"),
            ("Weekdays", "weekdays"),
        ]

        def apply_quick(option_key: str, checked: bool = False) -> None:
            for btn in day_buttons:
                btn.blockSignals(True)
            try:
                if option_key == "today":
                    for btn in day_buttons:
                        btn.setChecked(False)
                    day_buttons[datetime.now().weekday()].setChecked(True)
                elif option_key == "everyday":
                    for btn in day_buttons:
                        btn.setChecked(True)
                elif option_key == "weekdays":
                    for i, btn in enumerate(day_buttons):
                        btn.setChecked(i < 5)
            finally:
                for btn in day_buttons:
                    btn.blockSignals(False)
                update_save_enabled()

        enabled_button: QPushButton | None = None
        if alarm is not None:
            enabled_button = QPushButton()
            enabled_button.setCheckable(True)
            is_enabled = alarm.get("enabled", True)
            enabled_button.setChecked(is_enabled)
            enabled_button.setText("Enabled" if is_enabled else "Disabled")
            enabled_button.setProperty("class", f"button {'is-alarm-enabled' if is_enabled else 'is-alarm-disabled'}")

            def on_enabled_toggled(checked: bool, button: QPushButton = enabled_button) -> None:
                button.setText("Enabled" if checked else "Disabled")
                button.setProperty("class", f"button {'is-alarm-enabled' if checked else 'is-alarm-disabled'}")
                refresh_widget_style(button)

            enabled_button.toggled.connect(on_enabled_toggled)
            quick_layout.addWidget(enabled_button)

        quick_group = QButtonGroup(popup)
        quick_group.setExclusive(True)

        for label, key in quick_options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("class", "button quick-option")
            quick_group.addButton(btn)
            btn.clicked.connect(partial(apply_quick, key))
            quick_layout.addWidget(btn)

        def clear_quick_days(checked: bool = False) -> None:
            self._clear_quick_group(quick_group)

        for btn in day_buttons:
            btn.clicked.connect(clear_quick_days)

        container_layout.addLayout(quick_layout)

        title_layout = QHBoxLayout()

        title_edit = QLineEdit()
        title_edit.setProperty("class", "alarm-input-title")
        title_edit.setPlaceholderText("Alarm title")
        title_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        if alarm is not None:
            title_edit.setText(alarm.get("title", ""))
        title_edit.setFocus()

        title_layout.addWidget(title_edit)
        container_layout.addLayout(title_layout)

        buttons: list[QPushButton] = []

        if alarm is not None:
            delete_btn = QPushButton("Delete")
            delete_btn.setProperty("class", "button delete")

            def delete_alarm(checked: bool = False, alarm: Alarm = alarm) -> None:
                if alarm in self._shared_state.alarms:
                    self._shared_state.alarms.remove(alarm)
                    self._shared_state.snoozed_alarms = [
                        s for s in self._shared_state.snoozed_alarms if s["alarm"] != alarm
                    ]
                    self._save_alarms()
                    self._refresh_alarm_ui()
                popup.close()

            delete_btn.clicked.connect(delete_alarm)
            buttons.append(delete_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "button save")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")

        buttons.extend([save_btn, cancel_btn])

        def save_alarm_func():
            selected_days = [i for i, btn in enumerate(day_buttons) if btn.isChecked()]
            if not selected_days:
                selected_days = [datetime.now().weekday()]
            time_value = f"{hour_spin.value():02d}:{minute_spin.value():02d}"

            new_alarm_data: Alarm = {
                "time": time_value,
                "days": selected_days,
                "enabled": enabled_button.isChecked() if enabled_button is not None else True,
                "title": title_edit.text().strip(),
            }

            if alarm is not None:
                if not new_alarm_data.get("enabled", True):
                    self._shared_state.snoozed_alarms = [
                        s for s in self._shared_state.snoozed_alarms if s["alarm"] != alarm
                    ]
                alarm.update(new_alarm_data)
            else:
                self._shared_state.alarms.append(new_alarm_data)

            self._save_alarms()
            self._refresh_alarm_ui()

            popup.close()

        def _has_selected_day() -> bool:
            return any(btn.isChecked() for btn in day_buttons)

        def update_save_enabled():
            save_btn.setEnabled(bool(title_edit.text().strip()) and _has_selected_day())

        update_save_enabled()

        def on_title_changed(text: str) -> None:
            update_save_enabled()

        def on_day_clicked(checked: bool = False) -> None:
            update_save_enabled()

        title_edit.textChanged.connect(on_title_changed)
        for btn in day_buttons:
            btn.clicked.connect(on_day_clicked)
        save_btn.clicked.connect(save_alarm_func)
        cancel_btn.clicked.connect(lambda: popup.close())

        footer_frame = self._create_footer_container(buttons)

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        popup.adjustSize()
        popup.setPosition(
            alignment=self.config.calendar.alignment,
            direction=self.config.calendar.direction,
            offset_left=self.config.calendar.offset_left,
            offset_top=self.config.calendar.offset_top,
        )

        popup.show()

    def _save_alarms(self):
        """Persist alarms and refresh UI across widgets."""
        self._shared_state.save_alarms()
        self._shared_state.notify_all_widgets(update_tooltip=True)

    def trigger_alarm(self, alarm: Alarm) -> None:
        """Start alarm behavior (play sound and show active alarm popup)."""
        self.play_sound(loop_duration_ms=16000)

        try:
            self._show_active_alarm_popup(alarm)
        except Exception:
            logging.exception("Failed to show active alarm popup")

    def play_sound(self, loop_duration_ms: int = 0) -> None:
        """Play the configured notification sound; loop if loop_duration_ms>0."""
        if not os.path.exists(NOTIFICATION_SOUND):
            logging.warning("Notification sound file not found: %s", NOTIFICATION_SOUND)
            return

        try:
            if loop_duration_ms > 0:
                winsound.PlaySound(NOTIFICATION_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                QTimer.singleShot(loop_duration_ms, self._stop_alarm_sound)
            else:
                winsound.PlaySound(NOTIFICATION_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logging.error("Failed to play notification sound: %s", e)

    def _stop_alarm_sound(self):
        """Stop any playing notification sound (winsound)."""
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _refresh_alarm_ui(self):
        """Request all widgets to refresh alarm-related UI and tooltip."""
        self._shared_state.notify_all_widgets(update_tooltip=True)

    def _show_active_alarm_popup(self, alarm: Alarm) -> None:
        """Display a centered popup for an active alarm with controls."""
        win = QFrame(self)
        win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        try:
            hwnd = int(win.winId())
            enable_blur(hwnd, DarkMode=True, RoundCorners=True, RoundCornersType="normal", BorderColor="None")
        except Exception:
            pass
        win.setProperty("class", "active-alarm-window")
        win.activateWindow()

        layout = QVBoxLayout(win)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_text_icon = self.config.alarm_icons.disabled
        title_icon = QLabel(title_text_icon)
        title_icon.setProperty("class", "alarm-title-icon")
        title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_text = alarm.get("title") or "Alarm"
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setProperty("class", "alarm-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(title_icon)
        layout.addWidget(title)

        try:
            now = datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
            display_time = now.strftime("%H:%M")
        except Exception:
            display_time = datetime.now().strftime("%H:%M")

        info = QLabel(display_time)
        info.setProperty("class", "alarm-info")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        buttons_config = [
            ("Stop", None),
            ("Snooze 1 min", 1),
            ("Snooze 3 min", 3),
            ("Snooze 5 min", 5),
        ]

        alarm_buttons: list[tuple[QPushButton, int | None]] = []
        for label, snooze_minutes in buttons_config:
            btn = QPushButton(label)
            btn.setProperty("class", "button")
            btn_layout.addWidget(btn)
            alarm_buttons.append((btn, snooze_minutes))

        layout.addLayout(btn_layout)

        def _stop_action():
            self._stop_alarm_sound()
            self._shared_state.snoozed_alarms = [s for s in self._shared_state.snoozed_alarms if s["alarm"] != alarm]
            self._refresh_alarm_ui()
            win.close()
            win.deleteLater()

        def _snooze_action(minutes: int, checked: bool = False) -> None:
            self._stop_alarm_sound()

            snooze_until = datetime.now() + timedelta(minutes=minutes)
            self._shared_state.snoozed_alarms.append({"alarm": alarm, "snooze_until": snooze_until})

            self._shared_state.notify_all_widgets(update_tooltip=True)
            win.close()
            win.deleteLater()

        for btn, snooze_minutes in alarm_buttons:
            if snooze_minutes is None:
                btn.clicked.connect(_stop_action)
            else:
                btn.clicked.connect(partial(_snooze_action, snooze_minutes))
        win.adjustSize()

        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center())) or QApplication.primaryScreen()
        if screen is None:
            win.show()
            return
        geom = screen.availableGeometry()

        x = geom.x() + (geom.width() - win.width()) // 2
        y = geom.y() + (geom.height() - win.height()) // 2
        win.move(x, y)
        win.show()

    def _show_timer_dialog(self):
        """Show the timer dialog allowing the user to set and start a timer."""
        popup = self._create_dialog_popup(class_name="timer")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        popup.setLayout(layout)

        # Container for dialog content
        container_frame = QFrame()
        container_frame.setProperty("class", "clock-popup-container")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Create time grid with default values
        grid_wrapper, minutes_spin, seconds_spin = self._create_time_grid("Minutes", "Seconds", (0, 99), (0, 59), 5, 0)
        container_layout.addLayout(grid_wrapper)

        quick_layout = QHBoxLayout()
        quick_options = [("1 min", 1), ("5 min", 5), ("10 min", 10), ("30 min", 30), ("60 min", 60)]

        def set_quick(minutes_total: int, checked: bool = False) -> None:
            minutes_spin.blockSignals(True)
            seconds_spin.blockSignals(True)
            try:
                minutes_spin.setValue(minutes_total)
                seconds_spin.setValue(0)
            finally:
                minutes_spin.blockSignals(False)
                seconds_spin.blockSignals(False)

        quick_group = QButtonGroup(popup)
        quick_group.setExclusive(True)

        for label, mins in quick_options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("class", "button quick-option")
            quick_group.addButton(btn)
            btn.clicked.connect(partial(set_quick, mins))
            quick_layout.addWidget(btn)

        def clear_quick_minutes(value: int) -> None:
            self._clear_quick_group(quick_group)

        minutes_spin.valueChanged.connect(clear_quick_minutes)
        seconds_spin.valueChanged.connect(clear_quick_minutes)

        container_layout.addLayout(quick_layout)

        # Create action buttons
        start_btn = QPushButton("Start")
        start_btn.setProperty("class", "button start")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")

        def start_timer():
            total_seconds = minutes_spin.value() * 60 + seconds_spin.value()
            if total_seconds > 0:
                self._shared_state.timer_seconds_remaining = total_seconds
                self._shared_state.timer_active = True
                self._shared_state.notify_all_widgets()
                popup.close()

        start_btn.clicked.connect(start_timer)
        cancel_btn.clicked.connect(lambda: popup.close())

        # Create button container
        footer_frame = self._create_footer_container([start_btn, cancel_btn])

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        popup.adjustSize()
        popup.setPosition(
            alignment=self.config.calendar.alignment,
            direction=self.config.calendar.direction,
            offset_left=self.config.calendar.offset_left,
            offset_top=self.config.calendar.offset_top,
        )

        popup.show()

    def _format_timer_display(self):
        """Format the shared timer remaining seconds into a display string."""
        hours = self._shared_state.timer_seconds_remaining // 3600
        minutes = (self._shared_state.timer_seconds_remaining % 3600) // 60
        seconds = self._shared_state.timer_seconds_remaining % 60

        if hours > 0:
            return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
        else:
            return f"[{minutes:02d}:{seconds:02d}]"

    def _cancel_timer(self):
        """Cancel the shared timer and notify widgets to update display."""
        self._shared_state.timer_active = False
        self._shared_state.timer_seconds_remaining = 0
        self._shared_state.notify_all_widgets()

    def _timer_finished(self):
        """Handle shared timer finishing: stop and play a notification."""
        self._shared_state.timer_active = False
        self._shared_state.timer_seconds_remaining = 0
        self._shared_state.notify_all_widgets()
        self.play_sound()

    def _clear_quick_group(self, qgroup: QButtonGroup | None) -> None:
        """Clear (uncheck) all buttons in a quick-selection QButtonGroup."""
        if not qgroup:
            return

        was_exclusive = qgroup.exclusive()
        qgroup.setExclusive(False)

        for btn in qgroup.buttons():
            btn.setChecked(False)

        qgroup.setExclusive(was_exclusive)

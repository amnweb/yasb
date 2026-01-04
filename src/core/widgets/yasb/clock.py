import json
import locale
import logging
import os
import re
import winsound
from datetime import date, datetime, timedelta
from itertools import cycle
from zoneinfo import ZoneInfo, available_timezones

from PyQt6.QtCore import QDate, QEasingCurve, QLocale, QPoint, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor
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
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import apply_qmenu_style
from core.utils.win32.win32_accent import Blur
from core.validation.widgets.yasb.clock import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH

_holidays_cache = {"module": None, "supported_countries": None, "country_holidays": {}}
NOTIFICATION_SOUND = os.path.join(SCRIPT_PATH, "assets", "sound", "notification02.wav")


class ClockWidgetSharedState:
    """Shared state shared between all clock widget instances."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the shared state (only runs once for the singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self._widget_instances = []
        self._alarms = []
        self._snoozed_alarms = []
        self._triggered_alarms = set()
        self._last_check_minute = None
        self._startup_minute = datetime.now().strftime("%H:%M")
        self._timer_seconds_remaining = 0
        self._timer_active = False
        self._alarms_file = os.path.join(HOME_CONFIGURATION_DIR, "alarms.json")
        self._load_alarms()

    def register_widget(self, widget):
        """Register a widget instance and start timer if this is first."""
        if widget not in self._widget_instances:
            self._widget_instances.append(widget)

            if len(self._widget_instances) == 1:
                widget.start_timer()

            def update_widget():
                try:
                    widget._update_label()
                    widget._update_tooltip()
                except Exception:
                    pass

            QTimer.singleShot(0, update_widget)

    def unregister_widget(self, widget):
        """Remove a widget instance from the shared list."""
        if widget in self._widget_instances:
            self._widget_instances.remove(widget)

    def on_timer_tick(self):
        """Called on each timer tick: update timer, handle snoozes and alarms."""
        if self._timer_active:
            if self._timer_seconds_remaining == 0:
                self._timer_finished()
            elif self._timer_seconds_remaining > 0:
                self._timer_seconds_remaining -= 1

        for snoozed in self._snoozed_alarms[:]:
            snooze_until = snoozed.get("snooze_until")
            if snooze_until and datetime.now() >= snooze_until:
                alarm = snoozed["alarm"]
                self._snoozed_alarms.remove(snoozed)
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

        for idx, alarm in enumerate(self._alarms):
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

    def _trigger_alarm(self, alarm):
        """Trigger an alarm on the first registered widget (UI action)."""
        if self._widget_instances:
            try:
                self._widget_instances[0]._trigger_alarm(alarm)
            except Exception:
                pass

    def _timer_finished(self):
        """Handle the shared timer finishing: stop active timer and play sound."""
        self._timer_active = False
        self._timer_seconds_remaining = 0
        if self._widget_instances:
            try:
                self._widget_instances[0]._play_sound()
            except Exception:
                pass

    def notify_all_widgets(self, update_tooltip=False):
        """Notify all registered widgets to refresh label and optional tooltip."""
        for widget in self._widget_instances[:]:
            try:
                widget._update_label()
                if update_tooltip:
                    widget._update_tooltip()
            except Exception:
                pass

    def _load_alarms(self):
        """Load alarms from disk into shared state, if the file exists."""
        try:
            if os.path.exists(self._alarms_file):
                with open(self._alarms_file, "r", encoding="utf-8") as f:
                    self._alarms = json.load(f)
        except Exception as e:
            logging.error(f"Error loading alarms: {e}")
            self._alarms = []

    def save_alarms(self):
        """Persist alarms to disk in a tidy JSON format."""
        try:
            json_str = json.dumps(self._alarms, indent=2, ensure_ascii=False)
            json_str = re.sub(
                r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]",
                lambda m: "[" + m.group(1).replace("\n", "").replace(" ", "") + "]",
                json_str,
            )
            with open(self._alarms_file, "w", encoding="utf-8") as f:
                f.write(json_str)
        except Exception as e:
            logging.error(f"Error saving alarms: {e}")


class FormattedSpinBox(QSpinBox):
    def textFromValue(self, value):
        """Format numeric value with two digits (e.g. 3 -> '03')."""
        return f"{value:02d}"

    def __init__(self, *args, **kwargs):
        """Create the formatted spin box and make the line edit read-only."""
        super().__init__(*args, **kwargs)
        self.lineEdit().setReadOnly(True)

    def showEvent(self, event):
        """Adjust selection colors after the widget is shown so colors match."""
        super().showEvent(event)
        current_color = self.palette().color(self.foregroundRole())
        self.lineEdit().setStyleSheet(f"""
            QLineEdit {{
                selection-background-color: transparent;
                selection-color: {current_color.name()};
            }}
        """)


def _get_holidays_module():
    """Lazily import the `holidays` module and cache supported countries."""
    import importlib

    if _holidays_cache["module"] is None:
        _holidays_cache["module"] = importlib.import_module("holidays")
        _holidays_cache["supported_countries"] = set(_holidays_cache["module"].list_supported_countries())
    return _holidays_cache["module"]


def _get_cached_country_holidays(country, year, subdivision=None):
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
        parent=None,
        timezone=None,
        country_code=None,
        subdivision=None,
        show_holidays=True,
        holiday_color=None,
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoFillBackground(False)
        self._holidays = set()
        self._current_year = None
        format = self.weekdayTextFormat(Qt.DayOfWeek.Monday)
        for day in range(Qt.DayOfWeek.Monday.value, Qt.DayOfWeek.Sunday.value + 1):
            self.setWeekdayTextFormat(Qt.DayOfWeek(day), format)

        table_view = self.findChild(QTableView)
        if table_view:
            table_view.setProperty("class", "calendar-table")

        if parent and parent._locale:
            qt_locale = QLocale(parent._locale)
            self.setLocale(qt_locale)

        self.update_calendar_display()
        self._update_holidays_for_year(self.selectedDate().year())
        self.currentPageChanged.connect(self._on_page_changed)

    def _update_holidays_for_year(self, year):
        """Update the holiday cache for the given year (if supported)."""
        self._holidays = set()
        self._current_year = year
        if _holidays_cache["supported_countries"] is None:
            return
        country = None
        if (
            self.country_code
            and re.fullmatch(r"[A-Z]{2}", self.country_code.upper())
            and self.country_code.upper() in _holidays_cache["supported_countries"]
        ):
            country = self.country_code.upper()
        if not country:
            return
        h = _get_cached_country_holidays(country, year, self.subdivision)
        self._holidays = set(h.keys())

    def _on_page_changed(self, year, month):
        """When calendar page changes, refresh holidays if year changed."""
        if year != self._current_year:
            self._update_holidays_for_year(year)

    def paintCell(self, painter, rect, date):
        """Custom paint for cells; draw holiday dates in holiday_color."""
        if date < self.minimumDate() or date > self.maximumDate():
            return
        pydate = date.toPyDate()
        is_holiday = self.show_holidays and pydate in self._holidays
        if is_holiday:
            is_selected = date == self.selectedDate()
            if is_selected:
                painter.save()
                super().paintCell(painter, rect, date)
                painter.restore()
            else:
                painter.save()
                painter.setPen(QColor(self.holiday_color))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
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
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        locale: str,
        tooltip: bool,
        update_interval: int,
        calendar: dict[str, str],
        timezones: list[str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        icons: dict[str, str] = None,
        alarm_icons: dict[str, str] = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(update_interval, class_name=f"clock-widget {class_name}")
        self._locale = locale
        self._tooltip = tooltip
        self._active_tz = None
        self._timezones_list = self._validate_timezones(timezones if timezones else [None])
        self._timezones = cycle(self._timezones_list)
        self._active_datetime_format_str = ""
        self._active_datetime_format = None
        self._animation = animation
        self._label_content = label
        self._calendar = calendar
        self._padding = container_padding
        self._label_alt_content = label_alt
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._icons = icons or {}
        self._alarm_icons = alarm_icons
        self._current_hour = None
        self._current_minute = None
        self._previous_alarm_state = False
        self._timer_visible = False
        self._country_code = self._calendar["country_code"] or self.get_country_code()
        self._subdivision = self._calendar.get("subdivision")
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self._timer_label = QLabel()
        self._timer_label.setProperty("class", "label timer")
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer_label.hide()
        add_shadow(self._timer_label, self._label_shadow)
        self._widget_container_layout.addWidget(self._timer_label)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("next_timezone", self._next_timezone)
        self.register_callback("toggle_calendar", self._toggle_calendar)
        self.register_callback("context_menu", self._show_context_menu)
        self.register_callback("timer_tick", self._on_timer_tick)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "timer_tick"

        self._show_alt_label = False

        self._shared_state = ClockWidgetSharedState()
        self._shared_state.register_widget(self)

        self._next_timezone()
        self._update_label()

        if self._calendar["show_holidays"]:
            QTimer.singleShot(0, _get_holidays_module)

    def _on_timer_tick(self):
        """Forward a timer tick event into the shared state handler."""
        self._shared_state.on_timer_tick()

    def _validate_timezones(self, timezones):
        """Validate provided timezone strings and return the valid ones."""
        valid_timezones = []
        available = available_timezones()
        for tz in timezones:
            if tz is None:
                # None means use system local timezone
                valid_timezones.append(None)
            elif tz in available:
                valid_timezones.append(tz)
            else:
                logging.warning(
                    f"Invalid timezone '{tz}' ignored. Use format like 'America/New_York' or 'Europe/London'"
                )

        if not valid_timezones:
            logging.warning("No valid timezones found, using system local timezone")
            valid_timezones = [None]

        return valid_timezones

    def _toggle_calendar(self):
        """Show the calendar popup, optionally using an animation."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_calendar()

    def _toggle_label(self):
        """Toggle between primary and alternate label layouts."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _get_icon_for_hour(self, hour: int) -> str:
        """Return the icon string for a given hour (with fallback for PM)."""
        key = f"clock_{hour:02d}"
        icon = self._icons.get(key)
        if icon is None and 13 <= hour <= 23:
            fallback_key = f"clock_{hour - 12:02d}"
            icon = self._icons.get(fallback_key, "")
        return icon or ""

    def _set_locale_context(self):
        """Temporarily set LC_TIME (and LC_CTYPE when possible) to the widget's
        configured locale and return the previous settings so they can be
        restored later. Returns (org_locale_time, org_locale_ctype).
        """
        if not self._locale:
            return None, None

        org_locale_time = locale.getlocale(locale.LC_TIME)
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

    def _restore_locale_context(self, org_locale_time, org_locale_ctype):
        """Restore previously saved locale values if they exist."""
        if org_locale_time is None:
            return

        locale.setlocale(locale.LC_TIME, org_locale_time)
        if org_locale_ctype:
            try:
                locale.setlocale(locale.LC_CTYPE, org_locale_ctype)
            except locale.Error:
                pass

    def _update_label(self):
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

        timer_active = self._shared_state._timer_active and self._shared_state._timer_seconds_remaining >= 0
        if timer_active:
            self._timer_label.setText(self._format_timer_display())
            if not self._timer_visible:
                self._timer_label.show()
                self._timer_visible = True

        else:
            if self._timer_visible:
                self._timer_label.hide()
                self._timer_visible = False

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon_placeholder = re.sub(r"<span.*?>|</span>", "", part).strip()
                    if icon_placeholder == "{icon}":
                        if hour_changed:
                            icon = self._get_icon_for_hour(now.hour)
                            active_widgets[widget_index].setText(icon)
                            hour_class = f"clock_{current_hour}"
                            active_widgets[widget_index].setProperty("class", f"icon {hour_class}")
                            refresh_widget_style(active_widgets[widget_index])
                    elif icon_placeholder == "{alarm}":
                        if self._shared_state._snoozed_alarms:
                            active_widgets[widget_index].setText(self._alarm_icons["snooze"])
                            active_widgets[widget_index].setProperty("class", "icon alarm snooze")
                            active_widgets[widget_index].setVisible(True)
                            refresh_widget_style(active_widgets[widget_index])
                        elif self._has_enabled_alarms():
                            active_widgets[widget_index].setText(self._alarm_icons["enabled"])
                            active_widgets[widget_index].setProperty("class", "icon alarm")
                            active_widgets[widget_index].setVisible(True)
                            refresh_widget_style(active_widgets[widget_index])
                        else:
                            active_widgets[widget_index].setText("")
                            active_widgets[widget_index].setVisible(False)

                    else:
                        active_widgets[widget_index].setText(icon_placeholder)
                else:
                    has_alarm = "{alarm}" in part and (self._shared_state._snoozed_alarms or self._has_enabled_alarms())

                    if "{icon}" in part:
                        icon = self._get_icon_for_hour(now.hour)
                        part = part.replace("{icon}", icon)

                    if "{alarm}" in part:
                        if self._shared_state._snoozed_alarms:
                            part = part.replace("{alarm}", self._alarm_icons["snooze"])
                        elif self._has_enabled_alarms():
                            part = part.replace("{alarm}", self._alarm_icons["enabled"])
                        else:
                            part = part.replace("{alarm}", "")
                    try:
                        datetime_format_search = re.search(r"\{(.*)}", part)
                        datetime_format_str = datetime_format_search.group()
                        datetime_format = datetime_format_search.group(1)
                        format_label_content = part.replace(datetime_format_str, now.strftime(datetime_format))
                    except Exception:
                        format_label_content = part

                    active_widgets[widget_index].setText(format_label_content)

                    alarm_state_changed = has_alarm != self._previous_alarm_state
                    if has_alarm:
                        if self._shared_state._snoozed_alarms:
                            active_widgets[widget_index].setProperty("class", "label alarm snooze")
                        else:
                            active_widgets[widget_index].setProperty("class", "label alarm")
                        refresh_widget_style(active_widgets[widget_index])
                    else:
                        hour_class = f"clock_{current_hour}"
                        active_widgets[widget_index].setProperty("class", f"label {hour_class}")
                        if hour_changed or alarm_state_changed:
                            refresh_widget_style(active_widgets[widget_index])

                    self._previous_alarm_state = has_alarm
                widget_index += 1

        self._restore_locale_context(org_locale_time, org_locale_ctype)

    def _update_tooltip(self):
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
                logging.error(f"Error updating tooltip for timezone '{self._active_tz}': {e}")

    def _next_timezone(self):
        """Rotate to the next timezone in the configured list."""
        try:
            self._active_tz = next(self._timezones)
            if self._active_tz:
                ZoneInfo(self._active_tz)  # Validate timezone
            self._update_tooltip()
            self._update_label()
            if self._tooltip and hasattr(self, "_tooltip_filter"):
                self._tooltip_filter.show_tooltip()
        except Exception as e:
            logging.error(f"Error switching to timezone '{self._active_tz}': {e}")
            self._active_tz = None
            self._update_tooltip()
            self._update_label()

    def update_month_label(self, year, month):
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
        if self._calendar["show_week_numbers"]:
            self.update_week_label(date)
        if self._calendar["show_holidays"]:
            self.update_holiday_label(date)

    def update_week_label(self, qdate: QDate):
        """Set the week number label for the given QDate."""
        week_number = qdate.weekNumber()[0]
        self.week_label.setText(f"Week {week_number}")

    def update_holiday_label(self, qdate: QDate):
        """Show holiday name for the selected date, if available for country."""
        if _holidays_cache["supported_countries"] is None:
            self.holiday_label.setText("")
            return
        country = None
        if (
            self._country_code
            and re.fullmatch(r"[A-Z]{2}", self._country_code.upper())
            and self._country_code.upper() in _holidays_cache["supported_countries"]
        ):
            country = self._country_code.upper()
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

    def get_country_code(self):
        """Try to detect the user's country code from Windows geo APIs."""
        if not self._calendar["show_holidays"]:
            return None
        import ctypes

        try:
            GetUserGeoID = ctypes.windll.kernel32.GetUserGeoID
            geo_id = GetUserGeoID(16)
            buf = ctypes.create_unicode_buffer(3)
            GetGeoInfoW = ctypes.windll.kernel32.GetGeoInfoW
            result = GetGeoInfoW(geo_id, 4, buf, len(buf), 0)
            country_code = buf.value if result else ""
            if country_code:
                return country_code
        except Exception:
            pass

        return None

    def show_calendar(self):
        """Build and show the calendar popup (includes optional extended UI)."""
        self._yasb_calendar = PopupWidget(
            self,
            self._calendar["blur"],
            self._calendar["round_corners"],
            self._calendar["round_corners_type"],
            self._calendar["border_color"],
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
        if self._calendar.get("show_years", True):
            self.year_label = QLabel(str(datetime_now.year))
            self.year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.year_label.setProperty("class", "year-label")
            date_layout.addWidget(self.year_label)

        self.date_label = QLabel(str(datetime_now.day))
        self.date_label.setProperty("class", "date-label")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.date_label)

        if self._calendar["show_week_numbers"]:
            week_number = QDate(datetime_now.year, datetime_now.month, datetime_now.day).weekNumber()[0]
            self.week_label = QLabel(f"Week {week_number}")
            self.week_label.setProperty("class", "week-label")
            self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_layout.addWidget(self.week_label)
            self.update_week_label(QDate(datetime_now.year, datetime_now.month, datetime_now.day))
        if self._calendar["show_holidays"]:
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
            show_holidays=self._calendar["show_holidays"],
            holiday_color=self._calendar["holiday_color"],
        )
        self.calendar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.calendar.currentPageChanged.connect(self.update_month_label)
        self.calendar.clicked.connect(self.update_selected_date)

        layout.addWidget(self.calendar)

        if self._calendar["extended"]:
            actions_layout = QVBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            right_frame = QFrame()
            right_frame.setProperty("class", "extended-container")
            right_frame.setLayout(actions_layout)

            alarm_btn = QPushButton("Set Alarm")
            alarm_btn.setProperty("class", "button alarm small")
            alarm_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            timer_btn = QPushButton("Set Timer")
            timer_btn.setProperty("class", "button timer small")
            timer_btn.setCursor(Qt.CursorShape.PointingHandCursor)

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

            upcoming_widgets = []
            for i in range(4):
                lbl = QLabel("")
                lbl.setProperty("class", "upcoming-events-item")
                lbl.setWordWrap(False)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
                actions_layout.addWidget(lbl)
                upcoming_widgets.append(lbl)

            try:
                if self._calendar["show_holidays"] and _holidays_cache["supported_countries"] is not None:
                    country = None
                    if (
                        self._country_code
                        and re.fullmatch(r"[A-Z]{2}", self._country_code.upper())
                        and self._country_code.upper() in _holidays_cache["supported_countries"]
                    ):
                        country = self._country_code.upper()

                    if country:
                        today_dt = (
                            datetime.now(ZoneInfo(self._active_tz)) if self._active_tz else datetime.now().astimezone()
                        ).date()
                        holidays = {}
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
            alignment=self._calendar["alignment"],
            direction=self._calendar["direction"],
            offset_left=self._calendar["offset_left"],
            offset_top=self._calendar["offset_top"],
        )

        self._yasb_calendar.show()

    def _show_context_menu(self):
        """Build and display the context menu for the clock widget."""
        menu = QMenu(self.window())
        menu.setProperty("class", "context-menu")
        apply_qmenu_style(menu)
        if len(self._timezones_list) > 1:
            tz_menu = QMenu("Timezones", menu)
            tz_menu.setProperty("class", "context-menu submenu")
            apply_qmenu_style(tz_menu)

            for tz in self._timezones_list:
                tz_display = tz.replace("_", " ")
                tz_action = tz_menu.addAction(tz_display)
                tz_action.triggered.connect(lambda checked=False, timezone=tz: self._set_timezone(timezone))

            menu.addMenu(tz_menu)
            menu.addSeparator()

        if self._shared_state._timer_active:
            cancel_timer_action = menu.addAction("Cancel Timer")
            cancel_timer_action.triggered.connect(lambda: self._cancel_timer())
        else:
            set_timer_action = menu.addAction("Set Timer")
            set_timer_action.triggered.connect(lambda: self._show_timer_dialog())

        menu.addSeparator()

        set_alarm_action = menu.addAction("Set Alarm")
        set_alarm_action.triggered.connect(lambda: self._show_alarm_dialog())

        if self._shared_state._alarms:
            menu.addSeparator()
            alarms_label = menu.addAction("Alarms")
            alarms_label.setEnabled(False)

            for alarm in self._shared_state._alarms:
                alarm_text = self._format_alarm_text(alarm)
                alarm_action = menu.addAction(alarm_text)
                alarm_action.triggered.connect(lambda checked=False, a=alarm: self._show_alarm_dialog(a))

        margin = 6
        menu_size = menu.sizeHint()

        bar_widget = self.window()
        bar_top_left = bar_widget.mapToGlobal(bar_widget.rect().topLeft()) if bar_widget else QPoint(0, 0)
        bar_height = bar_widget.height() if bar_widget else 0

        button_center = self.mapToGlobal(self.rect().center())
        new_x = button_center.x() - menu_size.width() / 2

        bar_alignment = getattr(bar_widget, "_alignment", {}) if bar_widget else {}
        bar_position = bar_alignment.get("position") if isinstance(bar_alignment, dict) else None
        if bar_position == "top":
            new_y = bar_top_left.y() + bar_height + margin
        else:
            new_y = bar_top_left.y() - menu_size.height() - margin
        pos = QPoint(int(new_x), int(new_y))

        menu.popup(pos)
        menu.activateWindow()

    def _set_timezone(self, timezone):
        """Make the supplied timezone the active one (and rotate the list)."""
        self._timezones = cycle([timezone] + [tz for tz in self._timezones_list if tz != timezone])
        self._next_timezone()

    def _format_alarm_text(self, alarm):
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
            f"{self._alarm_icons['enabled']} " if alarm.get("enabled", True) else f"{self._alarm_icons['disabled']} "
        )
        return f"{enabled_str} {time_str} ({days_str})"

    def _has_enabled_alarms(self):
        """Return True if there are any enabled or snoozed alarms."""
        return (
            any(alarm.get("enabled", True) for alarm in self._shared_state._alarms)
            or len(self._shared_state._snoozed_alarms) > 0
        )

    def _get_alarms_tooltip(self):
        """Build the multi-line tooltip text describing active and snoozed alarms."""
        enabled_alarms = [alarm for alarm in self._shared_state._alarms if alarm.get("enabled", True)]

        if self._shared_state._snoozed_alarms and not enabled_alarms:
            if len(self._shared_state._snoozed_alarms) == 1:
                snooze_time = self._shared_state._snoozed_alarms[0]["snooze_until"].strftime("%H:%M:%S")
                return f"Snoozed alarm returns at {snooze_time}"
            else:
                return f"{len(self._shared_state._snoozed_alarms)} snoozed alarms"

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

        if self._shared_state._snoozed_alarms:
            for snoozed in self._shared_state._snoozed_alarms:
                snooze_time = snoozed["snooze_until"].strftime("%H:%M:%S")
                tooltip_lines.append(f"Snoozed alarm returns at {snooze_time}")

        return "\n".join(tooltip_lines)

    def _create_dialog_popup(self, class_name):
        """Create a configured PopupWidget used for dialogs (timer/alarm)."""
        popup = PopupWidget(
            self,
            self._calendar["blur"],
            self._calendar["round_corners"],
            self._calendar["round_corners_type"],
            self._calendar["border_color"],
        )
        popup.setProperty("class", f"clock-popup {class_name}")
        return popup

    def _create_time_grid(self, label1_text, label2_text, spin1_range, spin2_range, spin1_value=None, spin2_value=None):
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

    def _create_footer_container(self, buttons):
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

    def _show_alarm_dialog(self, alarm=None):
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

        if is_edit_mode:
            hour, minute = map(int, alarm["time"].split(":"))
        else:
            now = datetime.now()
            hour, minute = now.hour, now.minute

        grid_wrapper, hour_spin, minute_spin = self._create_time_grid("Hour", "Minute", (0, 23), (0, 59), hour, minute)
        container_layout.addLayout(grid_wrapper)

        days_layout = QHBoxLayout()
        day_buttons = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(day_names):
            btn = QPushButton(day)
            btn.setCheckable(True)
            btn.setProperty("class", "button day")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_edit_mode:
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

        def apply_quick(option_key: str):
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

        enabled_button = None
        if is_edit_mode:
            enabled_button = QPushButton()
            enabled_button.setCheckable(True)
            enabled_button.setCursor(Qt.CursorShape.PointingHandCursor)
            is_enabled = alarm.get("enabled", True)
            enabled_button.setChecked(is_enabled)
            enabled_button.setText("Enabled" if is_enabled else "Disabled")
            enabled_button.setProperty("class", f"button {'is-alarm-enabled' if is_enabled else 'is-alarm-disabled'}")

            def on_enabled_toggled(checked):
                enabled_button.setText("Enabled" if checked else "Disabled")
                enabled_button.setProperty("class", f"button {'is-alarm-enabled' if checked else 'is-alarm-disabled'}")
                refresh_widget_style(enabled_button)

            enabled_button.toggled.connect(on_enabled_toggled)
            quick_layout.addWidget(enabled_button)

        quick_group = QButtonGroup(popup)
        quick_group.setExclusive(True)

        for label, key in quick_options:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setProperty("class", "button quick-option")
            quick_group.addButton(btn)
            btn.clicked.connect(lambda checked, k=key: apply_quick(k))
            quick_layout.addWidget(btn)

        popup._alarm_quick_group = quick_group

        for btn in day_buttons:
            btn.clicked.connect(lambda _checked, q=quick_group: self._clear_quick_group(q))

        container_layout.addLayout(quick_layout)

        title_layout = QHBoxLayout()

        title_edit = QLineEdit()
        title_edit.setProperty("class", "alarm-input-title")
        title_edit.setPlaceholderText("Alarm title")
        title_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        if is_edit_mode:
            title_edit.setText(alarm.get("title", ""))
        title_edit.setFocus()

        title_layout.addWidget(title_edit)
        container_layout.addLayout(title_layout)

        buttons = []

        if is_edit_mode:
            delete_btn = QPushButton("Delete")
            delete_btn.setProperty("class", "button delete")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def delete_alarm():
                if alarm in self._shared_state._alarms:
                    self._shared_state._alarms.remove(alarm)
                    self._shared_state._snoozed_alarms = [
                        s for s in self._shared_state._snoozed_alarms if s["alarm"] != alarm
                    ]
                    self._save_alarms()
                    self._refresh_alarm_ui()
                popup.close()

            delete_btn.clicked.connect(delete_alarm)
            buttons.append(delete_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "button save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons.extend([save_btn, cancel_btn])

        def save_alarm_func():
            selected_days = [i for i, btn in enumerate(day_buttons) if btn.isChecked()]
            if not selected_days:
                selected_days = [datetime.now().weekday()]
            time_value = f"{hour_spin.value():02d}:{minute_spin.value():02d}"

            new_alarm_data = {
                "time": time_value,
                "days": selected_days,
                "enabled": enabled_button.isChecked() if is_edit_mode else True,
                "title": title_edit.text().strip(),
            }

            if is_edit_mode:
                if not new_alarm_data["enabled"]:
                    self._shared_state._snoozed_alarms = [
                        s for s in self._shared_state._snoozed_alarms if s["alarm"] != alarm
                    ]
                alarm.update(new_alarm_data)
            else:
                self._shared_state._alarms.append(new_alarm_data)

            self._save_alarms()
            self._refresh_alarm_ui()

            popup.close()

        def _has_selected_day() -> bool:
            return any(btn.isChecked() for btn in day_buttons)

        def update_save_enabled():
            save_btn.setEnabled(bool(title_edit.text().strip()) and _has_selected_day())

        update_save_enabled()

        title_edit.textChanged.connect(lambda _text: update_save_enabled())
        for btn in day_buttons:
            btn.clicked.connect(lambda _checked, u=update_save_enabled: u())
        save_btn.clicked.connect(save_alarm_func)
        cancel_btn.clicked.connect(lambda: popup.close())

        footer_frame = self._create_footer_container(buttons)

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        popup.adjustSize()
        popup.setPosition(
            alignment=self._calendar["alignment"],
            direction=self._calendar["direction"],
            offset_left=self._calendar["offset_left"],
            offset_top=self._calendar["offset_top"],
        )

        popup.show()

    def _save_alarms(self):
        """Persist alarms and refresh UI across widgets."""
        self._shared_state.save_alarms()
        self._shared_state.notify_all_widgets(update_tooltip=True)

    def _trigger_alarm(self, alarm):
        """Start alarm behavior (play sound and show active alarm popup)."""
        self._play_sound(loop_duration_ms=16000)

        try:
            self._show_active_alarm_popup(alarm)
        except Exception:
            logging.exception("Failed to show active alarm popup")

    def _play_sound(self, loop_duration_ms=0):
        """Play the configured notification sound; loop if loop_duration_ms>0."""
        if not os.path.exists(NOTIFICATION_SOUND):
            logging.warning(f"Notification sound file not found: {NOTIFICATION_SOUND}")
            return

        try:
            if loop_duration_ms > 0:
                winsound.PlaySound(NOTIFICATION_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                QTimer.singleShot(loop_duration_ms, self._stop_alarm_sound)
            else:
                winsound.PlaySound(NOTIFICATION_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logging.error(f"Failed to play notification sound: {e}")

    def _stop_alarm_sound(self):
        """Stop any playing notification sound (winsound)."""
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _refresh_alarm_ui(self):
        """Request all widgets to refresh alarm-related UI and tooltip."""
        self._shared_state.notify_all_widgets(update_tooltip=True)

    def _show_active_alarm_popup(self, alarm):
        """Display a centered popup for an active alarm with controls."""
        win = QFrame(self)
        win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        try:
            hwnd = int(win.winId())
            Blur(hwnd, Acrylic=False, DarkMode=True, RoundCorners=True, RoundCornersType="normal", BorderColor="None")
        except Exception:
            pass
        win.setProperty("class", "active-alarm-window")
        win.activateWindow()

        layout = QVBoxLayout(win)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_text_icon = self._alarm_icons["disabled"]
        title_icon = QLabel(title_text_icon)
        title_icon.setProperty("class", "alarm-title-icon")
        title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def create_shake_animation():
            animation = QPropertyAnimation(title_icon, b"pos")
            animation.setDuration(1000)
            animation.setLoopCount(16)

            def start_shake():
                original_pos = title_icon.pos()
                animation.setKeyValueAt(0, original_pos)
                animation.setKeyValueAt(0.1, QPoint(original_pos.x() - 10, original_pos.y()))
                animation.setKeyValueAt(0.2, QPoint(original_pos.x() + 10, original_pos.y()))
                animation.setKeyValueAt(0.3, QPoint(original_pos.x() - 10, original_pos.y()))
                animation.setKeyValueAt(0.4, QPoint(original_pos.x() + 10, original_pos.y()))
                animation.setKeyValueAt(0.5, QPoint(original_pos.x() - 5, original_pos.y()))
                animation.setKeyValueAt(0.6, QPoint(original_pos.x() + 5, original_pos.y()))
                animation.setKeyValueAt(0.7, QPoint(original_pos.x() - 5, original_pos.y()))
                animation.setKeyValueAt(0.8, QPoint(original_pos.x() + 5, original_pos.y()))
                animation.setKeyValueAt(0.9, original_pos)
                animation.setKeyValueAt(1.0, original_pos)
                animation.setEasingCurve(QEasingCurve.Type.InOutSine)
                animation.start()

            QTimer.singleShot(10, start_shake)
            return animation

        title_text = alarm.get("title") or "Alarm"
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setProperty("class", "alarm-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(title_icon)
        layout.addWidget(title)

        win._icon_animation = create_shake_animation()

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

        alarm_buttons = []
        for label, snooze_minutes in buttons_config:
            btn = QPushButton(label)
            btn.setProperty("class", "button")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_layout.addWidget(btn)
            alarm_buttons.append((btn, snooze_minutes))

        layout.addLayout(btn_layout)

        def _stop_action():
            self._stop_alarm_sound()
            self._shared_state._snoozed_alarms = [s for s in self._shared_state._snoozed_alarms if s["alarm"] != alarm]
            self._refresh_alarm_ui()
            win.close()
            win.deleteLater()

        def _snooze_action(minutes: int):
            self._stop_alarm_sound()

            snooze_until = datetime.now() + timedelta(minutes=minutes)
            self._shared_state._snoozed_alarms.append({"alarm": alarm, "snooze_until": snooze_until})

            self._shared_state.notify_all_widgets(update_tooltip=True)
            win.close()
            win.deleteLater()

        for btn, snooze_minutes in alarm_buttons:
            if snooze_minutes is None:
                btn.clicked.connect(_stop_action)
            else:
                btn.clicked.connect(lambda checked=False, mins=snooze_minutes: _snooze_action(mins))
        win.adjustSize()

        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center())) or QApplication.primaryScreen()
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

        def set_quick(minutes_total: int):
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
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setProperty("class", "button quick-option")
            quick_group.addButton(btn)
            btn.clicked.connect(lambda checked, mins=mins: set_quick(mins))
            quick_layout.addWidget(btn)

        popup._timer_quick_group = quick_group

        minutes_spin.valueChanged.connect(lambda _v, q=quick_group: self._clear_quick_group(q))
        seconds_spin.valueChanged.connect(lambda _v, q=quick_group: self._clear_quick_group(q))

        container_layout.addLayout(quick_layout)

        # Create action buttons
        start_btn = QPushButton("Start")
        start_btn.setProperty("class", "button start")
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def start_timer():
            total_seconds = minutes_spin.value() * 60 + seconds_spin.value()
            if total_seconds > 0:
                self._shared_state._timer_seconds_remaining = total_seconds
                self._shared_state._timer_active = True
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
            alignment=self._calendar["alignment"],
            direction=self._calendar["direction"],
            offset_left=self._calendar["offset_left"],
            offset_top=self._calendar["offset_top"],
        )

        popup.show()

    def _format_timer_display(self):
        """Format the shared timer remaining seconds into a display string."""
        hours = self._shared_state._timer_seconds_remaining // 3600
        minutes = (self._shared_state._timer_seconds_remaining % 3600) // 60
        seconds = self._shared_state._timer_seconds_remaining % 60

        if hours > 0:
            return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
        else:
            return f"[{minutes:02d}:{seconds:02d}]"

    def _cancel_timer(self):
        """Cancel the shared timer and notify widgets to update display."""
        self._shared_state._timer_active = False
        self._shared_state._timer_seconds_remaining = 0
        self._shared_state.notify_all_widgets()

    def _timer_finished(self):
        """Handle shared timer finishing: stop and play a notification."""
        self._shared_state._timer_active = False
        self._shared_state._timer_seconds_remaining = 0
        self._shared_state.notify_all_widgets()
        self._play_sound()

    def _clear_quick_group(self, qgroup: QButtonGroup | None) -> None:
        """Clear (uncheck) all buttons in a quick-selection QButtonGroup."""
        if not qgroup:
            return

        was_exclusive = qgroup.exclusive()
        qgroup.setExclusive(False)

        for btn in qgroup.buttons():
            btn.setChecked(False)

        qgroup.setExclusive(was_exclusive)

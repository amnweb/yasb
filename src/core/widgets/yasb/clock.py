import locale
import re
from datetime import date, datetime
from itertools import cycle
from typing import cast

import pytz
from PyQt6.QtCore import QDate, QLocale, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QCalendarWidget, QFrame, QHBoxLayout, QLabel, QSizePolicy, QStyle, QTableView, QVBoxLayout
from tzlocal import get_localzone_name

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.clock import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

_holidays_cache = {"module": None, "supported_countries": None, "country_holidays": {}}


def _get_holidays_module():
    """
    Lazy load the holidays module and cache it.
    This function ensures that the module is only loaded once and caches the supported countries.
    If the module is already loaded, it returns the cached module.
    """
    import importlib

    if _holidays_cache["module"] is None:
        _holidays_cache["module"] = importlib.import_module("holidays")
        _holidays_cache["supported_countries"] = set(_holidays_cache["module"].list_supported_countries())
    return _holidays_cache["module"]


def _get_cached_country_holidays(country, year, subdivision=None):
    """Get cached country holidays or fetch and cache them."""
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
        if year != self._current_year:
            self._update_holidays_for_year(year)

    def paintCell(self, painter, rect, date):
        if date < self.minimumDate() or date > self.maximumDate():
            return
        pydate = date.toPyDate()
        is_holiday = self.show_holidays and pydate in self._holidays
        if is_holiday:
            # For holidays, we need to handle selection state manually
            is_selected = date == self.selectedDate()
            if is_selected:
                # Selected holiday use default selection style form styles.css
                painter.save()
                super().paintCell(painter, rect, date)
                painter.restore()
            else:
                # Non-selected holiday just paint holiday text with holiday color
                painter.save()
                painter.setPen(QColor(self.holiday_color))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
                painter.restore()
        else:
            super().paintCell(painter, rect, date)

    def update_calendar_display(self):
        if self.timezone:
            datetime_now = datetime.now(pytz.timezone(self.timezone))
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
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(update_interval, class_name=f"clock-widget {class_name}")
        self._locale = locale
        self._tooltip = tooltip
        self._active_tz = None
        self._timezones = cycle(timezones if timezones else [get_localzone_name()])
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
        self._current_hour = None
        self._country_code = self._calendar["country_code"] or self.get_country_code()
        self._subdivision = self._calendar.get("subdivision")
        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("next_timezone", self._next_timezone)
        self.register_callback("toggle_calendar", self._toggle_calendar)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self._show_alt_label = False

        self._next_timezone()
        self._update_label()
        self.start_timer()
        if self._calendar["show_holidays"]:
            QTimer.singleShot(0, _get_holidays_module)

    def _toggle_calendar(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_calendar()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _get_icon_for_hour(self, hour: int) -> str:
        key = f"clock_{hour:02d}"
        icon = self._icons.get(key)
        if icon is None and 13 <= hour <= 23:
            fallback_key = f"clock_{hour - 12:02d}"
            icon = self._icons.get(fallback_key, "")
        return icon or ""

    def _reload_css(self, label: QLabel):
        style = cast(QStyle, label.style())
        style.unpolish(label)
        style.polish(label)
        label.update()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        now = datetime.now(pytz.timezone(self._active_tz))
        current_hour = f"{now.hour:02d}"
        hour_changed = self._current_hour != current_hour
        if hour_changed:
            self._current_hour = current_hour
        if self._locale:
            org_locale_time = locale.getlocale(locale.LC_TIME)
            try:
                org_locale_ctype = locale.getlocale(locale.LC_CTYPE)
            except locale.Error:
                pass
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
                            self._reload_css(active_widgets[widget_index])
                    else:
                        active_widgets[widget_index].setText(icon_placeholder)
                else:
                    try:
                        if self._locale:
                            locale.setlocale(locale.LC_TIME, self._locale)
                            try:
                                locale.setlocale(locale.LC_CTYPE, self._locale)
                            except locale.Error:
                                pass
                        datetime_format_search = re.search("\\{(.*)}", part)
                        datetime_format_str = datetime_format_search.group()
                        datetime_format = datetime_format_search.group(1)
                        datetime_now = datetime.now(pytz.timezone(self._active_tz))
                        format_label_content = part.replace(datetime_format_str, datetime_now.strftime(datetime_format))
                    except Exception:
                        format_label_content = part
                    active_widgets[widget_index].setText(format_label_content)
                    if hour_changed:
                        hour_class = f"clock_{current_hour}"
                        active_widgets[widget_index].setProperty("class", f"label {hour_class}")
                        self._reload_css(active_widgets[widget_index])
                widget_index += 1
        if self._locale:
            locale.setlocale(locale.LC_TIME, org_locale_time)
            try:
                locale.setlocale(locale.LC_CTYPE, org_locale_ctype)
            except locale.Error:
                pass

    def _next_timezone(self):
        self._active_tz = next(self._timezones)
        if self._tooltip:
            set_tooltip(self, self._active_tz)
        self._update_label()

    def update_month_label(self, year, month):
        qlocale = QLocale(self._locale) if self._locale else QLocale.system()
        new_month = qlocale.monthName(month)
        self.month_label.setText(new_month)

        selected_day = self.calendar.selectedDate().day()
        days_in_month = QDate(year, month, 1).daysInMonth()
        if selected_day > days_in_month:
            selected_day = days_in_month

        newDate = QDate(year, month, selected_day)
        self.day_label.setText(qlocale.dayName(newDate.dayOfWeek()))
        self.date_label.setText(newDate.toString("d"))

    def update_selected_date(self, date: QDate):
        qlocale = QLocale(self._locale) if self._locale else QLocale.system()
        self.day_label.setText(qlocale.dayName(date.dayOfWeek()))
        self.month_label.setText(qlocale.monthName(date.month()))
        self.date_label.setText(date.toString("d"))
        if self._calendar["show_week_numbers"]:
            self.update_week_label(date)
        if self._calendar["show_holidays"]:
            self.update_holiday_label(date)

    def update_week_label(self, qdate: QDate):
        week_number = qdate.weekNumber()[0]
        self.week_label.setText(f"Week {week_number}")

    def update_holiday_label(self, qdate: QDate):
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
        """Retrieve the country code based on the user's locale or system settings."""
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
        self._yasb_calendar = PopupWidget(
            self,
            self._calendar["blur"],
            self._calendar["round_corners"],
            self._calendar["round_corners_type"],
            self._calendar["border_color"],
        )
        self._yasb_calendar.setProperty("class", "calendar")

        # Create main layout
        layout = QHBoxLayout()
        layout.setProperty("class", "calendar-layout")
        self._yasb_calendar.setLayout(layout)

        # Left side: Today Date
        date_layout = QVBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(0)
        date_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        datetime_now = datetime.now(pytz.timezone(self._active_tz))
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

        current_year = QDate.currentDate().year()
        min_date = QDate(current_year, 1, 1)
        max_date = QDate(current_year, 12, 31)

        self.calendar.setMinimumDate(min_date)
        self.calendar.setMaximumDate(max_date)
        self.calendar.currentPageChanged.connect(self.update_month_label)
        self.calendar.clicked.connect(self.update_selected_date)

        layout.addWidget(self.calendar)

        self._yasb_calendar.adjustSize()

        self._yasb_calendar.setPosition(
            alignment=self._calendar["alignment"],
            direction=self._calendar["direction"],
            offset_left=self._calendar["offset_left"],
            offset_top=self._calendar["offset_top"],
        )

        self._yasb_calendar.show()

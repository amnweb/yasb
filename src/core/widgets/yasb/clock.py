import locale
import re
from datetime import datetime
from itertools import cycle

import pytz
from PyQt6.QtCore import QDate, QLocale, Qt
from PyQt6.QtWidgets import QCalendarWidget, QHBoxLayout, QLabel, QSizePolicy, QTableView, QVBoxLayout, QWidget
from tzlocal import get_localzone_name

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.clock import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class CustomCalendar(QCalendarWidget):
    def __init__(self, parent=None, timezone=None):
        super().__init__(parent)
        self.timezone = timezone
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setNavigationBarVisible(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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

    def paintCell(self, painter, rect, date):
        if date < self.minimumDate() or date > self.maximumDate():
            return  # Skip drawing
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
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container: QWidget = QWidget()
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

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
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
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
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
            self.setToolTip(self._active_tz)
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

        layout.addLayout(date_layout)

        self.calendar = CustomCalendar(self, self._active_tz)
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

import re
import pytz
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.clock import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel
from datetime import datetime
from tzlocal import get_localzone_name
from itertools import cycle


class ClockWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            locale: str,
            update_interval: int,
            timezones: list[str],
            callbacks: dict[str, str],
    ):
        super().__init__(update_interval, class_name="clock-widget")
        self._locale = locale
        self._active_tz = None
        self._timezones = cycle(timezones if timezones else [get_localzone_name()])
        self._active_datetime_format_str = ''
        self._active_datetime_format = None

        self._label_content = label
        self._label_alt_content = label_alt

        if self._locale:
            import locale
            print(locale.locale_alias)
            locale.setlocale(locale.LC_TIME, self._locale)
        self._label = QLabel()
        self._label_alt = QLabel()
        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")
        self.widget_layout.addWidget(self._label)
        self.widget_layout.addWidget(self._label_alt)
        self.register_callback("toggle_label", self._toggle_label)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("next_timezone", self._next_timezone)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

        self._label.show()
        self._label_alt.hide()
        self._show_alt_label = False

        self._next_timezone()
        self._update_label()
        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label

        if self._show_alt_label:
            self._label.hide()
            self._label_alt.show()
        else:
            self._label.show()
            self._label_alt.hide()

        self._update_label()

    def _update_label(self):
        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        try:
            datetime_format_search = re.search('\\{(.*)}', active_label_content)
            datetime_format_str = datetime_format_search.group()
            datetime_format = datetime_format_search.group(1)
            datetime_now = pytz.utc.localize(datetime.utcnow()).astimezone(pytz.timezone(self._active_tz))
            format_label_content = active_label_content.replace(
                datetime_format_str,
                datetime_now.strftime(datetime_format)
            )
            active_label.setText(format_label_content)
        except Exception:
            active_label.setText(active_label_content)

    def _next_timezone(self):
        self._active_tz = next(self._timezones)
        self.setToolTip(self._active_tz)
        self._update_label()

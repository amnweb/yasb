import psutil
from humanize import naturalsize
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.traffic import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel


class TrafficWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    # initialize io counters
    io = psutil.net_io_counters()
    bytes_sent = io.bytes_sent
    bytes_recv = io.bytes_recv
    interval = 1  # second(s)

    def __init__(
        self,
        label: str,
        label_alt: str,
        update_interval: int,
        callbacks: dict[str, str],
    ):
        super().__init__(update_interval, class_name="traffic-widget")
        self.interval = update_interval // 1000

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        self._label = QLabel()
        self._label_alt = QLabel()
        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")
        self.widget_layout.addWidget(self._label)
        self.widget_layout.addWidget(self._label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self._label.show()
        self._label_alt.hide()

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
        # Update the active label at each timer interval
        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        active_label_formatted = active_label_content

        try:
            upload_speed, download_speed = self._get_speed()
        except Exception:
            upload_speed, download_speed = "N/A", "N/A"

        label_options = [
            ("{upload_speed}", upload_speed),
            ("{download_speed}", download_speed),
        ]

        for option, value in label_options:
            active_label_formatted = active_label_formatted.replace(option, str(value))

        active_label.setText(active_label_formatted)

    def _get_speed(self) -> [str, str]:
        current_io = psutil.net_io_counters()
        upload_diff = current_io.bytes_sent - self.bytes_sent
        download_diff = current_io.bytes_recv - self.bytes_recv

        if upload_diff < 1024:
            upload_speed = f"{upload_diff} B/s"
        else:
            upload_speed = naturalsize(
                (current_io.bytes_sent - self.bytes_sent) // self.interval,
            ) + "/s"

        if download_diff < 1024:
            download_speed = f"{download_diff} B/s"
        else:
            download_speed = naturalsize(
                (current_io.bytes_recv - self.bytes_recv) // self.interval,
            ) + "/s"

        self.bytes_sent = current_io.bytes_sent
        self.bytes_recv = current_io.bytes_recv
        return upload_speed, download_speed

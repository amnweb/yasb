import datetime
import hashlib
import json
import os
import re
import urllib.request
from typing import Callable

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.shell_utils import shell_open
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ToastNotifier, add_shadow, build_widget_label, refresh_widget_style
from core.validation.widgets.yasb.glucose_monitor import GlucoseMonitorConfig
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH


class GlucoseMonitorWorker(QThread):
    @classmethod
    def get_instance(cls):
        return cls()

    status_updated = pyqtSignal(int, float, str, str)
    error_signal = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._url: str | None = None
        self.running = True

    def set_url(self, host: str, secret: str) -> None:
        secret_hash = hashlib.sha1(secret.encode()).hexdigest()
        self._url = f"{host}/api/v1/entries/current.json?secret={secret_hash}"

    def stop(self) -> None:
        self.running = False
        self.wait()

    def run(self) -> None:
        if not self.running:
            return

        try:
            with urllib.request.urlopen(self._url) as response:
                data = json.loads(response.read().decode("utf-8"))
                status = response.status

            if status != 200:
                raise RuntimeError(f"Response status code should be 200 but got {status}")

            resp_json = data[0]
            self.status_updated.emit(
                resp_json["sgv"],
                resp_json["delta"],
                resp_json["dateString"],
                resp_json["direction"],
            )
        except Exception:
            self.error_signal.emit("Connection error")


class GlucoseMonitor(BaseWidget):
    validation_schema = GlucoseMonitorConfig

    update_interval_in_milliseconds = 1 * 60 * 1_000
    datetime_format = "%Y-%m-%dT%H:%M:%S.%f%z"

    direction_icons_mapping = {
        "double_up": "DoubleUp",
        "single_up": "SingleUp",
        "forty_five_up": "FortyFiveUp",
        "flat": "Flat",
        "forty_five_down": "FortyFiveDown",
        "single_down": "SingleDown",
        "double_down": "DoubleDown",
    }

    def __init__(self, config: GlucoseMonitorConfig) -> None:
        super().__init__(timer_interval=self.update_interval_in_milliseconds, class_name="cgm-widget")
        self.config = config

        self._error_message: str | None = None
        self._is_sgv_in_range: bool = False

        self._direction_icons = {
            self.direction_icons_mapping[key]: value for key, value in self.config.direction_icons.model_dump().items()
        }

        self._available_sgv_measurement_units: dict[str, Callable[[int | float], str]] = {
            "mg/dl": lambda sgv: str(round(sgv)),
            "mmol/l": lambda sgv: f"{sgv / 18:.1f}",
        }

        if not (convert_sgv := self._available_sgv_measurement_units.get(self.config.sgv_measurement_units)):
            raise ValueError("Wrong measurement units")
        self._convert_sgv = convert_sgv

        self._icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")
        self._status_data = {}

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container_layout.setSpacing(0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self.config.label, self.config.error_label, self.config.label_shadow.model_dump())

        self.register_callback("open_cgm", self._open_cgm)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        secret = self.config.secret != "env" and self.config.secret or os.getenv(self.config.secret_env_name)

        if not secret:
            self._error_message = "Missing Secret"
            self._update_label()
        else:
            self._worker = GlucoseMonitorWorker.get_instance()
            self._worker.set_url(self.config.host, secret)
            self._worker.status_updated.connect(self._handle_status_update)
            self._worker.error_signal.connect(self._handle_error_signal)

            self._update_timer = QTimer()
            self._update_timer.timeout.connect(self._worker.start)
            self._update_timer.start(self.update_interval_in_milliseconds)

            self._worker.start()

    def _open_cgm(self) -> None:
        shell_open(self.config.host)

    def _update_label(self) -> None:
        for widget in self._widgets:
            widget.setVisible(not self._error_message)
        for widget in self._widgets_alt:
            widget.setVisible(bool(self._error_message))

        active_widgets = self._error_message and self._widgets_alt or self._widgets
        active_label_content = self._error_message and self.config.error_label or self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = list(filter(None, label_parts))
        widget_index = 0

        format_data = (
            self._error_message
            and {
                "error_message": self._error_message,
            }
            or self._status_data
        )

        for part in label_parts:
            part = part.strip()
            if not part or widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                active_widgets[widget_index].setText(icon.format_map(format_data))

                current_class = active_widgets[widget_index].property("class") or ""
                if "sgv" in current_class.split():
                    new_class = self._is_sgv_in_range and "sgv in-range" or "sgv out-range"
                    active_widgets[widget_index].setProperty("class", new_class)
                    refresh_widget_style(active_widgets[widget_index])
            else:
                formatted_text = part.format_map(format_data)
                active_widgets[widget_index].setText(formatted_text)
            widget_index += 1

        if self.config.tooltip:
            set_tooltip(
                widget=self._widget_container,
                text=self._error_message or self.config.tooltip.format_map(self._status_data),
            )

    def _handle_error_signal(self, message: str) -> None:
        prev_error_message = self._error_message
        self._error_message = message
        self._update_label()

        if self.config.notify_on_error and not prev_error_message:
            toaster = ToastNotifier()
            toaster.show(self._icon_path, "Glucose Monitor", message)

    def _handle_status_update(
        self,
        sgv: int,
        sgv_delta: float,
        date_string: str,
        direction: str,
    ) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        last_update_time = datetime.datetime.strptime(date_string, self.datetime_format)
        delta_time_in_minutes = int((now - last_update_time).total_seconds() // 60)
        direction = self._direction_icons[direction]

        sgv = self._convert_sgv(sgv)
        sgv_delta = self._convert_sgv(sgv_delta)

        self._status_data = {
            "sgv": sgv,
            "sgv_delta": sgv_delta,
            "delta_time_in_minutes": delta_time_in_minutes,
            "direction": direction,
        }

        sgv_as_float = float(sgv)
        self._is_sgv_in_range = self.config.sgv_range.min <= sgv_as_float <= self.config.sgv_range.max

        self._error_message = None
        self._update_label()

import datetime
import hashlib
import json
import os
import re
import urllib.request
import webbrowser
from typing import Callable

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import ToastNotifier, build_widget_label
from core.validation.widgets.yasb.glucose_monitor import VALIDATION_SCHEMA
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
        except RuntimeError as e:
            self.error_signal.emit(str(e))
        except Exception:
            self.error_signal.emit("Error while loading response")


class GlucoseMonitor(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

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

    def __init__(
        self,
        label: str,
        tooltip: str,
        host: str,
        secret: str,
        secret_env_name: str,
        direction_icons: dict[str, str],
        sgv_measurement_units: str,
        callbacks: dict[str, str],
    ) -> None:
        super().__init__(timer_interval=self.update_interval_in_milliseconds, class_name="cgm-widget")

        self._label_content = label
        self._tooltip = tooltip
        self._host = host
        self._secret = secret != "env" and secret or os.getenv(secret_env_name)

        self._direction_icons = {self.direction_icons_mapping[key]: value for key, value in direction_icons.items()}

        self._sgv_measurement_units = sgv_measurement_units
        self._available_sgv_measurement_units: dict[str, Callable[[int | float], str]] = {
            "mg/dl": lambda sgv: str(round(sgv)),
            "mmol/l": lambda sgv: f"{sgv / 18:.1f}",
        }
        self._icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")
        self._status_data = {}

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content)

        self.register_callback("open_cgm", self._open_cgm)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._worker = GlucoseMonitorWorker.get_instance()
        self._worker.set_url(self._host, self._secret)
        self._worker.status_updated.connect(self._handle_status_update)
        self._worker.error_signal.connect(self._handle_error_signal)

        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._worker.start)
        self._update_timer.start(self.update_interval_in_milliseconds)

        self._worker.start()

    def _open_cgm(self) -> None:
        webbrowser.open(self._host)

    def _update_label(self) -> None:
        active_widgets = self._widgets
        active_label_content = self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = list(filter(None, label_parts))
        widget_index = 0

        for part in label_parts:
            part = part.strip()
            if not part or widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                active_widgets[widget_index].setText(icon)
            else:
                formatted_text = part.format_map(self._status_data)
                active_widgets[widget_index].setText(formatted_text)
            widget_index += 1

        if self._tooltip:
            set_tooltip(
                widget=self._widget_container,
                text=self._tooltip.format_map(self._status_data),
            )

    def _handle_error_signal(self, message: str) -> None:
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

        if not (convert_sgv := self._available_sgv_measurement_units.get(self._sgv_measurement_units)):
            self._handle_error_signal("Wrong measurement units")

        sgv = convert_sgv(sgv)
        sgv_delta = convert_sgv(sgv_delta)

        self._status_data = {
            "sgv": sgv,
            "sgv_delta": sgv_delta,
            "delta_time_in_minutes": delta_time_in_minutes,
            "direction": direction,
        }
        self._update_label()

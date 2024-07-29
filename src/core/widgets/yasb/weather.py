import logging
from datetime import datetime
import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
from pyquery import PyQuery
import threading

# Suppress urllib3 logging
logging.getLogger("urllib3").setLevel(logging.WARNING)

class WeatherWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        update_interval: int,
        location_id: str,
        temp_format: str,
        callbacks: dict[str, str],
        icons: dict[str, str],
    ):
        super().__init__((update_interval * 1000), class_name="weather-widget")
        self.location_id = location_id
        self.temp_format = temp_format
        self.icons = icons
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self.weather_data = {"temp": "N/A", "icon": self.icons["default"], "humidity": "N/A"}

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        # Initialize container
        self._widget_container = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "fetch_weather_data"
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("fetch_weather_data", self._fetch_and_update_weather_data)

        # Start the timer after initial setup
        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            widgets = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.hide()
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                    label.setText("Loading...")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _update_label(self):
        active_widgets = self._show_alt_label and self._widgets_alt or self._widgets
        active_label_content = self._show_alt_label and self._label_alt_content or self._label_content
        label_parts = re.split(r'(<span.*?>.*?</span>)', active_label_content)

        label_options = {
            "{temp}": self.weather_data["temp"],
            "{icon}": self.weather_data["icon"],
            "{humidity}": self.weather_data["humidity"]
        }

        widget_index = 0
        try:
            for part in label_parts:
                part = part.strip()
                for option, value in label_options.items():
                    part = part.replace(option, str(value))
                if not part or widget_index >= len(active_widgets):
                    continue
                if isinstance(active_widgets[widget_index], QLabel):
                    if '<span' in part and '</span>' in part:
                        icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                        active_widgets[widget_index].setText(icon)
                    else:
                        active_widgets[widget_index].setText(part)
                    if not active_widgets[widget_index].isVisible():
                        active_widgets[widget_index].show()
                    widget_index += 1
        except Exception as e:
            logging.exception(f"Failed to update label: {e}")

    def _fetch_and_update_weather_data(self):
        threading.Thread(target=self._fetch_weather_data).start()

    def _fetch_weather_data(self):
        try:
            weather_data = self.fetch_weather_data()
            self.weather_data.update({
                "temp": weather_data["temp"],
                "icon": weather_data["icon"],
                "humidity": weather_data["humidity"],
            })
            self._label_alt_content = weather_data["temp_alt"]
            QTimer.singleShot(0, self._update_label)
        except Exception as e:
            logging.exception(f"Failed to fetch weather data: {e}")

    def fetch_weather_data(self) -> dict:
        try:
            url = self._build_weather_url()
            html_data = PyQuery(url=url)
            temp = html_data("span[data-testid='TemperatureValue']").eq(0).text()
            temp_min = html_data("div[class*='CurrentConditions--tempHiLoValue--'] > span[data-testid='TemperatureValue']").eq(1).text()
            temp_max = html_data("div[class*='CurrentConditions--tempHiLoValue--'] > span[data-testid='TemperatureValue']").eq(0).text()
            humidity = html_data("div[data-testid='wxData'] > span[data-testid='PercentageValue']").eq(0).text()
            temp_alt = f"Day {temp_max} • Night {temp_min} • Humidity {humidity}"
            status_code = html_data("#regionHeader").attr("class").split(" ")[2].split("-")[2]
            icon = self.icons.get(status_code, self.icons["default"])
            logging.info(f"Fetched new weather data at {datetime.now()}")
        except Exception as e:
            temp = "N/A"
            humidity = "N/A"
            temp_alt = f"{self.icons['default']} N/A"
            icon = self.icons["default"]
            logging.warning("Failed to retrieve weather info")
        if self.callback_left == "do_nothing":
            self.callback_left = f"exec cmd /c start {url}"
        return {"temp": temp, "humidity": humidity, "temp_alt": temp_alt, "icon": icon}

    def _build_weather_url(self) -> str:
        base_url = "https://weather.com/en-GB/weather/today/l/" if self.temp_format == "celsius" else "https://weather.com/weather/today/l/"
        return base_url + self.location_id
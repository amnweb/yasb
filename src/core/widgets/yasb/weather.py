import logging
from datetime import datetime
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel
from pyquery import PyQuery

# Suppress urllib3 logging
logging.basicConfig(level=logging.ERROR)  # Set to DEBUG level for detailed logs
logging.getLogger("urllib3").setLevel(logging.WARNING)

class WeatherWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            update_interval: int,
            class_name: str,
            location_id: str,
            temp_format: str,
            callbacks: dict[str, str],
            icons: dict[str, str]
    ):
        super().__init__(update_interval, class_name=f"system-widget {class_name}")
        self.update_interval = update_interval
        self.location_id = location_id
        self.temp_format = temp_format
        self.icons = icons  # Store the icons dictionary

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        self._label = self._create_label("label", visible=False)  # Initially hidden
        self._label_alt = self._create_label("label alt", visible=False)  # Initially hidden

        self.register_callbacks(callbacks)
        
        # Initialize _cached_label_options
        self._cached_label_options = []
        # Show the main label after initialization
        self._label.setVisible(True)
        # Start the timer after initial setup
        self.start_timer()

    def _create_label(self, css_class: str, visible=True) -> QLabel:
        label = QLabel()
        label.setProperty("class", css_class)
        label.setVisible(visible)
        self.widget_layout.addWidget(label)
        return label

    def register_callbacks(self, callbacks: dict[str, str]):
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("fetch_weather_data", self._fetch_and_cache_weather_data)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "fetch_weather_data"
         
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
        try:
            if self._should_update_cache():
                self._fetch_and_cache_weather_data()

            # Update both labels with cached data
            self._update_label_text(self._label, self._label_content)
            self._update_label_text(self._label_alt, self._label_alt_content)
            
        except Exception as e:
            self._label.setText(self._label_content)
            self._label_alt.setText(self._label_alt_content)
            logging.exception(f"Failed to update label: {e}")

    def _update_label_text(self, label: QLabel, content: str):
        if not hasattr(self, '_cached_label_options'):
            self._cached_label_options = []

        formatted_content = content
        for option, value in self._cached_label_options:
            formatted_content = formatted_content.replace(option, str(value))
        label.setText(formatted_content)

    def _should_update_cache(self) -> bool:
        # Always return False to keep the cache forever
        return False

    def _fetch_and_cache_weather_data(self):
        weather_data = self.fetch_weather_data()
        self._cached_label_options = [
            ("{temp}", weather_data["temp"]),
            ("{icon}", weather_data["icon"]),
            ("{humidity}", weather_data["humidity"]),
            ("{temp_alt}", weather_data["temp_alt"])
        ]
        self._update_label()

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
            logging.info("Fetch weather data")
        except Exception as e:
            temp = 'N/A'
            temp_alt = f"{self.icons['default']} N/A"
            icon = self.icons["default"]
            logging.warning("Failed to retrieve weather info")

        if self.callback_left == "do_nothing":
            self.callback_left = f"exec cmd /c start {url}"

        return {"temp": temp, "humidity": humidity, "temp_alt": temp_alt, "icon": icon}

    def _build_weather_url(self) -> str:
        base_url = "https://weather.com/en-GB/weather/today/l/" if self.temp_format == "celsius" else "https://weather.com/weather/today/l/"
        url = base_url + self.location_id
        return url

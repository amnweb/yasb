import logging
from datetime import datetime
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel
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
        self.icons = icons  # Store the icons dictionary

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        # Create labels with placeholder text
        self._label = self._create_label("label", visible=False, placeholder="Loading...")  # Initially hidden
        self._label_alt = self._create_label("label alt", visible=False, placeholder="Loading...")  # Initially hidden

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "fetch_weather_data"

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("fetch_weather_data", self._fetch_and_update_weather_data)

        # Show the main label after initialization
        self._label.setVisible(True)
        # Start the timer after initial setup
        self.start_timer()

    def _create_label(self, css_class: str, visible=True, placeholder="") -> QLabel:
        label = QLabel(placeholder)
        label.setProperty("class", css_class)
        label.setVisible(visible)
        self.widget_layout.addWidget(label)
        return label

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
            # Replace placeholders with actual values
            label_text = self._label_content.format(
                temp=self.weather_data["temp"],
                icon=self.weather_data["icon"],
                humidity=self.weather_data["humidity"],
            )
            self._label.setText(label_text)
            self._label_alt.setText(self._label_alt_content)
        except Exception as e:
            logging.exception(f"Failed to update label: {e}")

    def _fetch_and_update_weather_data(self):
        # Run the fetch operation in a separate thread
        threading.Thread(target=self._fetch_weather_data).start()

    def _fetch_weather_data(self):
        weather_data = self.fetch_weather_data()
        # Directly update the label content without caching
        self.weather_data = {
            "temp": weather_data["temp"],
            "icon": weather_data["icon"],
            "humidity": weather_data["humidity"],
        }
        self._label_alt_content = weather_data["temp_alt"]
        # Update the label on the main thread
        self._update_label()

    def fetch_weather_data(self) -> dict:
        try:
            url = self._build_weather_url()
            html_data = PyQuery(url=url)

            temp = html_data("span[data-testid='TemperatureValue']").eq(0).text()
            temp_min = (html_data("div[class*='CurrentConditions--tempHiLoValue--'] > span[data-testid='TemperatureValue']").eq(1).text())
            temp_max = (html_data("div[class*='CurrentConditions--tempHiLoValue--'] > span[data-testid='TemperatureValue']").eq(0).text())
            humidity = (html_data("div[data-testid='wxData'] > span[data-testid='PercentageValue']").eq(0).text())
            temp_alt = f"Day {temp_max} • Night {temp_min} • Humidity {humidity}"

            status_code = (html_data("#regionHeader").attr("class").split(" ")[2].split("-")[2])
            icon = self.icons.get(status_code, self.icons["default"])
            logging.info(f"Fetched new weather data at {datetime.now()}")
        except Exception as e:
            temp = "N/A"
            humidity = "N/A"
            temp_alt = f"{self.icons['default']} N/A"
            icon = self.icons["default"]
            logging.warning("Failed to retrieve weather info")
            # logging.exception(e)

        if self.callback_left == "do_nothing":
            self.callback_left = f"exec cmd /c start {url}"

        return {"temp": temp, "humidity": humidity, "temp_alt": temp_alt, "icon": icon}

    def _build_weather_url(self) -> str:
        base_url = ("https://weather.com/en-GB/weather/today/l/" if self.temp_format == "celsius" else "https://weather.com/weather/today/l/")
        url = base_url + self.location_id
        return url

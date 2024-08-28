import json
import logging
import re
import urllib.request
import urllib.parse
import threading
from datetime import datetime
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

class WeatherWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            update_interval: int,
            hide_decimal: bool,
            location: str,
            api_key: str,
            callbacks: dict[str, str],
            icons: dict[str, str]
    ):
        super().__init__((update_interval * 1000), class_name="weather-widget")
        self._label_content = label
        self._label_alt_content = label_alt
        self._location = location
        self._hide_decimal = hide_decimal
        self._icons = icons
        self._api_key = api_key
        self.api_url = f"http://api.weatherapi.com/v1/forecast.json?key={self._api_key}&q={urllib.parse.quote(self._location)}&days=1&aqi=no&alerts=no"
        
        # Store weather data
        self.weather_data = None
        self._show_alt_label = False
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"
        
        self.callback_timer = "fetch_weather_data"
        self.register_callback("fetch_weather_data", self.fetch_weather_data)       
        # Start the timer after initializing everything
        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label(update_class=False)

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
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
                    label.setText("weather update...")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
            return widgets
        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)
        
    def _reload_css(self,label: QLabel):
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()
        
    def _update_label(self,update_class=True):
        if self.weather_data is None:
            logging.warning("Weather data is not yet available.")
            return
        active_widgets = self._show_alt_label and self._widgets_alt or self._widgets
        active_label_content = self._show_alt_label and self._label_alt_content or self._label_content
        label_parts = re.split(r'(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
 
        widget_index = 0
        try:
            for part in label_parts:
                part = part.strip()
                for option, value in self.weather_data.items():
                    part = part.replace(option, str(value))
                if not part or widget_index >= len(active_widgets):
                    continue
                if isinstance(active_widgets[widget_index], QLabel):
                    if '<span' in part and '</span>' in part:
                        icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                        icon = self._icons.get(icon, self._icons["default"])
                        active_widgets[widget_index].setText(icon)
                        if update_class:
                        # Retrieve current class and append new class based on weather conditions
                            current_class = active_widgets[widget_index].property("class") or ""
                            append_class_icon = self.weather_data.get('{icon_class}', "")
                            # Create the new class string
                            new_class = f"{current_class} {append_class_icon}"
                            active_widgets[widget_index].setProperty("class", new_class)
                            # Update css
                            self._reload_css(active_widgets[widget_index])
                    else:
                        active_widgets[widget_index].setText(part)
                    if not active_widgets[widget_index].isVisible():
                        active_widgets[widget_index].show()
                    widget_index += 1
        except Exception as e:
            logging.exception(f"Failed to update label: {e}")

    def fetch_weather_data(self):
        # Start a new thread to fetch weather data
        threading.Thread(target=self._get_weather_data).start()

    def _get_weather_data(self):
        self.weather_data = self.get_weather_data(self.api_url)
        QTimer.singleShot(0, self._update_label)
        
    def get_weather_data(self, api_url):
        logging.info(f"Fetched new weather data at {datetime.now()}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
                'Cache-Control': 'no-cache',
                'Referer': 'http://google.com'
            }
            request = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(request) as response:
                weather_data = json.loads(response.read())
                current = weather_data['current']
                forecast = weather_data['forecast']['forecastday'][0]['day']
                def format_temp(temp, unit):
                    return f'{int(temp) if self._hide_decimal else temp}°{unit}'
                conditions_data = current['condition']['text']
                conditions_code = current['condition']['code']
                 
                if conditions_code in {1063,1180,1183,1186,1189,1192,1195,1198,1201,1240,1243,1246,1273,1276,1279}:
                    conditions_data = "rainy"
                    
                if conditions_code in {1003}:
                    conditions_data = "cloudy"
                    
                if conditions_code in {1114,1210,1213,1219,1222,1225,1237,1255,1258,1261,1264,1246,1282}:
                    conditions_data = "snowyIcy"
                icon_string = f"{conditions_data}{'Day' if current['is_day'] == 1 else 'Night'}".strip()
                return {
                    '{temp_c}': format_temp(current['temp_c'], 'C'),
                    '{min_temp_c}': format_temp(forecast['mintemp_c'], 'C'),
                    '{max_temp_c}': format_temp(forecast['maxtemp_c'], 'C'),
                    '{temp_f}': format_temp(current['temp_f'], 'F'),
                    '{min_temp_f}': format_temp(forecast['mintemp_f'], 'F'),
                    '{max_temp_f}': format_temp(forecast['maxtemp_f'], 'F'),
                    '{location}': weather_data['location']['name'],
                    '{humidity}': f"{current['humidity']}%",
                    '{is_day}': current['is_day'],
                    '{icon}': icon_string[0].lower() + icon_string[1:],
                    '{icon_class}': icon_string[0].lower() + icon_string[1:],
                    '{conditions}': conditions_data
                }
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            logging.error(f"Error occurred: {e}")
            return {
                '{temp_c}': 'N/A',
                '{min_temp_c}': 'N/A',
                '{max_temp_c}': 'N/A',
                '{temp_f}': 'N/A',
                '{min_temp_f}': 'N/A',
                '{max_temp_f}': 'N/A',
                '{location}': 'Unknown',
                '{humidity}': 'N/A',
                '{is_day}': 0,
                '{icon}': 'unknown',
                '{icon_class}': '',
                '{conditions}': 'No Data'
            }
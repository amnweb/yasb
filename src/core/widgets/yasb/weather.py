import json
import logging
import os
import re
import urllib.request
import urllib.parse
import threading
from datetime import datetime
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap
from core.utils.utilities import PopupWidget
from core.utils.widgets.animation_manager import AnimationManager
from settings import DEBUG

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
            units: str,
            show_alerts: bool,
            weather_card: dict[str, str],
            callbacks: dict[str, str],
            icons: dict[str, str],
            container_padding: dict[str, int],
            animation: dict[str, str]
    ):
        super().__init__((update_interval * 1000), class_name="weather-widget")
        self._label_content = label
        self._label_alt_content = label_alt
        self._location = location if location != 'env' else os.getenv('YASB_WEATHER_LOCATION')
        self._hide_decimal = hide_decimal
        self._icons = icons
        self._api_key = api_key if api_key != 'env' else os.getenv('YASB_WEATHER_API_KEY')
        if not self._api_key or not self._location:
            logging.error("API key or location is missing. Please provide a valid API key and location.")
            self.hide()
            return
        self.api_url = f"http://api.weatherapi.com/v1/forecast.json?key={self._api_key}&q={urllib.parse.quote(self._location)}&days=3&aqi=no&alerts=yes"
        self._units = units
        self._show_alerts = show_alerts
        self._padding = container_padding
        # Store weather data
        self.weather_data = None
        self._show_alt_label = False
        self._animation = animation
        self._weather_card = weather_card
        self._icon_cache = dict()

        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_card", self._toggle_card)
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
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label(update_class=False)

    def _toggle_card(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._popup_card()

            
    def _popup_card(self):
        if self.weather_data is None:
            logging.warning("Weather data is not yet available.")
            return

        self.dialog = PopupWidget(self, self._weather_card['blur'], self._weather_card['round_corners'], self._weather_card['round_corners_type'], self._weather_card['border_color'])
    
        self.dialog.setProperty("class", "weather-card")
        self.dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.dialog.setWindowFlag(Qt.WindowType.Popup)
        self.dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
 

        main_layout = QVBoxLayout()
        frame_today = QWidget()
        frame_today.setProperty("class", "weather-card-today")
        layout_today = QVBoxLayout(frame_today)
        
        today_label0 = QLabel(f"{self.weather_data['{location}']} {self.weather_data['{temp}']}")
        today_label0.setProperty("class", "label location")
        today_label0.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        today_label1 = QLabel(f"Feels like {self.weather_data['{feelslike}']} - {self.weather_data['{condition_text}']} - Humidity {self.weather_data['{humidity}']}\nPressure {self.weather_data['{pressure}']} - Visibility {self.weather_data['{vis}']} - Cloud {self.weather_data['{cloud}']}%")
        today_label1.setProperty("class", "label")
        today_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        today_label2 = QLabel(
            f"{self.weather_data['{alert_title}']}"
            f"{'<br>Alert expires ' + self.weather_data['{alert_end_date}'] if self.weather_data['{alert_end_date}'] else ''}"
            f"<br>{self.weather_data['{alert_desc}']}"
        )
        today_label2.setProperty("class", "label arert")
        today_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_label2.setWordWrap(True)
        
        
        layout_today.addWidget(today_label0)
        layout_today.addWidget(today_label1)
        if self._show_alerts and self.weather_data['{alert_title}'] and self.weather_data['{alert_desc}']:
            layout_today.addWidget(today_label2)
 
        # Create frames for each day
        frame_day0 = QWidget()
        frame_day0.setProperty("class", "weather-card-day")
        frame_day1 = QWidget()
        frame_day1.setProperty("class", "weather-card-day")
        frame_day2 = QWidget()
        frame_day2.setProperty("class", "weather-card-day")
 
        # Create layouts for frames
        layout_day0 = QHBoxLayout(frame_day0)
        layout_day1 = QHBoxLayout(frame_day1)
        layout_day2 = QHBoxLayout(frame_day2)

        # Day 0
        row_day0_label = QLabel(f"Today\nMin: {self.weather_data['{min_temp}']}\nMax: {self.weather_data['{max_temp}']}")
        row_day0_label.setProperty("class", "label")
        row_day0_icon_label = QLabel()
        try:
            if (self.weather_data['{day0_icon}']) in self._icon_cache:
                icon_data_day0 = self._icon_cache[self.weather_data['{day0_icon}']]
            else:
                icon_data_day0 = urllib.request.urlopen(self.weather_data['{day0_icon}'], timeout=2).read()
            pixmap_day0 = QPixmap()
            pixmap_day0.loadFromData(icon_data_day0)
            scaled_pixmap_day0 = pixmap_day0.scaledToHeight(self._weather_card['icon_size'], Qt.TransformationMode.SmoothTransformation)
            row_day0_icon_label.setPixmap(scaled_pixmap_day0)
            self._icon_cache[self.weather_data['{day0_icon}']] = icon_data_day0
        except:
            logging.warning("Could not load day0 icon")

        # Add widgets to frame layouts
        layout_day0.addWidget(row_day0_label)
        layout_day0.addWidget(row_day0_icon_label)

        # Day 1
        row_day1_label = QLabel(f"{self.weather_data['{day1_name}']}\nMin: {self.weather_data['{day1_min_temp}']}\nMax: {self.weather_data['{day1_max_temp}']}")
        row_day1_label.setProperty("class", "label")
        row_day1_icon_label = QLabel()
        try:
            if (self.weather_data['{day1_icon}']) in self._icon_cache:
                icon_data_day1 = self._icon_cache[self.weather_data['{day1_icon}']]
            else:
                icon_data_day1 = urllib.request.urlopen(self.weather_data['{day1_icon}'], timeout=2).read()
            pixmap_day1 = QPixmap()
            pixmap_day1.loadFromData(icon_data_day1)
            scaled_pixmap_day1 = pixmap_day1.scaledToHeight(self._weather_card['icon_size'], Qt.TransformationMode.SmoothTransformation)
            row_day1_icon_label.setPixmap(scaled_pixmap_day1)
            self._icon_cache[self.weather_data['{day1_icon}']] = icon_data_day1
        except:
            logging.warning("Could not load day1 icon")

        layout_day1.addWidget(row_day1_label)
        layout_day1.addWidget(row_day1_icon_label)

        # Day 2
        row_day2_label = QLabel(f"{self.weather_data['{day2_name}']}\nMin: {self.weather_data['{day2_min_temp}']}\nMax: {self.weather_data['{day2_max_temp}']}")
        row_day2_label.setProperty("class", "label")
        row_day2_icon_label = QLabel()
        try:
            if (self.weather_data['{day2_icon}']) in self._icon_cache:
                icon_data_day2 = self._icon_cache[self.weather_data['{day2_icon}']]
            else:
                icon_data_day2 = urllib.request.urlopen(self.weather_data['{day2_icon}'], timeout=2).read()
            pixmap_day2 = QPixmap()
            pixmap_day2.loadFromData(icon_data_day2)
            scaled_pixmap_day2 = pixmap_day2.scaledToHeight(self._weather_card['icon_size'], Qt.TransformationMode.SmoothTransformation)
            row_day2_icon_label.setPixmap(scaled_pixmap_day2)
            self._icon_cache[self.weather_data['{day2_icon}']] = icon_data_day2
        except:
            logging.warning("Could not load day2 icon")

        layout_day2.addWidget(row_day2_label)
        layout_day2.addWidget(row_day2_icon_label)

        # Create days layout and add frames
        days_layout = QHBoxLayout()
        days_layout.addWidget(frame_day0)
        days_layout.addWidget(frame_day1)
        days_layout.addWidget(frame_day2)

        # Add the "Current" label on top, days on bottom
        main_layout.addWidget(frame_today)
        main_layout.addLayout(days_layout)

        self.dialog.setLayout(main_layout)
        
 
        # Position the dialog 
        self.dialog.adjustSize()
        widget_global_pos = self.mapToGlobal(QPoint(0, self.height() + self._weather_card['distance']))
        if self._weather_card['direction'] == 'up':
            global_y = self.mapToGlobal(QPoint(0, 0)).y() - self.dialog.height() - self._weather_card['distance']
            widget_global_pos = QPoint(self.mapToGlobal(QPoint(0, 0)).x(), global_y)

        if self._weather_card['alignment'] == 'left':
            global_position = widget_global_pos
        elif self._weather_card['alignment'] == 'right':
            global_position = QPoint(
                widget_global_pos.x() + self.width() - self.dialog.width(),
                widget_global_pos.y()
            )
        elif self._weather_card['alignment'] == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (self.width() - self.dialog.width()) // 2,
                widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos
        
        self.dialog.move(global_position)
        self.dialog.show() 
        


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
                label.setCursor(Qt.CursorShape.PointingHandCursor)
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
        # if DEBUG:
        #     logging.debug(f"Weather data: {self.weather_data}")
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


    def _format_date_string(self, date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d")
    
    def _format_alert_datetime(self, iso_datetime):
        if iso_datetime is None:
            return "Unknown"
        dt = datetime.fromisoformat(iso_datetime)
        return dt.strftime("%B %d, %Y at %H:%M")

    def _format_temp(self, temp_f, temp_c):
        temp = temp_f if self._units == 'imperial' else temp_c
        value = int(temp) if self._hide_decimal else temp
        unit = '°F' if self._units == 'imperial' else '°C'
        return f"{value}{unit}"

    def _format_measurement(self, imperial_val, imperial_unit, metric_val, metric_unit):
        if self._units == 'imperial':
            return f"{imperial_val} {imperial_unit}"
        return f"{metric_val} {metric_unit}"
    
    def fetch_weather_data(self):
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
                alerts = weather_data['alerts']
                current = weather_data['current']
                forecast = weather_data['forecast']['forecastday'][0]['day']
                forecast1 = weather_data['forecast']['forecastday'][1]
                forecast2 = weather_data['forecast']['forecastday'][2]

                conditions_data = current['condition']['text']
                conditions_code = current['condition']['code']
                 
                if conditions_code in {1063,1180,1183,1186,1189,1192,1195,1198,1201,1240,1243,1246,1273,1276,1279}:
                    conditions_data = "rainy"
                    
                if conditions_code in {1003}:
                    conditions_data = "cloudy"
                    
                if conditions_code in {1114,1210,1213,1219,1222,1225,1237,1255,1258,1261,1264,1246,1282}:
                    conditions_data = "snowyIcy"
                icon_string = f"{conditions_data}{'Day' if current['is_day'] == 1 else 'Night'}".strip()

                # Load icons into cache for current and future forecasts if not already cached
                # We will try to load the images for 1sec, if it fails we will try again when popup is opened
                img_icon_keys = [f'http:{day["condition"]["icon"]}' for day in [forecast] + [forecast1["day"], forecast2["day"]]]
                for key in img_icon_keys:
                    if key not in self._icon_cache:
                        try:
                            with urllib.request.urlopen(key, timeout=1) as icon_response:
                                self._icon_cache[key] = icon_response.read()
                        except urllib.error.URLError as e:
                            logging.warning(f"Could not load icon {key}: {e}")
                        except Exception as e:
                            logging.warning(f"An unexpected error occurred while loading icon {key}: {e}")

                return {
                    # Current conditions
                    '{temp}':      self._format_temp(current['temp_f'], current['temp_c']),
                    '{feelslike}': self._format_temp(current['feelslike_f'], current['feelslike_c']),
                    '{humidity}':  f"{current['humidity']}%",
                    '{cloud}':     current['cloud'],
                    
                    # Forecast today
                    '{min_temp}':  self._format_temp(forecast['mintemp_f'], forecast['mintemp_c']),
                    '{max_temp}':  self._format_temp(forecast['maxtemp_f'], forecast['maxtemp_c']),
                    
                    # Location and conditions
                    '{location}':       weather_data['location']['name'],
                    '{location_region}': weather_data['location']['region'],
                    '{location_country}': weather_data['location']['country'],
                    '{time_zone}':      weather_data['location']['tz_id'],
                    '{localtime}':      weather_data['location']['localtime'],
                    '{conditions}':     conditions_data,
                    '{condition_text}': current['condition']['text'],
                    '{is_day}':        current['is_day'],
                    
                    # Icons
                    '{icon}':       icon_string[0].lower() + icon_string[1:],
                    '{icon_class}': icon_string[0].lower() + icon_string[1:],
                    '{day0_icon}':  f'http:{forecast["condition"]["icon"]}',
                    
                    # Wind data
                    '{wind}':        self._format_measurement(current['wind_mph'], 'mph', current['wind_kph'], 'km/h'),
                    '{wind_dir}':    current['wind_dir'],
                    '{wind_degree}': current['wind_degree'],
                    
                    # Other measurements
                    '{pressure}': self._format_measurement(current['pressure_in'], 'in', current['pressure_mb'], 'mb'),
                    '{precip}':   self._format_measurement(current['precip_in'], 'in', current['precip_mm'], 'mm'),
                    '{vis}':      self._format_measurement(current['vis_miles'], 'mi', current['vis_km'], 'km'),
                    '{uv}':       current['uv'],
                    
                    # Future forecasts
                    '{day1_name}':     self._format_date_string(forecast1['date']),
                    '{day1_min_temp}': self._format_temp(forecast1['day']['mintemp_f'], forecast1['day']['mintemp_c']),
                    '{day1_max_temp}': self._format_temp(forecast1['day']['maxtemp_f'], forecast1['day']['maxtemp_c']),
                    '{day1_icon}':     f'http:{forecast1["day"]["condition"]["icon"]}',
                    
                    '{day2_name}':     self._format_date_string(forecast2['date']),
                    '{day2_min_temp}': self._format_temp(forecast2['day']['mintemp_f'], forecast2['day']['mintemp_c']),
                    '{day2_max_temp}': self._format_temp(forecast2['day']['maxtemp_f'], forecast2['day']['maxtemp_c']),
                    '{day2_icon}':     f'http:{forecast2["day"]["condition"]["icon"]}',
                    
                    # Alerts
                    '{alert_title}':    alerts['alert'][0]['headline'] if alerts['alert'] and alerts['alert'][0]['headline'] else None,
                    '{alert_desc}':     alerts['alert'][0]['desc'] if alerts['alert'] and alerts['alert'][0]['desc'] else None,
                    '{alert_end_date}':    self._format_alert_datetime(alerts['alert'][0]['expires']) if alerts['alert'] and alerts['alert'][0]['expires'] else None,
                }
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            logging.error(f"Error fetching weather data: {e}")
            return {
                '{temp}': 'N/A',
                '{min_temp}': 'N/A',
                '{max_temp}': 'N/A',
                '{location}': 'N/A',
                '{location_region}': 'N/A',
                '{location_country}': 'N/A',
                '{time_zone}': 'N/A',
                '{localtime}': 'N/A,',
                '{humidity}': 'N/A',
                '{is_day}': 'N/A',
                '{day0_icon}': 'N/A',
                '{icon}': 'N/A',
                '{icon_class}': 'N/A',
                '{conditions}': 'N/A',
                '{condition_text}': 'N/A',
                '{wind}': 'N/A',
                '{wind_dir}': 'N/A',
                '{wind_degree}': 'N/A',
                '{pressure}': 'N/A',
                '{precip}': 'N/A',
                '{uv}': 'N/A',
                '{vis}': 'N/A',
                '{cloud}': 'N/A',
                '{feelslike}': 'N/A',
                '{day1_name}': 'N/A',
                '{day1_min_temp}': 'N/A',
                '{day1_max_temp}': 'N/A',
                '{day1_icon}': 'N/A',
                '{day2_name}': 'N/A',
                '{day2_min_temp}': 'N/A',
                '{day2_max_temp}': 'N/A',
                '{day2_icon}': 'N/A',
                '{alert_title}': None,
                '{alert_desc}': None,
                '{alert_end_date}': None
            }
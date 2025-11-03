import logging
import os
import re
import traceback
import urllib.parse
from datetime import datetime
from functools import partial
from typing import Any

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.weather.api import IconFetcher, WeatherDataFetcher
from core.utils.widgets.weather.widgets import (
    ClickableWidget,
    HourlyData,
    HourlyTemperatureLineWidget,
    HourlyTemperatureScrollArea,
)
from core.validation.widgets.yasb.weather import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class WeatherWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        update_interval: int,
        hide_decimal: bool,
        location: str,
        api_key: str,
        units: str,
        show_alerts: bool,
        weather_card: dict[str, str],
        callbacks: dict[str, str],
        tooltip: bool,
        icons: dict[str, str],
        container_padding: dict[str, int],
        animation: dict[str, str],
        label_shadow: dict[str, Any],
        container_shadow: dict[str, Any],
    ):
        super().__init__(class_name=f"weather-widget {class_name}")
        self._label_content = label
        self._label_alt_content = label_alt
        self._location = location if location != "env" else os.getenv("YASB_WEATHER_LOCATION")
        self._hide_decimal = hide_decimal
        self._icons = icons
        self._tooltip = tooltip
        self._api_key = api_key if api_key != "env" else os.getenv("YASB_WEATHER_API_KEY")
        if not self._api_key or not self._location:
            logging.error("API key or location is missing. Please provide a valid API key and location.")
            self.hide()
            return

        self._api_url = f"http://api.weatherapi.com/v1/forecast.json?key={self._api_key}&q={urllib.parse.quote(self._location)}&days=3&aqi=no&alerts=yes"

        # Create network manager, request and timer
        self._weather_fetcher = WeatherDataFetcher.get_instance(self, QUrl(self._api_url), update_interval * 1000)
        self._weather_fetcher.finished.connect(self.process_weather_data)
        self._weather_fetcher.finished.connect(lambda *_: self._update_label(True))
        self._icon_fetcher = IconFetcher.get_instance(self)

        # Retry timer
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._weather_fetcher.make_request)

        # Set weather data formatting
        self._units = units
        self._show_alerts = show_alerts
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        # Store weather data
        self._weather_data: dict[str, Any] | None = None
        self._hourly_data_today: list[dict[str, Any]] = []
        self._hourly_data_2: list[dict[str, Any]] = []
        self._hourly_data_3: list[dict[str, Any]] = []
        self._current_time: datetime | None = None
        self._show_alt_label = False
        self._animation = animation
        self._weather_card: dict[str, Any] = weather_card
        self._weather_card_daily_widgets: list[ClickableWidget] = []

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"],
            self._padding["top"],
            self._padding["right"],
            self._padding["bottom"],
        )

        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_card", self._toggle_card)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        if not self._weather_fetcher.started:
            self._weather_fetcher.start()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])  # type: ignore
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label(update_class=False)

    def _toggle_card(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])  # type: ignore
        self._popup_card()

    def _popup_card(self):
        if self._weather_data is None:
            logging.warning("Weather data is not yet available.")
            return

        self.dialog = PopupWidget(
            self,
            self._weather_card["blur"],
            self._weather_card["round_corners"],
            self._weather_card["round_corners_type"],
            self._weather_card["border_color"],
        )
        self.dialog.setProperty("class", "weather-card")

        main_layout = QVBoxLayout()
        frame_today = QWidget()
        frame_today.setProperty("class", "weather-card-today")
        layout_today = QVBoxLayout(frame_today)

        today_label0 = QLabel(f"{self._weather_data['{location}']} {self._weather_data['{temp}']}")
        today_label0.setProperty("class", "label location")
        today_label0.setAlignment(Qt.AlignmentFlag.AlignCenter)

        today_label1 = QLabel(
            f"Feels like {self._weather_data['{feelslike}']} - {self._weather_data['{condition_text}']} - Humidity {self._weather_data['{humidity}']}\nPressure {self._weather_data['{pressure}']} - Visibility {self._weather_data['{vis}']} - Cloud {self._weather_data['{cloud}']}%"
        )
        today_label1.setProperty("class", "label")
        today_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        today_label2 = QLabel(
            f"{self._weather_data['{alert_title}']}"
            f"{'<br>Alert expires ' + self._weather_data['{alert_end_date}'] if self._weather_data['{alert_end_date}'] else ''}"
            f"<br>{self._weather_data['{alert_desc}']}"
        )
        today_label2.setProperty("class", "label alert")
        today_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_label2.setWordWrap(True)

        layout_today.addWidget(today_label0)
        layout_today.addWidget(today_label1)
        if self._show_alerts and self._weather_data["{alert_title}"] and self._weather_data["{alert_desc}"]:
            layout_today.addWidget(today_label2)

        # Create hourly layout and add frames (before the daily widget to pass it to press event)
        hourly_temperature_widget = HourlyTemperatureLineWidget(
            units=self._units,
            config=self._weather_card,
        )
        hourly_temperature_widget.setProperty("class", "hourly-data")
        hourly_temperature_scroll_area = HourlyTemperatureScrollArea()
        hourly_temperature_scroll_area.setWidget(hourly_temperature_widget)

        # NOTE: # This is needed for Qt >=6.10.0 because QScrollArea
        # refuses to play nicely with background color and border styles
        hourly_container_wrapper = QFrame()
        hourly_container_wrapper_layout = QHBoxLayout()
        hourly_container_wrapper.setLayout(hourly_container_wrapper_layout)
        hourly_container_wrapper_layout.addWidget(hourly_temperature_scroll_area)
        hourly_container_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        hourly_container_wrapper.setProperty("class", "hourly-container")

        @pyqtSlot(int)
        def switch_hourly_data(day_idx: int):
            combined_data = []
            current_time = None
            if day_idx == 0:
                combined_data = self._hourly_data_today + self._hourly_data_2
                current_time = self._current_time
            elif day_idx == 1:
                combined_data = self._hourly_data_2
                current_time = None
            elif day_idx == 2:
                combined_data = self._hourly_data_3
                current_time = None
            else:
                raise ValueError(f"Invalid day index: {day_idx}")
            parsed_data: list[HourlyData] = []
            for h in combined_data:
                temp = h["temp_c"] if self._units == "metric" else h["temp_f"]
                if self._hide_decimal:
                    temp = round(temp)
                parsed_data.append(
                    HourlyData(
                        temp=temp,
                        wind=h["wind_kph"] if self._units == "metric" else h["wind_mph"],
                        icon_url=f"http:{h['condition']['icon']}",
                        time=datetime.strptime(h["time"], "%Y-%m-%d %H:%M"),
                    )
                )
            hourly_temperature_widget.update_weather(parsed_data, current_time)
            for i, w in enumerate(self._weather_card_daily_widgets):
                if i == day_idx:
                    w.setProperty("class", "weather-card-day active")
                else:
                    w.setProperty("class", "weather-card-day")

        # Create frames for each day
        day_widgets: list[QWidget] = []
        failed_icons: list[tuple[QLabel, str]] = []
        self._weather_card_daily_widgets = []
        for i in range(3):
            frame_day = ClickableWidget()
            self._weather_card_daily_widgets.append(frame_day)
            if self._hourly_data_today and self._weather_card["show_hourly_forecast"]:
                frame_day.clicked.connect(partial(switch_hourly_data, i))
            frame_day.setProperty("class", "weather-card-day")
            if i == 0:
                name = "Today"
                min_temp = self._weather_data["{min_temp}"]
                max_temp = self._weather_data["{max_temp}"]
            else:
                name = self._weather_data[f"{{day{i}_name}}"]
                min_temp = self._weather_data[f"{{day{i}_min_temp}}"]
                max_temp = self._weather_data[f"{{day{i}_max_temp}}"]
            row_day_label = QLabel(f"{name}\nMin: {min_temp}\nMax: {max_temp}", frame_day)
            row_day_label.setProperty("class", "label")

            # Create the icon label and pixmap
            row_day_icon_label = QLabel(frame_day)
            icon_url = self._weather_data[f"{{day{i}_icon}}"]
            icon_data_day = self._icon_fetcher.get_icon(icon_url)
            if bool(icon_data_day):
                self._set_pixmap(row_day_icon_label, icon_data_day)
            else:
                failed_icons.append((row_day_icon_label, icon_url))
            # Add widgets to frame layouts
            layout_day = QHBoxLayout()
            frame_day.setLayout(layout_day)
            layout_day.addWidget(row_day_label)
            layout_day.addWidget(row_day_icon_label)
            day_widgets.append(frame_day)

        # Create days layout and add frames
        days_layout = QHBoxLayout()
        for widget in day_widgets:
            days_layout.addWidget(widget)

        switch_hourly_data(0)

        # Add the "Current" label on top, days on bottom
        main_layout.addWidget(frame_today)
        main_layout.addLayout(days_layout)

        # If we have no data just don't add the widget at all
        if self._hourly_data_today and self._weather_card["show_hourly_forecast"]:
            main_layout.addWidget(hourly_container_wrapper)

        self.dialog.setLayout(main_layout)

        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._weather_card["alignment"],
            direction=self._weather_card["direction"],
            offset_left=self._weather_card["offset_left"],
            offset_top=self._weather_card["offset_top"],
        )
        self.dialog.show()

        # Scroll to the current hour. Must be done after the window is shown.
        if hsb := hourly_temperature_scroll_area.horizontalScrollBar():
            hsb.setValue(self._weather_card["hourly_point_spacing"] // 2 - 5)

        # If any icons failed to load, try to fetch them again once
        if failed_icons:
            try:
                # Create a temporary icon fetcher to fetch the missing icons
                temp_icon_fetcher = IconFetcher(self.dialog)
                temp_icon_fetcher.fetch_icons([icon_url for _, icon_url in failed_icons])

                def update_failed_icons():
                    for label, icon_url in failed_icons:
                        # Update the cached icons
                        new_icon = temp_icon_fetcher.get_icon(icon_url)
                        if not bool(new_icon):
                            continue
                        self._icon_fetcher.set_icon(icon_url, new_icon)
                        self._set_pixmap(label, temp_icon_fetcher.get_icon(icon_url))
                    # Cleanup
                    temp_icon_fetcher.deleteLater()

                temp_icon_fetcher.finished.connect(update_failed_icons)  # type: ignore
            except Exception as e:
                logging.debug(f"Failed to update weather card icons: {e}")

    def _set_pixmap(self, label: QLabel, icon_bytes: bytes):
        """Set the pixmap for the day icon label."""
        pixmap = QPixmap()
        pixmap.loadFromData(icon_bytes)
        dpr = label.devicePixelRatioF()
        pixmap.setDevicePixelRatio(dpr)
        scaled_pixmap_day = pixmap.scaledToHeight(
            self._weather_card["icon_size"], Qt.TransformationMode.SmoothTransformation
        )
        label.setPixmap(scaled_pixmap_day)

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content: str, is_alt: bool = False) -> list[QLabel]:
            label_parts = re.split("(<span.*?>.*?</span>)", content)
            label_parts = [part for part in label_parts if part]
            widgets: list[QLabel] = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.hide()
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label alt" if is_alt else "label")
                    label.setText("weather update...")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                add_shadow(label, self._label_shadow)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _reload_css(self, label: QLabel):
        refresh_widget_style(label)
        label.update()

    @pyqtSlot(bool)
    def _update_label(self, update_class: bool = True):
        if self._weather_data is None:
            logging.warning("Weather data is not yet available.")
            return

        active_widgets = self._show_alt_label and self._widgets_alt or self._widgets
        active_label_content = self._show_alt_label and self._label_alt_content or self._label_content
        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        if self._tooltip:
            set_tooltip(
                self,
                f"{self._weather_data['{location}']}\nMin {self._weather_data['{min_temp}']}\nMax {self._weather_data['{max_temp}']}",
            )

        widget_index = 0

        try:
            for part in label_parts:
                part = part.strip()
                for option, value in self._weather_data.items():
                    part = part.replace(option, str(value))
                if not part or widget_index >= len(active_widgets):
                    continue
                if "<span" in part and "</span>" in part:
                    icon_name = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(self._icons.get(icon_name, icon_name))
                    if update_class:
                        # Retrieve current class and append new class based on weather conditions
                        current_class = active_widgets[widget_index].property("class") or ""
                        append_class_icon = self._weather_data.get("{icon_class}", "")
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

    def _format_date_string(self, date_str: str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d")

    def _format_alert_datetime(self, iso_datetime: str | None):
        if iso_datetime is None:
            return "Unknown"
        dt = datetime.fromisoformat(iso_datetime)
        return dt.strftime("%B %d, %Y at %H:%M")

    def _format_temp(self, temp_f: float, temp_c: float) -> str:
        temp = temp_f if self._units == "imperial" else temp_c
        unit = "°F" if self._units == "imperial" else "°C"
        value = round(temp) if self._hide_decimal else temp
        return f"{value}{unit}"

    def _format_measurement(self, imperial_val: str, imperial_unit: str, metric_val: str, metric_unit: str) -> str:
        if self._units == "imperial":
            return f"{imperial_val} {imperial_unit}"
        return f"{metric_val} {metric_unit}"

    @pyqtSlot(dict)
    def process_weather_data(self, weather_data: dict[str, Any]):
        try:
            if not weather_data:
                raise Exception("Weather data is empty.")
            alerts = weather_data["alerts"]
            forecast = weather_data["forecast"]["forecastday"][0]["day"]
            forecast1 = weather_data["forecast"]["forecastday"][1]
            forecast2 = weather_data["forecast"]["forecastday"][2]

            self._hourly_data_today = weather_data["forecast"]["forecastday"][0]["hour"]
            self._hourly_data_2 = forecast1["hour"]
            self._hourly_data_3 = forecast2["hour"]
            self._current_time = datetime.strptime(weather_data["location"]["localtime"], "%Y-%m-%d %H:%M")
            all_hourly_data = self._hourly_data_today + self._hourly_data_2 + self._hourly_data_3

            current: dict[str, Any] = weather_data["current"]
            conditions_data = current["condition"]["text"]
            conditions_code = current["condition"]["code"]

            # Get the weather icon string and weather text based on the code and time of day
            weather_icon_string, weather_text = get_weather(conditions_code, current["is_day"])

            # Load icons images into cache for current and future forecasts if not already cached
            img_icon_keys = [
                f"http:{day['condition']['icon']}"
                for day in [forecast] + [forecast1["day"], forecast2["day"]] + all_hourly_data
            ]
            self._icon_fetcher.fetch_icons(list(set(img_icon_keys)))

            self._weather_data = {
                # Current conditions
                "{temp}": self._format_temp(current["temp_f"], current["temp_c"]),
                "{feelslike}": self._format_temp(current["feelslike_f"], current["feelslike_c"]),
                "{humidity}": f"{current['humidity']}%",
                "{cloud}": current["cloud"],
                # Forecast today
                "{min_temp}": self._format_temp(forecast["mintemp_f"], forecast["mintemp_c"]),
                "{max_temp}": self._format_temp(forecast["maxtemp_f"], forecast["maxtemp_c"]),
                # Location and conditions
                "{location}": weather_data["location"]["name"],
                "{location_region}": weather_data["location"]["region"],
                "{location_country}": weather_data["location"]["country"],
                "{time_zone}": weather_data["location"]["tz_id"],
                "{localtime}": weather_data["location"]["localtime"],
                "{conditions}": conditions_data,
                "{condition_text}": weather_text,
                "{is_day}": "Day" if current["is_day"] else "Night",
                # Icons
                "{icon}": weather_icon_string,
                "{icon_class}": weather_icon_string,
                "{day0_icon}": f"http:{forecast['condition']['icon']}",
                # Wind data
                "{wind}": self._format_measurement(current["wind_mph"], "mph", current["wind_kph"], "km/h"),
                "{wind_dir}": current["wind_dir"],
                "{wind_degree}": current["wind_degree"],
                # Other measurements
                "{pressure}": self._format_measurement(current["pressure_in"], "in", current["pressure_mb"], "mb"),
                "{precip}": self._format_measurement(current["precip_in"], "in", current["precip_mm"], "mm"),
                "{vis}": self._format_measurement(current["vis_miles"], "mi", current["vis_km"], "km"),
                "{uv}": current["uv"],
                # Future forecasts
                "{day1_name}": self._format_date_string(forecast1["date"]),
                "{day1_min_temp}": self._format_temp(forecast1["day"]["mintemp_f"], forecast1["day"]["mintemp_c"]),
                "{day1_max_temp}": self._format_temp(forecast1["day"]["maxtemp_f"], forecast1["day"]["maxtemp_c"]),
                "{day1_icon}": f"http:{forecast1['day']['condition']['icon']}",
                "{day2_name}": self._format_date_string(forecast2["date"]),
                "{day2_min_temp}": self._format_temp(forecast2["day"]["mintemp_f"], forecast2["day"]["mintemp_c"]),
                "{day2_max_temp}": self._format_temp(forecast2["day"]["maxtemp_f"], forecast2["day"]["maxtemp_c"]),
                "{day2_icon}": f"http:{forecast2['day']['condition']['icon']}",
                # Alerts
                "{alert_title}": alerts["alert"][0]["headline"]
                if alerts["alert"] and alerts["alert"][0]["headline"]
                else None,
                "{alert_desc}": alerts["alert"][0]["desc"] if alerts["alert"] and alerts["alert"][0]["desc"] else None,
                "{alert_end_date}": self._format_alert_datetime(alerts["alert"][0]["expires"])
                if alerts["alert"] and alerts["alert"][0]["expires"]
                else None,
            }
        except Exception as e:
            if not self._retry_timer.isActive():
                err = f"Error processing weather data: {e}. Retrying fetch in 10 seconds."
                if isinstance(e, (IndexError, KeyError, TypeError)):
                    err += f"\n{traceback.format_exc()}"
                logging.warning(err)
                self._retry_timer.start(10000)
            if self._weather_data is None:
                self._weather_data = {
                    "{temp}": "N/A",
                    "{min_temp}": "N/A",
                    "{max_temp}": "N/A",
                    "{location}": "N/A",
                    "{location_region}": "N/A",
                    "{location_country}": "N/A",
                    "{time_zone}": "N/A",
                    "{localtime}": "N/A",
                    "{humidity}": "N/A",
                    "{is_day}": "N/A",
                    "{day0_icon}": "N/A",
                    "{icon}": "N/A",
                    "{icon_class}": "N/A",
                    "{conditions}": "N/A",
                    "{condition_text}": "N/A",
                    "{wind}": "N/A",
                    "{wind_dir}": "N/A",
                    "{wind_degree}": "N/A",
                    "{pressure}": "N/A",
                    "{precip}": "N/A",
                    "{uv}": "N/A",
                    "{vis}": "N/A",
                    "{cloud}": "N/A",
                    "{feelslike}": "N/A",
                    "{day1_name}": "N/A",
                    "{day1_min_temp}": "N/A",
                    "{day1_max_temp}": "N/A",
                    "{day1_icon}": "N/A",
                    "{day2_name}": "N/A",
                    "{day2_min_temp}": "N/A",
                    "{day2_max_temp}": "N/A",
                    "{day2_icon}": "N/A",
                    "{alert_title}": None,
                    "{alert_desc}": None,
                    "{alert_end_date}": None,
                }


def get_weather(code: int, day: bool) -> tuple[str, str]:
    """Get the weather icon and text based on the weather code and time of day."""
    # fmt: off
    sunny_codes = {1000}
    cloudy_codes = {1003, 1006, 1009}
    foggy_codes = {1030, 1135, 1147}
    rainy_codes = {1063, 1150, 1153, 1180, 1183, 1186, 1189, 1192, 1195, 1240, 1243, 1246}
    snowy_codes = {1066, 1069, 1072, 1114, 1168, 1171, 1198, 1201, 1204, 1207, 1210, 1213, 1216, 1219, 1222, 1225, 1237, 1249, 1252, 1255, 1258, 1261, 1264}
    thunderstorm_codes = {1087, 1273, 1276, 1279, 1282}
    blizzard_codes = {1117}
    # fmt: on
    time = "Day" if day else "Night"
    if code in sunny_codes:
        if day:
            return "sunnyDay", "Sunny"
        return "clearNight", "Clear"
    if code in cloudy_codes:
        return f"cloudy{time}", "Cloudy"
    if code in foggy_codes:
        return f"foggy{time}", "Foggy"
    if code in rainy_codes:
        return f"rainy{time}", "Rainy"
    if code in snowy_codes:
        return f"snowy{time}", "Snowy"
    if code in thunderstorm_codes:
        return f"thunderstorm{time}", "Thunderstorm"
    if code in blizzard_codes:
        return f"blizzard{time}", "Blizzard"

    return "default", "Cloudy"

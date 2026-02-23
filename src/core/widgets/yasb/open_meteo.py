import logging
import re
import time
import traceback
from datetime import datetime
from functools import partial
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.open_meteo.api import GeocodingFetcher, OpenMeteoDataFetcher
from core.utils.widgets.open_meteo.icons import get_weather_icon
from core.utils.widgets.open_meteo.location import (
    get_widget_id,
    load_location,
    load_weather_cache,
    save_location,
    save_weather_cache,
)
from core.utils.widgets.open_meteo.widgets import (
    ClickableWidget,
    HourlyData,
    HourlyDataLineWidget,
    HourlyTemperatureScrollArea,
    render_svg_to_pixmap,
)
from core.validation.widgets.yasb.open_meteo import OpenMeteoWidgetConfig
from core.widgets.base import BaseWidget

logger = logging.getLogger("open_meteo")


class OpenMeteoWidget(BaseWidget):
    validation_schema = OpenMeteoWidgetConfig

    def __init__(self, config: OpenMeteoWidgetConfig):
        super().__init__(class_name=f"open-meteo-widget {config.class_name}")
        self.config = config
        self._label_content = config.label
        self._label_alt_content = config.label_alt

        # Weather state
        self._weather_data: dict[str, Any] | None = None
        self._has_valid_weather_data = False
        self._hourly_data: list[list[dict[str, Any]]] = [[] for _ in range(7)]
        self._current_time: datetime | None = None
        self._show_alt_label = False
        self._weather_card_daily_widgets: list[ClickableWidget] = []

        # Network
        self._weather_fetcher: OpenMeteoDataFetcher | None = None
        self._geocoding_fetcher: GeocodingFetcher | None = None

        # Location
        self._widget_id: str | None = None
        self._location_data: dict[str, Any] | None = None

        # Retry timer
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._retry_fetch)

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, config.container_shadow.model_dump())

        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_card", self._toggle_card)
        self.register_callback("update_label", self._update_label)

        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

        # Defer initialisation until screen_name and widget_name are set
        QTimer.singleShot(0, self._deferred_init)

    def _deferred_init(self):
        """Called after the framework has set screen_name / widget_name."""
        self._widget_id = get_widget_id(self)
        self._location_data = load_location(self._widget_id)

        if self._location_data:
            cached_data, last_updated_ms = load_weather_cache(self._widget_id)
            is_cache_valid = False

            if cached_data:
                time_diff_ms = int(time.time() * 1000) - last_updated_ms
                update_interval_ms = self.config.update_interval * 1000
                is_cache_valid = time_diff_ms < update_interval_ms

                # Load the cached data instantly to prevent "weather loading..." flash
                try:
                    self.process_weather_data(cached_data)
                    self._update_label(True)
                except Exception as e:
                    logger.warning(f"Failed to load cached weather data: {e}")
                    is_cache_valid = False

            # If the cache is fresh, start the delayed timer. Otherwise, start querying immediately.
            self._start_weather_fetcher(delayed=is_cache_valid)
        else:
            self._set_label_text("Setup location")
            logger.info(f"No saved location for {self._widget_id}. Awaiting user setup.")

    def _start_weather_fetcher(self, delayed: bool = False):
        """Start fetching weather data with saved coordinates."""
        if not self._location_data:
            return
        self._weather_fetcher = OpenMeteoDataFetcher(
            self,
            latitude=self._location_data["latitude"],
            longitude=self._location_data["longitude"],
            timeout=self.config.update_interval * 1000,
            units=self.config.units,
        )
        self._weather_fetcher.finished.connect(self.process_weather_data)
        self._weather_fetcher.finished.connect(lambda *_: self._update_label(True))
        self._weather_fetcher.finished.connect(self._save_weather_cache)
        self._weather_fetcher.start(delayed=delayed)

    def _save_weather_cache(self, data: dict[str, Any]):
        """Persist fresh API data to the local disk cache."""
        if data and self._widget_id:
            save_weather_cache(self._widget_id, data)

    def _retry_fetch(self):
        if self._weather_fetcher:
            self._weather_fetcher.make_request()

    def _toggle_label(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label(update_class=False)

    def _toggle_card(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._popup_card()

    def _popup_card(self):
        self.dialog = PopupWidget(
            self,
            self.config.weather_card.blur,
            self.config.weather_card.round_corners,
            self.config.weather_card.round_corners_type,
            self.config.weather_card.border_color,
        )
        self.dialog.setProperty("class", "open-meteo-card")

        # No location show setup UI
        if not self._location_data:
            self._show_location_setup()
            return

        # No weather data placeholder
        if self._weather_data is None or not self._has_valid_weather_data:
            self._show_placeholder()
            return

        # Full weather card
        self._build_weather_card()

    def _show_location_setup(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Setup Location")
        title.setProperty("class", "search-head")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel("Search for a location to set your weather widget")
        info.setProperty("class", "search-description")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search location...")
        search_input.setProperty("class", "search-input")
        search_input.setMinimumWidth(280)
        layout.addWidget(search_input)

        results_list = QListWidget()
        results_list.setProperty("class", "search-results")
        results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results_list.setVisible(False)
        layout.addWidget(results_list)

        # Store results for selection
        self._search_results: list[dict[str, Any]] = []

        # Create geocoding fetcher
        self._geocoding_fetcher = GeocodingFetcher(self.dialog)

        # Debounce timer for search
        debounce_timer = QTimer(self.dialog)
        debounce_timer.setSingleShot(True)
        debounce_timer.setInterval(400)

        def on_text_changed():
            debounce_timer.start()

        def do_search():
            query = search_input.text().strip()
            if len(query) >= 2:
                self._geocoding_fetcher.search(query)
            else:
                results_list.clear()
                results_list.setVisible(False)
                self.dialog.adjustSize()

        def on_results(results: list[dict[str, Any]]):
            self._search_results = results
            results_list.clear()
            if not results:
                results_list.setVisible(False)
                self.dialog.adjustSize()
                return
            for r in results:
                parts = [r.get("name", "Unknown")]
                if r.get("admin3"):
                    parts.append(r["admin3"])
                if r.get("admin2"):
                    parts.append(r["admin2"])
                if r.get("admin1"):
                    parts.append(r["admin1"])
                if r.get("country"):
                    parts.append(r["country"])
                item = QListWidgetItem(", ".join(parts))
                results_list.addItem(item)
            results_list.setVisible(True)
            # Resize dialog to accommodate the list
            self.dialog.adjustSize()

        def on_item_selected(item: QListWidgetItem):
            idx = results_list.row(item)
            if 0 <= idx < len(self._search_results):
                selected = self._search_results[idx]
                save_location(self._widget_id, selected)
                self._location_data = load_location(self._widget_id)
                self._set_label_text("Fetching data...")
                # Close the dialog and start fetching weather data
                self.dialog.hide()
                self._start_weather_fetcher()

        search_input.textChanged.connect(on_text_changed)
        debounce_timer.timeout.connect(do_search)
        self._geocoding_fetcher.results_ready.connect(on_results)
        results_list.itemClicked.connect(on_item_selected)

        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.weather_card.alignment,
            direction=self.config.weather_card.direction,
            offset_left=self.config.weather_card.offset_left,
            offset_top=self.config.weather_card.offset_top,
        )
        self.dialog.show()

    def _show_placeholder(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        icon_label = QLabel(self.config.icons.default)
        icon_label.setProperty("class", "no-data-icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_label = QLabel("Weather data not available")
        info_label.setProperty("class", "no-data-text")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_label)
        layout.addWidget(info_label)

        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.weather_card.alignment,
            direction=self.config.weather_card.direction,
            offset_left=self.config.weather_card.offset_left,
            offset_top=self.config.weather_card.offset_top,
        )
        self.dialog.show()

    def _build_weather_card(self):
        main_layout = QVBoxLayout()

        # Buttons container for temperature/rain/snow
        buttons_container = QFrame(self.dialog)
        buttons_container.setProperty("class", "hourly-data-buttons")
        buttons_container.setContentsMargins(0, 0, 0, 0)
        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_container.setLayout(buttons_layout)

        default_data_type = self.config.weather_card.hourly_forecast_buttons.default_view
        hourly_data_widget = HourlyDataLineWidget(
            units=self.config.units,
            config=self.config.weather_card.model_dump(),
            data_type=default_data_type,
        )
        hourly_scroll_area = HourlyTemperatureScrollArea()
        hourly_scroll_area.setWidget(hourly_data_widget)

        hourly_container_wrapper = QFrame()
        hourly_container_wrapper_layout = QHBoxLayout()
        hourly_container_wrapper.setLayout(hourly_container_wrapper_layout)
        hourly_container_wrapper_layout.addWidget(hourly_scroll_area)
        hourly_container_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        hourly_container_wrapper.setProperty("class", "hourly-container")

        # Create buttons if enabled
        buttons_config = self.config.weather_card.hourly_forecast_buttons
        if buttons_config.enabled and self.config.weather_card.show_hourly_forecast:
            button_configs = [
                ("temperature", buttons_config.temperature_icon),
                ("rain", buttons_config.rain_icon),
                ("snow", buttons_config.snow_icon),
            ]
            buttons: list[QLabel] = []

            for data_type, icon in button_configs:
                btn = QLabel(icon)
                btn.setProperty("class", f"hourly-data-button{' active' if data_type == default_data_type else ''}")
                btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                set_tooltip(btn, data_type.capitalize(), delay=400, position="top")
                buttons_layout.addWidget(btn)
                buttons.append(btn)

                def make_handler(dt: str, active_btn: QLabel):
                    def handler(ev: QMouseEvent | None):
                        hourly_data_widget.set_data_type(dt)
                        for b in buttons:
                            b.setProperty("class", f"hourly-data-button{' active' if b == active_btn else ''}")
                            refresh_widget_style(b)

                    return handler

                btn.mousePressEvent = make_handler(data_type, btn)

            buttons_layout.addStretch()

        # Today section
        frame_today = QWidget()
        frame_today.setProperty("class", "open-meteo-card-today")
        layout_today = QVBoxLayout(frame_today)

        today_label0 = QLabel(f"{self._weather_data['{location}']} {self._weather_data['{temp}']}")
        today_label0.setProperty("class", "label location")
        today_label0.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_label0.setCursor(Qt.CursorShape.PointingHandCursor)
        set_tooltip(today_label0, "Click to change location", delay=400, position="bottom")

        today_label0.mousePressEvent = self.reset_location

        # Sunrise/Sunset wrapper
        today_sunrise_sunset_container = QWidget()
        today_sunrise_sunset_container_layout = QHBoxLayout(today_sunrise_sunset_container)
        today_sunrise_sunset_container_layout.setContentsMargins(0, 0, 0, 0)
        today_sunrise_sunset_container_layout.setSpacing(4)
        today_sunrise_sunset_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sunrise_icon_label = QLabel(self.config.icons.sunnyDay)
        sunrise_icon_label.setProperty("class", "label sunrisesunset-icon")
        sunrise_text_label = QLabel(f"{self._weather_data.get('{sunrise}', 'N/A')}")
        sunrise_text_label.setProperty("class", "label sunrisesunset")

        sunset_icon_label = QLabel(self.config.icons.clearNight)
        sunset_icon_label.setProperty("class", "label sunrisesunset-icon")
        sunset_text_label = QLabel(f"{self._weather_data.get('{sunset}', 'N/A')}")
        sunset_text_label.setProperty("class", "label sunrisesunset")

        today_sunrise_sunset_container_layout.addWidget(sunrise_icon_label)
        today_sunrise_sunset_container_layout.addWidget(sunrise_text_label)
        today_sunrise_sunset_container_layout.addSpacing(16)
        today_sunrise_sunset_container_layout.addWidget(sunset_icon_label)
        today_sunrise_sunset_container_layout.addWidget(sunset_text_label)

        rain_c = self._weather_data.get("{rain_chance}", 0)
        snow_c = self._weather_data.get("{snow_chance}", 0)
        precip_parts = []
        if rain_c != "N/A" and isinstance(rain_c, (int, float)) and rain_c > 0:
            precip_parts.append(f"Rain chance {rain_c}%")
        if snow_c != "N/A" and isinstance(snow_c, (int, float)) and snow_c > 0:
            precip_parts.append(f"Snow chance {snow_c}%")

        if not precip_parts:
            precip_str = ""
        else:
            precip_str = " \u2022 ".join(precip_parts) + " \u2022 "

        today_label1 = QLabel(
            f"Feels like {self._weather_data['{feelslike}']} \u2022 "
            f"{self._weather_data['{condition_text}']} \u2022 "
            f"Humidity {self._weather_data['{humidity}']} \u2022 "
            f"Pressure {self._weather_data['{pressure}']}\n"
            f"Cloud {self._weather_data['{cloud}']}% \u2022 "
            f"{precip_str}"
            f"UV Index {self._weather_data['{uv}']}"
        )
        today_label1.setProperty("class", "label")
        today_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_today.addWidget(today_label0)
        layout_today.addWidget(today_sunrise_sunset_container)
        layout_today.addWidget(today_label1)

        # Switch hourly data by day
        @pyqtSlot(int)
        def switch_hourly_data(day_idx: int):
            if day_idx == 0:
                combined = self._hourly_data[0] + self._hourly_data[1]
                current_time = self._current_time
            elif 0 < day_idx < 7:
                combined = self._hourly_data[day_idx]
                current_time = None
            else:
                return

            parsed_data: list[HourlyData] = []
            for h in combined:
                temp = h["temperature_2m"]
                if self.config.hide_decimal:
                    temp = round(temp)
                parsed_data.append(
                    HourlyData(
                        temp=temp,
                        wind=h["wind_speed_10m"],
                        weather_code=h["weather_code"],
                        is_day=h.get("is_day", True),
                        time=datetime.strptime(h["time"], "%Y-%m-%dT%H:%M"),
                        precipitation_probability=h.get("precipitation_probability", 0),
                        humidity=h.get("relative_humidity_2m", 0),
                    )
                )
            hourly_data_widget.update_weather(parsed_data, current_time)
            for i, w in enumerate(self._weather_card_daily_widgets):
                if i == day_idx:
                    w.setProperty("class", "open-meteo-card-day active")
                else:
                    w.setProperty("class", "open-meteo-card-day")

        day_widgets: list[QWidget] = []
        self._weather_card_daily_widgets = []
        for i in range(7):
            frame_day = ClickableWidget()
            self._weather_card_daily_widgets.append(frame_day)
            if self._hourly_data[0] and self.config.weather_card.show_hourly_forecast:
                frame_day.clicked.connect(partial(switch_hourly_data, i))
            frame_day.setProperty("class", "open-meteo-card-day")

            if i == 0:
                day_text = "Today"
            elif i == 1:
                day_text = "Tomorrow"
            else:
                day_text = self._weather_data.get(f"{{day{i}_full_name}}", "")
            min_temp = self._weather_data[f"{{day{i}_min_temp}}"]
            max_temp = self._weather_data[f"{{day{i}_max_temp}}"]

            # Main vertical layout
            layout_day = QVBoxLayout()
            layout_day.setContentsMargins(8, 6, 8, 6)
            layout_day.setSpacing(4)
            layout_day.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_day.setLayout(layout_day)

            # 1. SVG icon
            row_day_icon_label = QLabel()
            day_code = self._weather_data.get(f"{{day{i}_weather_code}}", 0)
            svg_str, _, _ = get_weather_icon(int(day_code), True)
            dpr = row_day_icon_label.devicePixelRatioF()
            pixmap = render_svg_to_pixmap(svg_str, self.config.weather_card.icon_size, dpr)
            row_day_icon_label.setPixmap(pixmap)
            row_day_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_day.addWidget(row_day_icon_label)

            # 2. Day name
            day_name_label = QLabel(day_text)
            day_name_label.setProperty("class", "day-name")
            day_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_day.addWidget(day_name_label)

            # 3. Max Temp
            max_label = QLabel(str(max_temp))
            max_label.setProperty("class", "day-temp-max")
            max_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_day.addWidget(max_label)

            # 4. Min Temp
            min_label = QLabel(str(min_temp))
            min_label.setProperty("class", "day-temp-min")
            min_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_day.addWidget(min_label)
            day_widgets.append(frame_day)

        days_layout = QHBoxLayout()
        for widget in day_widgets:
            days_layout.addWidget(widget)

        switch_hourly_data(0)

        # Assemble card layout
        main_layout.addWidget(frame_today)
        main_layout.addLayout(days_layout)

        if self._hourly_data[0] and self.config.weather_card.show_hourly_forecast:
            main_layout.addWidget(hourly_container_wrapper)

        self.dialog.setLayout(main_layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.weather_card.alignment,
            direction=self.config.weather_card.direction,
            offset_left=self.config.weather_card.offset_left,
            offset_top=self.config.weather_card.offset_top,
        )
        self.dialog.show()

        # Position buttons absolutely
        if buttons_config.enabled and self.config.weather_card.show_hourly_forecast:
            buttons_container.adjustSize()
            buttons_container.move(0, 0)
            buttons_container.raise_()

        # Scroll to current hour
        if hsb := hourly_scroll_area.horizontalScrollBar():
            hsb.setValue(self.config.weather_card.hourly_point_spacing // 2 - 5)

    def reset_location(self, ev: QMouseEvent | None = None):
        """Clear the current location data and revert to the setup UI."""
        self.dialog.hide()
        self._weather_data = None
        self._has_valid_weather_data = False
        self._location_data = None
        save_location(self._widget_id, None)

        # Hide icons when reverting to setup mode
        for widget in self._widgets + self._widgets_alt:
            if widget.property("class") and "icon" in (widget.property("class") or ""):
                widget.hide()

        self._set_label_text("Setup location")

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content: str, is_alt: bool = False) -> list[QLabel]:
            label_parts = re.split(r"(<span.*?>.*?</span>)", content)
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
                add_shadow(label, self.config.label_shadow.model_dump())
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _set_label_text(self, text: str):
        """Set the same text on all visible label widgets."""
        for widget in self._widgets:
            if widget.property("class") and "icon" not in (widget.property("class") or ""):
                widget.setText(text)
                if not widget.isVisible():
                    widget.show()

    def _format_time(self, iso_time: str) -> str:
        """Format an ISO 8601 time string for display."""
        if not iso_time:
            return "N/A"
        try:
            dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M")
            if self.config.weather_card.time_format == "12h":
                return dt.strftime("%I:%M %p").lstrip("0")
            return dt.strftime("%H:%M")
        except ValueError, AttributeError:
            return iso_time

    def _reload_css(self, label: QLabel):
        refresh_widget_style(label)
        label.update()

    @pyqtSlot(bool)
    def _update_label(self, update_class: bool = True):
        if self._weather_data is None:
            return

        active_widgets = self._show_alt_label and self._widgets_alt or self._widgets
        active_label_content = self._show_alt_label and self._label_alt_content or self._label_content
        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        if self.config.tooltip:
            tooltip = (
                f"<strong>{self._weather_data['{location}']}</strong><br><br>Temperature<br>"
                f"Min {self._weather_data['{min_temp}']} / Max {self._weather_data['{max_temp}']}"
            )
            set_tooltip(self, tooltip)

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
                    active_widgets[widget_index].setText(self.config.icons.model_dump().get(icon_name, icon_name))
                    if update_class:
                        current_class = active_widgets[widget_index].property("class") or ""
                        append_class_icon = self._weather_data.get("{icon_class}", "")
                        new_class = f"{current_class} {append_class_icon}"
                        active_widgets[widget_index].setProperty("class", new_class)
                        self._reload_css(active_widgets[widget_index])
                else:
                    active_widgets[widget_index].setText(part)

                if not active_widgets[widget_index].isVisible():
                    active_widgets[widget_index].show()
                widget_index += 1
        except Exception as e:
            logger.exception(f"Failed to update label: {e}")

    @pyqtSlot(dict)
    def process_weather_data(self, weather_data: dict[str, Any]):
        try:
            if not weather_data:
                raise Exception("Weather data is empty.")

            current = weather_data.get("current", {})
            daily = weather_data.get("daily", {})
            hourly = weather_data.get("hourly", {})

            # Validate required fields
            if not current or not daily or not hourly:
                raise Exception("Incomplete weather data received.")

            # Parse current time from the response
            current_time_str = current.get("time", "")
            if current_time_str:
                self._current_time = datetime.strptime(current_time_str, "%Y-%m-%dT%H:%M")

            # Determine is_day for current conditions
            is_day = bool(current.get("is_day", 1))

            # Get weather description from WMO code
            current_code = current.get("weather_code", 0)
            _, icon_class, condition_text = get_weather_icon(current_code, is_day)

            # Split hourly data into per-day buckets (24 hours each)
            hourly_times = hourly.get("time", [])
            hourly_temps = hourly.get("temperature_2m", [])
            hourly_humidity = hourly.get("relative_humidity_2m", [])
            hourly_codes = hourly.get("weather_code", [])
            hourly_wind = hourly.get("wind_speed_10m", [])
            hourly_precip_prob = hourly.get("precipitation_probability", [])
            hourly_rain_vol = hourly.get("rain", [])
            hourly_snow_vol = hourly.get("snowfall", [])

            # Determine sunrise/sunset for is_day per hour
            daily_sunrise = daily.get("sunrise", [])
            daily_sunset = daily.get("sunset", [])

            for day_idx in range(7):
                start = day_idx * 24
                end = start + 24
                day_hourly: list[dict[str, Any]] = []
                sunrise_dt = None
                sunset_dt = None
                if day_idx < len(daily_sunrise) and daily_sunrise[day_idx]:
                    try:
                        sunrise_dt = datetime.strptime(daily_sunrise[day_idx], "%Y-%m-%dT%H:%M")
                    except ValueError:
                        pass
                if day_idx < len(daily_sunset) and daily_sunset[day_idx]:
                    try:
                        sunset_dt = datetime.strptime(daily_sunset[day_idx], "%Y-%m-%dT%H:%M")
                    except ValueError:
                        pass

                for h_idx in range(start, min(end, len(hourly_times))):
                    h_time_str = hourly_times[h_idx] if h_idx < len(hourly_times) else ""
                    h_is_day = True
                    if h_time_str and sunrise_dt and sunset_dt:
                        try:
                            h_dt = datetime.strptime(h_time_str, "%Y-%m-%dT%H:%M")
                            h_is_day = sunrise_dt <= h_dt <= sunset_dt
                        except ValueError:
                            pass
                    day_hourly.append(
                        {
                            "time": h_time_str,
                            "temperature_2m": hourly_temps[h_idx] if h_idx < len(hourly_temps) else 0,
                            "relative_humidity_2m": hourly_humidity[h_idx] if h_idx < len(hourly_humidity) else 0,
                            "weather_code": hourly_codes[h_idx] if h_idx < len(hourly_codes) else 0,
                            "wind_speed_10m": hourly_wind[h_idx] if h_idx < len(hourly_wind) else 0,
                            "precipitation_probability": hourly_precip_prob[h_idx]
                            if h_idx < len(hourly_precip_prob)
                            else 0,
                            "is_day": h_is_day,
                        }
                    )
                self._hourly_data[day_idx] = day_hourly

            # Format helpers
            def fmt_temp(val: float) -> str:
                unit = "°F" if self.config.units == "imperial" else "°C"
                v = round(val) if self.config.hide_decimal else val
                return f"{v}{unit}"

            def fmt_wind(val: float) -> str:
                unit = "mph" if self.config.units == "imperial" else "km/h"
                return f"{val} {unit}"

            # Daily data
            daily_times = daily.get("time", [])
            daily_max = daily.get("temperature_2m_max", [])
            daily_min = daily.get("temperature_2m_min", [])
            daily_codes = daily.get("weather_code", [])
            daily_precip_max = daily.get("precipitation_probability_max", [])

            daily_uv = daily.get("uv_index_max", [])

            location_name = "Unknown"
            if self._location_data:
                location_name = self._location_data.get("name", "Unknown")

            today_precip_prob = hourly_precip_prob[:24] if hourly_precip_prob else []
            today_rain_vol = hourly_rain_vol[:24] if hourly_rain_vol else []
            today_snow_vol = hourly_snow_vol[:24] if hourly_snow_vol else []

            max_rain_chance = 0
            max_snow_chance = 0

            for i, prob in enumerate(today_precip_prob):
                if prob is None:
                    continue
                vol_rain = today_rain_vol[i] if i < len(today_rain_vol) else 0
                vol_snow = today_snow_vol[i] if i < len(today_snow_vol) else 0

                if vol_rain is not None and vol_rain > 0 and prob > max_rain_chance:
                    max_rain_chance = prob
                if vol_snow is not None and vol_snow > 0 and prob > max_snow_chance:
                    max_snow_chance = prob

            self._weather_data = {
                # Current conditions
                "{temp}": fmt_temp(current.get("temperature_2m", 0)),
                "{feelslike}": fmt_temp(current.get("apparent_temperature", 0)),
                "{humidity}": f"{current.get('relative_humidity_2m', 0)}%",
                "{cloud}": current.get("cloud_cover", 0),
                "{pressure}": f"{current.get('pressure_msl', 0)} hPa",
                "{precipitation}": f"{current.get('precipitation', 0)} mm",
                "{wind}": fmt_wind(current.get("wind_speed_10m", 0)),
                "{wind_dir}": f"{current.get('wind_direction_10m', 0)}°",
                "{is_day}": "Day" if is_day else "Night",
                "{condition_text}": condition_text,
                "{icon}": icon_class,
                "{icon_class}": icon_class,
                # Location
                "{location}": location_name,
                # Sunrise / Sunset
                "{sunrise}": self._format_time(daily.get("sunrise", [""])[0]) if daily.get("sunrise") else "N/A",
                "{sunset}": self._format_time(daily.get("sunset", [""])[0]) if daily.get("sunset") else "N/A",
                # Today forecast
                "{min_temp}": fmt_temp(daily_min[0]) if daily_min else "N/A",
                "{max_temp}": fmt_temp(daily_max[0]) if daily_max else "N/A",
                "{precipitation_probability}": f"{daily_precip_max[0]}%" if daily_precip_max else "N/A",
                "{rain_chance}": max_rain_chance,
                "{snow_chance}": max_snow_chance,
                "{uv}": f"{daily_uv[0]}" if daily_uv else "N/A",
            }

            # Per-day forecast data
            for i in range(7):
                if i < len(daily_times):
                    date_obj = datetime.strptime(daily_times[i], "%Y-%m-%d")
                    day_name = date_obj.strftime("%B %d")
                    day_short = date_obj.strftime("%a")
                    day_full = date_obj.strftime("%A")
                    day_number = date_obj.strftime("%d").lstrip("0")
                else:
                    day_name = "N/A"
                    day_short = "N/A"
                    day_full = "N/A"
                    day_number = ""
                self._weather_data[f"{{day{i}_name}}"] = day_name
                self._weather_data[f"{{day{i}_short_name}}"] = day_short
                self._weather_data[f"{{day{i}_full_name}}"] = day_full
                self._weather_data[f"{{day{i}_number}}"] = day_number
                self._weather_data[f"{{day{i}_min_temp}}"] = fmt_temp(daily_min[i]) if i < len(daily_min) else "N/A"
                self._weather_data[f"{{day{i}_max_temp}}"] = fmt_temp(daily_max[i]) if i < len(daily_max) else "N/A"
                self._weather_data[f"{{day{i}_weather_code}}"] = daily_codes[i] if i < len(daily_codes) else 0

            self._has_valid_weather_data = True

        except Exception as e:
            if not self._retry_timer.isActive():
                err = f"Error processing Open-Meteo data: {e}. Retrying in 10s."
                if isinstance(e, (IndexError, KeyError, TypeError)):
                    err += f"\n{traceback.format_exc()}"
                logger.warning(err)
                self._retry_timer.start(10000)
            self._has_valid_weather_data = False
            if self._weather_data is None:
                self._weather_data = {
                    "{temp}": "N/A",
                    "{min_temp}": "N/A",
                    "{max_temp}": "N/A",
                    "{precipitation_probability}": "N/A",
                    "{location}": "N/A",
                    "{humidity}": "N/A",
                    "{is_day}": "N/A",
                    "{icon}": "default",
                    "{icon_class}": "default",
                    "{condition_text}": "N/A",
                    "{wind}": "N/A",
                    "{wind_dir}": "N/A",
                    "{pressure}": "N/A",
                    "{precipitation}": "N/A",
                    "{uv}": "N/A",
                    "{cloud}": "N/A",
                    "{feelslike}": "N/A",
                }
                for i in range(7):
                    self._weather_data[f"{{day{i}_name}}"] = "N/A"
                    self._weather_data[f"{{day{i}_min_temp}}"] = "N/A"
                    self._weather_data[f"{{day{i}_max_temp}}"] = "N/A"
                    self._weather_data[f"{{day{i}_weather_code}}"] = 0

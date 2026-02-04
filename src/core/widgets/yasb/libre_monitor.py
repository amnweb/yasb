import json
import re
from collections import deque
from urllib.parse import quote

from PyQt6.QtCore import QEventLoop, Qt, QUrl
from PyQt6.QtNetwork import QAuthenticator, QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.libre_monitor import LibreMonitorConfig
from core.widgets.base import BaseWidget


class LibreHardwareMonitorWidget(BaseWidget):
    validation_schema = LibreMonitorConfig

    def __init__(self, config: LibreMonitorConfig):
        super().__init__(config.update_interval, class_name=config.class_name)
        self.config = config
        self._show_alt_label = False
        self._history = deque([0.0] * self.config.histogram_num_columns, maxlen=self.config.histogram_num_columns)
        self._history_long: deque[float] = deque([], maxlen=self.config.history_size)

        # UI
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self.config.label, self.config.label_alt, self.config.label_shadow.model_dump())

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self._data = None
        # Create a network manager to handle the LHM connection asynchronously
        self._network_manager = QNetworkAccessManager()
        # Called when the request is finished
        self._network_manager.finished.connect(self._handle_network_response)
        # Called if the server requests authentication
        self._network_manager.authenticationRequired.connect(self._handle_authentication)

        # Create a request
        url = QUrl(
            f"http://{self.config.server_host}:{self.config.server_port}/Sensor?action=Get&id={quote(self.config.sensor_id)}"
        )
        self.request = QNetworkRequest(url)
        self.request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/x-www-form-urlencoded",
        )

        # Callbacks
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_timer = "update_label"

        # Timer
        self.start_timer()

    def _toggle_label(self):
        """Toggle between main and alt labels"""
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_menu(self):
        """Toggle the popup menu"""
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_popup_menu()

    def _show_popup_menu(self):
        """Shows a popup menu with sensors information"""
        self._menu = PopupWidget(
            self,
            self.config.libre_menu.blur,
            self.config.libre_menu.round_corners,
            self.config.libre_menu.round_corners_type,
            self.config.libre_menu.border_color,
        )
        self._menu.setProperty("class", "libre-menu")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.config.libre_menu.header_label:
            header_label = QLabel(self.config.libre_menu.header_label)
            header_label.setProperty("class", "header")
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(header_label)

        self.sensors_container = QWidget()
        self.sensor_value_labels = {}

        self.sensors_layout = QGridLayout(self.sensors_container)
        col_count = self.config.libre_menu.columns

        for idx, sensor in enumerate(self.config.libre_menu.sensors):
            sensor_id = sensor.id
            sensor_name = sensor.name or sensor_id

            sensor_widget = QFrame()
            sensor_widget.setProperty("class", "sensor-item")
            sensor_layout = QHBoxLayout(sensor_widget)

            name_label = QLabel(sensor_name)
            name_label.setProperty("class", "sensor-name")

            value_label = QLabel()
            value_label.setProperty("class", "sensor-value")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.sensor_value_labels[sensor_id] = value_label

            sensor_layout.addWidget(name_label)
            sensor_layout.addStretch(1)
            sensor_layout.addWidget(value_label)

            row = idx // col_count
            col = idx % col_count
            self.sensors_layout.addWidget(sensor_widget, row, col)

        layout.addWidget(self.sensors_container)

        self._menu.setLayout(layout)
        self._menu.adjustSize()
        self._menu.setPosition(
            self.config.libre_menu.alignment,
            self.config.libre_menu.direction,
            self.config.libre_menu.offset_left,
            self.config.libre_menu.offset_top,
        )
        self._menu.show()
        self._update_menu_content()

    def _update_menu_content(self):
        """Update only the values in the existing labels if popup is open"""
        if self._is_menu_visible():
            for sensor in self.config.libre_menu.sensors:
                sensor_id = sensor.id
                value_label = self.sensor_value_labels.get(sensor_id)
                if value_label is not None and isinstance(value_label, QLabel):
                    try:
                        self._update_sensor_value(sensor_id, value_label)
                    except RuntimeError:
                        continue

    def _update_sensor_value(self, sensor_id, value_label):
        """Update just the value for a specific sensor"""
        if not self._is_menu_visible():
            return
        url = QUrl(
            f"http://{self.config.server_host}:{self.config.server_port}/Sensor?action=Get&id={quote(sensor_id)}"
        )
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded")
        manager = QNetworkAccessManager()
        manager.authenticationRequired.connect(self._handle_authentication)
        reply = manager.post(request, b"")
        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            bytes_string = reply.readAll().data()
            data = json.loads(bytes_string.decode("utf-8"))
            if data.get("result") == "ok":
                value = data.get("value", "N/A")
                unit = data.get("format", "").split(" ")[-1]
                value_label.setText(f"{value:.{self.config.libre_menu.precision}f} {unit}")
            else:
                # Sensor missing or not found
                value_label.setText("N/A")
        reply.deleteLater()

    def _is_menu_visible(self):
        """Check if the popup menu is visible"""
        try:
            if getattr(self, "_menu", None) is not None and isinstance(self._menu, QWidget) and self._menu.isVisible():
                return True
        except RuntimeError, AttributeError:
            return False

    def _get_histogram_bar(self, value: float, value_min: float, value_max: float):
        """Gets the appropriate histogram element from the icons list based on the value and min/max"""
        bar_index = int((value - value_min) / max((value_max - value_min), 0.00001) * 10)
        bar_index = min(abs(bar_index), 8)
        return self.config.histogram_icons[bar_index]

    def _update_label(self):
        """Make a request and update the label with the received data"""
        if self.config.sensor_id:
            # If sensor_id is empty skip call
            self._make_request()
        info = {
            "status": "",
            "value": "",
            "unit": "",
            "min": "",
            "max": "",
            "histogram": "",
        }
        if self._data and self._data.get("result") == "ok":
            value = self._data.get("value", 0.0)

            self._history.append(float(value))
            self._history_long.append(float(value))
            history_min_value = min(self._history_long)
            history_max_value = max(self._history_long)
            min_val = history_min_value if self.config.histogram_fixed_min is None else self.config.histogram_fixed_min
            max_val = history_max_value if self.config.histogram_fixed_max is None else self.config.histogram_fixed_max

            info["value"] = f"{value:.{self.config.precision}f}"
            info["min"] = f"{history_min_value:.{self.config.precision}f}"
            info["max"] = f"{history_max_value:.{self.config.precision}f}"
            info["unit"] = self._data.get("format", "Error Error").split(" ")[-1]
            info["histogram"] = (
                "".join([self._get_histogram_bar(val, min_val, max_val) for val in self._history])
                .encode("utf-8")
                .decode("unicode_escape")
            )
        elif self._data:
            info["value"] = self._data.get("status", "")

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    formatted_text = part.format(info=info) if info else part
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

        # Update popup menu if it's visible
        if self._is_menu_visible():
            self._update_menu_content()

    def _make_request(self):
        """Makes a post request to LibreHardwareMonitor"""
        self._network_manager.post(self.request, b"")

    def _handle_network_response(self, reply: QNetworkReply):
        """
        Handles the network response from the QNetworkAccessManager.
        Handles the potential error codes and populates the data dict with the result.
        """
        if reply.error() == QNetworkReply.NetworkError.NoError:
            bytes_string = reply.readAll().data()
            self._data = json.loads(bytes_string.decode("utf-8"))
            if self._data.get("result") == "ok":
                self._data["status"] = "Connected..."
            else:
                self._data["status"] = self.config.sensor_id_error_label
                self._data["histogram"] = self.config.sensor_id_error_label
        elif reply.error() == QNetworkReply.NetworkError.AuthenticationRequiredError:
            self._data = {
                "status": self.config.auth_error_label,
                "result": "fail",
                "value": "",
                "histogram": self.config.auth_error_label,
            }
        else:
            self._data = {
                "status": self.config.connection_error_label,
                "result": "fail",
                "value": "",
                "histogram": self.config.auth_error_label,
            }
        reply.deleteLater()

    def _handle_authentication(self, _: QNetworkReply, auth: QAuthenticator):
        """If server requests auth, this will be called and username and password will be set"""
        if self.config.server_username and self.config.server_password:
            auth.setUser(self.config.server_username)
            auth.setPassword(self.config.server_password)

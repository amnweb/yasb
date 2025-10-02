import json
import re
from collections import deque
from urllib.parse import quote

from PyQt6.QtCore import QEventLoop, Qt, QUrl
from PyQt6.QtNetwork import QAuthenticator, QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.libre_monitor import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class LibreHardwareMonitorWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        class_name: str,
        label: str,
        label_alt: str,
        update_interval: int,
        sensor_id: str,
        histogram_icons: list[str],
        histogram_num_columns: int,
        precision: int,
        history_size: int,
        histogram_fixed_min: float | None,
        histogram_fixed_max: float | None,
        sensor_id_error_label,
        connection_error_label,
        auth_error_label,
        server_host: str,
        server_port: int,
        server_username: str,
        server_password: str,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict,
        libre_menu: dict,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(update_interval, class_name=class_name)
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._sensor_id = sensor_id
        self._precision = precision
        self._history = deque([0.0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._history_long: deque[float] = deque([], maxlen=history_size)
        self._histogram_fixed_min = histogram_fixed_min
        self._histogram_fixed_max = histogram_fixed_max
        self._sensor_id_error_label = sensor_id_error_label
        self._connection_error_label = connection_error_label
        self._auth_error_label = auth_error_label
        self._histogram_icons = histogram_icons
        self._histogram_num_columns = histogram_num_columns
        self._server_host = server_host
        self._server_port = server_port
        self._server_username = server_username
        self._server_password = server_password
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._libre_menu = libre_menu
        # UI
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

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
        url = QUrl(f"http://{self._server_host}:{self._server_port}/Sensor?action=Get&id={quote(self._sensor_id)}")
        self.request = QNetworkRequest(url)
        self.request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/x-www-form-urlencoded",
        )

        # Callbacks
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        # Timer
        self.start_timer()

    def _toggle_label(self):
        """Toggle between main and alt labels"""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_menu(self):
        """Toggle the popup menu"""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_popup_menu()

    def _show_popup_menu(self):
        """Shows a popup menu with sensors information"""
        self._menu = PopupWidget(
            self,
            self._libre_menu["blur"],
            self._libre_menu["round_corners"],
            self._libre_menu["round_corners_type"],
            self._libre_menu["border_color"],
        )
        self._menu.setProperty("class", "libre-menu")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self._libre_menu["header_label"]:
            header_label = QLabel(self._libre_menu["header_label"])
            header_label.setProperty("class", "header")
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(header_label)

        self.sensors_container = QWidget()
        self.sensor_value_labels = {}

        self.sensors_layout = QGridLayout(self.sensors_container)
        col_count = self._libre_menu["columns"]

        for idx, sensor in enumerate(self._libre_menu["sensors"]):
            sensor_id = sensor["id"]
            sensor_name = sensor["name"]

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
            self._libre_menu["alignment"],
            self._libre_menu["direction"],
            self._libre_menu["offset_left"],
            self._libre_menu["offset_top"],
        )
        self._menu.show()
        self._update_menu_content()

    def _update_menu_content(self):
        """Update only the values in the existing labels if popup is open"""
        if self._is_menu_visible():
            for sensor in self._libre_menu["sensors"]:
                sensor_id = sensor["id"]
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
        url = QUrl(f"http://{self._server_host}:{self._server_port}/Sensor?action=Get&id={quote(sensor_id)}")
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
                value_label.setText(f"{value:.{self._libre_menu['precision']}f} {unit}")
            else:
                # Sensor missing or not found
                value_label.setText("N/A")
        reply.deleteLater()

    def _is_menu_visible(self):
        """Check if the popup menu is visible"""
        try:
            if getattr(self, "_menu", None) is not None and isinstance(self._menu, QWidget) and self._menu.isVisible():
                return True
        except (RuntimeError, AttributeError):
            return False

    def _get_histogram_bar(self, value: float, value_min: float, value_max: float):
        """Gets the appropriate histogram element from the icons list based on the value and min/max"""
        bar_index = int((value - value_min) / max((value_max - value_min), 0.00001) * 10)
        bar_index = min(abs(bar_index), 8)
        return self._histogram_icons[bar_index]

    def _update_label(self):
        """Make a request and update the label with the received data"""
        if self._sensor_id:
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
            min_val = history_min_value if self._histogram_fixed_min is None else self._histogram_fixed_min
            max_val = history_max_value if self._histogram_fixed_max is None else self._histogram_fixed_max

            info["value"] = f"{value:.{self._precision}f}"
            info["min"] = f"{history_min_value:.{self._precision}f}"
            info["max"] = f"{history_max_value:.{self._precision}f}"
            info["unit"] = self._data.get("format", "Error Error").split(" ")[-1]
            info["histogram"] = (
                "".join([self._get_histogram_bar(val, min_val, max_val) for val in self._history])
                .encode("utf-8")
                .decode("unicode_escape")
            )
        elif self._data:
            info["value"] = self._data.get("status", "")

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
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
                self._data["status"] = self._sensor_id_error_label
                self._data["histogram"] = self._sensor_id_error_label
        elif reply.error() == QNetworkReply.NetworkError.AuthenticationRequiredError:
            self._data = {
                "status": self._auth_error_label,
                "result": "fail",
                "value": "",
                "histogram": self._auth_error_label,
            }
        else:
            self._data = {
                "status": self._connection_error_label,
                "result": "fail",
                "value": "",
                "histogram": self._auth_error_label,
            }
        reply.deleteLater()

    def _handle_authentication(self, _: QNetworkReply, auth: QAuthenticator):
        """If server requests auth, this will be called and username and password will be set"""
        if self._server_username and self._server_password:
            auth.setUser(self._server_username)
            auth.setPassword(self._server_password)

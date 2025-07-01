import logging
import re

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.traffic.connection_monitor import InternetChecker
from core.utils.widgets.traffic.traffic_manager import TrafficDataManager
from core.validation.widgets.yasb.traffic import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


class TrafficWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    _instances_by_interface: dict[str, list["TrafficWidget"]] = {}
    _shared_timers: dict[str, QTimer] = {}
    _shared_data: dict[str, dict] = {}

    def __init__(
        self,
        label: str,
        label_alt: str,
        interface: str,
        update_interval: int,
        hide_if_offline: bool,
        max_label_length: int,
        max_label_length_align: str,
        hide_decimal: bool,
        speed_threshold: dict,
        speed_unit: str,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        menu: dict,
        label_shadow: dict,
        container_shadow: dict,
    ):
        super().__init__(class_name="traffic-widget")

        self.interval = update_interval / 1000
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._interface = interface
        self._hide_if_offline = hide_if_offline
        self._max_label_length = max_label_length
        self._max_label_length_align = max_label_length_align.lower()
        self._hide_decimal = hide_decimal
        self._speed_threshold = speed_threshold
        self._speed_unit = speed_unit.lower()
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._menu = menu

        TrafficDataManager.setup_global_data_storage()

        # Initialize session bytes sent and received
        self.session_bytes_sent, self.session_bytes_recv = TrafficDataManager.initialize_interface(self._interface)

        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")

        add_shadow(self._widget_container, self._container_shadow)

        self.widget_layout.addWidget(self._widget_container)
        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self._initialize_instance_counters()
        self._setup_callbacks_and_timers(update_interval, callbacks)

        # Initial data update
        QTimer.singleShot(200, lambda: TrafficWidget._update_interface_data(self._interface))

    def _setup_callbacks_and_timers(self, update_interval, callbacks):
        """Setup callbacks, timers, and internet checker"""

        # Create interface-specific internet checker
        try:
            self.internet_checker = InternetChecker(parent=self, interface=self._interface)
            self.internet_checker.connection_changed.connect(self._on_connection_changed)

            self._is_internet_connected = True
            if DEBUG:
                logging.info(f"Internet checker initialized for interface {self._interface}")

        except Exception as e:
            logging.error(f"Failed to initialize InternetChecker for interface {self._interface}: {e}")
            self._is_internet_connected = False  # Default to disconnected if checker fails

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("reset_data", self._reset_traffic_data)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        if self._interface not in TrafficWidget._instances_by_interface:
            TrafficWidget._instances_by_interface[self._interface] = []
        TrafficWidget._instances_by_interface[self._interface].append(self)

        if update_interval > 0 and self._interface not in TrafficWidget._shared_timers:
            TrafficWidget._shared_timers[self._interface] = QTimer(self)
            TrafficWidget._shared_timers[self._interface].setInterval(update_interval)
            TrafficWidget._shared_timers[self._interface].timeout.connect(
                lambda: TrafficWidget._update_interface_data(self._interface)
            )
            TrafficWidget._shared_timers[self._interface].start()

    def _initialize_instance_counters(self):
        """Initialize instance-specific counters"""

        self.bytes_sent = 0
        self.bytes_recv = 0

        def get_initial_counters():
            try:
                initial_io = TrafficDataManager.get_interface_io_counters(self._interface)
                if initial_io:
                    self.bytes_sent = initial_io.bytes_sent
                    self.bytes_recv = initial_io.bytes_recv
                else:
                    logging.warning(f"Could not get initial IO counters for interface {self._interface}")
            except Exception as e:
                logging.error(f"Error initializing instance counters: {e}")

        QTimer.singleShot(100, get_initial_counters)

    @classmethod
    def _update_interface_data(cls, interface: str):
        """Update data for all widgets with the same interface"""
        if interface not in cls._instances_by_interface:
            return

        instances = cls._instances_by_interface[interface][:]
        if not instances:
            return

        try:
            # Get the network data once for this interface
            net_data = cls._get_shared_net_data(interface, instances[0])

            # Store shared data
            cls._shared_data[interface] = net_data  # type: ignore

            # Update all instances with the same interface
            for instance in instances[:]:
                try:
                    instance._update_from_shared_data(net_data)
                except RuntimeError:
                    # Instance was deleted, remove from list
                    cls._instances_by_interface[interface].remove(instance)

        except Exception as e:
            logging.error(f"Error updating interface data for {interface}: {e}")

    @classmethod
    def _get_shared_net_data(cls, interface: str, reference_instance):
        """Get network data for a specific interface using a reference instance"""
        try:
            # Use the data manager to calculate everything
            net_data = TrafficDataManager.calculate_network_data(
                interface=interface,
                previous_sent=reference_instance.bytes_sent,
                previous_recv=reference_instance.bytes_recv,
                session_sent=reference_instance.session_bytes_sent,
                session_recv=reference_instance.session_bytes_recv,
                interval_seconds=reference_instance.interval,
                speed_unit=reference_instance._speed_unit,
                hide_decimal=reference_instance._hide_decimal,
                speed_threshold=reference_instance._speed_threshold,
                max_label_length=reference_instance._max_label_length,
                max_label_length_align=reference_instance._max_label_length_align,
            )

            if net_data and net_data.get("reset_occurred"):
                # Update session baseline if reset occurred
                reference_instance.session_bytes_sent = net_data["current_io"].bytes_sent
                reference_instance.session_bytes_recv = net_data["current_io"].bytes_recv

            if net_data:
                # Update instance counters
                reference_instance.bytes_sent = net_data["current_io"].bytes_sent
                reference_instance.bytes_recv = net_data["current_io"].bytes_recv

            return net_data

        except Exception as e:
            logging.error(f"Error getting network data for interface {interface}: {e}")
            # Return default values if an error occurs
            return {
                "upload_speed": "0 Kbps",
                "download_speed": "0 Kbps",
                "raw_upload_speed": "0",
                "raw_download_speed": "0",
                "today_uploaded": "< 1 MB",
                "today_downloaded": "< 1 MB",
                "session_uploaded": "< 1 MB",
                "session_downloaded": "< 1 MB",
                "session_duration": "just now",
                "alltime_uploaded": "< 1 MB",
                "alltime_downloaded": "< 1 MB",
            }

    def _update_from_shared_data(self, shared_data):
        """Update this instance from shared data"""
        if shared_data is None:
            return

        # Update instance counters from shared data
        if "current_io" in shared_data:
            self.bytes_sent = shared_data["current_io"].bytes_sent
            self.bytes_recv = shared_data["current_io"].bytes_recv

        # Update label
        self._update_label_with_data(shared_data)

        # Update menu if visible
        if self._is_menu_visible():
            net_data = (
                shared_data["raw_upload_speed"],
                shared_data["raw_download_speed"],
                shared_data["today_uploaded"],
                shared_data["today_downloaded"],
                shared_data["session_uploaded"],
                shared_data["session_downloaded"],
                shared_data["alltime_uploaded"],
                shared_data["alltime_downloaded"],
                shared_data["session_duration"],
            )
            self._update_menu_content(net_data)

    def _update_label_with_data(self, shared_data):
        """Update label with provided data"""
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets  # type: ignore
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        label_options = [
            ("{upload_speed}", shared_data["upload_speed"]),
            ("{download_speed}", shared_data["download_speed"]),
            ("{today_uploaded}", shared_data["today_uploaded"]),
            ("{today_downloaded}", shared_data["today_downloaded"]),
            ("{session_uploaded}", shared_data["session_uploaded"]),
            ("{session_downloaded}", shared_data["session_downloaded"]),
            ("{alltime_uploaded}", shared_data["alltime_uploaded"]),
            ("{alltime_downloaded}", shared_data["alltime_downloaded"]),
        ]

        for part in label_parts:
            part = part.strip()
            for option, value in label_options:
                part = part.replace(option, str(value))

            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)

                # Update CSS class based on internet connection status
                current_class = active_widgets[widget_index].property("class") or ""
                if not self._is_internet_connected:
                    if "offline" not in current_class:
                        new_class = f"{current_class} offline".strip()
                        active_widgets[widget_index].setProperty("class", new_class)
                else:
                    # Remove offline class if connected
                    if "offline" in current_class:
                        new_class = current_class.replace("offline", "").strip()
                        new_class = " ".join(new_class.split())
                        active_widgets[widget_index].setProperty("class", new_class)
                active_widgets[widget_index].setStyleSheet("")

                widget_index += 1

    def _on_connection_changed(self, is_connected: bool):
        """Handle internet connection status changes"""

        self._is_internet_connected = is_connected

        if self._hide_if_offline:
            current_visibility = self.isVisible()
            if current_visibility == is_connected:
                return

            self.setVisible(is_connected)

        # Update menu if it's visible
        if self._is_menu_visible() and "internet-info" in self.menu_labels:
            self._update_internet_info_in_menu()

    def _update_internet_info_in_menu(self):
        """Update only the internet info in the menu"""
        if "internet-info" in self.menu_labels:
            try:
                net_status = "connected" if self._is_internet_connected else "disconnected"
                status_text = f"Internet {net_status.capitalize()}"
                self.menu_labels["internet-info"].setText(status_text)
                self.menu_labels["internet-info"].setProperty("class", f"internet-info {net_status}")
                self.menu_labels["internet-info"].setStyleSheet("")
            except (RuntimeError, AttributeError):
                pass

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])  # type: ignore
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:  # type: ignore
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:  # type: ignore
            widget.setVisible(self._show_alt_label)
        # Force update with current shared data
        if self._interface in TrafficWidget._shared_data:
            self._update_from_shared_data(TrafficWidget._shared_data[self._interface])

    def _update_label(self):
        """Update label - now just triggers shared data update"""
        TrafficWidget._update_interface_data(self._interface)

    def _toggle_menu(self):
        """Show traffic statistics popup menu"""
        self._menu_widget = PopupWidget(
            self,
            self._menu["blur"],
            self._menu["round_corners"],
            self._menu["round_corners_type"],
            self._menu["border_color"],
        )
        self._menu_widget.setProperty("class", "traffic-menu")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Helper function to create sections
        def create_section(title, class_name):
            container = QFrame()
            container.setProperty("class", f"section {class_name}-section")

            section_layout = QVBoxLayout(container)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            if title is not None:
                title_label = QLabel(title)
                title_label.setProperty("class", "section-title")
                section_layout.addWidget(title_label)

            return container, section_layout

        # Helper function to create speed column
        def create_speed_column(label_prefix, placeholder_text):
            column_container = QFrame()
            column_container.setProperty("class", label_prefix)
            column_layout = QVBoxLayout(column_container)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(0)
            column_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            speed_value = QLabel()
            speed_value.setProperty("class", f"speed-value {label_prefix}-value")
            speed_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column_layout.addWidget(speed_value)

            speed_unit = QLabel()
            speed_unit.setProperty("class", f"speed-unit {label_prefix}-unit")
            speed_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column_layout.addWidget(speed_unit)

            placeholder = QLabel(placeholder_text)
            placeholder.setProperty("class", f"speed-placeholder {label_prefix}-placeholder")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column_layout.addWidget(placeholder)

            return column_container, speed_value, speed_unit

        # Header with reset button
        header_container = QWidget()
        header_container.setProperty("class", "header")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        header_label = QLabel("Network Traffic")
        header_label.setProperty("class", "title")
        header_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        reset_button = QPushButton("Reset All")
        reset_button.setProperty("class", "reset-button")
        reset_button.setToolTip("Reset all traffic data")
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.clicked.connect(self._reset_traffic_data)
        header_layout.addWidget(reset_button)

        layout.addWidget(header_container)

        # Store label references for updates
        self.menu_labels = {}

        # Create Current Speed section with two columns
        speed_container, speed_section_layout = create_section(None, "speeds")

        # Create horizontal layout for two columns
        speed_columns_layout = QHBoxLayout()
        speed_columns_layout.setContentsMargins(0, 0, 0, 0)
        speed_columns_layout.setSpacing(0)

        # Download column
        download_column, download_value, download_unit = create_speed_column("download-speed", "Download")
        speed_columns_layout.addWidget(download_column)

        # Add separator between columns
        separator = QFrame()
        separator.setProperty("class", "speed-separator")
        speed_columns_layout.addWidget(separator)

        # Upload column
        upload_column, upload_value, upload_unit = create_speed_column("upload-speed", "Upload")
        speed_columns_layout.addWidget(upload_column)

        # Add columns to speed section
        speed_columns_widget = QWidget()
        speed_columns_widget.setLayout(speed_columns_layout)
        speed_section_layout.addWidget(speed_columns_widget)

        # Store speed label references
        self.menu_labels["upload-speed-value"] = upload_value
        self.menu_labels["upload-speed-unit"] = upload_unit
        self.menu_labels["download-speed-value"] = download_value
        self.menu_labels["download-speed-unit"] = download_unit

        layout.addWidget(speed_container)

        # Create other sections (updated titles and classes)
        other_sections = [
            ("Session Total", "session", ["session-upload", "session-download", "session-duration"]),
            ("Today's Total", "today", ["today-upload", "today-download"]),
            ("All-Time Total", "alltime", ["alltime-upload", "alltime-download"]),
        ]

        for title, class_name, label_classes in other_sections:
            container, section_layout = create_section(title, class_name)

            for label_class in label_classes:
                # Create a horizontal container for each data row
                data_container = QWidget()
                data_layout = QHBoxLayout(data_container)
                data_layout.setContentsMargins(0, 0, 0, 0)
                data_layout.setSpacing(0)

                # Create separate labels for text and value
                text_label = QLabel()
                value_label = QLabel()
                # Set CSS classes for styling
                text_label.setProperty("class", f"data-text {label_class}-text")
                value_label.setProperty("class", f"data-value {label_class}-value")
                text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                # Add labels to the horizontal layout
                data_layout.addWidget(text_label)
                data_layout.addWidget(value_label)

                # Add the container to the section
                section_layout.addWidget(data_container)

                # Store references for updates
                self.menu_labels[f"{label_class}-text"] = text_label
                self.menu_labels[f"{label_class}-value"] = value_label

            layout.addWidget(container)

        if self._menu["show_interface_name"]:
            interface_label = QLabel(f"Network Interface: {self._interface.capitalize()}")
            interface_label.setProperty("class", "interface-info")
            interface_label.setWordWrap(True)
            interface_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(interface_label)

        if self._menu["show_internet_info"]:
            status_text = "Internet Connected" if self._is_internet_connected else "Internet Disconnected"
            internet_info = QLabel(status_text)
            internet_info.setProperty("class", "internet-info")
            internet_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(internet_info)

            self.menu_labels["internet-info"] = internet_info

        self._menu_widget.setLayout(layout)
        self._menu_widget.adjustSize()
        self._menu_widget.setPosition(
            self._menu["alignment"], self._menu["direction"], self._menu["offset_left"], self._menu["offset_top"]
        )
        self._menu_widget.show()
        self._update_menu_content()

    def _update_menu_content(self, data=None):
        """Update the content of the popup menu with fresh data"""
        if self._is_menu_visible():
            try:
                if data is None:
                    if (
                        self._interface in TrafficWidget._shared_data
                        and TrafficWidget._shared_data[self._interface] is not None
                    ):
                        shared_data = TrafficWidget._shared_data[self._interface]
                        data = (
                            shared_data["raw_upload_speed"],
                            shared_data["raw_download_speed"],
                            shared_data["today_uploaded"],
                            shared_data["today_downloaded"],
                            shared_data["session_uploaded"],
                            shared_data["session_downloaded"],
                            shared_data["alltime_uploaded"],
                            shared_data["alltime_downloaded"],
                            shared_data["session_duration"],
                        )
                    else:
                        data = ("0", "0", "< 1 MB", "< 1 MB", "< 1 MB", "< 1 MB", "< 1 MB", "< 1 MB", "just now")

                (
                    raw_upload_speed,
                    raw_download_speed,
                    today_uploaded,
                    today_downloaded,
                    session_uploaded,
                    session_downloaded,
                    alltime_uploaded,
                    alltime_downloaded,
                    session_duration,
                ) = data

                # Helper function to split speed and unit
                def split_speed_unit(speed_str):
                    parts = speed_str.strip().split()
                    if len(parts) >= 2:
                        return parts[0], parts[1]  # value, unit
                    return speed_str, ""

                # Update speed columns
                upload_value, upload_unit_text = split_speed_unit(raw_upload_speed)
                download_value, download_unit_text = split_speed_unit(raw_download_speed)

                self.menu_labels["upload-speed-value"].setText(upload_value)
                self.menu_labels["upload-speed-unit"].setText(upload_unit_text)
                self.menu_labels["download-speed-value"].setText(download_value)
                self.menu_labels["download-speed-unit"].setText(download_unit_text)

                # Update other sections
                label_updates = {
                    "session-upload": ("Uploaded:", session_uploaded),
                    "session-download": ("Downloaded:", session_downloaded),
                    "session-duration": ("Duration:", session_duration),
                    "today-upload": ("Uploaded:", today_uploaded),
                    "today-download": ("Downloaded:", today_downloaded),
                    "alltime-upload": ("Uploaded:", alltime_uploaded),
                    "alltime-download": ("Downloaded:", alltime_downloaded),
                }

                for class_name, (text, value) in label_updates.items():
                    text_key = f"{class_name}-text"
                    value_key = f"{class_name}-value"

                    self.menu_labels[text_key].setText(text.strip())
                    self.menu_labels[value_key].setText(value.strip())

                self._update_internet_info_in_menu()

            except RuntimeError:
                pass
            except Exception as e:
                logging.error(f"Error updating menu content: {e}")

    def _reset_traffic_data(self):
        """Reset all traffic data to zero"""
        try:
            # Reset data in TrafficDataManager
            TrafficDataManager.reset_interface_data(self._interface)

            # Reset instance counters
            current_io = TrafficDataManager.get_interface_io_counters(self._interface)
            if current_io:
                self.bytes_sent = current_io.bytes_sent
                self.bytes_recv = current_io.bytes_recv
                self.session_bytes_sent = current_io.bytes_sent
                self.session_bytes_recv = current_io.bytes_recv

            TrafficWidget._update_interface_data(self._interface)

            if self._is_menu_visible():
                self._update_menu_content()

        except Exception as e:
            logging.error(f"Error resetting traffic data: {e}")

    def _is_menu_visible(self):
        """Check if the popup menu is visible"""
        try:
            if (
                getattr(self, "_menu_widget", None) is not None
                and isinstance(self._menu_widget, QWidget)
                and self._menu_widget.isVisible()
            ):
                return True
        except (RuntimeError, AttributeError):
            return False
        return False

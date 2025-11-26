import logging
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, ToastNotifier, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.server_monitor import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG, SCRIPT_PATH


# Add new worker class
class ServerCheckWorker(QThread):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    status_updated = pyqtSignal(list)
    progress_updated = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        if ServerCheckWorker._instance is not None:
            raise Exception("This class is a singleton!")
        super().__init__(parent)
        self.servers = []
        self.running = True
        ServerCheckWorker._instance = self

    def set_servers(self, servers, ssl_verify, ssl_check, timeout):
        self.servers = servers
        self.ssl_check = ssl_check
        self.ssl_verify = ssl_verify
        self.timeout = timeout

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        if self.running:
            server_statuses = []
            total = len(self.servers)
            updated = 0
            for server in self.servers:
                if not self.running:
                    break

                updated += 1
                self.progress_updated.emit(server, updated, total)

                status = self.check_single_server(server, self.ssl_verify, self.ssl_check, self.timeout)
                server_statuses.append(status)

            self.status_updated.emit(server_statuses)

    def check_single_server(self, server, ssl_verify, ssl_check, timeout):
        # Move existing ping_server logic here
        ping_result = self.ping_server(server, ssl_verify, ssl_check, timeout)
        if DEBUG:
            logging.debug(f"Server: {server} - {ping_result}")
        if ping_result is None:
            return {"name": server, "ssl": "N/A", "response_time": "N/A", "response_code": "N/A", "status": "Offline"}
        return {
            "name": server,
            "ssl": ping_result["ssl"],
            "response_time": f"{ping_result['response_time']}ms" if ping_result["response_time"] else None,
            "response_code": ping_result["response_code"],
            "status": ping_result["status"],
        }

    def ping_server(self, server, ssl_verify, ssl_check, timeout):
        """Check server availability and collect status information."""
        http_status = None
        response_time = None
        final_hostname = server
        url = f"https://{server}" if ssl_check else f"http://{server}"

        # Configure SSL context if needed
        context = ssl.create_default_context() if not ssl_verify else None
        if context:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            # Time the request
            start_time = datetime.now()
            request = urllib.request.Request(url, method="GET")

            try:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    http_status = response.status
                    # Get redirect hostname if any
                    parsed_url = urlparse(response.url)
                    final_hostname = parsed_url.netloc or server
            except urllib.error.HTTPError as e:
                http_status = e.code

            # Calculate response time if we got a status code
            if http_status is not None:
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)

        except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError, PermissionError, OSError):
            pass

        # Check SSL if needed and determine status
        ssl_days = self.check_ssl_expiry(final_hostname, timeout) if ssl_check else None
        status = "Online" if http_status is not None and http_status < 500 else "Offline"

        return {"status": status, "response_time": response_time, "response_code": http_status, "ssl": ssl_days}

    def check_ssl_expiry(self, hostname, timeout):
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    exp_date = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                    days_left = (exp_date - datetime.now()).days
                    return days_left
        except (
            socket.gaierror,
            socket.timeout,
            ssl.SSLError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
            ConnectionError,
            PermissionError,
            OSError,
        ):
            return


class ServerMonitor(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        servers: list[str],
        tooltip: bool,
        update_interval: int,
        ssl_check: bool,
        ssl_verify: bool,
        ssl_warning: int,
        desktop_notifications: dict[str, bool],
        timeout: int,
        menu: dict[str, str],
        icons: dict[str, int],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="server-widget")
        self._show_alt_label = False
        self._label_content = label
        self._servers = servers
        self._update_interval = update_interval * 1000
        self._icons = icons
        self._tooltip = tooltip
        self._ssl_check = ssl_check
        self._ssl_verify = ssl_verify
        self._ssl_warning = ssl_warning
        self._desktop_notifications = desktop_notifications
        self._timeout = timeout
        self._label_alt_content = label_alt
        self._padding = container_padding
        self._menu = menu
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._last_refresh_time = None
        self._server_status_data = None
        self._first_run = True
        self._animations = []
        self._icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._update_label()

        # Setup worker thread
        self._worker = ServerCheckWorker.get_instance()
        self._worker.set_servers(self._servers, self._ssl_verify, self._ssl_check, self._timeout)
        self._worker.status_updated.connect(self._handle_status_update)

        # Create and start update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._worker.start)
        self._update_timer.start(self._update_interval)
        # Initial update
        self._worker.start()

    def _handle_status_update(self, status_data):
        online_count = sum(1 for s in status_data if s.get("status") == "Online")
        offline_count = sum(1 for s in status_data if s.get("status") == "Offline")
        min_ssl = min((s["ssl"] for s in status_data if isinstance(s["ssl"], int)), default=0) if status_data else 0
        status_data.append(
            {
                "online_count": online_count,
                "offline_count": offline_count,
                "ssl_warning": True if min_ssl < self._ssl_warning else False,
            }
        )
        self._server_status_data = status_data
        self._last_refresh_time = datetime.now()
        self._update_label()
        self._send_notification()
        if hasattr(self, "dialog") and self.dialog:
            try:
                if self.dialog.isVisible():
                    if self._first_run:
                        self.dialog.hide()
                        self.show_menu()
            except RuntimeError:
                pass
        self._first_run = False

    def closeEvent(self, event):
        self._worker.stop()
        # self._worker.wait()
        self._cleanup_logging()
        super().closeEvent(event)

    def _cleanup_logging(self):
        # Ensure all logging handlers are flushed and closed properly
        for handler in logging.root.handlers[:]:
            handler.flush()
            handler.close()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_menu()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        try:
            online_count = self._server_status_data[-1]["online_count"]
            offline_count = self._server_status_data[-1]["offline_count"]
            ssl_warning = self._server_status_data[-1]["ssl_warning"]
            total_count = len(self._servers)
        except Exception:
            online_count = 0
            offline_count = 0
            ssl_warning = False
            total_count = len(self._servers)

        if offline_count > 0:
            self._widget_container.setProperty("class", "widget-container error")
        elif ssl_warning:
            self._widget_container.setProperty("class", "widget-container warning")
        else:
            self._widget_container.setProperty("class", "widget-container")
        # Force style update
        self._widget_container.setStyleSheet(self._widget_container.styleSheet())

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    # Ensure the icon is correctly set
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    formatted_text = part.format(online=online_count, offline=offline_count, total=total_count)
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1
        if self._tooltip:
            set_tooltip(
                self._widget_container, f"{online_count} online, {offline_count} offline of {total_count} servers"
            )

    def _send_notification(self):
        try:
            offline_count = self._server_status_data[-1]["offline_count"]
            ssl_warning = self._server_status_data[-1]["ssl_warning"]
        except Exception:
            offline_count = 0
            ssl_warning = False
        toaster = ToastNotifier()
        if offline_count > 0 and self._desktop_notifications["offline"]:
            toaster.show(self._icon_path, "Server Monitor", f"{offline_count} server(s) are offline")
        if ssl_warning and self._desktop_notifications["ssl"]:
            toaster.show(self._icon_path, "Server Monitor", "Some servers have SSL certificate expiring soon")

    def show_menu(self):
        self.dialog = PopupWidget(
            self,
            self._menu["blur"],
            self._menu["round_corners"],
            self._menu["round_corners_type"],
            self._menu["border_color"],
        )
        self.dialog.setProperty("class", "server-menu")

        # Get server data list
        server_data_list = self._server_status_data or None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add header widget
        header_widget = QWidget()
        header_widget.setProperty("class", "server-menu-header")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # Add refresh time
        refresh_time = "Never" if not self._last_refresh_time else self._get_time_ago()
        refresh_label = QLabel(f"Last check {refresh_time}")
        refresh_label.setProperty("class", "refresh-time")
        header_layout.addWidget(refresh_label)

        header_layout.addStretch()

        # Add reload button
        reload_button = QLabel(self._icons["reload"])
        reload_button.setProperty("class", "reload-button")
        reload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_button.mousePressEvent = lambda _: self._trigger_reload()
        header_layout.addWidget(reload_button)
        if server_data_list is not None:
            layout.addWidget(header_widget)

        scroll_area = self._build_server_rows(server_data_list)
        layout.addWidget(scroll_area)
        self.dialog.setLayout(layout)

        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._menu["alignment"],
            direction=self._menu["direction"],
            offset_left=self._menu["offset_left"],
            offset_top=self._menu["offset_top"],
        )
        self.dialog.show()

        # Add helper methods

    def _get_time_ago(self):
        if not self._last_refresh_time:
            return "Never"

        diff = datetime.now() - self._last_refresh_time
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return f"{seconds} seconds ago"

        minutes = seconds // 60
        if minutes == 1:
            return "1 minute ago"
        else:
            return f"{minutes} minutes ago"

    def _create_loading_overlay(self):
        overlay = QWidget(self.dialog)
        overlay.setProperty("class", "server-menu-overlay")
        overlay_layout = QVBoxLayout(overlay)

        # Store label as instance variable
        self._loading_label = QLabel()
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setProperty("class", "text")

        def update_progress(server, updated, total):
            if not self._loading_label.isVisible():
                return
            try:
                self._loading_label.setText(f"<br>Checking {updated}/{total} servers<br><b>{server}</b><br>")
            except RuntimeError:
                self._worker.progress_updated.disconnect(update_progress)

        self._worker.progress_updated.connect(update_progress)
        overlay_layout.addWidget(self._loading_label)

        overlay.setFixedSize(self.dialog.size())
        overlay.show()

        # Store cleanup function
        def cleanup():
            self._worker.progress_updated.disconnect(update_progress)
            if hasattr(self, "_loading_label"):
                delattr(self, "_loading_label")

        overlay.destroyed.connect(cleanup)
        return overlay

    def _update_menu_content(self):
        layout = self.dialog.layout()
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        server_data_list = self._server_status_data
        scroll_area = self._build_server_rows(server_data_list)
        layout.addWidget(scroll_area)

        header_widget = layout.itemAt(0).widget()
        refresh_label = header_widget.layout().itemAt(0).widget()
        refresh_time = self._get_time_ago()
        refresh_label.setText(f"Last check {refresh_time}")

    def _trigger_reload(self):
        # Create and show loading overlay
        overlay = self._create_loading_overlay()

        def handle_update(status_data):
            online_count = sum(1 for s in status_data if s.get("status") == "Online")
            offline_count = sum(1 for s in status_data if s.get("status") == "Offline")
            min_ssl = min((s["ssl"] for s in status_data if isinstance(s["ssl"], int)), default=0) if status_data else 0
            status_data.append(
                {
                    "online_count": online_count,
                    "offline_count": offline_count,
                    "ssl_warning": True if min_ssl < self._ssl_warning else False,
                }
            )
            self._server_status_data = status_data
            self._last_refresh_time = datetime.now()
            self._update_label()
            self._send_notification()
            try:
                if hasattr(self, "dialog") and self.dialog:
                    try:
                        if self.dialog.isVisible():
                            self._update_menu_content()
                    except RuntimeError:
                        pass
            finally:
                try:
                    if overlay:
                        overlay.deleteLater()
                except RuntimeError:
                    pass  # Overlay was already deleted

        self._current_update_handler = handle_update
        self._worker.status_updated.connect(self._current_update_handler)
        self._worker.start()
        self._worker.finished.connect(self._cleanup_handler)

    def _cleanup_handler(self):
        if hasattr(self, "_current_update_handler"):
            self._worker.status_updated.disconnect(self._current_update_handler)
            delattr(self, "_current_update_handler")

    def _build_server_rows(self, server_data_list):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setViewportMargins(0, 0, -4, 0)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        row_container = QWidget()
        row_container.setProperty("class", "server-menu-container")

        row_container_layout = QVBoxLayout(row_container)
        # row_container_layout.setContentsMargins(0, 0, 0, 0)

        if server_data_list is None:
            loading_widget = QWidget()
            loading_layout = QVBoxLayout(loading_widget)
            loading_layout.setContentsMargins(0, 0, 0, 0)

            # Create a label to show real-time progress
            self._loading_label_menu = QLabel(f"Checking 0/{len(self._servers)} servers<br><b>please wait...</b>")
            self._loading_label_menu.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._loading_label_menu.setProperty("class", "placeholder")

            loading_layout.addWidget(self._loading_label_menu)
            row_container_layout.addWidget(loading_widget)

            # Connect the worker's progress signal to update the label
            def update_progress(server, updated, total):
                if not self._loading_label_menu.isVisible():
                    return
                self._loading_label_menu.setText(f"Checking {updated}/{total} servers<br><b>{server}</b>")

            self._worker.progress_updated.connect(update_progress)

            # Cleanup after widget is destroyed
            def cleanup():
                if self._worker and self._worker.progress_updated and update_progress:
                    try:
                        self._worker.progress_updated.disconnect(update_progress)
                    except:
                        pass

            loading_widget.destroyed.connect(cleanup)

        else:
            for server_data in server_data_list:
                if not server_data or server_data.get("name") is None:
                    continue
                row_widget = QWidget()
                server_status = QLabel()
                if server_data["status"] == "Online":
                    server_data_status = self._icons["online"]
                    server_data_response_time = server_data["response_time"]
                    class_name = "online"
                else:
                    server_data_status = self._icons["offline"]
                    server_data_response_time = ""
                    class_name = "offline"

                if server_data["ssl"] is not None and server_data["ssl"] < self._ssl_warning:
                    server_data_status = self._icons["warning"]
                    class_name += " warning"

                if (server_data["ssl"] is not None and server_data["ssl"] < self._ssl_warning) or server_data[
                    "status"
                ] == "Offline":
                    # Add opacity effect for animation
                    opacity_effect = QGraphicsOpacityEffect()
                    server_status.setGraphicsEffect(opacity_effect)
                    animation = QPropertyAnimation(opacity_effect, b"opacity")
                    animation.setDuration(1000)
                    animation.setStartValue(1.0)
                    animation.setEndValue(0.6)
                    animation.setLoopCount(-1)
                    animation.setEasingCurve(QEasingCurve.Type.SineCurve)
                    animation.start()
                    self._animations.append(animation)  # Store animation reference

                row_widget.setProperty("class", f"row {class_name}")
                row_widget_layout = QVBoxLayout(row_widget)
                row_widget_layout.setContentsMargins(0, 0, 0, 0)
                row_widget_layout.setSpacing(0)

                name_status_widget = QWidget()
                h_layout = QHBoxLayout(name_status_widget)
                h_layout.setContentsMargins(0, 0, 0, 0)

                server_name = QLabel(server_data["name"])
                server_name.setProperty("class", "name")
                h_layout.addWidget(server_name)
                h_layout.addStretch()

                server_status.setText(server_data_status)
                server_status.setProperty("class", "status")
                h_layout.addWidget(server_status)

                if self._ssl_check:
                    ssl_status = f", SSL certificate expires in {server_data['ssl']} days"
                else:
                    ssl_status = ""
                if server_data["status"] == "Online":
                    details_text = (
                        f"{server_data_response_time}{ssl_status}, response code: {server_data['response_code']}"
                    )
                else:
                    details_text = "Server is offline"

                details = QLabel(details_text)
                details.setProperty("class", "details")

                row_widget_layout.addWidget(name_status_widget)
                row_widget_layout.addWidget(details)
                row_container_layout.addWidget(row_widget)

        scroll_area.setWidget(row_container)
        return scroll_area

import logging
import os
import re
from datetime import datetime

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import LoaderLine, PopupWidget, ToastNotifier, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.server_monitor.service import ServerCheckService
from core.validation.widgets.yasb.server_monitor import ServerMonitorConfig
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH


class ServerMonitor(BaseWidget):
    validation_schema = ServerMonitorConfig

    _last_notified_run_by_service: dict[int, int] = {}

    def __init__(self, config: ServerMonitorConfig):
        super().__init__(class_name="server-widget")
        self.config = config
        self._show_alt_label = False
        self._last_refresh_time = None
        self._server_status_data = None
        self._first_run = True
        self._animations = []
        self._icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self.config.label, self.config.label_alt, self.config.label_shadow.model_dump())

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self._update_label()

        self._service = ServerCheckService.get_instance(
            servers=self.config.servers,
            ssl_verify=self.config.ssl_verify,
            ssl_check=self.config.ssl_check,
            timeout=self.config.timeout,
            update_interval_s=self.config.update_interval,
        )
        self._service_released = False
        self._service.status_updated.connect(self._handle_status_update)
        self._service.refresh_started.connect(self._on_refresh_started)
        self.destroyed.connect(lambda *_: self._release_service())

    def _release_service(self) -> None:
        if getattr(self, "_service_released", False):
            return
        self._service_released = True
        ServerMonitor._last_notified_run_by_service.pop(id(self._service), None)
        try:
            self._service.release()
        except Exception:
            pass

    def _on_refresh_started(self) -> None:
        if hasattr(self, "dialog") and self.dialog:
            try:
                if self.dialog.isVisible():
                    self._set_menu_loader(True)
            except RuntimeError:
                return

    def _handle_status_update(self, run_id: int, status_data):
        status_list: list[dict] = [dict(s) for s in (status_data or []) if isinstance(s, dict)]

        online_count = sum(1 for s in status_list if s.get("status") == "Online")
        offline_count = sum(1 for s in status_list if s.get("status") == "Offline")
        ssl_values = [s["ssl"] for s in status_list if isinstance(s.get("ssl"), int)]
        min_ssl = min(ssl_values) if ssl_values else None
        ssl_warning = bool(min_ssl is not None and min_ssl < self.config.ssl_warning)

        status_list.append(
            {
                "online_count": online_count,
                "offline_count": offline_count,
                "ssl_warning": ssl_warning,
            }
        )

        self._server_status_data = status_list
        self._last_refresh_time = datetime.now()
        self._update_label()
        self._send_notification(run_id, offline_count, ssl_warning)

        if hasattr(self, "dialog") and self.dialog:
            try:
                if self.dialog.isVisible():
                    self._set_menu_loader(False)
                    try:
                        self._update_menu_content()
                    except Exception:
                        pass
                    if self._first_run:
                        self.dialog.hide()
                        self.show_menu()
            except RuntimeError:
                pass
        self._first_run = False

    def _set_menu_loader(self, active: bool) -> None:
        loader = getattr(self, "_menu_loader_line", None)
        if loader is None:
            return
        try:
            if active:
                loader.start()
            else:
                loader.stop()
        except RuntimeError:
            return

    def closeEvent(self, event):
        self._release_service()
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
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self.show_menu()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        try:
            online_count = self._server_status_data[-1]["online_count"]
            offline_count = self._server_status_data[-1]["offline_count"]
            ssl_warning = self._server_status_data[-1]["ssl_warning"]
            total_count = len(self.config.servers)
        except Exception:
            online_count = 0
            offline_count = 0
            ssl_warning = False
            total_count = len(self.config.servers)

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
        if self.config.tooltip:
            set_tooltip(
                self._widget_container, f"{online_count} online, {offline_count} offline of {total_count} servers"
            )

    def _send_notification(self, run_id: int, offline_count: int, ssl_warning: bool) -> None:
        # Dedupe across multiple widget instances for the same shared-service run.
        service_id = id(self._service)
        if ServerMonitor._last_notified_run_by_service.get(service_id) == run_id:
            return
        ServerMonitor._last_notified_run_by_service[service_id] = run_id

        toaster = ToastNotifier()
        if offline_count > 0 and self.config.desktop_notifications.offline:
            toaster.show(self._icon_path, "Server Monitor", f"{offline_count} server(s) are offline")
        if ssl_warning and self.config.desktop_notifications.ssl:
            toaster.show(self._icon_path, "Server Monitor", "Some servers have SSL certificate expiring soon")

    def show_menu(self):
        self.dialog = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
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
        reload_button = QLabel(self.config.icons.reload)
        reload_button.setProperty("class", "reload-button")
        reload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_button.mousePressEvent = lambda _: self._trigger_reload()
        header_layout.addWidget(reload_button)
        layout.addWidget(header_widget)

        # Single loader: attached to header, positioned at the header bottom edge.
        self._menu_loader_line = LoaderLine(header_widget)
        self._menu_loader_line.attach_to_widget(header_widget)
        self._menu_loader_line.stop()

        scroll_area = self._build_server_rows(server_data_list)
        layout.addWidget(scroll_area)
        self.dialog.setLayout(layout)

        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self.dialog.show()

        # If a refresh is currently in progress, keep the loader visible.
        try:
            if self._service.is_running():
                self._set_menu_loader(True)
        except RuntimeError:
            pass

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

    def _update_menu_content(self):
        layout = self.dialog.layout()
        if layout is None:
            return
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        server_data_list = self._server_status_data
        scroll_area = self._build_server_rows(server_data_list)
        layout.addWidget(scroll_area)

        try:
            header_widget = layout.itemAt(0).widget()
            refresh_label = header_widget.layout().itemAt(0).widget()
            refresh_time = self._get_time_ago()
            refresh_label.setText(f"Last check {refresh_time}")
        except Exception:
            pass

    def _trigger_reload(self):
        self._set_menu_loader(True)
        self._service.start_now()

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

            placeholder = QLabel("Checking servers...\nThis may take a few seconds.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setProperty("class", "placeholder")

            loading_layout.addWidget(placeholder)
            row_container_layout.addWidget(loading_widget)

        else:
            for server_data in server_data_list:
                if not server_data or server_data.get("name") is None:
                    continue
                row_widget = QWidget()
                server_status = QLabel()
                if server_data["status"] == "Online":
                    server_data_status = self.config.icons.online
                    server_data_response_time = server_data["response_time"]
                    class_name = "online"
                else:
                    server_data_status = self.config.icons.offline
                    server_data_response_time = ""
                    class_name = "offline"

                if isinstance(server_data.get("ssl"), int) and server_data["ssl"] < self.config.ssl_warning:
                    server_data_status = self.config.icons.warning
                    class_name += " warning"

                if (isinstance(server_data.get("ssl"), int) and server_data["ssl"] < self.config.ssl_warning) or (
                    server_data["status"] == "Offline"
                ):
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

                ssl_status = ""
                if self.config.ssl_check and isinstance(server_data.get("ssl"), int):
                    ssl_status = f", SSL certificate expires in {server_data['ssl']} days"
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

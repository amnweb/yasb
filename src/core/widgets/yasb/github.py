import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime
from enum import StrEnum
from typing import Any

from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QPainter, QPaintEvent
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.github import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


class Corner(StrEnum):
    """Enum for notification dot position corners."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class NotificationLabel(QLabel):
    """Draws a QLabel with a dot on any of the four corners of the icon."""

    def __init__(
        self,
        *args: Any,
        color: str = "red",
        corner: Corner = Corner.BOTTOM_LEFT,
        margin: list[int] = [1, 1],
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._show_dot = False
        self._color = color
        self._corner = corner
        self._margin = margin

    def show_dot(self, enabled: bool):
        self._show_dot = enabled
        self.update()

    def set_corner(self, corner: str | Corner):
        """Set the corner where the dot should appear."""
        self._corner = corner
        self.update()

    def set_color(self, color: str):
        """Set the color of the notification dot."""
        self._color = color
        self.update()

    def paintEvent(self, a0: QPaintEvent | None):
        super().paintEvent(a0)
        if self._show_dot:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(self._color))
            painter.setPen(Qt.PenStyle.NoPen)

            radius = 6
            margin_x = self._margin[0]
            margin_y = self._margin[1]

            # Calculate position based on the specified corner
            x = y = 0
            if self._corner == Corner.TOP_LEFT:
                x = margin_x
                y = margin_y
            elif self._corner == Corner.TOP_RIGHT:
                x = self.width() - radius - margin_x
                y = margin_y
            elif self._corner == Corner.BOTTOM_LEFT:
                x = margin_x
                y = self.height() - radius - margin_y
            elif self._corner == Corner.BOTTOM_RIGHT:
                x = self.width() - radius - margin_x
                y = self.height() - radius - margin_y

            painter.drawEllipse(QPoint(x + radius // 2, y + radius // 2), radius // 2, radius // 2)


class GithubWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        token: str,
        tooltip: bool,
        max_notification: int,
        notification_dot: dict[str, Any],
        only_unread: bool,
        max_field_size: int,
        menu: dict[str, str],
        icons: dict[str, str],
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__((update_interval * 1000), class_name="github-widget")

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._token = token if token != "env" else os.getenv("YASB_GITHUB_TOKEN")
        self._tooltip = tooltip
        self._menu_popup = menu
        self._icons = icons
        self._max_notification = max_notification
        self._only_unread = only_unread
        self._max_field_size = max_field_size
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._notification_label: NotificationLabel | None = None
        self._notification_label_alt: NotificationLabel | None = None
        self._notification_dot: dict[str, Any] = notification_dot

        self._github_data = []

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
        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("get_github_data", self.get_github_data)

        callbacks = {"on_left": "toggle_menu", "on_right": "toggle_label"}
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]

        self.callback_timer = "get_github_data"
        self.start_timer()

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_menu()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split("(<span.*?>.*?</span>)", content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    label = NotificationLabel(
                        icon,
                        corner=self._notification_dot["corner"],
                        color=self._notification_dot["color"],
                        margin=self._notification_dot["margin"],
                    )
                    label.setProperty("class", class_result)
                    if is_alt:
                        self._notification_label_alt = label
                    else:
                        self._notification_label = label
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                add_shadow(label, self._label_shadow)
                self._widget_container_layout.addWidget(label)

                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _update_label(self):
        notification_count = len([notification for notification in self._github_data if notification["unread"]])
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        # Split label content and filter out empty parts
        label_parts = [part.strip() for part in re.split(r"(<span.*?>.*?</span>)", active_label_content) if part]

        # Setting the notification dot if enabled and the label exists
        if self._notification_dot["enabled"]:
            if not self._show_alt_label and self._notification_label is not None:
                self._notification_label.show_dot(notification_count > 0)
            if self._show_alt_label and self._notification_label_alt is not None:
                self._notification_label_alt.show_dot(notification_count > 0)

        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            current_widget = active_widgets[widget_index]
            icon = ""

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                current_widget.setText(icon)
                if self._tooltip:
                    current_widget.setToolTip(f"Notifications {notification_count}")
                # Update class based on notification count
                current_classes = current_widget.property("class").split()
                notification_class = "new-notification"
                if notification_count > 0:
                    current_classes.append(notification_class)
                else:
                    current_classes = [cls for cls in current_classes if cls != notification_class]
                current_widget.setProperty("class", " ".join(current_classes))

            else:
                formatted_text = part.format(data=notification_count)
                current_widget.setText(formatted_text)
            current_widget.style().unpolish(current_widget)

    def mark_as_read(self, notification_id, container_label):
        for notification in self._github_data:
            if notification["id"] == notification_id:
                notification["unread"] = False
                break
        self._update_label()
        current_classes = container_label.property("class").split()
        if "new" in current_classes:
            current_classes.remove("new")
        container_label.setProperty("class", " ".join(current_classes))
        container_label.setStyleSheet(container_label.styleSheet())
        container_label.repaint()

    def mark_as_read_notification_on_github(self, notification_id):
        headers = {"Authorization": f"token {self._token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/notifications/threads/{notification_id}"
        req = urllib.request.Request(url, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(req):
                QTimer.singleShot(0, self._update_label)
                if DEBUG:
                    logging.info(f"Notification {notification_id} marked as read on GitHub.")
        except urllib.error.HTTPError as e:
            logging.error(f"HTTP Error occurred: {e.code} - {e.reason}")
        except Exception as e:
            logging.error(
                f"An unexpected error occurred: {str(e)}, in most cases this error when there is no internet connection."
            )

    def _handle_mouse_press_event(self, event, notification_id, url, container_label):
        self.mark_as_read(notification_id, container_label)
        self._menu.hide()
        QDesktopServices.openUrl(QUrl(url))
        self.mark_as_read_notification_on_github(notification_id)

    def _create_container_mouse_press_event(self, notification_id, url, container_label):
        def mouse_press_event(event):
            self._handle_mouse_press_event(event, notification_id, url, container_label)

        return mouse_press_event

    def show_menu(self):
        notifications_count = len(self._github_data)
        notifications_unread_count = len([notification for notification in self._github_data if notification["unread"]])

        self._menu = PopupWidget(
            self,
            self._menu_popup["blur"],
            self._menu_popup["round_corners"],
            self._menu_popup["round_corners_type"],
            self._menu_popup["border_color"],
        )
        self._menu.setProperty("class", "github-menu")

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("<span style='font-weight:bold'>GitHub</span> Notifications")
        header_label.setProperty("class", "header")
        main_layout.addWidget(header_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_area.setViewportMargins(0, 0, -4, 0)  # overlay the scrollbar 6px to the left
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        main_layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_widget.setProperty("class", "contents")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll_area.setWidget(scroll_widget)

        if notifications_count > 0:
            for notification in self._github_data:
                repo_title = notification["title"]
                repo_description = f"{notification['type']}: {notification['repository']}"
                repo_title = (
                    (notification["title"][: self._max_field_size - 3] + "...")
                    if len(notification["title"]) > self._max_field_size
                    else notification["title"]
                )
                repo_description = (
                    (repo_description[: self._max_field_size - 3] + "...")
                    if len(repo_description) > self._max_field_size
                    else repo_description
                )

                icon_type = {
                    "Issue": self._icons["issue"],
                    "PullRequest": self._icons["pull_request"],
                    "Release": self._icons["release"],
                    "Discussion": self._icons["discussion"],
                }.get(notification["type"], self._icons["default"])

                new_item_class = "new" if notification["unread"] else ""

                container = QWidget()
                container.setProperty("class", f"item {new_item_class}")
                container.setContentsMargins(0, 0, 8, 0)
                container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

                icon_label = QLabel(f"{icon_type}")
                icon_label.setProperty("class", "icon")

                title_label = QLabel(repo_title)
                title_label.setProperty("class", "title")

                description_label = QLabel(repo_description)
                description_label.setProperty("class", "description")

                text_content = QWidget()
                text_content_layout = QVBoxLayout(text_content)
                text_content_layout.addWidget(title_label)
                text_content_layout.addWidget(description_label)
                text_content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                text_content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                text_content_layout.setContentsMargins(0, 0, 0, 0)
                text_content_layout.setSpacing(0)

                container_layout = QHBoxLayout(container)
                container_layout.addWidget(icon_label)
                container_layout.addWidget(text_content, 1)
                container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(0)
                scroll_layout.addWidget(container)

                container.mousePressEvent = self._create_container_mouse_press_event(
                    notification["id"], notification["url"], container
                )
        else:
            large_label = QLabel(self._icons["github_logo"])
            large_label.setStyleSheet("font-size:88px;font-weight:400")
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.4)
            large_label.setGraphicsEffect(opacity_effect)

            no_data = QLabel("No unread notifications")
            no_data.setStyleSheet("font-size:18px;font-weight:400;font-family: Segoe UI")
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.5)
            no_data.setGraphicsEffect(opacity_effect)

            # Create a vertical layout to center the widgets
            center_layout = QVBoxLayout()
            center_layout.addStretch()
            center_layout.addWidget(large_label, alignment=Qt.AlignmentFlag.AlignCenter)
            center_layout.addWidget(no_data, alignment=Qt.AlignmentFlag.AlignCenter)
            center_layout.addStretch()

            # Add the center layout to the scroll layout
            scroll_layout.addLayout(center_layout)
        if notifications_count > 0:
            footer_label = QLabel(f"Unread notifications ({notifications_unread_count})")
            footer_label.setProperty("class", "footer")
            main_layout.addWidget(footer_label)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_popup["alignment"],
            direction=self._menu_popup["direction"],
            offset_left=self._menu_popup["offset_left"],
            offset_top=self._menu_popup["offset_top"],
        )

        self._menu.show()

    def get_github_data(self):
        threading.Thread(target=self._get_github_data).start()

    def _get_github_data(self):
        self._github_data = self._get_github_notifications(self._token)
        QTimer.singleShot(0, self._update_label)

    def _get_github_notifications(self, token):
        if DEBUG:
            logging.info(f"Check for GitHub notifications at {datetime.now()}")
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        params = {
            "all": "false" if self._only_unread else "true",
            "participating": "false",
            "per_page": self._max_notification,
        }

        url = "https://api.github.com/notifications"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                notifications = json.loads(response.read().decode())
            result = []
            if notifications:
                for notification in notifications:
                    repo_full_name = notification["repository"]["full_name"]
                    subject_type = notification["subject"]["type"]
                    subject_url = notification["subject"]["url"]
                    unread = notification["unread"]

                    if subject_type == "Issue":
                        github_url = subject_url.replace("api.github.com/repos", "github.com")
                    elif subject_type == "PullRequest":
                        github_url = subject_url.replace("api.github.com/repos", "github.com").replace(
                            "/pulls/", "/pull/"
                        )
                    elif subject_type == "Release":
                        github_url = f"https://github.com/{repo_full_name}/releases"
                    elif subject_type == "Discussion":
                        github_url = subject_url.replace("api.github.com/repos", "github.com")
                    else:
                        github_url = notification["repository"]["html_url"]

                    result.append(
                        {
                            "id": notification["id"],
                            "repository": repo_full_name,
                            "title": notification["subject"]["title"],
                            "type": subject_type,
                            "url": github_url,
                            "unread": unread,
                        }
                    )
                return result
            else:
                return []

        except urllib.error.URLError:
            logging.error("No internet connection. Unable to fetch notifications.")
            return []
        except urllib.error.HTTPError as e:
            logging.error(f"HTTP Error occurred: {e.code} - {e.reason}")
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            return []

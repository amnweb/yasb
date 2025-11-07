import os
import re
from enum import StrEnum
from typing import Any

from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QPainter, QPaintEvent
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, get_relative_time, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.github.api import GitHubDataManager
from core.validation.widgets.yasb.github import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


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
        reason_filters: list[str] | None,
        show_comment_count: bool,
        max_field_size: int,
        menu: dict[str, str],
        icons: dict[str, str],
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(timer_interval=None, class_name="github-widget")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._github_token = token if token != "env" else os.getenv("YASB_GITHUB_TOKEN")
        self._tooltip = tooltip
        self._menu_popup = menu
        self._icons = icons
        self._max_notification = max_notification
        self._only_unread = only_unread
        self._reason_filters = [str(reason) for reason in (reason_filters or []) if str(reason).strip()]
        self._show_comment_count = show_comment_count
        self._max_field_size = max_field_size
        self._update_interval = update_interval
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._show_categories = self._menu_popup.get("show_categories", True)
        categories_order = self._menu_popup.get("categories_order", [])
        if isinstance(categories_order, list):
            self._categories_order = [str(category) for category in categories_order]
        else:
            self._categories_order = []

        self._notification_label: NotificationLabel | None = None
        self._notification_label_alt: NotificationLabel | None = None
        self._notification_dot: dict[str, Any] = notification_dot

        self._shared_cursor = QCursor(Qt.CursorShape.PointingHandCursor)

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        callbacks = {"on_left": "toggle_menu", "on_right": "toggle_label"}
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]

        GitHubDataManager.register_callback(self._on_data_update)

        GitHubDataManager.initialize(
            token=self._github_token,
            only_unread=self._only_unread,
            max_notification=self._max_notification,
            update_interval=self._update_interval,
            reason_filters=self._reason_filters,
            show_comment_count=self._show_comment_count,
        )

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

    def _on_data_update(self, _notifications: list):
        QTimer.singleShot(0, self._update_label)

    def _update_label(self):
        github_data = GitHubDataManager.get_data()
        notification_count = len([notification for notification in github_data if notification["unread"]])
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
                    set_tooltip(current_widget, f"Notifications {notification_count}")
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
            refresh_widget_style(current_widget)

    def mark_as_read(self, notification_id, container_label):
        # Update in GitHubDataManager and sync with GitHub API
        GitHubDataManager.mark_as_read(notification_id, sync_to_github=True, token=self._github_token)
        current_classes = container_label.property("class").split()
        if "new" in current_classes:
            current_classes.remove("new")
        container_label.setProperty("class", " ".join(current_classes))
        container_label.setStyleSheet(container_label.styleSheet())
        container_label.repaint()

    def _mark_all_as_read(self):
        """Mark all notifications as read."""
        GitHubDataManager.mark_all_as_read(self._github_token)
        self._menu.hide()

    def _handle_mouse_press_event(self, event, notification_id, url, container_label):
        self.mark_as_read(notification_id, container_label)
        self._menu.hide()
        QDesktopServices.openUrl(QUrl(url))

    def _create_container_mouse_press_event(self, notification_id, url, container_label):
        def mouse_press_event(event):
            self._handle_mouse_press_event(event, notification_id, url, container_label)

        return mouse_press_event

    def _format_category_title(self, category_type: str) -> str:
        """Return a human-friendly label for a GitHub notification type."""
        custom_titles = {
            "Issue": "Issues",
            "PullRequest": "Pull Requests",
            "Release": "Releases",
            "Discussion": "Discussions",
            "CheckSuite": "Check Suites",
        }
        if category_type in custom_titles:
            return custom_titles[category_type]
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", category_type)
        return spaced.strip() or category_type

    def _resolve_icon_and_states(self, notification: dict[str, Any]) -> tuple[str, list[str]]:
        """Return icon and state class list for a notification."""
        notification_type = notification.get("type", "")
        state_classes: list[str] = []

        if notification_type == "Issue":
            issue_state = (notification.get("issue_state") or "").lower()
            if issue_state == "closed":
                icon_type = self._icons["issue_closed"]
            else:
                icon_type = self._icons["issue"]
            if issue_state:
                state_classes.append(issue_state)
        elif notification_type == "PullRequest":
            pr_state = (notification.get("pull_request_state") or "").lower()
            pr_is_merged = bool(notification.get("pull_request_is_merged"))
            pr_is_draft = bool(notification.get("pull_request_is_draft"))

            if pr_is_merged:
                icon_type = self._icons["pull_request_merged"]
                state_classes.append("merged")
            elif pr_state == "closed":
                icon_type = self._icons["pull_request_closed"]
            elif pr_is_draft:
                icon_type = self._icons["pull_request_draft"]
                state_classes.append("draft")
            else:
                icon_type = self._icons["pull_request"]

            if pr_state:
                state_classes.append(pr_state)
        elif notification_type == "Discussion":
            discussion_answered = bool(notification.get("discussion_is_answered"))
            if discussion_answered:
                icon_type = self._icons["discussion_answered"]
                state_classes.append("answered")
            else:
                icon_type = self._icons["discussion"]
        elif notification_type == "Release":
            icon_type = self._icons["release"]
        elif notification_type == "CheckSuite":
            icon_type = self._icons["checksuite"]
        else:
            icon_type = self._icons["default"]

        return icon_type, state_classes

    def _create_notification_item(
        self,
        notification: dict[str, Any],
        extra_classes: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> QFrame:
        title = notification["title"]
        if len(title) > self._max_field_size:
            title = title[: self._max_field_size - 3] + "..."

        if self._show_categories:
            repo_description = notification["repository"]
        else:
            repo_description = f"{notification['type']} • {notification['repository']}"

        updated_at = notification.get("updated_at", "")
        relative_time = get_relative_time(updated_at)
        if relative_time:
            repo_description = f"{repo_description} • Updated {relative_time}"

        if len(repo_description) > self._max_field_size:
            repo_description = repo_description[: self._max_field_size - 3] + "..."

        notification_type = notification.get("type", "")
        icon_type, state_classes = self._resolve_icon_and_states(notification)
        base_class = notification_type.lower() if notification_type else ""

        classes = ["item"]
        if notification.get("unread"):
            classes.append("new")

        if base_class:
            classes.append(base_class)
        if extra_classes:
            classes.extend(extra_classes)

        comment_count_value = notification.get("comment_count")

        container = QFrame(parent)
        container.setProperty("class", " ".join(dict.fromkeys(classes)))
        container.setContentsMargins(0, 0, 0, 0)
        container.setCursor(self._shared_cursor)

        icon_label = QLabel(icon_type)
        icon_classes = ["icon", base_class] if base_class else ["icon"]
        icon_classes.extend(state_classes)
        icon_label.setProperty("class", " ".join(dict.fromkeys(icon_classes)))

        title_label = QLabel(title)
        title_label.setProperty("class", "title")
        title_label.setContentsMargins(0, 0, 0, 0)

        description_label = QLabel(repo_description)
        description_label.setProperty("class", "description")
        description_label.setContentsMargins(0, 0, 0, 0)

        text_content = QWidget()
        text_content_layout = QVBoxLayout(text_content)
        text_content_layout.addWidget(title_label)
        text_content_layout.addWidget(description_label)
        text_content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_content_layout.setContentsMargins(0, 0, 0, 0)
        text_content_layout.setSpacing(0)

        container_layout = QHBoxLayout(container)
        container_layout.addWidget(icon_label)
        container_layout.addWidget(text_content, 1)

        if self._show_comment_count and isinstance(comment_count_value, int):
            comment_wrapper = QWidget()
            comment_wrapper_layout = QHBoxLayout(comment_wrapper)
            comment_wrapper_layout.setContentsMargins(8, 0, 0, 0)
            comment_wrapper_layout.setSpacing(0)

            comment_icon_text = (self._icons.get("comment", "") or "").strip()
            if comment_icon_text:
                comment_icon_label = QLabel(comment_icon_text)
                comment_icon_label.setProperty("class", "comment-icon")
                comment_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                comment_wrapper_layout.addWidget(comment_icon_label)

            comment_value_label = QLabel(str(comment_count_value))
            comment_value_label.setProperty("class", "comment-count")
            comment_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            comment_wrapper_layout.addWidget(comment_value_label)

            container_layout.addWidget(comment_wrapper)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        container.mousePressEvent = self._create_container_mouse_press_event(
            notification["id"], notification["url"], container
        )

        return container

    def show_menu(self):
        github_data = GitHubDataManager.get_data()
        notifications_count = len(github_data)
        notifications_unread_count = len([notification for notification in github_data if notification["unread"]])

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

        # Build the content first before attaching to scroll area
        if notifications_count > 0:
            if self._show_categories:
                grouped_notifications: dict[str, list[dict[str, Any]]] = {}
                for notification in github_data:
                    grouped_notifications.setdefault(notification["type"], []).append(notification)

                category_lookup = {key.lower(): key for key in grouped_notifications}

                ordered_categories: list[str] = []
                for configured_category in self._categories_order:
                    actual_key = category_lookup.get(configured_category.lower())
                    if actual_key and actual_key not in ordered_categories:
                        ordered_categories.append(actual_key)

                # Add remaining categories not in configured order
                for category in grouped_notifications:
                    if category not in ordered_categories:
                        ordered_categories.append(category)

                for category_type in ordered_categories:
                    items = grouped_notifications[category_type]

                    section_header = QLabel(self._format_category_title(category_type))
                    section_header.setProperty("class", "section-header")
                    section_header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    scroll_layout.addWidget(section_header)

                    section_widget = QFrame()
                    section_widget.setProperty("class", "section")

                    section_layout = QVBoxLayout(section_widget)
                    section_layout.setContentsMargins(0, 0, 0, 0)
                    section_layout.setSpacing(0)

                    items_count = len(items)
                    for index, notification in enumerate(items):
                        position_classes: list[str] = []
                        if index == 0:
                            position_classes.append("first")
                        if index == items_count - 1:
                            position_classes.append("last")
                        container = self._create_notification_item(
                            notification,
                            position_classes,
                            parent=section_widget,
                        )
                        section_layout.addWidget(container)

                    scroll_layout.addWidget(section_widget)
            else:
                section_widget = QFrame()
                section_widget.setProperty("class", "section")

                section_layout = QVBoxLayout(section_widget)
                section_layout.setContentsMargins(0, 0, 0, 0)
                section_layout.setSpacing(0)

                notifications_count_total = len(github_data)
                for index, notification in enumerate(github_data):
                    position_classes: list[str] = []
                    if index == 0:
                        position_classes.append("first")
                    if index == notifications_count_total - 1:
                        position_classes.append("last")
                    container = self._create_notification_item(
                        notification,
                        position_classes,
                        parent=section_widget,
                    )
                    section_layout.addWidget(container)

                scroll_layout.addWidget(section_widget)
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

        # Attach the fully-built widget to scroll area
        scroll_area.setWidget(scroll_widget)

        if notifications_count > 0:
            # Create footer container
            footer_container = QFrame()
            footer_container.setProperty("class", "footer")
            footer_layout = QHBoxLayout(footer_container)
            footer_layout.setContentsMargins(0, 0, 0, 0)
            footer_layout.setSpacing(0)

            # Left side - unread count
            footer_label = QLabel(f"Unread notifications ({notifications_unread_count})")
            footer_label.setProperty("class", "label")
            footer_layout.addWidget(footer_label)

            footer_layout.addStretch()

            # Right side - mark all as read button
            mark_all_label = QLabel("Mark all as read")
            mark_all_label.setProperty("class", "label")
            mark_all_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            mark_all_label.mousePressEvent = lambda event: self._mark_all_as_read()
            footer_layout.addWidget(mark_all_label)

            main_layout.addWidget(footer_container)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_popup["alignment"],
            direction=self._menu_popup["direction"],
            offset_left=self._menu_popup["offset_left"],
            offset_top=self._menu_popup["offset_top"],
        )

        self._menu.show()

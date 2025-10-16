import logging
import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.event_service import EventService
from core.utils.utilities import add_shadow, build_widget_label, is_windows_10, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.system_function import notification_center, quick_settings
from core.validation.widgets.yasb.notifications import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

try:
    from core.utils.widgets.notifications.windows_notification import WindowsNotificationEventListener
except ImportError:
    WindowsNotificationEventListener = None
    logging.warning("Failed to load Windows Notification Event Listener")


class NotificationsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    windows_notification_update_signal = pyqtSignal(int)
    event_listener = WindowsNotificationEventListener

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        hide_empty: bool,
        tooltip: bool,
        icons: dict,
        container_padding: dict,
        animation: dict[str, str],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"notification-widget {class_name}")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._notification_count = 0

        self._hide_empty = hide_empty
        self._tooltip = tooltip
        self._icons = icons
        self._padding = container_padding
        self._animation = animation
        self._callbacks = callbacks
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

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

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_notification", self._toggle_notification)
        self.register_callback("clear_notifications", self._clear_notifications)

        # Register the WindowsNotificationUpdate event
        self.event_service = EventService()
        self.event_service.register_event("WindowsNotificationUpdate", self.windows_notification_update_signal)
        self.windows_notification_update_signal.connect(self._on_windows_notification_update)

        self._update_label()

    def _on_windows_notification_update(self, total_notifications):
        self._notification_count = total_notifications
        if total_notifications > 0:
            self.setVisible(True)
        elif self._hide_empty:
            self.setVisible(False)
        self._update_label()

    def _toggle_notification(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if is_windows_10():
            quick_settings()
        else:
            notification_center()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _clear_notifications(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if WindowsNotificationEventListener:
            self.event_service.emit_event("WindowsNotificationClear", "clear_all_notifications")

    def _update_label(self):
        if self._notification_count == 0 and self._hide_empty:
            self.setVisible(False)
            return

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        if self._notification_count > 0:
            icon = self._icons["new"]
        else:
            icon = self._icons["default"]

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        # Provide replacements for {count} and {icon}
        label_options = [("{count}", self._notification_count), ("{icon}", icon)]

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

                # Update class based on notification count
                current_class = active_widgets[widget_index].property("class")
                if self._notification_count > 0:
                    if "new-notification" not in current_class:
                        current_class += " new-notification"
                else:
                    current_class = current_class.replace(" new-notification", "")

                active_widgets[widget_index].setProperty("class", current_class.strip())

                widget_index += 1
        for widget in active_widgets:
            refresh_widget_style(widget)

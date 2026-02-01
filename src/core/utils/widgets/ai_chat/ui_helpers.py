import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow
from core.utils.widgets.ai_chat.ui_components import NotificationLabel
from core.utils.win32.utilities import get_foreground_hwnd, set_foreground_hwnd


class FocusManager:
    def __init__(self, owner):
        self._owner = owner

    def remember_foreground(self):
        self._owner._previous_hwnd = get_foreground_hwnd()

    def restore_previous_focus(self):
        if getattr(self._owner, "_previous_hwnd", 0):
            try:
                set_foreground_hwnd(self._owner._previous_hwnd)
            finally:
                self._owner._previous_hwnd = 0


class FloatingWindowController:
    def __init__(self, owner):
        self._owner = owner

    def toggle_floating(self):
        if not self._owner._is_popup_valid():
            return

        if not self._owner._is_floating:
            self._owner._original_position = self._owner._popup_chat.pos()
            self._owner._is_floating = True
            self._owner._popup_chat.set_floating(True)
            screen = self._owner._popup_chat.screen()
            if screen:
                screen_geometry = screen.availableGeometry()
                popup_size = self._owner._popup_chat.size()
                center_x = screen_geometry.x() + (screen_geometry.width() - popup_size.width()) // 2
                center_y = screen_geometry.y() + (screen_geometry.height() - popup_size.height()) // 2
                self._owner._popup_chat.move(center_x, center_y)

            self._owner.float_btn.setText(self._owner._icons["float_off"])
            set_tooltip(self._owner.float_btn, "Dock window")
            if hasattr(self._owner, "close_btn"):
                self._owner.close_btn.setVisible(True)
        else:
            self._owner._is_floating = False
            self._owner._popup_chat.set_floating(False)
            if self._owner._original_position:
                self._owner._popup_chat.move(self._owner._original_position)

            self._owner.float_btn.setText(self._owner._icons["float_on"])
            set_tooltip(self._owner.float_btn, "Float window")
            if hasattr(self._owner, "close_btn"):
                self._owner.close_btn.setVisible(False)

    def header_mouse_press(self, event: QMouseEvent):
        if self._owner._is_floating and event.button() == Qt.MouseButton.LeftButton:
            self._owner._drag_position = (
                event.globalPosition().toPoint() - self._owner._popup_chat.frameGeometry().topLeft()
            )
            event.accept()

    def header_mouse_move(self, event: QMouseEvent):
        if (
            self._owner._is_floating
            and hasattr(self._owner, "_drag_position")
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._owner._popup_chat.move(event.globalPosition().toPoint() - self._owner._drag_position)
            event.accept()

    def header_mouse_release(self, event: QMouseEvent):
        if hasattr(self._owner, "_drag_position"):
            delattr(self._owner, "_drag_position")
            event.accept()


class LabelBuilder:
    def __init__(self, owner):
        self._owner = owner

    def create_dynamically_label(self, content: str):
        label_parts = re.split("(<span.*?>.*?</span>)", content)
        label_parts = [part for part in label_parts if part]
        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                class_name = re.search(r'class=(["\"])([^"\"]+?)\1', part)
                class_result = class_name.group(2) if class_name else "icon"
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                label = NotificationLabel(
                    icon,
                    corner=self._owner._notification_dot["corner"],
                    color=self._owner._notification_dot["color"],
                    margin=self._owner._notification_dot["margin"],
                )
                label.setProperty("class", class_result)
                self._owner._notification_label = label
            else:
                label = NotificationLabel(
                    part,
                    corner=self._owner._notification_dot["corner"],
                    color=self._owner._notification_dot["color"],
                    margin=self._owner._notification_dot["margin"],
                )
                label.setProperty("class", "label")
                self._owner._notification_label = label
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            add_shadow(label, self._owner._label_shadow)
            self._owner._widget_container_layout.addWidget(label)
            label.show()

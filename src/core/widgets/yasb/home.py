import logging
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.power_menu.power_commands import PowerOperations
from core.validation.widgets.yasb.home import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class HomeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        container_padding: dict,
        power_menu: bool,
        system_menu: bool,
        blur: bool,
        round_corners: bool,
        round_corners_type: str,
        border_color: str,
        alignment: str,
        direction: str,
        distance: int,
        offset_top: int,
        offset_left: int,
        menu_labels: dict[str, str],
        animation: dict[str, str],
        callbacks: dict[str, str],
        menu_list: list[str, dict[str]] = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="home-widget")
        self.power_operations = PowerOperations()
        self._label = label
        self._menu_list = menu_list
        self._padding = container_padding
        self._power_menu = power_menu
        self._system_menu = system_menu
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color
        self._alignment = alignment
        self._direction = direction
        self._distance = distance
        self._offset_top = offset_top
        self._offset_left = offset_left
        self._menu_labels = menu_labels
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
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
        build_widget_label(self, self._label, None, self._label_shadow)

        self.register_callback("toggle_menu", self._toggle_menu)
        self.callback_left = callbacks["on_left"]

    def create_menu_action(self, path):
        path = os.path.expanduser(path)
        return (
            lambda: os.startfile(path)
            if os.path.exists(path)
            else logging.error(f"The system cannot find the file specified: '{path}'")
        )

    def _create_menu(self):
        self._menu = PopupWidget(self, self._blur, self._round_corners, self._round_corners_type, self._border_color)
        self._menu.setProperty("class", "home-menu")

        # Create main vertical layout for the popup
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        if self._system_menu:
            # System menu items
            self._add_menu_item(
                main_layout,
                self._menu_labels["about"],
                lambda: subprocess.Popen("winver", shell=True, creationflags=subprocess.CREATE_NO_WINDOW),
            )

            self._menu._add_separator(main_layout)

            self._add_menu_item(main_layout, self._menu_labels["system"], lambda: os.startfile("ms-settings:"))

            self._add_menu_item(
                main_layout,
                self._menu_labels["task_manager"],
                lambda: subprocess.Popen("taskmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW),
            )

            self._menu._add_separator(main_layout)

        # Custom menu items
        if isinstance(self._menu_list, list):
            for menu_item in self._menu_list:
                if "title" in menu_item and "path" in menu_item:
                    self._add_menu_item(main_layout, menu_item["title"], self.create_menu_action(menu_item["path"]))
        if self._menu_list is not None and len(self._menu_list) > 0 and self._power_menu:
            self._menu._add_separator(main_layout)

        if self._power_menu:
            self._add_menu_item(main_layout, self._menu_labels["hibernate"], lambda: self.power_operations.hibernate())
            self._add_menu_item(main_layout, self._menu_labels["sleep"], lambda: self.power_operations.sleep())
            self._add_menu_item(main_layout, self._menu_labels["restart"], lambda: self.power_operations.restart())
            self._add_menu_item(main_layout, self._menu_labels["shutdown"], lambda: self.power_operations.shutdown())

            self._menu._add_separator(main_layout)

            self._add_menu_item(main_layout, self._menu_labels["lock"], lambda: self.power_operations.lock())
            self._add_menu_item(main_layout, self._menu_labels["logout"], lambda: self.power_operations.signout())

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._alignment,
            direction=self._direction,
            offset_left=self._offset_left,
            offset_top=self._offset_top,
        )
        self._menu.show()

    def _add_menu_item(self, layout, text, triggered_func):
        # Create widget container
        item = QWidget()
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)

        # Create label
        label = QLabel(text)
        label.setProperty("class", "menu-item")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setCursor(Qt.CursorShape.PointingHandCursor)

        # Add label to layout
        item_layout.addWidget(label)

        # Add click event
        def mouse_press_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._menu.hide()
                triggered_func()

        item.mousePressEvent = mouse_press_handler
        layout.addWidget(item)

        return item

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._create_menu()

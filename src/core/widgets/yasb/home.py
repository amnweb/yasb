import logging
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.power_menu.power_commands import PowerOperations
from core.validation.widgets.yasb.home import HomeConfig, MenuItemConfig
from core.widgets.base import BaseWidget


class HomeWidget(BaseWidget):
    validation_schema = HomeConfig

    def __init__(self, config: HomeConfig):
        super().__init__(class_name="home-widget")
        self.config = config
        self.power_operations = PowerOperations()
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
        build_widget_label(self, self.config.label, None, self.config.label_shadow.model_dump())

        self.register_callback("toggle_menu", self._toggle_menu)
        self.callback_left = self.config.callbacks.on_left

    def create_menu_action(self, menu_item: MenuItemConfig):
        action_keys = [key for key in ("command", "uri", "path") if getattr(menu_item, key, None)]
        if len(action_keys) > 1:
            return lambda: logging.error("Home menu item must define only one of: 'path', 'uri', or 'command'.")
        if len(action_keys) == 0:
            return lambda: logging.error("Home menu item missing 'path', 'uri', or 'command'.")

        if menu_item.command:
            command = menu_item.command
            if not command:
                return lambda: logging.error("Home menu item missing 'command'.")

            args = menu_item.args
            shell = menu_item.shell
            show_window = menu_item.show_window or False
            if args is not None:
                cmd = [command, *args]
                if shell is None:
                    shell = False
            else:
                cmd = command
                if shell is None:
                    shell = True

            creation_flags = subprocess.CREATE_NEW_CONSOLE if show_window else subprocess.CREATE_NO_WINDOW
            return lambda: subprocess.Popen(cmd, shell=shell, creationflags=creation_flags)

        if menu_item.uri:
            uri = menu_item.uri
            if not uri:
                return lambda: logging.error("Home menu item missing 'uri'.")
            return lambda: os.startfile(uri)

        if menu_item.path:
            path = menu_item.path
            if not path:
                return lambda: logging.error("Home menu item missing 'path'.")
            path = os.path.expanduser(path)
            return lambda: (
                os.startfile(path)
                if os.path.exists(path)
                else logging.error(f"The system cannot find the file specified: '{path}'")
            )

    def _create_menu(self):
        self._menu = PopupWidget(
            self,
            self.config.blur,
            self.config.round_corners,
            self.config.round_corners_type,
            self.config.border_color,
        )
        self._menu.setProperty("class", "home-menu")

        # Create main vertical layout for the popup
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        if self.config.system_menu:
            # System menu items
            self._add_menu_item(
                main_layout,
                self.config.menu_labels.about,
                lambda: subprocess.Popen("winver", shell=True, creationflags=subprocess.CREATE_NO_WINDOW),
            )

            self._menu._add_separator(main_layout)

            self._add_menu_item(main_layout, self.config.menu_labels.system, lambda: os.startfile("ms-settings:"))

            self._add_menu_item(
                main_layout,
                self.config.menu_labels.task_manager,
                lambda: subprocess.Popen("taskmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW),
            )

            self._menu._add_separator(main_layout)

        # Custom menu items
        if isinstance(self.config.menu_list, list):
            for menu_item in self.config.menu_list:
                if menu_item.separator:
                    self._menu._add_separator(main_layout)
                    continue
                if menu_item.title:
                    self._add_menu_item(main_layout, menu_item.title, self.create_menu_action(menu_item))
        if self.config.menu_list is not None and len(self.config.menu_list) > 0 and self.config.power_menu:
            self._menu._add_separator(main_layout)

        if self.config.power_menu:
            self._add_menu_item(
                main_layout,
                self.config.menu_labels.hibernate,
                lambda: self.power_operations.hibernate(),
            )
            self._add_menu_item(main_layout, self.config.menu_labels.sleep, lambda: self.power_operations.sleep())
            self._add_menu_item(main_layout, self.config.menu_labels.restart, lambda: self.power_operations.restart())
            self._add_menu_item(main_layout, self.config.menu_labels.shutdown, lambda: self.power_operations.shutdown())

            self._menu._add_separator(main_layout)

            self._add_menu_item(main_layout, self.config.menu_labels.lock, lambda: self.power_operations.lock())
            self._add_menu_item(main_layout, self.config.menu_labels.logout, lambda: self.power_operations.signout())

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.alignment,
            direction=self.config.direction,
            offset_left=self.config.offset_left,
            offset_top=self.config.offset_top,
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
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._create_menu()

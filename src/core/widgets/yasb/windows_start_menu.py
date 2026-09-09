from PyQt6.QtWidgets import QLabel

from core.utils.win32.system_function import start_menu
from core.validation.widgets.yasb.windows_start_menu import WindowsStartMenuConfig
from core.widgets.base import BaseWidget


class WindowsStartMenu(BaseWidget):
    validation_schema = WindowsStartMenuConfig

    def __init__(self, config: WindowsStartMenuConfig):
        super().__init__(class_name="windows-start-menu")
        self._init_container()

        self._label = self._create_label(config)
        self._widget_container_layout.addWidget(self._label)

        self.register_callback("start_menu", start_menu)
        self.callback_left = "start_menu"

    def _create_label(self, config: WindowsStartMenuConfig) -> QLabel:
        label = QLabel(config.icon)

        # Increase the clickable area of the label.
        label.setContentsMargins(4, 4, 4, 4)

        return label

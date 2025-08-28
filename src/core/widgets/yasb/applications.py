import logging
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.system_function import function_map
from core.validation.widgets.yasb.applications import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ApplicationsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        class_name: str,
        app_list: list[str, dict[str]],
        image_icon_size: int,
        animation: dict[str, str],
        tooltip: bool,
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"apps-widget {class_name}")
        self._label = label

        self._apps = app_list
        self._padding = container_padding
        self._image_icon_size = image_icon_size
        self._animation = animation
        self._tooltip = tooltip
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
        self._update_label()

    def _update_label(self):
        if isinstance(self._apps, list):
            for app_data in self._apps:
                if "icon" in app_data and "launch" in app_data:
                    # Create a container widget for each label
                    label_container = QWidget()
                    label_layout = QHBoxLayout(label_container)
                    label_layout.setContentsMargins(0, 0, 0, 0)
                    label_layout.setSpacing(0)

                    # Create the label
                    label = ClickableLabel(self)
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    label.setProperty("class", "label")

                    app_name = app_data.get("name", "")
                    if app_name and self._tooltip:
                        set_tooltip(label, app_name, 0)

                    # Set icon
                    icon = app_data["icon"]
                    if os.path.isfile(icon):
                        pixmap = QPixmap(icon).scaled(
                            self._image_icon_size,
                            self._image_icon_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        label.setPixmap(pixmap)
                    else:
                        label.setText(icon)

                    label.data = app_data["launch"]
                    label.container = label_container  # Store reference to container

                    # Add shadow to the label
                    add_shadow(label, self._label_shadow)

                    # Add label to its container
                    label_layout.addWidget(label)

                    # Add container to main layout
                    self._widget_container_layout.addWidget(label_container)
        else:
            logging.error(f"Expected _apps to be a list but got {type(self._apps)}")

    def execute_code(self, data):
        try:
            if data in function_map:
                function_map[data]()
            else:
                try:
                    if not any(param in data for param in ["-new-tab", "-new-window", "-private-window"]):
                        data = data.split()
                    subprocess.Popen(data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                except Exception as e:
                    logging.error(f"Error starting app: {str(e)}")
        except Exception as e:
            logging.error(f'Exception occurred: {str(e)} "{data}"')


class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.data:
            if self.parent_widget._animation["enabled"]:
                AnimationManager.animate(
                    self.container, self.parent_widget._animation["type"], self.parent_widget._animation["duration"]
                )
            self.parent_widget.execute_code(self.data)

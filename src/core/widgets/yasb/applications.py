import logging
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.win32.system_function import function_map
from core.validation.widgets.yasb.applications import ApplicationsWidgetConfig
from core.widgets.base import BaseWidget


class ApplicationsWidget(BaseWidget):
    validation_schema = ApplicationsWidgetConfig

    def __init__(self, config: ApplicationsWidgetConfig):
        super().__init__(class_name=f"apps-widget {config.class_name}")
        self.config = config

        # Construct container
        self._init_container()
        self._update_label()

    def _update_label(self):
        for app_data in self.config.app_list:
            if app_data.icon and app_data.launch:
                # Create a container widget for each label
                label_container = QWidget()
                label_layout = QHBoxLayout(label_container)
                label_layout.setContentsMargins(0, 0, 0, 0)
                label_layout.setSpacing(0)

                # Create the label
                label = ClickableLabel(self)
                label.setProperty("class", "label")

                app_name = app_data.name
                if app_name and self.config.tooltip:
                    set_tooltip(label, app_name, 0)

                # Set icon
                icon = app_data.icon
                if os.path.isfile(icon):
                    pixmap = QPixmap(icon).scaled(
                        self.config.image_icon_size,
                        self.config.image_icon_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    label.setPixmap(pixmap)
                else:
                    label.setText(icon)

                label.data = app_data.launch
                label.container = label_container  # Store reference to container

                # Add label to its container
                label_layout.addWidget(label)

                # Add container to main layout
                self._widget_container_layout.addWidget(label_container)

    def execute_code(self, data: str):
        try:
            if data in function_map:
                function_map[data]()
            else:
                try:
                    cmd_args: str | list[str] = data
                    if not any(param in data for param in ["-new-tab", "-new-window", "-private-window"]):
                        cmd_args = data.split()
                    subprocess.Popen(cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                except Exception as e:
                    logging.error("Error starting app: %s", e)
        except Exception as e:
            logging.error('Exception occurred: %s "%s"', e, data)


class ClickableLabel(QLabel):
    def __init__(self, parent: ApplicationsWidget | None = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None

    def mousePressEvent(self, event):
        if event is not None:
            event.accept()

    def mouseReleaseEvent(self, event):
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.data and self.parent_widget:
            self.parent_widget.execute_code(self.data)
        event.accept()

import os
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.applications import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QGraphicsOpacityEffect
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtCore import Qt, QTimer
import subprocess
import logging
from core.utils.win32.system_function import function_map

class ApplicationsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, class_name: str,app_list:  list[str, dict[str]], image_icon_size: int, container_padding: dict):
        super().__init__(class_name=f"apps-widget {class_name}")
        self._label = label
        self._apps = app_list
        self._padding = container_padding
        self._image_icon_size = image_icon_size
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._update_label()

    def _update_label(self):
        if isinstance(self._apps, list):
            for app_data in self._apps:
                if 'icon' in app_data and 'launch' in app_data:
                    label = ClickableLabel(self)
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    label.setProperty("class", "label")
                    icon = app_data['icon']
                    if os.path.isfile(icon):
                        pixmap = QPixmap(icon).scaled(self._image_icon_size, self._image_icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        label.setPixmap(pixmap)
                    else:
                        label.setText(icon)
                    label.data = app_data['launch']
                    self._widget_container_layout.addWidget(label)
        else:
            logging.error(f"Expected _apps to be a list but got {type(self._apps)}")

    def execute_code(self, data):
        try:
            if data in function_map:
                function_map[data]()
            else:    
                try:
                    command = data.split()
                    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                except Exception as e:
                    logging.error(f"Error starting app: {str(e)}")
        except Exception as e:
            logging.error(f"Exception occurred: {str(e)} \"{data}\"")
 
        
class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None
        self._opacity_effect = None
        self._blink_timer = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.data:
            self._blink_on_click()
            self.parent_widget.execute_code(self.data)

    def _blink_on_click(self, duration=200):
        if hasattr(self, '_opacity_effect') and self._opacity_effect is not None:
            self._opacity_effect.setOpacity(1.0)
            if self._blink_timer.isActive():
                self._blink_timer.stop()

        self._opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.4)

        self._blink_timer = QTimer()
        step = 0
        steps = 20
        increment = 0.5 / steps

        def animate():
            nonlocal step
            new_opacity = self._opacity_effect.opacity() + increment
            if new_opacity >= 1.0:
                new_opacity = 1.0
                self._opacity_effect.setOpacity(new_opacity)
                self._blink_timer.stop()
                self._opacity_effect = None
                return
            self._opacity_effect.setOpacity(new_opacity)
            step += 1

        self._blink_timer.timeout.connect(animate)
        self._blink_timer.start(duration // steps)
            
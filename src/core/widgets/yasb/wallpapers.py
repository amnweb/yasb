import os
import logging
import ctypes
import random
import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.wallpapers import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from core.widgets.yasb.applications import ClickableLabel

class WallpapersWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    _timer_running = False
    def __init__(
        self,
        label: str,
        update_interval: int,
        change_automatically: bool,
        image_path: str
    ):
        super().__init__(int(update_interval * 1000), class_name="wallpapers-widget")

        self._label_content = label
        self._change_automatically = change_automatically
        self._image_path = image_path
        self._last_image = None  # Track the last selected image

        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content)

        self.register_callback("change_background", self.change_background)

        self.callback_timer = "change_background"
        if self._change_automatically:
            self.start_timer()

    def start_timer(self):
        if not WallpapersWidget._timer_running:
            if self.timer_interval and self.timer_interval > 0:
                self.timer.timeout.connect(self._timer_callback)
                self.timer.start(self.timer_interval)
                WallpapersWidget._timer_running = True

    def _create_dynamically_label(self, content: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content) #Filters out empty parts before entering the loop
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = ClickableLabel(icon)
                    label.setProperty("class", class_result)
                    label.setToolTip(f'Change Wallaper')
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = ClickableLabel(part)
                    label.setProperty("class", "label") 
                    label.setToolTip(f'Change Wallaper')
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                label.clicked.connect(self.change_background)
            return widgets
        self._widgets = process_content(content)

        
    def _update_label(self):
        active_widgets = self._widgets
        active_label_content = self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if part:              
                if '<span' in part and '</span>' in part:
                    # Update icon ClickableLabel
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1
 

    def change_background(self):
        try:
            # Define valid image extensions
            valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
            # Get a list of all image files in the images folder
            images = [f for f in os.listdir(self._image_path) if os.path.isfile(os.path.join(self._image_path, f)) and f.lower().endswith(valid_extensions)]
            if not images:
                return

            # Select a random image that is different from the last one
            random_image = random.choice(images)
            while random_image == self._last_image and len(images) > 1:
                random_image = random.choice(images)

            # Full path to the selected image
            image_path = os.path.join(self._image_path, random_image)
            # Change the desktop background
            ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 3)
            # Update the last selected image
            self._last_image = random_image
        except Exception as e:
            logging.error("Error changing wallpaper: %s", str(e))
    
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        super().mouseReleaseEvent(event) 
import psutil
import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.disk import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt

class DiskWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            volume_label: str,
            update_interval: int,
            callbacks: dict[str, str],
    ):
        super().__init__(int(update_interval * 1000), class_name="disk-widget")
 
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._volume_label = volume_label
        
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

        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"
        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
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
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets
        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        try:
            disk_space = self._get_space()
        except Exception:
            disk_space = None

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    # Ensure the icon is correctly set
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    # Update label with formatted content
                    formatted_text = part.format(space=disk_space, volume_label=self._volume_label) if disk_space else part
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

 

    def _get_space(self):
        partitions = psutil.disk_partitions()
        specific_partitions = [partition for partition in partitions if partition.device in (f'{self._volume_label}:\\')]
 
        for partition in specific_partitions:
            usage = psutil.disk_usage(partition.mountpoint)
            percent_used = usage.percent
            percent_free = 100 - percent_used
            return {
                "total": {
                    'mb': f"{usage.total / (1024 ** 2):.1f}MB",
                    'gb': f"{usage.total / (1024 ** 3):.1f}GB"
                },
                "free": {
                    'mb': f"{usage.free / (1024 ** 2):.1f}MB",
                    'gb': f"{usage.free / (1024 ** 3):.1f}GB",
                    'percent': f"{percent_free:.1f}%"
                },
                "used": {
                    'mb': f"{usage.used / (1024 ** 2):.1f}MB",
                    'gb': f"{usage.used / (1024 ** 3):.1f}GB",
                    'percent': f"{percent_used:.1f}%"
                }
            }
        return None
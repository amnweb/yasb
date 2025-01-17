import re
import psutil
import logging
from settings import DEBUG
from humanize import naturalsize
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.traffic import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel,QHBoxLayout,QWidget
from PyQt6.QtCore import Qt
from core.utils.widgets.animation_manager import AnimationManager

class TrafficWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    # initialize io counters
    io = psutil.net_io_counters()
    bytes_sent = io.bytes_sent
    bytes_recv = io.bytes_recv
    interval = 1

    def __init__(
        self,
        label: str,
        label_alt: str,
        interface: str,
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
    ):
        super().__init__(update_interval, class_name="traffic-widget")
        self.interval = update_interval // 1000

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._interface = interface
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
       
        self._create_dynamically_label(self._label_content,self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"
        if DEBUG:
            if self._interface == "Auto":
                logging.debug("Network Interface: Auto")
            else:
                logging.debug(f"Network Interface: {self._interface}")
        self.start_timer()

    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
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
            upload_speed, download_speed = self._get_speed()
        except Exception:
            upload_speed, download_speed = "N/A", "N/A"

        label_options = [("{upload_speed}", upload_speed), ("{download_speed}", download_speed)]

        for part in label_parts:
            part = part.strip()
            for option, value in label_options:
                part = part.replace(option, str(value))
            
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1


    def _get_speed(self) -> list[str]:
        if self._interface == "Auto":
            current_io = psutil.net_io_counters()
        else:
            io_counters = psutil.net_io_counters(pernic=True)
            if self._interface not in io_counters:
                return "N/A", "N/A"
            current_io = io_counters[self._interface]
            
        upload_diff = current_io.bytes_sent - self.bytes_sent
        download_diff = current_io.bytes_recv - self.bytes_recv

        if upload_diff < 1024:
            upload_speed = f"{upload_diff} B/s"
        else:
            upload_speed = naturalsize(
                (current_io.bytes_sent - self.bytes_sent) // self.interval,
            ) + "/s"

        if download_diff < 1024:
            download_speed = f"{download_diff} B/s"
        else:
            download_speed = naturalsize(
                (current_io.bytes_recv - self.bytes_recv) // self.interval,
            ) + "/s"

        self.bytes_sent = current_io.bytes_sent
        self.bytes_recv = current_io.bytes_recv
        return upload_speed, download_speed
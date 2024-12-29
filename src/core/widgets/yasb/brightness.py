import re
import ctypes
import logging
from settings import DEBUG
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.brightness import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QWheelEvent, QCursor
from core.utils.win32.utilities import get_monitor_info
import screen_brightness_control as sbc
from datetime import datetime

if DEBUG:
    logging.getLogger("screen_brightness_control").setLevel(logging.INFO)
else:
    logging.getLogger("screen_brightness_control").setLevel(logging.CRITICAL)
 
user32 = ctypes.WinDLL('user32', use_last_error=True)

class BrightnessWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        tooltip: bool,
        brightness_icons: list[str],
        hide_unsupported: bool,
        auto_light: bool,
        auto_light_icon: str,
        auto_light_night_level: int,
        auto_light_night_start_time: str,
        auto_light_night_end_time: str,
        auto_light_day_level: int,
        container_padding: dict[str, int],
        callbacks: dict[str, str]
    ):
        super().__init__(class_name="brightness-widget")
        self._show_alt_label = False
        
        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip = tooltip
        self._padding = container_padding
        self._brightness_icons = brightness_icons
        self._hide_unsupported = hide_unsupported
        self._auto_light = auto_light
        self._auto_light_icon = auto_light_icon
        self._auto_light_night_level = auto_light_night_level
        self._auto_light_night_start = datetime.strptime(auto_light_night_start_time, "%H:%M").time()
        self._auto_light_night_end = datetime.strptime(auto_light_night_end_time, "%H:%M").time()
        self._auto_light_day_level = auto_light_day_level
        self._step = 1
        self._current_mode = None
        
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'], self._padding['top'], self._padding['right'], self._padding['bottom'])
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        
        QTimer.singleShot(10, self._update_label)
        
        if self._auto_light:
            self._auto_light_timer = QTimer()
            self._auto_light_timer.timeout.connect(self.auto_light)
            self._auto_light_timer.start(60000)
            QTimer.singleShot(1000, self.auto_light)
        
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
                part = part.strip()
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
                label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                    label.setProperty("class", "label alt")
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
            percent = self.get_brightness()
            if percent is None:
                if self._hide_unsupported:
                    self.hide()
                return
            if percent is not None:
                icon = self.get_brightness_icon(percent)
                if self._tooltip:
                    self.setToolTip(f'Brightness {percent}%')
            else:
                percent, icon = 0, "not supported"
        except Exception:
             percent, icon = 0, "not supported"
            
        label_options = {
            "{icon}": icon,
            "{percent}": percent
        }
        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if '<span' in part and '</span>' in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                widget_index += 1


    def extract_display_number(self, device_path: str) -> int:
        try:
            # Extract everything after 'DISPLAY'
            display_num = device_path.split('DISPLAY')[-1]
            # Convert to integer, removing any non-numeric chars, we need to get onlu integer
            return int(''.join(filter(str.isdigit, display_num)))
        except (IndexError, ValueError):
            if DEBUG:
                logging.warning(f"Failed to extract display number from {device_path}")
            return None
    
    
    def get_monitor_handle(self):
        try:
            hwnd = int(self.winId())
            hmonitor = user32.MonitorFromWindow(hwnd, 2)
            monitor_info = get_monitor_info(hmonitor)
            
            if not monitor_info:
                if DEBUG:
                    logging.warning("Failed to get monitor info")
                return None
            
            if not isinstance(self.extract_display_number(monitor_info['device']), int):
                if DEBUG:
                    logging.warning("Failed to get monitor number")
                return None
            
            return {
                'device_name': self.screen().name(),
                'device_id': self.extract_display_number(monitor_info['device']) - 1,
                'device': monitor_info['device']
            }
 
        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to get monitor handle: {e}")
            return None
        

    def get_brightness(self):
        monitor_info = self.get_monitor_handle()      
        try:
            if DEBUG:
                logging.info(f" device_id = {monitor_info['device_id']}, device {monitor_info['device']}, device_name {monitor_info['device_name']}")
            brightness = sbc.get_brightness(display=monitor_info['device_id'])[0]
            return brightness
        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to get primary display brightness: {e}")
            return None
 

    def set_brightness(self, brightness: int, device_id: int) -> None:
        try:   
            sbc.set_brightness(brightness, display=device_id)
            self._update_label()
        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to set laptop brightness: {e}")
           
      
    def update_brightness(self, increase: bool, decrease: bool) -> None:
        try:
            current = self.get_brightness()
            if current is None:
                return
            if increase:
                new_brightness = min(current + self._step, 100)
            elif decrease:
                new_brightness = max(current - self._step, 0)
            else:
                return
            
            monitor_info = self.get_monitor_handle()
            try:
                if not monitor_info:
                    return None

                self.set_brightness(new_brightness, monitor_info['device_id'])
            except Exception as e:
                if DEBUG:
                    logging.warning(f"Failed to set laptop brightness: {e}")

        except Exception as e:
            if DEBUG:
                logging.warning(f"Failed to update brightness: {e}")
    

    def get_brightness_icon(self, brightness: int):
        if self._auto_light:
            return self._auto_light_icon
        if 0 <= brightness <= 25:
            icon = self._brightness_icons[0]
        elif 26 <= brightness <= 50:
            icon = self._brightness_icons[1]
        elif 51 <= brightness <= 75:
            icon = self._brightness_icons[2]
        else:
            icon = self._brightness_icons[3]
        return icon


    def auto_light(self):
        current_time = datetime.now().time()
        monitor_info = self.get_monitor_handle()
        if not monitor_info:
            return
        # Handle midnight crossing
        if self._auto_light_night_start <= self._auto_light_night_end:
            is_night = self._auto_light_night_start <= current_time <= self._auto_light_night_end
        else:
            is_night = current_time >= self._auto_light_night_start or current_time <= self._auto_light_night_end
        new_mode = 'night' if is_night else 'day'
        # Only set brightness if mode changed
        if new_mode != self._current_mode:
            self._current_mode = new_mode
            if is_night:
                self.set_brightness(self._auto_light_night_level, monitor_info['device_id'])
            else:
                self.set_brightness(self._auto_light_day_level, monitor_info['device_id'])
        
        
    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.update_brightness(increase=True, decrease=False)
        elif event.angleDelta().y() < 0:
            self.update_brightness(increase=False, decrease=True)
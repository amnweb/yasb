import re
import pytz
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.clock import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from datetime import datetime
from tzlocal import get_localzone_name
from itertools import cycle
from core.utils.widgets.animation_manager import AnimationManager

class ClockWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            locale: str,
            tooltip: bool,
            update_interval: int,
            timezones: list[str],
            animation: dict[str, str],
            container_padding: dict[str, int],
            callbacks: dict[str, str],
    ):
        super().__init__(update_interval, class_name="clock-widget")
        self._locale = locale
        self._tooltip = tooltip
        self._active_tz = None
        self._timezones = cycle(timezones if timezones else [get_localzone_name()])
        self._active_datetime_format_str = ''
        self._active_datetime_format = None
        self._animation = animation
        self._label_content = label
        self._padding = container_padding
        self._label_alt_content = label_alt
        if self._locale:
            import locale
            locale.setlocale(locale.LC_TIME, self._locale)
 
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

        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("next_timezone", self._next_timezone)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

        self._show_alt_label = False

        self._next_timezone()
        self._update_label()
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
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setCursor(Qt.CursorShape.PointingHandCursor)
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

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    try:
                        datetime_format_search = re.search('\\{(.*)}', part)
                        datetime_format_str = datetime_format_search.group()
                        datetime_format = datetime_format_search.group(1)
                        datetime_now = datetime.now(pytz.timezone(self._active_tz))
                        format_label_content = part.replace(datetime_format_str,datetime_now.strftime(datetime_format))
                    except Exception:
                        format_label_content = part                    
                    active_widgets[widget_index].setText(format_label_content)
                widget_index += 1
                
    def _next_timezone(self):
        self._active_tz = next(self._timezones)
        if self._tooltip:
            self.setToolTip(self._active_tz)
        self._update_label()

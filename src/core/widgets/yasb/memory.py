import logging
import re
import psutil
from humanize import naturalsize
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.memory import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel,QHBoxLayout,QWidget
from PyQt6.QtCore import Qt
from core.utils.widgets.animation_manager import AnimationManager

class MemoryWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    def __init__(
            self,
            label: str,
            label_alt: str,
            update_interval: int,
            animation: dict[str, str],
            callbacks: dict[str, str],
            memory_thresholds: dict[str, int],
            container_padding: dict[str, int]
    ):
        super().__init__(update_interval, class_name="memory-widget")
        self._memory_thresholds = memory_thresholds
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        
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

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

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
            virtual_mem = psutil.virtual_memory()
            swap_mem = psutil.swap_memory()
            label_options = {
                "{virtual_mem_free}": naturalsize(virtual_mem.free, True, True),
                "{virtual_mem_percent}": virtual_mem.percent,
                "{virtual_mem_total}": naturalsize(virtual_mem.total, True, True),
                "{virtual_mem_avail}": naturalsize(virtual_mem.available, True, True),
                "{virtual_mem_used}": naturalsize(virtual_mem.used, True, True),
                "{virtual_mem_outof}": f"{naturalsize(virtual_mem.used, True, True)} / {naturalsize(virtual_mem.total, True, True)}",
                "{swap_mem_free}": naturalsize(swap_mem.free, True, True),
                "{swap_mem_percent}": swap_mem.percent,
                "{swap_mem_total}": naturalsize(swap_mem.total, True, True),
            }
            for part in label_parts:
                part = part.strip()
                for fmt_str, value in label_options.items():
                    part = part.replace(fmt_str, str(value))

                if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    if '<span' in part and '</span>' in part:
                        icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                        active_widgets[widget_index].setText(icon)
                    else:
                        active_widgets[widget_index].setText(part)
                        # Set memory threshold as property
                        active_widgets[widget_index].setProperty("class", f"label status-{self._get_virtual_memory_threshold(virtual_mem.percent)}")
                        active_widgets[widget_index].setStyleSheet('')
                    widget_index += 1



        except Exception:
            logging.exception("Failed to retrieve updated memory info")
            if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                active_widgets[widget_index].setText(active_label_content)
                widget_index += 1

    def _get_virtual_memory_threshold(self, virtual_memory_percent) -> str:
        if virtual_memory_percent <= self._memory_thresholds['low']:
            return "low"
        elif self._memory_thresholds['low'] < virtual_memory_percent <= self._memory_thresholds['medium']:
            return "medium"
        elif self._memory_thresholds['medium'] < virtual_memory_percent <= self._memory_thresholds['high']:
            return "high"
        elif self._memory_thresholds['high'] < virtual_memory_percent:
            return "critical"

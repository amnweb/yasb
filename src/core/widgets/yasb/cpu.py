import re
import psutil
from collections import deque
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.cpu import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from core.utils.widgets.animation_manager import AnimationManager
class CpuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            histogram_icons: list[str],
            histogram_num_columns: int,
            update_interval: int,
            animation: dict[str, str],
            container_padding: dict[str, int],
            callbacks: dict[str, str]
    ):
        super().__init__(update_interval, class_name="cpu-widget")
        self._histogram_icons = histogram_icons
        self._cpu_freq_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._cpu_perc_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
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

        self._create_dynamically_label(self._label_content, self._label_alt_content)

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
            info = self._get_cpu_info()
        except Exception:
            info = None

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    # Ensure the icon is correctly set
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    # Update label with formatted content
                    formatted_text = part.format(info=info) if info else part
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1
 
 
    def _get_histogram_bar(self, num, num_min, num_max):
        bar_index = int((num - num_min) / (num_max - num_min) * 10)
        bar_index = 8 if bar_index > 8 else bar_index
        return self._histogram_icons[bar_index]

    def _get_cpu_info(self) -> dict:
        cpu_freq = psutil.cpu_freq()
        cpu_stats = psutil.cpu_stats()
        min_freq = cpu_freq.min
        max_freq = cpu_freq.max
        current_freq = cpu_freq.current
        current_perc = psutil.cpu_percent()
        cores_perc = psutil.cpu_percent(percpu=True)

        self._cpu_freq_history.append(current_freq)
        self._cpu_perc_history.append(current_perc)

        return {
            'cores': {
                'physical': psutil.cpu_count(logical=False),
                'total': psutil.cpu_count(logical=True)
            },
            'freq': {
                'min': min_freq,
                'max': max_freq,
                'current': current_freq
            },
            'percent': {
                'core': cores_perc,
                'total': current_perc
            },
            'stats': {
                'context_switches': cpu_stats.ctx_switches,
                'interrupts': cpu_stats.interrupts,
                'soft_interrupts': cpu_stats.soft_interrupts,
                'sys_calls': cpu_stats.syscalls
            },
            'histograms': {
                'cpu_freq': "".join([
                    self._get_histogram_bar(freq, min_freq, max_freq) for freq in self._cpu_freq_history
                ]).encode('utf-8').decode('unicode_escape'),
                'cpu_percent': "".join([
                    self._get_histogram_bar(percent, 0, 100) for percent in self._cpu_perc_history
                ]).encode('utf-8').decode('unicode_escape'),
                'cores': "".join([
                    self._get_histogram_bar(percent, 0, 100) for percent in cores_perc
                ]).encode('utf-8').decode('unicode_escape'),
            }
        }

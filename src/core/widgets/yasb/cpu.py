import logging
import re
from collections import deque

import psutil
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.utils.utilities import add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.cpu import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class CpuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    # Class-level shared data and timer
    _instances: list["CpuWidget"] = []
    _shared_timer: QTimer | None = None

    def __init__(
        self,
        label: str,
        label_alt: str,
        histogram_icons: list[str],
        histogram_num_columns: int,
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="cpu-widget")
        self._histogram_icons = histogram_icons
        self._cpu_freq_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._cpu_perc_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        # Add this instance to the shared instances list
        if self not in CpuWidget._instances:
            CpuWidget._instances.append(self)

        if update_interval > 0 and CpuWidget._shared_timer is None:
            CpuWidget._shared_timer = QTimer(self)
            CpuWidget._shared_timer.setInterval(update_interval)
            CpuWidget._shared_timer.timeout.connect(CpuWidget._notify_instances)
            CpuWidget._shared_timer.start()

        CpuWidget._notify_instances()

    @classmethod
    def _notify_instances(cls):
        """Fetch CPU data and update all instances."""
        if not cls._instances:
            return

        try:
            cpu_freq = psutil.cpu_freq()
            cpu_stats = psutil.cpu_stats()
            current_perc = psutil.cpu_percent()
            cores_perc = psutil.cpu_percent(percpu=True)
            cpu_cores = {"physical": psutil.cpu_count(logical=False), "total": psutil.cpu_count(logical=True)}

            # Update each instance using the shared data
            for inst in cls._instances[:]:
                try:
                    inst._update_label(cpu_freq, cpu_stats, current_perc, cores_perc, cpu_cores)
                except RuntimeError:
                    cls._instances.remove(inst)

        except Exception as e:
            logging.error(f"Error updating shared CPU data: {e}")

    def _update_label(self, cpu_freq, cpu_stats, current_perc, cores_perc, cpu_cores):
        """Update the label with CPU data."""

        self._cpu_freq_history.append(cpu_freq.current)
        self._cpu_perc_history.append(current_perc)

        cpu_info = {
            "cores": cpu_cores,
            "freq": {"min": cpu_freq.min, "max": cpu_freq.max, "current": cpu_freq.current},
            "percent": {"core": cores_perc, "total": current_perc},
            "stats": {
                "context_switches": cpu_stats.ctx_switches,
                "interrupts": cpu_stats.interrupts,
                "soft_interrupts": cpu_stats.soft_interrupts,
                "sys_calls": cpu_stats.syscalls,
            },
            "histograms": {
                "cpu_freq": "".join(
                    [self._get_histogram_bar(freq, cpu_freq.min, cpu_freq.max) for freq in self._cpu_freq_history]
                )
                .encode("utf-8")
                .decode("unicode_escape"),
                "cpu_percent": "".join([self._get_histogram_bar(percent, 0, 100) for percent in self._cpu_perc_history])
                .encode("utf-8")
                .decode("unicode_escape"),
                "cores": "".join([self._get_histogram_bar(percent, 0, 100) for percent in cores_perc])
                .encode("utf-8")
                .decode("unicode_escape"),
            },
        }

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    label_class = "label alt" if self._show_alt_label else "label"
                    formatted_text = part.format(info=cpu_info)
                    active_widgets[widget_index].setText(formatted_text)
                    active_widgets[widget_index].setProperty("class", label_class)
                    active_widgets[widget_index].setStyleSheet("")
                widget_index += 1

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        CpuWidget._notify_instances()

    def _get_histogram_bar(self, num, num_min, num_max):
        if num_max == num_min:
            return self._histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self._histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self._histogram_icons) - 1)
        return self._histogram_icons[bar_index]

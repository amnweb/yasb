import logging
import re
from collections import deque

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.cpu.cpu_api import CpuAPI
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
        class_name: str,
        histogram_icons: list[str],
        histogram_num_columns: int,
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        cpu_thresholds: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
        hide_decimal: bool = False,
    ):
        super().__init__(class_name=f"cpu-widget {class_name}")
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
        self._cpu_thresholds = cpu_thresholds
        self._progress_bar = progress_bar
        self._hide_decimal = hide_decimal

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self._progress_bar)

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
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

        self._show_placeholder()

    def _show_placeholder(self):
        """Display placeholder (zero/default) CPU data."""
        data = CpuAPI.CpuData(
            freq=CpuAPI.CpuFreq(current=0, min=0, max=0),
            percent=0,
            percent_per_core=[0],
            cores_physical=1,
            cores_logical=1,
        )
        self._update_label(data)

    @classmethod
    def _notify_instances(cls):
        """Fetch CPU data and update all instances."""
        if not cls._instances:
            return

        try:
            data = CpuAPI.get_data()

            # Update each instance using the shared data
            for inst in cls._instances[:]:
                try:
                    inst._update_label(data)
                except RuntimeError:
                    cls._instances.remove(inst)

        except Exception as e:
            logging.error(f"Error updating shared CPU data: {e}")

    def _update_label(self, data: CpuAPI.CpuData):
        """Update the label with CPU data."""
        self._cpu_freq_history.append(data.freq.current)
        self._cpu_perc_history.append(data.percent)

        _round = lambda value: round(value) if self._hide_decimal else value
        cpu_info = {
            "cores": {"physical": data.cores_physical, "total": data.cores_logical},
            "freq": {"min": _round(data.freq.min), "max": _round(data.freq.max), "current": _round(data.freq.current)},
            "percent": {"core": [_round(core) for core in data.percent_per_core], "total": _round(data.percent)},
            # stats removed - zeroed values for backward compatibility
            "stats": {"context_switches": 0, "interrupts": 0, "soft_interrupts": 0, "sys_calls": 0},
            "histograms": {
                "cpu_freq": "".join(
                    [self._get_histogram_bar(f, data.freq.min, data.freq.max) for f in self._cpu_freq_history]
                ),
                "cpu_percent": "".join([self._get_histogram_bar(p, 0, 100) for p in self._cpu_perc_history]),
                "cores": "".join([self._get_histogram_bar(p, 0, 100) for p in data.percent_per_core]),
            },
        }

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            self.progress_widget.set_value(data.percent)

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
                    active_widgets[widget_index].setProperty(
                        "class", f"{label_class} status-{self._get_cpu_threshold(data.percent)}"
                    )
                    refresh_widget_style(active_widgets[widget_index])
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

    def _get_cpu_threshold(self, percent: float) -> str:
        if percent <= self._cpu_thresholds["low"]:
            return "low"
        elif self._cpu_thresholds["low"] < percent <= self._cpu_thresholds["medium"]:
            return "medium"
        elif self._cpu_thresholds["medium"] < percent <= self._cpu_thresholds["high"]:
            return "high"
        elif self._cpu_thresholds["high"] < percent:
            return "critical"

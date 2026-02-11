import re
from collections import deque

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.cpu.cpu_api import CpuData, CpuFreq, CpuWorker
from core.validation.widgets.yasb.cpu import CpuConfig
from core.widgets.base import BaseWidget


class CpuWidget(BaseWidget):
    validation_schema = CpuConfig

    _instances: list["CpuWidget"] = []
    _worker: CpuWorker | None = None

    def __init__(self, config: CpuConfig):
        super().__init__(class_name=f"cpu-widget {config.class_name}")
        self.config = config
        self._cpu_freq_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._cpu_perc_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._show_alt_label = False
        self._last_data: CpuData | None = None
        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self.config.progress_bar.model_dump())

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self.config.label, self.config.label_alt, self.config.label_shadow.model_dump())

        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        # Add this instance to the shared instances list
        if self not in CpuWidget._instances:
            CpuWidget._instances.append(self)

        # Start the shared CPU worker thread
        if self.config.update_interval > 0 and CpuWidget._worker is None:
            worker = CpuWorker.get_instance(self.config.update_interval)
            worker.data_ready.connect(CpuWidget._on_data_ready)
            worker.start()
            CpuWidget._worker = worker

        self._show_placeholder()

    def _show_placeholder(self):
        """Display placeholder (zero/default) CPU data."""
        data = CpuData(
            freq=CpuFreq(current=0, min=0, max=0),
            percent=0,
            percent_per_core=[0],
            cores_physical=1,
            cores_logical=1,
        )
        self._update_label(data)

    @classmethod
    def _on_data_ready(cls, data: CpuData):
        """Slot called on the main thread when new CPU data arrives from the worker."""
        for inst in cls._instances[:]:
            try:
                inst._last_data = data
                inst._update_label(data)
            except RuntimeError:
                cls._instances.remove(inst)

    def _update_label(self, data: CpuData):
        """Update the label with CPU data."""
        self._cpu_freq_history.append(data.freq.current)
        self._cpu_perc_history.append(data.percent)

        _round = lambda value: round(value) if self.config.hide_decimal else value
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
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if self.config.progress_bar.enabled and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self.config.progress_bar.position == "left" else self._widget_container_layout.count(),
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
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        # Re-render with last known data
        if self._last_data is not None:
            self._update_label(self._last_data)

    def _get_histogram_bar(self, num: float, num_min: float, num_max: float) -> str:
        if num_max == num_min:
            return self.config.histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self.config.histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self.config.histogram_icons) - 1)
        return self.config.histogram_icons[bar_index]

    def _get_cpu_threshold(self, percent: float) -> str:
        if percent <= self.config.cpu_thresholds.low:
            return "low"
        elif self.config.cpu_thresholds.low < percent <= self.config.cpu_thresholds.medium:
            return "medium"
        elif self.config.cpu_thresholds.medium < percent <= self.config.cpu_thresholds.high:
            return "high"
        elif self.config.cpu_thresholds.high < percent:
            return "critical"

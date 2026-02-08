import re
from collections import deque

from humanize import naturalsize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.gpu.gpu_worker import GpuData, GpuWorker
from core.validation.widgets.yasb.gpu import GpuConfig
from core.widgets.base import BaseWidget


class GpuWidget(BaseWidget):
    validation_schema = GpuConfig

    # Class-level shared data and worker
    _instances: list["GpuWidget"] = []
    _worker: GpuWorker | None = None

    def __init__(self, config: GpuConfig):
        super().__init__(class_name=f"gpu-widget {config.class_name}")
        self.config = config
        self._gpu_util_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._gpu_mem_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._show_alt_label = False
        self._last_gpu_data: GpuData | None = None

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
        if self not in GpuWidget._instances:
            GpuWidget._instances.append(self)

        # Start the shared GPU worker thread
        if self.config.update_interval > 0 and GpuWidget._worker is None:
            worker = GpuWorker.get_instance(self.config.update_interval)
            worker.data_ready.connect(GpuWidget._on_gpu_data)
            worker.start()
            GpuWidget._worker = worker

        self._show_placeholder()

    @classmethod
    def _on_gpu_data(cls, gpu_data_list: list[GpuData]):
        """Slot called on main thread when GPU worker emits data."""
        for inst in cls._instances[:]:
            try:
                gpu_data = next((g for g in gpu_data_list if g.index == inst.config.gpu_index), None)
                if gpu_data:
                    inst._update_label(gpu_data)
                else:
                    inst._show_placeholder()
            except RuntimeError:
                cls._instances.remove(inst)

    def _show_placeholder(self):
        """Display placeholder GPU data without any subprocess calls."""
        gpu_data = GpuData(
            index=0,
            utilization=0,
            mem_total=0,
            mem_used=0,
            mem_free=0,
            temp=0,
            fan_speed=0,
            power_draw="0",
        )
        self._update_label(gpu_data)

    def _update_label(self, gpu_data: GpuData):
        """Update the label with GPU data."""
        self._last_gpu_data = gpu_data
        self._gpu_util_history.append(gpu_data.utilization)
        self._gpu_mem_history.append(gpu_data.mem_used)
        _temp = gpu_data.temp if self.config.units == "metric" else (gpu_data.temp * (9 / 5) + 32)
        _temp = round(_temp) if self.config.hide_decimal else _temp
        _power_draw = str(gpu_data.power_draw).strip() or 0
        _naturalsize = lambda value: naturalsize(value, True, True, "%.0f" if self.config.hide_decimal else "%.1f")
        gpu_info = {
            "index": gpu_data.index,
            "utilization": gpu_data.utilization,
            "mem_total": _naturalsize(gpu_data.mem_total * 1024 * 1024),
            "mem_used": _naturalsize(gpu_data.mem_used * 1024 * 1024),
            "mem_free": _naturalsize(gpu_data.mem_free * 1024 * 1024),
            "temp": _temp,
            "fan_speed": gpu_data.fan_speed,
            "power_draw": _power_draw,
            "histograms": {
                "utilization": "".join([self._get_histogram_bar(val, 0, 100) for val in self._gpu_util_history]),
                "mem_used": "".join(
                    [self._get_histogram_bar(val, 0, gpu_data.mem_total or 1) for val in self._gpu_mem_history]
                ),
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
            self.progress_widget.set_value(gpu_data.utilization)

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    label_class = "label alt" if self._show_alt_label else "label"
                    formatted_text = part.format(info=gpu_info)
                    active_widgets[widget_index].setText(formatted_text)
                    active_widgets[widget_index].setProperty("class", label_class)
                    active_widgets[widget_index].setProperty(
                        "class", f"{label_class} status-{self._get_gpu_threshold(gpu_data.utilization)}"
                    )
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

    def _get_gpu_threshold(self, utilization: float) -> str:
        if utilization <= self.config.gpu_thresholds.low:
            return "low"
        elif self.config.gpu_thresholds.low < utilization <= self.config.gpu_thresholds.medium:
            return "medium"
        elif self.config.gpu_thresholds.medium < utilization <= self.config.gpu_thresholds.high:
            return "high"
        elif self.config.gpu_thresholds.high < utilization:
            return "critical"

    def _get_histogram_bar(self, num: float, num_min: float, num_max: float) -> str:
        if num_max == num_min:
            return self.config.histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self.config.histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self.config.histogram_icons) - 1)
        return self.config.histogram_icons[bar_index]

    def _toggle_label(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        for inst in GpuWidget._instances[:]:
            try:
                inst._update_label(inst._last_gpu_data)
            except RuntimeError:
                GpuWidget._instances.remove(inst)

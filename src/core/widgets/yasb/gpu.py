import logging
import os
import re
import shutil
from collections import deque
from subprocess import PIPE, Popen

from humanize import naturalsize
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.gpu import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class GpuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    # Class-level shared data and timer
    _instances: list["GpuWidget"] = []
    _shared_timer: QTimer | None = None
    _nvidia_smi_path: str | None = None  # Cache for resolved nvidia-smi path

    def __init__(
        self,
        gpu_index: int,
        label: str,
        label_alt: str,
        histogram_icons: list[str],
        histogram_num_columns: int,
        update_interval: int,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        gpu_thresholds: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
    ):
        super().__init__(class_name="gpu-widget")
        self._gpu_index = gpu_index
        self._histogram_icons = histogram_icons
        self._gpu_util_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._gpu_mem_history = deque([0] * histogram_num_columns, maxlen=histogram_num_columns)
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._gpu_thresholds = gpu_thresholds
        self._progress_bar = progress_bar

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self._progress_bar)

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
        if self not in GpuWidget._instances:
            GpuWidget._instances.append(self)

        if update_interval > 0 and GpuWidget._shared_timer is None:
            GpuWidget._shared_timer = QTimer(self)
            GpuWidget._shared_timer.setInterval(update_interval)
            GpuWidget._shared_timer.timeout.connect(GpuWidget._notify_instances)
            GpuWidget._shared_timer.start()

        self._show_placeholder()

    def _show_placeholder(self):
        """Display placeholder GPU data without any subprocess calls."""

        class DummyGpu:
            index = 0
            utilization = 0
            mem_total = 0
            mem_used = 0
            mem_free = 0
            temp = 0

        gpu_data = DummyGpu()
        self._update_label(gpu_data)

    @classmethod
    def _get_nvidia_smi_path(cls):
        if cls._nvidia_smi_path is not None:
            return cls._nvidia_smi_path
        path = shutil.which("nvidia-smi")
        if path:
            cls._nvidia_smi_path = path
        else:
            cls._nvidia_smi_path = os.path.join(
                os.environ["SystemDrive"] + "\\", "Program Files", "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"
            )
        return cls._nvidia_smi_path

    @classmethod
    def _notify_instances(cls):
        """Fetch GPU data and update all instances."""
        if not cls._instances:
            return
        try:
            nvidia_smi = cls._get_nvidia_smi_path()
            gpu = Popen(
                [
                    nvidia_smi,
                    "--query-gpu=index,utilization.gpu,memory.total,memory.used,memory.free,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                stdout=PIPE,
                stderr=PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            stdout, stderr = gpu.communicate(timeout=2)
            if gpu.returncode != 0 or not stdout:
                lines = []
            else:
                lines = stdout.decode("utf-8").strip().split("\n")
            for inst in cls._instances[:]:
                try:
                    # Find the line for the correct GPU index
                    gpu_line = next((l for l in lines if l.startswith(str(inst._gpu_index) + ",")), None)
                    if gpu_line:
                        fields = [f.strip() for f in gpu_line.split(",")]

                        class GpuData:
                            index = int(fields[0])
                            utilization = int(fields[1])
                            mem_total = int(fields[2])
                            mem_used = int(fields[3])
                            mem_free = int(fields[4])
                            temp = int(fields[5])

                        inst._update_label(GpuData)
                    else:
                        inst._show_placeholder()
                except Exception:
                    cls._instances.remove(inst)
        except Exception as e:
            logging.error(f"Error updating shared GPU data: {e}")
            for inst in cls._instances[:]:
                inst._show_placeholder()

    def _update_label(self, gpu_data):
        """Update the label with GPU data."""
        self._gpu_util_history.append(gpu_data.utilization)
        self._gpu_mem_history.append(gpu_data.mem_used)

        gpu_info = {
            "index": gpu_data.index,
            "utilization": gpu_data.utilization,
            "mem_total": naturalsize(gpu_data.mem_total * 1024 * 1024, True, True),
            "mem_used": naturalsize(gpu_data.mem_used * 1024 * 1024, True, True),
            "mem_free": naturalsize(gpu_data.mem_free * 1024 * 1024, True, True),
            "temp": gpu_data.temp,
            "histograms": {
                "utilization": "".join([self._get_histogram_bar(val, 0, 100) for val in self._gpu_util_history]),
                "mem_used": "".join(
                    [self._get_histogram_bar(val, 0, gpu_data.mem_total or 1) for val in self._gpu_mem_history]
                ),
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
                    active_widgets[widget_index].setStyleSheet("")
                widget_index += 1

    def _get_gpu_threshold(self, utilization) -> str:
        if utilization <= self._gpu_thresholds["low"]:
            return "low"
        elif self._gpu_thresholds["low"] < utilization <= self._gpu_thresholds["medium"]:
            return "medium"
        elif self._gpu_thresholds["medium"] < utilization <= self._gpu_thresholds["high"]:
            return "high"
        elif self._gpu_thresholds["high"] < utilization:
            return "critical"

    def _get_histogram_bar(self, num, num_min, num_max):
        if num_max == num_min:
            return self._histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self._histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self._histogram_icons) - 1)
        return self._histogram_icons[bar_index]

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        GpuWidget._notify_instances()

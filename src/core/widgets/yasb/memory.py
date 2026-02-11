import re

from humanize import naturalsize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.memory.memory_api import MemoryData, MemoryWorker, SwapMemory, VirtualMemory
from core.validation.widgets.yasb.memory import MemoryConfig
from core.widgets.base import BaseWidget


class MemoryWidget(BaseWidget):
    validation_schema = MemoryConfig

    _instances: list["MemoryWidget"] = []
    _worker: MemoryWorker | None = None

    def __init__(self, config: MemoryConfig):
        super().__init__(class_name=f"memory-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._last_data: MemoryData | None = None

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self.config.progress_bar.model_dump())
        # Construct container
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
        if self not in MemoryWidget._instances:
            MemoryWidget._instances.append(self)

        # Start the shared memory worker thread
        if self.config.update_interval > 0 and MemoryWidget._worker is None:
            worker = MemoryWorker.get_instance(self.config.update_interval)
            worker.data_ready.connect(MemoryWidget._on_data_ready)
            worker.start()
            MemoryWidget._worker = worker

        self._show_placeholder()

    def _show_placeholder(self):
        """Display placeholder (zero/default) memory data."""
        virtual_mem = VirtualMemory(total=0, available=0, percent=0.0, used=0, free=0)
        swap_mem = SwapMemory(total=0, used=0, free=0, percent=0.0)
        self._update_label(virtual_mem, swap_mem)

    @classmethod
    def _on_data_ready(cls, data: MemoryData):
        """Slot called on main thread when new memory data arrives from the worker."""
        for inst in cls._instances[:]:
            try:
                inst._last_data = data
                inst._update_label(data.virtual, data.swap)
            except RuntimeError:
                cls._instances.remove(inst)

    def _update_label(self, virtual_mem, swap_mem):
        """Update label using shared memory data."""

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        _round = lambda value: round(value) if self.config.hide_decimal else value
        _naturalsize = lambda value: naturalsize(value, True, True, "%.0f" if self.config.hide_decimal else "%.1f")
        label_options = {
            "{virtual_mem_free}": _naturalsize(virtual_mem.free),
            "{virtual_mem_percent}": _round(virtual_mem.percent),
            "{virtual_mem_total}": _naturalsize(virtual_mem.total),
            "{virtual_mem_avail}": _naturalsize(virtual_mem.available),
            "{virtual_mem_used}": _naturalsize(virtual_mem.used),
            "{virtual_mem_outof}": f"{_naturalsize(virtual_mem.used)} / {_naturalsize(virtual_mem.total)}",
            "{swap_mem_free}": _naturalsize(swap_mem.free),
            "{swap_mem_percent}": _round(swap_mem.percent),
            "{swap_mem_total}": _naturalsize(swap_mem.total),
            "{histogram}": "".join([self._get_histogram_bar(virtual_mem.percent, 0, 100)]),
        }

        if self.config.progress_bar.enabled and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self.config.progress_bar.position == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            self.progress_widget.set_value(virtual_mem.percent)

        for part in label_parts:
            part = part.strip()
            for fmt_str, value in label_options.items():
                part = part.replace(fmt_str, str(value))

            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                    # Set memory threshold as property
                    label_class = "label alt" if self._show_alt_label else "label"
                    active_widgets[widget_index].setProperty(
                        "class", f"{label_class} status-{self._get_virtual_memory_threshold(virtual_mem.percent)}"
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
            self._update_label(self._last_data.virtual, self._last_data.swap)

    def _get_virtual_memory_threshold(self, virtual_memory_percent: float) -> str:
        if virtual_memory_percent <= self.config.memory_thresholds.low:
            return "low"
        elif self.config.memory_thresholds.low < virtual_memory_percent <= self.config.memory_thresholds.medium:
            return "medium"
        elif self.config.memory_thresholds.medium < virtual_memory_percent <= self.config.memory_thresholds.high:
            return "high"
        elif self.config.memory_thresholds.high < virtual_memory_percent:
            return "critical"

    def _get_histogram_bar(self, num: float, num_min: float, num_max: float) -> str:
        if num_max == num_min:
            return self.config.histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self.config.histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self.config.histogram_icons) - 1)
        return self.config.histogram_icons[bar_index]

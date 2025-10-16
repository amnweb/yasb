import logging
import re

from humanize import naturalsize
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_progress_widget, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.memory import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class MemoryWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    _instances: list["MemoryWidget"] = []
    _shared_timer: QTimer | None = None

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        update_interval: int,
        histogram_icons: list[str],
        animation: dict[str, str],
        callbacks: dict[str, str],
        memory_thresholds: dict[str, int],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
        hide_decimal: bool = False,
    ):
        super().__init__(class_name=f"memory-widget {class_name}")
        self._memory_thresholds = memory_thresholds
        self._histogram_icons = histogram_icons
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._progress_bar = progress_bar
        self._hide_decimal = hide_decimal

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self._progress_bar)
        # Construct container
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
        if self not in MemoryWidget._instances:
            MemoryWidget._instances.append(self)

        if update_interval > 0 and MemoryWidget._shared_timer is None:
            MemoryWidget._shared_timer = QTimer(self)
            MemoryWidget._shared_timer.setInterval(update_interval)
            MemoryWidget._shared_timer.timeout.connect(MemoryWidget._notify_instances)
            MemoryWidget._shared_timer.start()

        self._show_placeholder()

    def _show_placeholder(self):
        """Display placeholder (zero/default) memory data without any psutil calls."""

        class DummyMem:
            free = 0
            percent = 0
            total = 0
            available = 0
            used = 0

        virtual_mem = DummyMem()
        swap_mem = DummyMem()

        self._update_label(virtual_mem, swap_mem)

    @classmethod
    def _notify_instances(cls):
        """Fetch memory data and update all instances."""
        if not cls._instances:
            return

        try:
            import psutil

            virtual_mem = psutil.virtual_memory()
            swap_mem = psutil.swap_memory()

            # Update each instance using the shared data
            for inst in cls._instances[:]:
                try:
                    inst._update_label(virtual_mem, swap_mem)
                except RuntimeError:
                    cls._instances.remove(inst)

        except Exception as e:
            logging.error(f"Error updating shared memory data: {e}")

    def _update_label(self, virtual_mem, swap_mem):
        """Update label using shared memory data."""

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        _round = lambda value: round(value) if self._hide_decimal else value
        _naturalsize = lambda value: naturalsize(value, True, True, "%.0f" if self._hide_decimal else "%.1f")
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

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
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
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        MemoryWidget._notify_instances()

    def _get_virtual_memory_threshold(self, virtual_memory_percent) -> str:
        if virtual_memory_percent <= self._memory_thresholds["low"]:
            return "low"
        elif self._memory_thresholds["low"] < virtual_memory_percent <= self._memory_thresholds["medium"]:
            return "medium"
        elif self._memory_thresholds["medium"] < virtual_memory_percent <= self._memory_thresholds["high"]:
            return "high"
        elif self._memory_thresholds["high"] < virtual_memory_percent:
            return "critical"

    def _get_histogram_bar(self, num, num_min, num_max):
        if num_max == num_min:
            return self._histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self._histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self._histogram_icons) - 1)
        return self._histogram_icons[bar_index]

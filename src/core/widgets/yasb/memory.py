import logging
import re

import psutil
from humanize import naturalsize
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.utils.utilities import add_shadow, build_widget_label
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
        update_interval: int,
        animation: dict[str, str],
        callbacks: dict[str, str],
        memory_thresholds: dict[str, int],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="memory-widget")
        self._memory_thresholds = memory_thresholds
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
        if self not in MemoryWidget._instances:
            MemoryWidget._instances.append(self)

        if update_interval > 0 and MemoryWidget._shared_timer is None:
            MemoryWidget._shared_timer = QTimer(self)
            MemoryWidget._shared_timer.setInterval(update_interval)
            MemoryWidget._shared_timer.timeout.connect(MemoryWidget._notify_instances)
            MemoryWidget._shared_timer.start()

        MemoryWidget._notify_instances()

    @classmethod
    def _notify_instances(cls):
        """Fetch memory data and update all instances."""
        if not cls._instances:
            return

        try:
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

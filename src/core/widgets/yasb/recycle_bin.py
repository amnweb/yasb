import re

from humanize import naturalsize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.recycle_bin.recycle_bin_monitor import RecycleBinMonitor
from core.validation.widgets.yasb.recycle_bin import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class RecycleBinWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        icons: dict[str, str],
        tooltip: bool,
        animation: dict[str, str],
        callbacks: dict[str, str],
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"recycle-bin-widget {class_name}")
        self._label_content = label
        self._label_alt_content = label_alt
        self._icons = icons
        self._tooltip = tooltip
        self._animation = animation
        self._padding = container_padding
        self._show_alt_label = False
        self._bin_info = {"num_items": 0, "size_bytes": 0}
        self._is_emptying = False
        self._empty_thread = None
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self.monitor = RecycleBinMonitor.get_instance()
        self.monitor.subscribe(id(self))
        self.monitor.bin_updated.connect(self._on_bin_update)

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("empty_bin", self._empty_bin)
        self.register_callback("open_bin", self._open_bin)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._update_label()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        class_name = "bin-filled" if self._bin_info["num_items"] > 0 else "bin-empty"

        label_options = {
            "{items_count}": self._bin_info["num_items"],
            "{items_size}": naturalsize(self._bin_info["size_bytes"], binary=True, format="%.2f"),
            "{icon}": self._get_current_icon(),
        }

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        base_class = active_widgets[widget_index].property("class").split()[0]
                        active_widgets[widget_index].setProperty("class", f"{base_class} {class_name}")
                        refresh_widget_style(active_widgets[widget_index])
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        alt_class = "alt" if self._show_alt_label else ""
                        active_widgets[widget_index].setText(formatted_text)
                        base_class = "label"
                        active_widgets[widget_index].setProperty("class", f"{base_class} {alt_class} {class_name}")
                        refresh_widget_style(active_widgets[widget_index])
                widget_index += 1
        if self._tooltip:
            set_tooltip(
                self._widget_container,
                f"Items: {self._bin_info['num_items']} ({naturalsize(self._bin_info['size_bytes'], binary=True, format='%.2f')})",
            )

    def _get_current_icon(self):
        """Get the icon based on the bin state"""
        if self._bin_info["num_items"] > 0:
            return self._icons["bin_filled"]
        else:
            return self._icons["bin_empty"]

    def _on_bin_update(self, bin_info):
        self._bin_info = bin_info
        self._update_label()

    def _empty_bin(self):
        # Prevent multiple emptying operations
        if self._is_emptying or self._bin_info["num_items"] == 0:
            return

        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])

        self._is_emptying = True

        # Update label to indicate emptying
        for widget in self._widgets:
            if "label" in widget.property("class"):
                widget.setText("Emptying...")
        # Get the thread and signal from monitor, and store the thread reference
        signal, self._empty_thread = self.monitor.empty_recycle_bin_async()
        signal.connect(self._on_empty_finished)

    def _on_empty_finished(self):
        # Reset emptying flag - bin_updated signal will handle the label update
        self._is_emptying = False

    def _open_bin(self):
        """Open the recycle bin"""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.monitor.open_recycle_bin()

    def shutdown(self):
        """Clean up resources when widget is being destroyed"""
        try:
            self.monitor.bin_updated.disconnect(self._on_bin_update)
            self.monitor.unsubscribe(id(self))  # Unsubscribe when widget is destroyed
        except Exception:
            pass
        super().shutdown()

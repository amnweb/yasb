import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel

from core.events.service import EventService
from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.dnd import DndConfig
from core.widgets.base import BaseWidget
from core.widgets.services.dnd.dnd_api import DndService


class DndWidget(BaseWidget):
    validation_schema = DndConfig
    dnd_status_changed_signal = pyqtSignal(str)

    def __init__(self, config: DndConfig):
        super().__init__(class_name=f"dnd-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._current_status = "unknown"
        self._last_active_status = self.config.default_active_mode
        self._event_service = EventService()

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_status", self._toggle_status)
        self.register_callback("cycle_status", self._cycle_status)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        DndService.initialize_wnf_listener()

        self.dnd_status_changed_signal.connect(self._update_label)
        self._event_service.register_event("dnd_status_changed", self.dnd_status_changed_signal)

        # Initial update
        self._update_label()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_status(self):
        self._current_status = DndService.get_status()
        if self._current_status == "disabled":
            next_mode = getattr(self.config, "default_active_mode", "priority")
        else:
            next_mode = "disabled"
        DndService.set_status(next_mode)

    def _cycle_status(self):
        """Cycle between disabled -> priority -> alarms -> disabled."""
        self._current_status = DndService.get_status()
        match self._current_status:
            case "disabled":
                next_mode = "priority"
            case "priority":
                next_mode = "alarms"
            case _:
                next_mode = "disabled"

        DndService.set_status(next_mode)

    def _set_status_class(self, widget, status: str):
        """Set or update the status class on the widget."""
        current_class = widget.property("class") or ""
        classes = set(current_class.split())
        classes = {c for c in classes if not c.startswith("status-")}
        classes.add(f"status-{status}")
        new_class = " ".join(sorted(classes))
        if current_class != new_class:
            widget.setProperty("class", new_class)
            refresh_widget_style(widget)

    def _update_label(self, status: str = None):
        if status:
            self._current_status = status
        elif self._current_status == "unknown":
            self._current_status = DndService.get_status()
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if self._current_status == "priority":
            icon_char = self.config.icons.priority
        elif self._current_status == "alarms":
            icon_char = self.config.icons.alarms
        else:
            icon_char = self.config.icons.disabled

        label_options = {
            "{icon}": icon_char,
            "{status}": self._current_status,
        }

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))

                if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    active_widgets[widget_index].setText(formatted_text)
                    self._set_status_class(active_widgets[widget_index], self._current_status)
                widget_index += 1

        self._update_tooltip()

    def _update_tooltip(self):
        if not self.config.tooltip:
            return

        if self._current_status == "disabled":
            tooltip_text = "Do Not Disturb (Off)"
        else:
            tooltip_text = f"Do Not Disturb (On) {self._current_status.title()}"
        set_tooltip(self._widget_container, tooltip_text)

        tooltip_filter = getattr(self._widget_container, "_tooltip_filter", None)
        if tooltip_filter and self._widget_container.underMouse():
            tooltip_filter.show_tooltip()

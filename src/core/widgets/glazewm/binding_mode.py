import logging
import re
from typing import Any

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.glazewm.client import BindingMode, GlazewmClient
from core.validation.widgets.glazewm.binding_mode import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

logger = logging.getLogger("glazewm_binding_mode")

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


class GlazewmBindingModeWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        glazewm_server_uri: str,
        hide_if_no_active: bool,
        label_if_no_active: str,
        default_icon: str,
        icons: dict[str, str],
        binding_modes_to_cycle_through: list[str],
        container_padding: dict[str, int],
        animation: dict[str, str],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="glazewm-binding-mode")
        self._label_content = label
        self._label_alt_content = label_alt
        self._show_alt_label = False
        self._hide_if_no_active = hide_if_no_active
        self._label_if_no_active = label_if_no_active
        self._default_icon = default_icon
        self._icons = icons
        self._binding_modes_to_cycle_through = binding_modes_to_cycle_through
        self._current_binding_mode_index = 0
        self._padding = container_padding
        self._animation = animation
        self._container_shadow = container_shadow
        self._label_shadow = label_shadow

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

        self.glazewm_client = GlazewmClient(
            glazewm_server_uri,
            [
                "sub -e binding_modes_changed",
                "query binding-modes",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)
        self.glazewm_client.binding_mode_changed.connect(self._update_binding_mode)
        self.glazewm_client.connect()

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("disable_binding_mode", self._disable_binding_mode)
        self.register_callback("next_binding_mode", lambda: self._cycle_through_binding_modes(1))
        self.register_callback("prev_binding_mode", lambda: self._cycle_through_binding_modes(-1))
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.hide()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _reload_css(self, label: QLabel):
        refresh_widget_style(label)
        label.update()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        label_options = {
            "{binding_mode}": self._active_binding_mode.display_name
            or self._active_binding_mode.name
            or self._label_if_no_active,
            "{icon}": self._icons.get(self._active_binding_mode.name or "none", self._default_icon),
        }
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    if icon in label_options:
                        active_widgets[widget_index].setProperty(
                            "class", f"icon {self._active_binding_mode.name or 'none'}"
                        )
                        active_widgets[widget_index].setText(formatted_text)
                    else:
                        active_widgets[widget_index].setText(icon)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        if active_widgets[widget_index].property("class") == "label-offline":
                            active_widgets[widget_index].setProperty("class", "label")
                        if not self._active_binding_mode.name:
                            active_widgets[widget_index].setProperty("class", "label-offline")
                self._reload_css(active_widgets[widget_index])
                widget_index += 1

    @pyqtSlot()
    def _disable_binding_mode(self):
        if self._active_binding_mode and self._active_binding_mode.name:
            self.glazewm_client.disable_binding_mode(self._active_binding_mode.name)

    @pyqtSlot()
    def _cycle_through_binding_modes(self, direction: int):
        if len(self._binding_modes_to_cycle_through) == 0:
            return

        self._current_binding_mode_index += direction
        if self._current_binding_mode_index < 0:
            self._current_binding_mode_index = len(self._binding_modes_to_cycle_through) - 1
        if self._current_binding_mode_index >= len(self._binding_modes_to_cycle_through):
            self._current_binding_mode_index = 0
        if self._binding_modes_to_cycle_through[self._current_binding_mode_index] == "none":
            self._disable_binding_mode()
            return

        self.glazewm_client.enable_binding_mode(self._binding_modes_to_cycle_through[self._current_binding_mode_index])

    @pyqtSlot(bool)
    def _update_connection_status(self, status: bool):
        if not status:
            self.hide()

    @pyqtSlot(BindingMode)
    def _update_binding_mode(self, binding_mode: BindingMode):
        if not binding_mode.name and "none" in self._binding_modes_to_cycle_through:
            self._current_binding_mode_index = self._binding_modes_to_cycle_through.index("none")

        if self._hide_if_no_active and not binding_mode.name:
            self.hide()
            return

        if binding_mode.name in self._binding_modes_to_cycle_through:
            self._current_binding_mode_index = self._binding_modes_to_cycle_through.index(binding_mode.name)

        self.show()
        self._active_binding_mode = binding_mode
        self._update_label()

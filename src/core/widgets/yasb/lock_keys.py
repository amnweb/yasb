import re

from PyQt6.QtWidgets import QLabel

from core.utils.utilities import refresh_widget_style
from core.utils.win32.bindings import user32
from core.validation.widgets.yasb.lock_keys import LockKeysConfig
from core.widgets.base import BaseWidget

VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90


class LockKeysWidget(BaseWidget):
    validation_schema = LockKeysConfig

    def __init__(self, config: LockKeysConfig) -> None:
        super().__init__(config.update_interval, class_name=f"lock-keys-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._caps_lock_active: bool | None = None
        self._num_lock_active: bool | None = None

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_state", self._update_state)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right
        self.callback_timer = "update_state"

        self.start_timer()

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_state(self) -> None:
        caps_lock_active = bool(user32.GetKeyState(VK_CAPITAL) & 0x0001)
        num_lock_active = bool(user32.GetKeyState(VK_NUMLOCK) & 0x0001)

        if caps_lock_active == self._caps_lock_active and num_lock_active == self._num_lock_active:
            return

        self._caps_lock_active = caps_lock_active
        self._num_lock_active = num_lock_active
        self._update_label()
        self._update_state_classes()

    def _update_label(self) -> None:
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        state_labels = self.config.state_labels
        label_options = {
            "{caps_lock}": state_labels.caps_lock_on if self._caps_lock_active else state_labels.caps_lock_off,
            "{num_lock}": state_labels.num_lock_on if self._num_lock_active else state_labels.num_lock_off,
        }

        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if not part:
                continue

            formatted_text = part
            for placeholder, value in label_options.items():
                formatted_text = formatted_text.replace(placeholder, value)

            if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                active_widgets[widget_index].setText(formatted_text)
            widget_index += 1

    def _update_state_classes(self) -> None:
        caps_class = "caps-lock-on" if self._caps_lock_active else "caps-lock-off"
        num_class = "num-lock-on" if self._num_lock_active else "num-lock-off"
        target_class = f"widget-container {caps_class} {num_class}"

        if self._widget_container.property("class") != target_class:
            self._widget_container.setProperty("class", target_class)
            refresh_widget_style(self._widget_container, *self._widgets, *self._widgets_alt)

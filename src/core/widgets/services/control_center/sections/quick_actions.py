import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.shell_utils import shell_open
from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import ElidedLabel
from core.validation.widgets.yasb.control_center import ControlCenterActionConfig
from core.widgets.services.control_center.api.keyboard import TouchKeyboardService
from core.widgets.services.control_center.api.screenshot import ScreenshotService
from core.widgets.services.control_center.api.theme import ThemeService
from core.widgets.services.dnd.dnd_api import DndService


class ActionButton(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            a0.accept()
            return
        super().mousePressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(a0.position().toPoint()):
                self.clicked.emit()
                a0.accept()
                return
        super().mouseReleaseEvent(a0)


class QuickActionsSectionWidget(QFrame):
    """Grid of configurable quick action buttons."""

    def __init__(
        self,
        parent: QWidget,
        config: object,
        refresh_popup: object,
        audio_services: dict[str, object],
        tooltip: bool = False,
    ):
        super().__init__(parent)
        self.config = config
        self.refresh_popup = refresh_popup
        self._audio_services = audio_services
        self._tooltip = tooltip
        self.setProperty("class", "section quick-actions")

        self._action_buttons: dict[str, ActionButton] = {}
        self._current_theme = (
            ThemeService.get_theme_mode() if "toggle_theme" in {a.id for a in config.actions} else None
        )
        self._current_dnd = (
            DndService.get_status() if {a.id for a in config.actions} & {"toggle_dnd", "cycle_dnd"} else None
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)

        columns = config.columns
        for i in range(columns):
            grid.setColumnStretch(i, 1)

        for index, action in enumerate(config.actions):
            button = self._create_action_button(action)
            self._action_buttons[action.id] = button
            grid.addWidget(button, index // columns, index % columns)

        layout.addLayout(grid)

    def _create_action_button(self, action: ControlCenterActionConfig) -> ActionButton:
        button = ActionButton(self)
        button.setProperty("class", f"button {action.id}")
        button.clicked.connect(lambda a=action: self._run_action(a))

        inline = self.config.label_position == "inline"
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter if inline else Qt.AlignmentFlag.AlignCenter
        button_layout = QHBoxLayout(button) if inline else QVBoxLayout(button)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        if inline:
            button_layout.setAlignment(align)

        icon_label = QLabel(action.icon, button)
        icon_label.setProperty("class", "icon")
        icon_label.setAlignment(align)

        text_label = ElidedLabel(action.label, button)
        text_label.setProperty("class", "title")
        text_label.setAlignment(align)

        if inline:
            button_layout.addWidget(icon_label, alignment=align)
            button_layout.addWidget(text_label, alignment=align)
        else:
            button_layout.addWidget(icon_label)
            button_layout.addWidget(text_label)

        if self._tooltip:
            set_tooltip(button, action.label, position="top")

        return button

    def _run_action(self, action: ControlCenterActionConfig):
        if action.command:
            parts = action.command.split(None, 1)
            shell_open(parts[0], parameters=parts[1] if len(parts) > 1 else None)
            self.refresh_popup()
            return

        action_id = action.id
        if action_id == "toggle_theme":
            self._current_theme = ThemeService.toggle_theme_mode() or self._current_theme
        elif action_id == "toggle_dnd":
            self._toggle_dnd()
        elif action_id == "cycle_dnd":
            current = DndService.get_status()
            new_status = "priority" if current == "disabled" else "alarms" if current == "priority" else "disabled"
            DndService.set_status(new_status)
            self._current_dnd = new_status
        elif action_id == "screenshot":
            active = CustomToolTip._active_tooltip
            if active is not None:
                active.hide()
            self.parentWidget().hide()
            ScreenshotService.start()
            return
        elif action_id == "touch_keyboard":
            TouchKeyboardService.toggle()
        elif action_id == "toggle_mute":
            interface = self._get_volume_interface()
            if interface is not None:
                interface.SetMute(not interface.GetMute(), None)
        elif action_id == "toggle_mic_mute":
            interface = self._get_microphone_interface()
            if interface is not None:
                interface.SetMute(not interface.GetMute(), None)
        else:
            logging.debug("Unknown control center action: %s", action_id)
        self.refresh_popup()

    def _toggle_dnd(self):
        status = DndService.get_status()
        new_status = "disabled" if status != "disabled" else "priority"
        DndService.set_status(new_status)
        self._current_dnd = new_status

    def _get_volume_interface(self):
        service = self._audio_services.get("output")
        return service.get_volume_interface() if service else None

    def _get_microphone_interface(self):
        service = self._audio_services.get("input")
        return service.get_microphone_interface() if service else None

    def refresh_state(self) -> None:
        if self._current_theme is not None:
            self._current_theme = ThemeService.get_theme_mode()
        if self._current_dnd is not None:
            self._current_dnd = DndService.get_status()

        for action_id, button in self._action_buttons.items():
            active = self._is_action_active(action_id)
            disabled = self._is_action_disabled(action_id)

            classes = ["button", action_id]
            if active:
                classes.append("active")
            if disabled:
                classes.append("disabled")

            button.setProperty("class", " ".join(classes))
            button.setEnabled(not disabled)

            if self._tooltip:
                action_label = next((a.label for a in self.config.actions if a.id == action_id), action_id)
                tooltip_text = f"{action_label} (Disabled)" if disabled else action_label
                set_tooltip(button, tooltip_text, position="top")

            for child in button.findChildren(QWidget):
                child_classes = (child.property("class") or "").split()
                child_classes = [c for c in child_classes if c not in ("active", "disabled")]
                if active:
                    child_classes.append("active")
                if disabled:
                    child_classes.append("disabled")
                child.setProperty("class", " ".join(child_classes))

    def _is_action_active(self, action_id: str) -> bool:
        if action_id in {"toggle_dnd", "cycle_dnd"}:
            return self._current_dnd is not None and self._current_dnd != "disabled"
        if action_id == "toggle_theme":
            return self._current_theme == "dark"
        if action_id == "toggle_mute":
            interface = self._get_volume_interface()
            return bool(interface.GetMute()) if interface is not None else False
        if action_id == "toggle_mic_mute":
            interface = self._get_microphone_interface()
            return bool(interface.GetMute()) if interface is not None else False
        return False

    def _is_action_disabled(self, action_id: str) -> bool:
        if action_id == "toggle_mute":
            return self._get_volume_interface() is None
        if action_id == "toggle_mic_mute":
            return self._get_microphone_interface() is None
        return False

from PyQt6.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from core.services.glazewm.client import BindingMode, GlazewmClient
from core.services.glazewm.connection import GlazewmConnection

BINDING_MODE_MESSAGES = [
    "sub -e binding_modes_changed",
    "query binding-modes",
]


class GlazewmBindingModes(GlazewmConnection):
    """The active GlazeWM binding mode. `name` is "" when none is active or while offline."""

    bindingModeChanged = pyqtSignal()

    MESSAGES = BINDING_MODE_MESSAGES

    _name = ""
    _display_name = ""

    @pyqtProperty(str, notify=bindingModeChanged)
    def name(self) -> str:
        return self._name

    @pyqtProperty(str, notify=bindingModeChanged)
    def displayName(self) -> str:
        return self._display_name or self._name

    @pyqtProperty(bool, notify=bindingModeChanged)
    def active(self) -> bool:
        return bool(self._name)

    def _bind(self, client: GlazewmClient) -> None:
        client.binding_mode_changed.connect(self._on_binding_mode)

    def _unbind(self, client: GlazewmClient) -> None:
        client.binding_mode_changed.disconnect(self._on_binding_mode)

    def _reset(self) -> None:
        self._set_binding_mode("", "")

    @pyqtSlot(BindingMode)
    def _on_binding_mode(self, mode: BindingMode) -> None:
        self._set_binding_mode(mode.name or "", mode.display_name or "")

    def _set_binding_mode(self, name: str, display_name: str) -> None:
        if (name, display_name) != (self._name, self._display_name):
            self._name = name
            self._display_name = display_name
            self.bindingModeChanged.emit()

    @pyqtSlot(str)
    def enableBindingMode(self, name: str) -> None:
        if (client := self.client) is not None and name:
            client.enable_binding_mode(name)

    @pyqtSlot()
    def disableBindingMode(self) -> None:
        """Disable the active binding mode, if any."""
        if (client := self.client) is not None and self._name:
            client.disable_binding_mode(self._name)

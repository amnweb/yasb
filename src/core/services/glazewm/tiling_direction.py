from PyQt6.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from core.services.glazewm.client import GlazewmClient, TilingDirection
from core.services.glazewm.connection import GlazewmConnection

TILING_DIRECTION_MESSAGES = [
    "sub -e focus_changed tiling_direction_changed focused_container_moved",
    "query tiling-direction",
]


class GlazewmTiling(GlazewmConnection):
    """Tiling direction of the focused container: "horizontal", "vertical", or "" while offline."""

    directionChanged = pyqtSignal()

    MESSAGES = TILING_DIRECTION_MESSAGES

    _direction = ""

    @pyqtProperty(str, notify=directionChanged)
    def direction(self) -> str:
        return self._direction

    def _bind(self, client: GlazewmClient) -> None:
        client.tiling_direction_processed.connect(self._on_direction)

    def _unbind(self, client: GlazewmClient) -> None:
        client.tiling_direction_processed.disconnect(self._on_direction)

    def _reset(self) -> None:
        self._set_direction("")

    @pyqtSlot(TilingDirection)
    def _on_direction(self, direction: TilingDirection) -> None:
        self._set_direction(str(direction))

    def _set_direction(self, direction: str) -> None:
        if direction != self._direction:
            self._direction = direction
            self.directionChanged.emit()

    @pyqtSlot()
    def toggleTilingDirection(self) -> None:
        if (client := self.client) is not None:
            client.toggle_tiling_direction()

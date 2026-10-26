from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal


class Hotkey(QObject):
    """A global key combination in a widget file, registered whenever the bars load or reload."""

    activated = pyqtSignal()
    keysChanged = pyqtSignal()
    screenChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._keys = ""
        self._screen = "active"

    def _get_keys(self) -> str:
        return self._keys

    def _set_keys(self, keys: str) -> None:
        if keys != self._keys:
            self._keys = keys
            self.keysChanged.emit()

    def _get_screen(self) -> str:
        return self._screen

    def _set_screen(self, screen: str) -> None:
        if screen != self._screen:
            self._screen = screen
            self.screenChanged.emit()

    keys = pyqtProperty(str, _get_keys, _set_keys, notify=keysChanged)
    # active: the screen of the focused window, cursor: the screen under the mouse, primary: the primary screen
    screen = pyqtProperty(str, _get_screen, _set_screen, notify=screenChanged)

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal
from PyQt6.QtQuick import QQuickWindow


class PopupGraphics(QObject):
    """Lets a popup window give back its graphics device, swapchain and scene graph each time it hides."""

    windowChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window: QQuickWindow | None = None

    def _get_window(self) -> QQuickWindow | None:
        return self._window

    def _set_window(self, window: QQuickWindow | None) -> None:
        if window is self._window:
            return
        self._window = window
        if window is not None:
            # Qt keeps both until the window is deleted, and a popup window lives as long as its widget
            window.setPersistentGraphics(False)
            window.setPersistentSceneGraph(False)
        self.windowChanged.emit()

    window = pyqtProperty(QQuickWindow, _get_window, _set_window, notify=windowChanged)

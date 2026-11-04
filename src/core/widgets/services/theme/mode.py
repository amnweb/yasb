from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.utils.qml import qml_property
from core.widgets.services.theme.service import ThemeService


class WindowsTheme(QObject):
    """Windows' light or dark mode for QML: whether apps are dark, followed live, and switching it."""

    darkChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dark = ThemeService.get_theme_mode() == "dark"
        # Qt hears Windows switch, from Settings or from here
        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._read)

    @qml_property(bool, notify=darkChanged)
    def dark(self) -> bool:
        return self._dark

    def _read(self) -> None:
        self._set_dark(ThemeService.get_theme_mode() == "dark")

    def _set_dark(self, dark: bool) -> None:
        if dark != self._dark:
            self._dark = dark
            self.darkChanged.emit()

    # Switches apps and the taskbar together, as Windows Settings does
    @pyqtSlot(bool)
    def setDark(self, dark: bool) -> None:
        if ThemeService.set_theme_mode("dark" if dark else "light"):
            self._set_dark(dark)

    @pyqtSlot()
    def toggle(self) -> None:
        self.setDark(not self._dark)

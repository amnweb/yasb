import platform
import re
from PyQt6.QtWidgets import QApplication, QFrame, QMenu
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QScreen
from core.utils.win32.blurWindow import Blur

def is_windows_10() -> bool:
    version = platform.version()
    return bool(re.match(r'^10\.0\.1\d{4}$', version))

def percent_to_float(percent: str) -> float:
    return float(percent.strip('%')) / 100.0

def is_valid_percentage_str(s: str) -> bool:
    return s.endswith("%") and len(s) <= 4 and s[:-1].isdigit()

def get_screen_by_name(screen_name: str) -> QScreen:
    return next(filter(lambda scr: screen_name in scr.name(), QApplication.screens()), None)

class PopupWidget(QFrame):
    """A custom QFrame widget that acts as a popup and hides itself when a mouse click occurs outside its geometry.
    This widget provides functionality for creating popup windows with optional blur effects and rounded corners.
    When a mouse click is detected outside the popup's geometry, it automatically hides and deletes itself.
    Args:
        parent (QWidget, optional): The parent widget. Defaults to None.
        blur (bool, optional): Whether to apply blur effect to the popup. Defaults to False.
        round_corners (bool, optional): Whether to apply rounded corners to the popup. Defaults to False.
        round_corners_type (str, optional): Type of rounded corners ('normal', 'small'). Defaults to "normal".
        border_color (str, optional): Color of the popup border ('System','hex', 'None'). Defaults to "None".
    Methods:
        showEvent(event): Handles the show event, applying blur effects if enabled.
        eventFilter(obj, event): Filters mouse click events to hide popup when clicked outside.
        hideEvent(event): Handles the hide event, cleaning up event filters.
    """
    def __init__(self, parent=None, blur=False, round_corners=False, round_corners_type="normal", border_color="None"):
        super().__init__(parent)
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color
        QApplication.instance().installEventFilter(self)
 
    def showEvent(self, event):
        if self._blur:
            Blur(
                self.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=False if is_windows_10() else self._round_corners,
                RoundCornersType=self._round_corners_type,
                BorderColor=self._border_color
            )
        self.activateWindow() 
        super().showEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                self.hide()
                self.deleteLater()
                return True
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

class ContextMenu(QMenu):
    """A custom context menu class that extends QMenu with additional functionality.
    This class implements a context menu that automatically closes when clicking outside
    its boundaries and provides proper window activation handling.
    Methods:
        showEvent(event): Handles the menu show event by activating the window
        hideEvent(event): Handles the menu hide event by removing the event filter
        eventFilter(obj, event): Filters events to detect clicks outside the menu
    Inherits:
        QMenu: Base menu class from Qt
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QApplication.instance().installEventFilter(self)

    def showEvent(self, event):
        self.activateWindow() 
        super().showEvent(event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                self.hide()
                self.deleteLater()
                return True
        return super().eventFilter(obj, event)
    

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
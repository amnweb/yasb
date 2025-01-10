import platform
import re
from PyQt6.QtWidgets import QApplication, QFrame
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QScreen

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
    """
    A custom QFrame widget that acts as a popup and hides itself when a mouse click occurs outside its geometry.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        QApplication.instance().installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)
        
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
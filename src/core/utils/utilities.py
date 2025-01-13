import platform
import re
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect
from PyQt6.QtCore import QEvent, QTimer
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
    """
    A custom QFrame widget that acts as a popup and hides itself when a mouse click occurs outside its geometry
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


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
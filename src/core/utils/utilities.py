import platform
import re
from typing import Any, cast

import psutil
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QColor, QScreen
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QWidget

from core.utils.win32.blurWindow import Blur


def is_windows_10() -> bool:
    version = platform.version()
    return bool(re.match(r'^10\.0\.1\d{4}$', version))

def is_process_running(process_name: str) -> bool:
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False

def percent_to_float(percent: str) -> float:
    return float(percent.strip('%')) / 100.0

def is_valid_percentage_str(s: str) -> bool:
    return s.endswith("%") and len(s) <= 4 and s[:-1].isdigit()

def get_screen_by_name(screen_name: str) -> QScreen:
    return next(filter(lambda scr: screen_name in scr.name(), QApplication.screens()), None)


def add_shadow(el: QWidget, options: dict[str, Any]) -> None:
    """"Add a shadow effect to a given element."""
    if not options["enabled"]:
        return

    shadow_effect = QGraphicsDropShadowEffect(el)
    shadow_effect.setOffset(options["offset"][0], options["offset"][1])
    shadow_effect.setBlurRadius(options["radius"])

    color = options["color"]
    if color.startswith('#'):
        color = color.lstrip('#')
        # Handle hex with alpha (#RRGGBBAA format)
        if len(color) == 8:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = int(color[6:8], 16)
            shadow_effect.setColor(QColor(r, g, b, a))
        else:
            # Regular hex color without alpha
            shadow_effect.setColor(QColor('#' + color))
    else:
        # Named colors like "black", "red", etc.
        shadow_effect.setColor(QColor(color))

    el.setGraphicsEffect(shadow_effect)

class PopupWidget(QWidget):
    """
    A custom popup widget that can be used to create a frameless, translucent window.
    This widget can be used to create custom popups with various styles and effects.
    Attributes:
        _blur (bool): Whether to apply a blur effect to the popup.
        _round_corners (bool): Whether to round the corners of the popup.
        _round_corners_type (str): Type of round corners to apply.
        _border_color (str): Color of the border.
    Methods:
        setProperty(name, value): Set a property for the popup widget.
        setPosition(alignment, direction, offset_left, offset_top): Position the popup relative to its parent widget.
        showEvent(event): Handle the show event for the popup.
        eventFilter(obj, event): Filter events to detect clicks outside the popup.
        hideEvent(event): Handle the hide event for the popup.
        resizeEvent(event): Handle the resize event for the popup.
    """
    def __init__(self, parent=None, blur=False, round_corners=False, round_corners_type="normal", border_color="None"):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color

        # Create the inner frame
        self._popup_content = QFrame(self)        

        QApplication.instance().installEventFilter(self)

    def setProperty(self, name, value):
        super().setProperty(name, value)
        if name == "class":
            self._popup_content.setProperty(name, value)

    def setPosition(self, alignment='left', direction='down', offset_left=0, offset_top=0):
        """
        Position the popup relative to its parent widget.
        Args:
            alignment (str): Where to align the popup - 'left', 'right', or 'center'
            direction (str): Whether popup appears above ('up') or below ('down') the parent
            offset_left (int): Horizontal offset in pixels
            offset_top (int): Vertical offset in pixels
        """
        parent = cast(QWidget, self.parent()) # parent should be a QWidget
        if not parent:
            return

        widget_global_pos = parent.mapToGlobal(QPoint(offset_left, parent.height() + offset_top))

        if direction == 'up':
            global_y = parent.mapToGlobal(QPoint(0, 0)).y() - self.height() - offset_top
            widget_global_pos = QPoint(parent.mapToGlobal(QPoint(0, 0)).x() + offset_left, global_y)

        if alignment == 'left':
            global_position = widget_global_pos
        elif alignment == 'right':
            global_position = QPoint(
                widget_global_pos.x() + parent.width() - self.width(),
                widget_global_pos.y()
            )
        elif alignment == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (parent.width() - self.width()) // 2,
                widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos

        # Determine screen where the parent is
        screen = QApplication.screenAt(parent.mapToGlobal(parent.rect().center()))
        if screen:
            available_geometry = screen.availableGeometry()
            # Ensure the popup fits horizontally
            x = max(available_geometry.left(), min(global_position.x(), available_geometry.right() - self.width()))
            # Ensure the popup fits vertically
            y = max(available_geometry.top(), min(global_position.y(), available_geometry.bottom() - self.height()))
            global_position = QPoint(x, y)
        self.move(global_position)

    def _add_separator(self, layout):
        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setProperty('class', 'separator')
        separator.setStyleSheet('border:none')
        layout.addWidget(separator)

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

    def resizeEvent(self, event):
        self._popup_content.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

from typing import Any, override

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame

from core.utils.utilities import refresh_widget_style


class ClickableWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            a0.accept()
        super().mousePressEvent(a0)

    @override
    def setProperty(self, name: str | None, value: Any) -> bool:
        super().setProperty(name, value)
        if name == "class":
            refresh_widget_style(self)
            self.update()
            return True
        return False

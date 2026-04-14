from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

from core.ui.theme import get_tokens, theme_key

_DASH_HEIGHT = 6.0
_DASH_RADIUS = 3.0
_DASH_INACTIVE_W = 6.0
_DASH_ACTIVE_W = 24.0
_DASH_GAP = 6.0
_DURATION = 300


class StepIndicator(QWidget):
    """Animated dash-style step indicator."""

    def __init__(self, count: int = 1, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = max(count, 1)
        self._current = 0
        self._theme_key = theme_key()
        self._build_colors(get_tokens())

        self._widths: list[float] = [_DASH_ACTIVE_W if i == 0 else _DASH_INACTIVE_W for i in range(self._count)]
        self._colors: list[QColor] = [
            QColor(self._color_active) if i == 0 else QColor(self._color_inactive) for i in range(self._count)
        ]

        total_w = int(_DASH_ACTIVE_W + (_DASH_INACTIVE_W * (self._count - 1)) + _DASH_GAP * (self._count - 1)) + 2
        self.setFixedSize(total_w, 20)
        self._anim_group: QParallelAnimationGroup | None = None

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_colors(self, t: dict[str, str]) -> None:
        self._color_active = QColor(t["accent_fill_default"])
        self._color_inactive = QColor(t["control_strong_fill_disabled"])

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_colors(get_tokens())
        for i in range(self._count):
            self._colors[i] = QColor(self._color_active if i == self._current else self._color_inactive)
        self.update()

    @pyqtProperty(float)
    def activeWidth(self) -> float:
        return self._widths[self._current]

    @activeWidth.setter
    def activeWidth(self, v: float) -> None:
        self._widths[self._current] = v
        self.update()

    @pyqtProperty(float)
    def prevWidth(self) -> float:
        return self._widths[self._prev] if hasattr(self, "_prev") else _DASH_INACTIVE_W

    @prevWidth.setter
    def prevWidth(self, v: float) -> None:
        if hasattr(self, "_prev"):
            self._widths[self._prev] = v
            self.update()

    @pyqtProperty(QColor)
    def activeColor(self) -> QColor:
        return self._colors[self._current]

    @activeColor.setter
    def activeColor(self, c: QColor) -> None:
        self._colors[self._current] = QColor(c)
        self.update()

    @pyqtProperty(QColor)
    def prevColor(self) -> QColor:
        return self._colors[self._prev] if hasattr(self, "_prev") else QColor(self._color_inactive)

    @prevColor.setter
    def prevColor(self, c: QColor) -> None:
        if hasattr(self, "_prev"):
            self._colors[self._prev] = QColor(c)
            self.update()

    def set_current(self, index: int) -> None:
        index = max(0, min(index, self._count - 1))
        if index == self._current:
            return
        self._prev = self._current
        self._current = index

        group = QParallelAnimationGroup(self)

        # Shrink previous dash
        a_pw = QPropertyAnimation(self, b"prevWidth")
        a_pw.setDuration(_DURATION)
        a_pw.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a_pw.setStartValue(self._widths[self._prev])
        a_pw.setEndValue(_DASH_INACTIVE_W)
        group.addAnimation(a_pw)

        # Fade previous color
        a_pc = QPropertyAnimation(self, b"prevColor")
        a_pc.setDuration(_DURATION)
        a_pc.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a_pc.setStartValue(self._colors[self._prev])
        a_pc.setEndValue(QColor(self._color_inactive))
        group.addAnimation(a_pc)

        # Expand new active dash
        a_aw = QPropertyAnimation(self, b"activeWidth")
        a_aw.setDuration(_DURATION)
        a_aw.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a_aw.setStartValue(self._widths[self._current])
        a_aw.setEndValue(_DASH_ACTIVE_W)
        group.addAnimation(a_aw)

        # Color active dash
        a_ac = QPropertyAnimation(self, b"activeColor")
        a_ac.setDuration(_DURATION)
        a_ac.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a_ac.setStartValue(self._colors[self._current])
        a_ac.setEndValue(QColor(self._color_active))
        group.addAnimation(a_ac)

        group.start()
        self._anim_group = group  # prevent GC

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        total_w = sum(self._widths) + _DASH_GAP * (self._count - 1)
        x = (self.width() - total_w) / 2.0
        cy = self.height() / 2.0

        for i in range(self._count):
            w = self._widths[i]
            rect = QRectF(x, cy - _DASH_HEIGHT / 2.0, w, _DASH_HEIGHT)
            p.setBrush(self._colors[i])
            p.drawRoundedRect(rect, _DASH_RADIUS, _DASH_RADIUS)
            x += w + _DASH_GAP

        p.end()

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QSizePolicy, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

TRACK_H = 4
TRACK_ACTIVE_H = 4
THUMB_RADIUS = 6
THUMB_OUTER_RADIUS = 10
_DURATION = 120


def _resolve(t: dict[str, str], key: str) -> QColor:
    return QColor(t[key])


class Slider(QWidget):
    """Horizontal slider with a numeric value label."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 100,
        value: int = 50,
        suffix: str = "%",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._value = max(minimum, min(maximum, value))
        self._suffix = suffix
        self._dragging = False
        self._hover = False

        self._theme_key = theme_key()
        tokens = get_tokens()
        self._build_colors(tokens)

        self._thumb_scale = 1.0

        self.setFixedHeight(THUMB_OUTER_RADIUS * 2 + 4)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self._font = QFont()
        self._font.setFamilies(list(FONT_FAMILIES))
        self._font.setPixelSize(12)

        self._anim_scale = QPropertyAnimation(self, b"thumb_scale")
        self._anim_scale.setDuration(_DURATION)
        self._anim_scale.setEasingCurve(QEasingCurve.Type.OutQuad)

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_colors(self, t: dict[str, str]) -> None:
        self._accent = _resolve(t, "accent_fill_default")
        self._track_bg = _resolve(t, "control_strong_stroke_default")
        self._thumb_border = _resolve(t, "control_strong_stroke_default")
        self._thumb_fill = _resolve(t, "accent_fill_default")
        self._text_color = _resolve(t, "text_primary")

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_colors(get_tokens())
        self.update()

    # Properties

    @pyqtProperty(float)
    def thumb_scale(self) -> float:
        return self._thumb_scale

    @thumb_scale.setter
    def thumb_scale(self, v: float) -> None:
        self._thumb_scale = v
        self.update()

    def value(self) -> int:
        return self._value

    def set_value(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            self.update()

    # Geometry helpers

    def _label_width(self) -> int:
        return 38

    def _track_rect(self) -> tuple[float, float, float, float]:
        lw = self._label_width()
        x = lw + 4 + THUMB_OUTER_RADIUS
        y = self.height() / 2 - TRACK_H / 2
        w = self.width() - x - THUMB_OUTER_RADIUS
        return x, y, w, TRACK_H

    def _ratio(self) -> float:
        rng = self._max - self._min
        return (self._value - self._min) / rng if rng > 0 else 0.0

    def _thumb_center_x(self) -> float:
        x, _, w, _ = self._track_rect()
        return x + self._ratio() * w

    def _value_from_x(self, px: float) -> int:
        x, _, w, _ = self._track_rect()
        ratio = max(0.0, min(1.0, (px - x) / w)) if w > 0 else 0.0
        return round(self._min + ratio * (self._max - self._min))

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            tx, _, _, _ = self._track_rect()
            if e.position().x() < tx - THUMB_OUTER_RADIUS:
                return
            self._dragging = True
            self.set_value(self._value_from_x(e.position().x()))
            self._animate_thumb(0.7)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._dragging:
            self.set_value(self._value_from_x(e.position().x()))

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._animate_thumb(1.0)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def _animate_thumb(self, target: float) -> None:
        self._anim_scale.stop()
        self._anim_scale.setStartValue(self._thumb_scale)
        self._anim_scale.setEndValue(target)
        self._anim_scale.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        tx, ty, tw, th = self._track_rect()
        cx = self._thumb_center_x()
        cy = self.height() / 2.0

        # Inactive track (background)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._track_bg)
        track_rect = QRectF(tx, ty, tw, th)
        p.drawRoundedRect(track_rect, th / 2, th / 2)

        # Active track (filled portion)
        if cx > tx:
            p.setBrush(self._accent)
            active_rect = QRectF(tx, ty, cx - tx, th)
            p.drawRoundedRect(active_rect, th / 2, th / 2)

        # Thumb outer circle
        r = THUMB_OUTER_RADIUS * self._thumb_scale
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(80, 80, 80, 200) if self._theme_key == "dark" else QColor(255, 255, 255, 200))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Thumb border
        p.setPen(QPen(QColor(0, 0, 0, 20), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Thumb inner (accent)
        ir = THUMB_RADIUS * self._thumb_scale
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._thumb_fill)
        p.drawEllipse(QRectF(cx - ir, cy - ir, ir * 2, ir * 2))

        # Value label
        lw = self._label_width()
        p.setFont(self._font)
        p.setPen(self._text_color)
        label_rect = QRectF(0, 0, lw, self.height())
        p.drawText(
            label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{self._value}{self._suffix}"
        )

        p.end()

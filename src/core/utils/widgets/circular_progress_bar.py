from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QConicalGradient, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QVBoxLayout


class CircularProgressBar(QFrame):
    """A circular progress bar widget"""

    def __init__(
        self,
        parent=None,
        size: int = 16,
        thickness: int = 2,
        value: float = 0.0,
        color="#00C800",
        background_color: str = "#3C3C3C",
        animation: bool = True,
    ):
        super().__init__(parent)

        self._size = size
        self._thickness = thickness
        self._value = value
        self._color_config = color
        self.setContentsMargins(0, 0, 0, 0)
        self._background_color = QColor(background_color)
        self._animation_enabled = animation
        self._animation = QPropertyAnimation(self, b"animatedValue")
        self._animation.setDuration(400)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFixedSize(self._size, self._size)
        self._update_angles()

    @pyqtProperty(float)
    def animatedValue(self):
        """Get the current animated value."""
        return self._value

    @animatedValue.setter
    def animatedValue(self, value: float):
        """Set the animated value and trigger a repaint."""
        self._value = value
        self._update_angles()
        self.update()

    def _update_angles(self):
        """Update the angle calculations based on current value."""
        self._angle_span = (self._value / 100.0) * 360

    def _create_progress_brush(self, rect):
        """Create a brush for the progress arc (solid color or gradient)."""
        if isinstance(self._color_config, list) and len(self._color_config) > 1:
            center = QPointF(rect.center())
            gradient = QConicalGradient(center, 90)
            step = 1.0 / (len(self._color_config) - 1)
            for i, color in enumerate(self._color_config):
                gradient.setColorAt(i * step, QColor(color))
            return gradient
        else:
            color = self._color_config[0] if isinstance(self._color_config, list) else self._color_config
            return QColor(color)

    def paintEvent(self, event):
        """Paint the circular progress bar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate margin based on thickness and ensure it is at least 2
        # Maybe is there better solution for margin calculation but I'm not sure how to do it
        margin = (self._thickness + 1) // 2 + 1
        rect = self.contentsRect().adjusted(margin, margin, -margin, -margin)

        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter.setPen(QPen(self._background_color, self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        if self._value > 0:
            progress_brush = self._create_progress_brush(rect)
            painter.setPen(QPen(progress_brush, self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.drawArc(rect, 90 * 16, -int(self._angle_span * 16))

    def set_value(self, value: float):
        """Set the current value and update the display."""
        new_value = max(0, min(value, 100.0))
        # If value hasn't changed significantly, no need to animate
        if abs(new_value - self._value) < 0.9:
            return
        if self._animation_enabled:
            if self._animation.state() == QPropertyAnimation.State.Running:
                self._animation.stop()

            self._animation.setStartValue(self._value)
            self._animation.setEndValue(new_value)
            self._animation.start()
        else:
            self._value = new_value
            self._update_angles()
            self.update()


class CircularProgressWidget(QFrame):
    """A widget that contains a CircularProgressBar and exposes its API."""

    def __init__(self, progress_bar: CircularProgressBar):
        super().__init__()
        self._progress_bar = progress_bar
        self.setProperty("class", "progress-circle")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(progress_bar)
        self.setLayout(layout)

    def set_value(self, value: float):
        self._progress_bar.set_value(value)

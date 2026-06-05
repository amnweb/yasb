from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QConicalGradient, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QVBoxLayout


class ProgressBar(QFrame):
    """A progress bar widget that supports circular and linear modes."""

    def __init__(
        self,
        parent=None,
        size: int = 16,
        thickness: int = 2,
        value: float = 0.0,
        color="#00C800",
        background_color: str = "#3C3C3C",
        animation: bool = True,
        progress_type: str = "circular",
        radius: int = 0,
    ):
        super().__init__(parent)

        self._size = size
        self._thickness = thickness
        self._value = value
        self._color_config = color
        self.setContentsMargins(0, 0, 0, 0)
        self._background_color = QColor(background_color)
        self._animation_enabled = animation
        self._progress_type = progress_type
        self._radius = radius

        self._animation = QPropertyAnimation(self, b"animatedValue")
        self._animation.setDuration(400)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        if self._progress_type == "circular":
            self.setFixedSize(self._size, self._size)
            self._update_angles()
        elif self._progress_type == "linear_horizontal":
            self.setFixedSize(self._size, self._thickness)
        elif self._progress_type == "linear_vertical":
            self.setFixedSize(self._thickness, self._size)

    @pyqtProperty(float)
    def animatedValue(self):
        """Get the current animated value."""
        return self._value

    @animatedValue.setter
    def animatedValue(self, value: float):
        """Set the animated value and trigger a repaint."""
        self._value = value
        if self._progress_type == "circular":
            self._update_angles()
        self.update()

    def _update_angles(self):
        """Update the angle calculations based on current value."""
        self._angle_span = (self._value / 100.0) * 360

    def _create_circular_progress_brush(self, rect):
        """Create a brush for the circular progress arc (solid color or gradient)."""
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

    def _create_linear_progress_brush(self, rect):
        """Create a brush for the linear progress bar (solid color or static linear gradient)."""
        if isinstance(self._color_config, list) and len(self._color_config) > 1:
            if self._progress_type == "linear_horizontal":
                gradient = QLinearGradient(rect.topLeft(), rect.topRight())
            else:
                gradient = QLinearGradient(rect.bottomLeft(), rect.topLeft())

            step = 1.0 / (len(self._color_config) - 1)
            for i, color in enumerate(self._color_config):
                gradient.setColorAt(i * step, QColor(color))
            return gradient
        else:
            color = self._color_config[0] if isinstance(self._color_config, list) else self._color_config
            return QColor(color)

    def paintEvent(self, event):
        """Paint the progress bar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._progress_type == "circular":
            self._paint_circular(painter)
        elif self._progress_type in ["linear_horizontal", "linear_vertical"]:
            self._paint_linear(painter)

    def _paint_circular(self, painter):
        # Calculate margin based on thickness and ensure it is at least 2
        margin = (self._thickness + 1) // 2 + 1
        rect = self.contentsRect().adjusted(margin, margin, -margin, -margin)

        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter.setPen(QPen(self._background_color, self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        if self._value > 0:
            progress_brush = self._create_circular_progress_brush(rect)
            painter.setPen(QPen(progress_brush, self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.drawArc(rect, 90 * 16, -int(self._angle_span * 16))

    def _paint_linear(self, painter):
        rect = QRectF(self.contentsRect())
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Draw background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color)
        painter.drawRoundedRect(rect, self._radius, self._radius)

        if self._value > 0:
            # Calculate the clip region for the progress
            inner_rect = QRectF(rect)
            if self._progress_type == "linear_horizontal":
                progress_width = rect.width() * (self._value / 100.0)
                inner_rect.setWidth(progress_width)
            else:
                progress_height = rect.height() * (self._value / 100.0)
                inner_rect.setTop(rect.bottom() - progress_height)

            # Use clipping to ensure the radius perfectly matches the background
            painter.setClipRect(inner_rect)

            # Draw the progress brush over the exact same rounded rect
            progress_brush = self._create_linear_progress_brush(rect)
            painter.setBrush(progress_brush)
            painter.drawRoundedRect(rect, self._radius, self._radius)

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
            if self._progress_type == "circular":
                self._update_angles()
            self.update()


class ProgressWidget(QFrame):
    """A widget that contains a ProgressBar and exposes its API."""

    def __init__(self, progress_bar: ProgressBar):
        super().__init__()
        self._progress_bar = progress_bar
        self.setProperty("class", "progress-container")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(progress_bar)
        self.setLayout(layout)

    def set_value(self, value: float):
        self._progress_bar.set_value(value)

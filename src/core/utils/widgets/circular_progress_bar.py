from PyQt6.QtCore import QPointF, Qt, pyqtProperty, pyqtSlot
from PyQt6.QtGui import QColor, QConicalGradient, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget


class CircularProgressBar(QWidget):
    """A circular progress bar widget."""

    def __init__(
        self,
        parent=None,
        size: int = 16,
        thickness: int = 2,
        value: float = 0.0,
        color="#00C800",
        background_color: str = "#3C3C3C",
    ):
        super().__init__(parent)

        self._size = size
        self._thickness = thickness
        self._value = value
        self._color_config = color
        self._background_color = QColor(background_color)
        self.setFixedSize(self._size, self._size)
        self._update_angles()

    def _update_angles(self):
        """Update the angle calculations based on current value."""
        self._angle_span = (self._value / 100.0) * 360

    def _create_progress_brush(self, rect):
        """Create a brush for the progress arc (solid color or gradient)."""
        if isinstance(self._color_config, list) and len(self._color_config) > 1:
            # Create gradient
            center = QPointF(rect.center())
            gradient = QConicalGradient(center, 90)

            # Distribute colors evenly across the gradient
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

        # Calculate drawing rectangle
        margin = self._thickness // 2
        rect = self.rect().adjusted(margin, margin, -margin, -margin)

        # Draw background circle
        painter.setPen(QPen(self._background_color, self._thickness, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        # Draw progress arc
        if self._value > 0:
            progress_brush = self._create_progress_brush(rect)
            painter.setPen(QPen(progress_brush, self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.drawArc(rect, 90 * 16, -int(self._angle_span * 16))

    @pyqtSlot(float)
    def set_value(self, value: float):
        """Set the current value and update the display."""
        self._value = max(0, min(value, 100.0))
        self._update_angles()
        self.update()

    def get_value(self) -> float:
        """Get the current value."""
        return self._value

    value = pyqtProperty(float, get_value, set_value)

    def set_color(self, color):
        """Set the progress color (can be a single color string or list of colors for gradient)."""
        self._color_config = color
        self.update()

    def set_background_color(self, color: str):
        """Set the background color."""
        self._background_color = QColor(color)
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

"""
Loading indicators: Spinner (indeterminate circular) and LoaderLine (horizontal).
"""

from PyQt6.QtCore import QEasingCurve, QElapsedTimer, QEvent, QObject, QPropertyAnimation, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PyQt6.QtWidgets import QWidget

from core.utils.qobject import is_valid_qobject


class Spinner(QWidget):
    """Indeterminate circular loading spinner.

    The spinner continuously animates a rotating arc to indicate ongoing activity.
    The color and thickness of the arc can be customized via constructor parameters.
    Example:
        spinner = Spinner(size=32, color="#FF0000", pen_width=4, parent=some_widget)
    """

    def __init__(
        self, size: int = 24, color: str = "#FFFFFF", pen_width: int | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = QColor(color)
        self._pen_width = pen_width if pen_width is not None else max(2, size // 10)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

    @staticmethod
    def _ease(t: float) -> float:
        if t < 0.5:
            return 4 * t * t * t
        p = 2 * t - 2
        return 0.5 * p * p * p + 1

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self._pen_width / 2.0 + 1.0
        rect = self.rect().toRectF().adjusted(m, m, -m, -m)
        pen = QPen(self._color)
        pen.setWidthF(self._pen_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap if self._pen_width <= 10 else Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        ms = self._elapsed.elapsed()
        cycle = ms / 1600
        phase = cycle % 1.0
        accum = (int(cycle) * 260.0) % 360.0
        base_rot = (ms / 2600) * 360.0 % 360.0

        if phase < 0.5:
            e = self._ease(phase * 2.0)
            span, start = 10 + 260 * e, accum
        else:
            e = self._ease((phase - 0.5) * 2.0)
            span, start = 270 - 260 * e, accum + 260 * e

        painter.drawArc(rect, int(-(start + base_rot) * 16), int(-span * 16))
        painter.end()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()


class LoaderLine(QWidget):
    """An animated horizontal loading indicator that displays a sliding segment.

    The loader can be attached to any widget and will automatically position
    itself at the bottom edge, resizing when the parent widget changes size.

    Example:
        loader = LoaderLine(parent)
        loader.configure(
            class_name="my-loader",
            height=2,
            duration_ms=1800,
            segment_ratio=0.25,
            easing=QEasingCurve.Type.Linear
        )
        loader.attach_to_widget(target_widget)
        loader.start()

    Attributes:
        offset (pyqtProperty[float]): Animation progress from 0.0 to 1.0.

    """

    def __init__(self, parent: QWidget | None = None, color: str | None = None):
        super().__init__(parent)
        self._offset = 0.0
        self._segment_ratio = 0.18
        self._color: QColor | None = QColor(color) if color else None
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(2400)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.setFixedHeight(1)
        self.setVisible(False)
        self._target_widget: QWidget | None = None
        self._auto_position_enabled = False
        self.setProperty("class", "loader-line")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.raise_()

    def configure(
        self,
        class_name: str | None = None,
        duration_ms: int | None = None,
        easing: QEasingCurve.Type | None = None,
        segment_ratio: float | None = None,
        height: int | None = None,
        color: str | None = None,
    ) -> None:
        if class_name:
            self.setProperty("class", class_name)
        if duration_ms is not None:
            self._animation.setDuration(duration_ms)
        if easing is not None:
            self._animation.setEasingCurve(easing)
        if segment_ratio is not None:
            self._segment_ratio = segment_ratio
        if height is not None:
            self.setFixedHeight(height)
            self._position_in_widget()
        if color is not None:
            self._color = QColor(color)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def attach_to_widget(self, target_widget: QWidget) -> None:
        if not target_widget:
            return
        self._target_widget = target_widget
        if self.parent() is not target_widget:
            self.setParent(target_widget)
        self._auto_position_enabled = True
        target_widget.installEventFilter(self)
        target_widget.destroyed.connect(lambda: self.detach_from_widget())
        QTimer.singleShot(0, self._position_in_widget)

    def detach_from_widget(self) -> None:
        if self._target_widget and is_valid_qobject(self._target_widget):
            try:
                self._target_widget.removeEventFilter(self)
            except Exception:
                pass
        self._target_widget = None
        self._auto_position_enabled = False

    def _position_in_widget(self) -> None:
        target_widget = self._target_widget
        if not target_widget or not is_valid_qobject(target_widget):
            return
        try:
            h = self.maximumHeight()
            if h <= 0 or h >= 10000:
                h = self.height() or self.sizeHint().height() or 2
            self.setGeometry(0, target_widget.height() - h, target_widget.width(), h)
        except RuntimeError:
            pass

    def eventFilter(self, obj: QObject, event: QEvent):
        if self._auto_position_enabled and obj is self._target_widget and event.type() == QEvent.Type.Resize:
            self._position_in_widget()
        return super().eventFilter(obj, event)

    def start(self) -> None:
        if self._animation.state() == QPropertyAnimation.State.Running:
            return
        self._offset = 0.0
        self.setVisible(True)
        self._animation.start()

    def stop(self) -> None:
        if self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        self.setVisible(False)
        self.update()

    def getOffset(self) -> float:
        return self._offset

    def setOffset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = pyqtProperty(float, fget=getOffset, fset=setOffset)

    def paintEvent(self, event: QPaintEvent):
        if not self.isVisible():
            return
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        phase = min(max(self._offset, 0.0), 1.0)
        size_scale = 0.2 + 1.2 * (1 - (2 * phase - 1) ** 2)
        segment_w = max(6, int(w * self._segment_ratio * size_scale))
        x = int((w + segment_w) * self._offset) - segment_w
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        line_color = self._color if self._color else self.palette().color(QPalette.ColorRole.WindowText)
        painter.fillRect(x, 0, segment_w, h, QColor(line_color))

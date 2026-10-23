from collections.abc import Callable
from typing import override

from PyQt6.QtCore import QEvent, QObject, QRectF, QRunnable, QSize, QSizeF, Qt, pyqtSignal
from PyQt6.QtGui import QEnterEvent, QImage, QImageReader, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

IMAGE_RADIUS = 6


class ImageView(QFrame):
    """A picture as wide as the view in the shape of `aspect`, at most max_height tall, cropped to fit."""

    def __init__(self, pixmap: QPixmap, aspect: QSizeF, max_height: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._aspect = aspect
        self._max_height = max_height
        policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    @override
    def hasHeightForWidth(self) -> bool:
        return True

    @override
    def heightForWidth(self, a0: int) -> int:
        margins = self.contentsMargins()
        width = a0 - margins.left() - margins.right()
        if width <= 0 or self._aspect.isEmpty():
            return margins.top() + margins.bottom()
        height = round(width * self._aspect.height() / self._aspect.width())
        return min(height, self._max_height) + margins.top() + margins.bottom()

    @override
    def sizeHint(self) -> QSize:
        return QSize(0, self.heightForWidth(self.width() or round(self._aspect.width())))

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        target = QRectF(self.contentsRect())
        if target.isEmpty() or self._pixmap.isNull():
            return
        source = QRectF(self._pixmap.rect())
        scale = max(target.width() / source.width(), target.height() / source.height())
        crop = QSizeF(target.width() / scale, target.height() / scale)
        source = QRectF(
            source.center().x() - crop.width() / 2, source.center().y() - crop.height() / 2, crop.width(), crop.height()
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(target, IMAGE_RADIUS, IMAGE_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(target, self._pixmap, source)
        painter.end()


class HoverFrame(QFrame):
    """Shows `shown` in place of `hidden` while the pointer is over the frame; both keep their space."""

    def __init__(self, shown: QWidget, hidden: QWidget | None = None):
        super().__init__()
        self._shown = shown
        self._hidden = hidden
        for widget in (shown, hidden):
            if widget is not None:
                policy = widget.sizePolicy()
                policy.setRetainSizeWhenHidden(True)
                widget.setSizePolicy(policy)
        shown.hide()

    @override
    def enterEvent(self, event: QEnterEvent | None) -> None:
        if self._hidden is not None:
            self._hidden.hide()
        self._shown.show()
        super().enterEvent(event)

    @override
    def leaveEvent(self, a0: QEvent | None) -> None:
        self._shown.hide()
        if self._hidden is not None:
            self._hidden.show()
        super().leaveEvent(a0)


class NotificationCard(HoverFrame):
    def __init__(self, on_click: Callable[[], None], time_label: QLabel, dismiss_label: QLabel):
        super().__init__(dismiss_label, time_label)
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self._on_click()


class ImageSignals(QObject):
    # key, image (null if unreadable)
    loaded = pyqtSignal(str, QImage)


class ImageLoader(QRunnable):
    """Reads a picture off the GUI thread, scaled to fit max_size, or cropped to a square of it."""

    def __init__(self, signals: ImageSignals, key: str, path: str, max_size: QSize, square: bool, circle: bool):
        super().__init__()
        self._signals = signals
        self._key = key
        self._path = path
        self._max_size = max_size
        self._square = square
        self._circle = circle

    @override
    def run(self):
        reader = QImageReader(self._path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if self._square else Qt.AspectRatioMode.KeepAspectRatio
            scaled = size.scaled(self._max_size, mode)
            if scaled.width() < size.width():
                reader.setScaledSize(scaled)
        image = reader.read()
        if not image.isNull() and self._square:
            image = self._crop(image)
        self._signals.loaded.emit(self._key, image)

    def _crop(self, image: QImage) -> QImage:
        side = self._max_size.width()
        image = image.scaled(
            side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
        )
        source = QRectF((image.width() - side) / 2, (image.height() - side) / 2, side, side)
        result = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._circle:
            path = QPainterPath()
            path.addEllipse(QRectF(0, 0, side, side))
            painter.setClipPath(path)
        painter.drawImage(QRectF(0, 0, side, side), image, source)
        painter.end()
        return result

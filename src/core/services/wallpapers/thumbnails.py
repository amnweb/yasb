import hashlib
import os
import threading
import time
from contextlib import suppress

from PyQt6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, QUrl, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QImage, QImageIOHandler, QImageReader

from core.utils.qml import qml_property
from core.utils.system import app_data_path

FOLDER = app_data_path("wallpaper_thumbnails")
MAX_BYTES = 100 * 1024 * 1024
MAX_AGE_SECONDS = 30 * 24 * 60 * 60
CACHE_VERSION = 1


def key(image_path: str, width: int, height: int) -> str | None:
    """The cache file name for *image_path* drawn at *width* x *height* pixels, or None if the image is gone."""
    try:
        stat = os.stat(image_path)
    except OSError:
        return None
    source = os.path.normcase(os.path.normpath(image_path))
    identity = f"{CACHE_VERSION}|{source}|{stat.st_mtime_ns}|{stat.st_size}|{width}x{height}"
    return hashlib.blake2b(identity.encode(), digest_size=16).hexdigest() + ".png"


def save(name: str, image: QImage) -> None:
    path = os.path.join(FOLDER, name)
    partial = f"{path}.{threading.get_ident()}.tmp"
    try:
        os.makedirs(FOLDER, exist_ok=True)
        if image.save(partial, "PNG"):
            os.replace(partial, path)
            return
    except OSError:
        pass
    with suppress(OSError):
        os.remove(partial)


def prune() -> None:
    """Deletes thumbnails older than MAX_AGE_SECONDS, then the oldest ones until the rest fit in MAX_BYTES."""
    entries: list[tuple[float, int, str]] = []
    try:
        with os.scandir(FOLDER) as scan:
            for entry in scan:
                stat = entry.stat()
                entries.append((stat.st_mtime, stat.st_size, entry.path))
    except OSError:
        return

    entries.sort()
    total = sum(size for _, size, _ in entries)
    expired = time.time() - MAX_AGE_SECONDS
    for modified, size, path in entries:
        if modified >= expired and total <= MAX_BYTES:
            break
        with suppress(OSError):
            os.remove(path)
            total -= size


def _render(image_path: str, width: int, height: int) -> QImage:
    """*image_path* scaled to cover *width* x *height* and cropped to it around the centre."""
    reader = QImageReader(image_path)
    reader.setAutoTransform(True)
    # size() and setScaledSize() are in the stored orientation, before the EXIF rotation
    sideways = bool(reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90)
    size = reader.size()
    if sideways:
        size.transpose()
    if size.isValid():
        cover = size.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        reader.setScaledSize(cover.transposed() if sideways else cover)
    image = reader.read()
    if image.isNull():
        return image
    if image.width() < width or image.height() < height or not size.isValid():
        image = image.scaled(
            width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
        )
    return image.copy((image.width() - width) // 2, (image.height() - height) // 2, width, height)


def cached_file(image_path: str, width: int, height: int) -> str:
    """The cached thumbnail of *image_path* at *width* x *height*, or "" when there is none yet."""
    name = key(image_path, width, height)
    path = os.path.join(FOLDER, name) if name else ""
    return path if path and os.path.exists(path) else ""


def thumbnail_file(image_path: str, width: int, height: int) -> str:
    """The cached thumbnail of *image_path* at *width* x *height*, made now when missing; "" when it can't be read."""
    if path := cached_file(image_path, width, height):
        return path
    name = key(image_path, width, height)
    image = _render(image_path, width, height)
    if name is None or image.isNull():
        return ""
    save(name, image)
    return cached_file(image_path, width, height)


class _Made(QObject):
    finished = pyqtSignal(str, int, int, str)


class _Job(QRunnable):
    def __init__(self, image_path: str, width: int, height: int):
        super().__init__()
        self._request = (image_path, width, height)
        self.signals = _Made()

    def run(self) -> None:
        self.signals.finished.emit(*self._request, thumbnail_file(*self._request))


_pool: QThreadPool | None = None


def _jobs() -> QThreadPool:
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(2)
    return _pool


class WallpaperThumbnail(QObject):
    """A wallpaper's thumbnail at a size in pixels, as a file QML loads. It is made off the GUI thread and cached."""

    pathChanged = pyqtSignal()
    sizeChanged = pyqtSignal()
    sourceChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._path = ""
        self._size = QSize()
        self._source = QUrl()
        self._job: _Job | None = None
        # QML sets path and size one after the other, so the thumbnail is looked up once both are in
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(0)
        self._update_timer.timeout.connect(self._update)

    def _get_path(self) -> str:
        return self._path

    def _set_path(self, value: str) -> None:
        if value != self._path:
            self._path = value
            self.pathChanged.emit()
            self._update_timer.start()

    path = pyqtProperty(str, _get_path, _set_path, notify=pathChanged)

    def _get_size(self) -> QSize:
        return self._size

    def _set_size(self, value: QSize) -> None:
        if value != self._size:
            self._size = value
            self.sizeChanged.emit()
            self._update_timer.start()

    size = pyqtProperty(QSize, _get_size, _set_size, notify=sizeChanged)

    @qml_property(QUrl, notify=sourceChanged)
    def source(self) -> QUrl:
        return self._source

    def _show(self, file: str) -> None:
        source = QUrl.fromLocalFile(file) if file else QUrl()
        if source != self._source:
            self._source = source
            self.sourceChanged.emit()

    def _update(self) -> None:
        self._job = None
        width, height = self._size.width(), self._size.height()
        if not self._path or width <= 0 or height <= 0:
            self._show("")
            return
        if file := cached_file(self._path, width, height):
            self._show(file)
            return
        self._show("")
        self._job = _Job(self._path, width, height)
        self._job.signals.finished.connect(self._on_made)
        _jobs().start(self._job)

    def _on_made(self, image_path: str, width: int, height: int, file: str) -> None:
        if (image_path, width, height) == (self._path, self._size.width(), self._size.height()):
            self._job = None
            self._show(file)

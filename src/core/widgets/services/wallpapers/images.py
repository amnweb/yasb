import logging
import os

from PyQt6.QtCore import QObject, QRect, QRunnable, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImageReader, QPainter, QPixmap

from core.utils.system import get_build_and_ubr

FILE_TYPES = ("png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff")
WEBP_BUILDS = ((26220, 7653), (26100, 8037))


def supported_types() -> tuple[str, ...]:
    """The extensions this Windows build can use as a wallpaper."""
    build, ubr = get_build_and_ubr()
    if any(build >= least_build and ubr >= least_ubr for least_build, least_ubr in WEBP_BUILDS):
        return FILE_TYPES + ("webp",)
    return FILE_TYPES


def collect_image_files(image_paths: str | list[str]) -> list[str]:
    """Every usable wallpaper under *image_paths*, sorted by path."""
    if isinstance(image_paths, str):
        image_paths = [image_paths]

    file_types = supported_types()
    files: list[str] = []
    for path in image_paths:
        if not os.path.exists(path):
            continue
        for root, _, names in os.walk(path):
            for name in names:
                if name.lower().endswith(file_types):
                    files.append(os.path.join(root, name))

    return sorted(files)


class ScanSignals(QObject):
    finished = pyqtSignal(list)


class FolderScanner(QRunnable):
    """Walks the wallpaper folders off the GUI thread."""

    def __init__(self, image_paths: str | list[str]):
        super().__init__()
        self.image_paths = image_paths
        self.signals = ScanSignals()

    def run(self):
        try:
            files = collect_image_files(self.image_paths)
        except Exception:
            logging.exception("Failed to scan wallpaper folders")
            files = []
        self.signals.finished.emit(files)


class ImageSignals(QObject):
    loaded = pyqtSignal(str, QPixmap, int)


class ImageLoader(QRunnable):
    def __init__(self, image_path, width, height, index, dpr: float = 1.0):
        super().__init__()
        self.image_path = image_path
        self.target_width = width
        self.target_height = height
        self.index = index
        self.dpr = float(dpr) if dpr else 1.0
        self.signals = ImageSignals()

    def run(self):
        target_w = int(self.target_width * self.dpr)
        target_h = int(self.target_height * self.dpr)

        reader = QImageReader(self.image_path)
        original_size = reader.size()

        if not original_size.isValid():
            reader.setScaledSize(QSize(target_w, target_h))
            image = reader.read()
        else:
            orig_aspect = original_size.width() / original_size.height()
            target_aspect = target_w / target_h if target_h != 0 else 1.0

            if orig_aspect > target_aspect:
                scaled_height = target_h
                scaled_width = int(scaled_height * orig_aspect)
            else:
                scaled_width = target_w
                scaled_height = int(scaled_width / orig_aspect) if orig_aspect != 0 else target_h

            reader.setScaledSize(QSize(scaled_width, scaled_height))
            image = reader.read()

        pixmap = QPixmap(target_w, target_h)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        x = (target_w - image.width()) // 2
        y = (target_h - image.height()) // 2

        source_x = max(0, -x)
        source_y = max(0, -y)
        source_width = min(image.width() - source_x, target_w)
        source_height = min(image.height() - source_y, target_h)

        painter.drawImage(
            QRect(max(0, x), max(0, y), source_width, source_height),
            image,
            QRect(source_x, source_y, source_width, source_height),
        )
        painter.end()

        pixmap.setDevicePixelRatio(self.dpr)

        self.signals.loaded.emit(self.image_path, pixmap, self.index)

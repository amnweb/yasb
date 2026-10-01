import ctypes
import logging
import math
import os
from functools import cmp_to_key, partial

import comtypes.client
import pythoncom
import win32api
from PyQt6.QtCore import QObject, QRect, QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImageIOHandler, QImageReader, QPainter, QPixmap

from core.utils.system import get_build_and_ubr
from core.utils.win32.bindings.shell32 import CLSID_DesktopWallpaper, IDesktopWallpaper
from core.widgets.services.wallpapers import thumbnails

FILE_TYPES = ("png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff")
WEBP_BUILDS = ((26220, 7653), (26100, 8037))
EDD_GET_DEVICE_INTERFACE_NAME = 1


def supported_types() -> tuple[str, ...]:
    """The extensions this Windows build can use as a wallpaper."""
    build, ubr = get_build_and_ubr()
    if any(build >= least_build and ubr >= least_ubr for least_build, least_ubr in WEBP_BUILDS):
        return FILE_TYPES + ("webp",)
    return FILE_TYPES


def collect_image_files(image_paths: str | list[str]) -> list[str]:
    """Every usable wallpaper under *image_paths*, in name order."""
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

    return sorted(files, key=cmp_to_key(ctypes.windll.shlwapi.StrCmpLogicalW))


def current_wallpapers(screens: dict[str, tuple[int, int, int, int]]) -> dict[str, str]:
    """The wallpaper Windows shows on each of *screens*, by screen name."""
    pythoncom.CoInitialize()
    desktop = comtypes.client.CreateObject(CLSID_DesktopWallpaper, interface=IDesktopWallpaper)
    wallpapers: dict[str, str] = {}
    for name, rect in screens.items():
        try:
            device = win32api.GetMonitorInfo(win32api.MonitorFromRect(rect))["Device"]
            # The monitor's device interface path is the monitor ID IDesktopWallpaper takes.
            monitor = win32api.EnumDisplayDevices(device, 0, EDD_GET_DEVICE_INTERFACE_NAME).DeviceID
            wallpapers[name] = desktop.GetWallpaper(monitor)
        except Exception:
            logging.debug("Could not read the wallpaper on %s", name, exc_info=True)
    return wallpapers


def find_wallpapers(files: list[str], wallpapers: dict[str, str]) -> dict[str, int]:
    """Where each screen's wallpaper sits in *files*, by screen name."""
    wanted: dict[str, list[str]] = {}
    for name, path in wallpapers.items():
        if path:
            wanted.setdefault(os.path.normcase(os.path.normpath(path)), []).append(name)

    found: dict[str, int] = {}
    for index, file in enumerate(files):
        if not wanted:
            break
        for name in wanted.pop(os.path.normcase(os.path.normpath(file)), ()):
            found[name] = index
    return found


class ScanSignals(QObject):
    finished = pyqtSignal(list, dict)


class FolderScanner(QRunnable):
    """Walks the wallpaper folders off the GUI thread and finds each screen's wallpaper in them."""

    def __init__(self, image_paths: str | list[str], screens: dict[str, tuple[int, int, int, int]]):
        super().__init__()
        self.image_paths = image_paths
        self.screens = screens
        self.signals = ScanSignals()

    def run(self):
        try:
            files = collect_image_files(self.image_paths)
        except Exception:
            logging.exception("Failed to scan wallpaper folders")
            files = []

        current: dict[str, int] = {}
        if files:
            try:
                current = find_wallpapers(files, current_wallpapers(self.screens))
            except Exception:
                logging.debug("Could not read the current wallpapers", exc_info=True)
        self.signals.finished.emit(files, current)
        thumbnails.prune()


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
        target_w = math.ceil(self.target_width * self.dpr)
        target_h = math.ceil(self.target_height * self.dpr)

        cache_key = thumbnails.key(self.image_path, target_w, target_h)
        cached = thumbnails.load(cache_key) if cache_key else None
        if cached is not None:
            pixmap = QPixmap.fromImage(cached)
            pixmap.setDevicePixelRatio(self.dpr)
            self.signals.loaded.emit(self.image_path, pixmap, self.index)
            return

        reader = QImageReader(self.image_path)
        reader.setAutoTransform(True)
        # size() and setScaledSize() are in the stored orientation, before the EXIF rotation.
        sideways = bool(reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90)
        original_size = reader.size()
        if sideways:
            original_size.transpose()

        if not original_size.isValid():
            scaled_size = QSize(target_w, target_h)
        else:
            orig_aspect = original_size.width() / original_size.height()
            target_aspect = target_w / target_h if target_h != 0 else 1.0

            if orig_aspect > target_aspect:
                scaled_height = target_h
                scaled_width = int(scaled_height * orig_aspect)
            else:
                scaled_width = target_w
                scaled_height = int(scaled_width / orig_aspect) if orig_aspect != 0 else target_h

            scaled_size = QSize(scaled_width, scaled_height)

        reader.setScaledSize(scaled_size.transposed() if sideways else scaled_size)
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
        thumbnail = pixmap.toImage()

        self.signals.loaded.emit(self.image_path, pixmap, self.index)
        if cache_key and not image.isNull():
            QThreadPool.globalInstance().start(partial(thumbnails.save, cache_key, thumbnail))

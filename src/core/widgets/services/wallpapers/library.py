import os
import random
from typing import Any

from PyQt6.QtCore import QObject, QStandardPaths, QThreadPool, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.utils.qml import qml_property
from core.widgets.services.wallpapers.images import FolderScanner
from core.widgets.services.wallpapers.manager import WallpaperManager


class WallpaperLibrary(QObject):
    """The wallpapers in the folders QML gives, and setting one of them."""

    foldersChanged = pyqtSignal()
    animationChanged = pyqtSignal()
    imagesChanged = pyqtSignal()
    currentChanged = pyqtSignal()
    scanningChanged = pyqtSignal()

    _last_random: str | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._folders: list[str] = []
        self._animation = ""
        self._images: list[dict[str, Any]] = []
        self._current: dict[str, int] = {}
        self._scans = 0
        self._pick_random = False
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    def _get_folders(self) -> list[str]:
        return self._folders

    def _set_folders(self, value: list[str]) -> None:
        if value != self._folders:
            self._folders = list(value)
            self.foldersChanged.emit()

    folders = pyqtProperty("QStringList", _get_folders, _set_folders, notify=foldersChanged)

    def _get_animation(self) -> str:
        return self._animation

    def _set_animation(self, value: str) -> None:
        if value != self._animation:
            self._animation = value
            self.animationChanged.emit()

    # The transition played before a wallpaper is set on every screen: circle, slide_top, diamond, split or "" for none
    animation = pyqtProperty(str, _get_animation, _set_animation, notify=animationChanged)

    @qml_property("QVariantList", notify=imagesChanged)
    def images(self) -> list[dict[str, Any]]:
        return self._images

    @qml_property(bool, notify=scanningChanged)
    def scanning(self) -> bool:
        return self._scans > 0

    @pyqtSlot()
    def refresh(self) -> None:
        screens = {
            screen.name(): (area.left(), area.top(), area.right(), area.bottom())
            for screen in QGuiApplication.screens()
            for area in [screen.geometry()]
        }
        # No folders means the Pictures folder
        folders = self._folders or [QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)]
        scanner = FolderScanner(folders, screens)
        scanner.signals.finished.connect(self._on_scanned)
        self._scans += 1
        if self._scans == 1:
            self.scanningChanged.emit()
        self._pool.start(scanner)

    def _on_scanned(self, files: list[str], current: dict[str, int]) -> None:
        self._scans -= 1
        images = [{"path": path, "name": os.path.splitext(os.path.basename(path))[0]} for path in files]
        if images != self._images:
            self._images = images
            self._current = current
            self.imagesChanged.emit()
        # Windows still shows the old wallpaper while a transition plays
        elif current != self._current and not WallpaperManager.transition_playing():
            self._current = current
            self.currentChanged.emit()
        if not self._scans:
            self.scanningChanged.emit()
        if self._pick_random:
            self._pick_random = False
            self._set_random()

    @pyqtSlot(str, result="int")
    def currentIndex(self, screenName: str) -> int:
        return self._current.get(screenName, -1)

    @pyqtSlot(result="int")
    def screenCount(self) -> int:
        return len(WallpaperManager.monitor_ids())

    @pyqtSlot(str)
    def setWallpaper(self, path: str) -> None:
        if not WallpaperManager.set_wallpaper(path, animation=self._animation):
            return
        index = next((index for index, image in enumerate(self._images) if image["path"] == path), -1)
        if index >= 0:
            self._current = {screen.name(): index for screen in QGuiApplication.screens()}
            self.currentChanged.emit()

    @pyqtSlot(str, int)
    def setWallpaperOn(self, path: str, screen: int) -> None:
        monitors = WallpaperManager.monitor_ids()
        if 0 <= screen < len(monitors):
            WallpaperManager.set_wallpaper(path, monitors[screen])

    @pyqtSlot()
    def setRandomWallpaper(self) -> None:
        self._pick_random = True
        self.refresh()

    def _set_random(self) -> None:
        paths = [image["path"] for image in self._images]
        choices = [path for path in paths if path != WallpaperLibrary._last_random] or paths
        if not choices:
            return
        pick = random.choice(choices)
        WallpaperLibrary._last_random = pick
        self.setWallpaper(pick)

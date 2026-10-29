import logging

from PyQt6.QtCore import QObject, QRectF, pyqtProperty, pyqtSignal
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.bar.window import BarWindow
from core.utils.win32.composition import BackdropWindow


class Backdrop(QObject):
    """Blurs behind an item while it shows in a popup window of a bar that has a backdrop."""

    itemChanged = pyqtSignal()
    barChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._item: QQuickItem | None = None
        self._bar: QQuickWindow | None = None
        self._window: QQuickWindow | None = None
        self._backdrop_window: BackdropWindow | None = None
        self._shown: tuple[object, ...] | None = None

    def _get_item(self) -> QQuickItem | None:
        return self._item

    def _set_item(self, item: QQuickItem | None) -> None:
        if item is self._item:
            return
        self._item = item
        if item is not None:
            item.windowChanged.connect(self._attach)
        self._attach()
        self.itemChanged.emit()

    item = pyqtProperty(QQuickItem, _get_item, _set_item, notify=itemChanged)

    def _get_bar(self) -> QQuickWindow | None:
        return self._bar

    def _set_bar(self, bar: QQuickWindow | None) -> None:
        if bar is not self._bar:
            self._bar = bar
            self._attach()
            self.barChanged.emit()

    # The bar window whose backdrop setting decides whether the item gets blur
    bar = pyqtProperty(QQuickWindow, _get_bar, _set_bar, notify=barChanged)

    def _attach(self) -> None:
        window = self._item.window() if self._item is not None else None
        if window is None or window is self._window:
            return
        bar = self._bar
        if not isinstance(bar, BarWindow) or not bar.config.backdrop:
            return
        if self._backdrop_window is not None:
            self._backdrop_window.close()
            self._backdrop_window = None
        self._window, self._shown = window, None
        try:
            self._backdrop_window = BackdropWindow(window)
        except OSError:
            logging.exception("Could not create the backdrop for a popup of bar %s", bar.name)
            return
        window.afterAnimating.connect(self._follow)
        self._follow()

    def _follow(self) -> None:
        item, window, backdrop = self._item, self._window, self._backdrop_window
        if item is None or window is None or backdrop is None or item.window() is not window:
            return
        rect = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
        radius = float(item.property("radius") or 0) * (rect.width() / item.width() if item.width() > 0 else 1)
        opacity = item.opacity() if item.isVisible() else 0.0
        parent = item.parentItem()
        while parent is not None:
            opacity *= parent.opacity()
            parent = parent.parentItem()
        area = QRectF(0, 0, window.width(), window.height())
        shown = (area.getRect(), rect.getRect(), radius, opacity)
        if shown != self._shown:
            self._shown = shown
            backdrop.set_shapes(area, [(rect, radius)])
            backdrop.set_opacity(opacity)

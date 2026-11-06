"""A live picture of another window, drawn by DWM into a QML item's place."""

import logging
from ctypes import byref, wintypes
from typing import Any

from PyQt6.QtCore import QRectF, pyqtProperty, pyqtSignal
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.utils.qml import qml_property
from core.utils.win32.bindings.dwmapi import (
    DwmQueryThumbnailSourceSize,
    DwmRegisterThumbnail,
    DwmUnregisterThumbnail,
    DwmUpdateThumbnailProperties,
)
from core.utils.win32.bindings.user32 import IsWindow
from core.utils.win32.constants import (
    DWM_TNP_OPACITY,
    DWM_TNP_RECTDESTINATION,
    DWM_TNP_RECTSOURCE,
    DWM_TNP_SOURCECLIENTAREAONLY,
    DWM_TNP_VISIBLE,
)
from core.utils.win32.structs import DWM_THUMBNAIL_PROPERTIES, RECT, SIZE


class _Handle:
    """The DWM thumbnail an item holds, kept apart from the item so it can be released once the item is gone."""

    def __init__(self) -> None:
        self.value = wintypes.HANDLE(0)

    def release(self, *_args: Any) -> None:
        if self.value.value:
            DwmUnregisterThumbnail(self.value)
            self.value = wintypes.HANDLE(0)


class WindowThumbnail(QQuickItem):
    """Shows another window, live, in this item's place. DWM draws it over the QML scene, so nothing in the item's
    place is seen; the item's visibility, opacity and clipping, through all its parents, carry over."""

    hwndChanged = pyqtSignal()
    sourceSizeChanged = pyqtSignal()

    def __init__(self, parent: QQuickItem | None = None) -> None:
        super().__init__(parent)
        self._hwnd = 0
        self._handle = _Handle()
        self._source = (0, 0)
        # The properties DWM was last given, so it is told only of changes
        self._shown: tuple[Any, ...] | None = None
        self._window: QQuickWindow | None = None
        self.destroyed.connect(self._handle.release)
        self.windowChanged.connect(self._attach)
        self.visibleChanged.connect(self._place)

    def _get_hwnd(self) -> int:
        return self._hwnd

    def _set_hwnd(self, hwnd: int) -> None:
        if hwnd == self._hwnd:
            return
        self._hwnd = hwnd
        self.hwndChanged.emit()
        self._register()

    # The window shown
    hwnd = pyqtProperty(int, _get_hwnd, _set_hwnd, notify=hwndChanged)

    # The size of the window shown, in pixels; 0 until it is known
    @qml_property(int, notify=sourceSizeChanged)
    def sourceWidth(self) -> int:
        return self._source[0]

    @qml_property(int, notify=sourceSizeChanged)
    def sourceHeight(self) -> int:
        return self._source[1]

    def _attach(self, window: QQuickWindow | None) -> None:
        if self._window is not None:
            self._window.afterAnimating.disconnect(self._place)
        self._window = window
        if window is not None:
            # A parent moving or fading says nothing to this item, so its place is checked each frame
            window.afterAnimating.connect(self._place)
        self._register()

    def _register(self) -> None:
        self._handle.release()
        self._shown = None
        if self._window is None or not self._hwnd or not IsWindow(self._hwnd):
            self._set_source((0, 0))
            return
        if DwmRegisterThumbnail(int(self._window.winId()), self._hwnd, byref(self._handle.value)) != 0:
            logging.debug("Could not show a thumbnail of window %s", self._hwnd)
            self._handle.value = wintypes.HANDLE(0)
            self._set_source((0, 0))
            return
        size = SIZE()
        if DwmQueryThumbnailSourceSize(self._handle.value, byref(size)) == 0:
            self._set_source((size.cx, size.cy))
        self._place()

    def _set_source(self, source: tuple[int, int]) -> None:
        if source != self._source:
            self._source = source
            self.sourceSizeChanged.emit()

    def geometryChange(self, newGeometry: QRectF, oldGeometry: QRectF) -> None:
        super().geometryChange(newGeometry, oldGeometry)
        self._place()

    def _opacity(self) -> float:
        opacity = 1.0
        item: QQuickItem | None = self
        while item is not None:
            opacity *= item.opacity()
            item = item.parentItem()
        return opacity

    def _place(self) -> None:
        if not self._handle.value.value or self._window is None:
            return
        # Read each time, as the window shown can be resized while it is
        size = SIZE()
        if DwmQueryThumbnailSourceSize(self._handle.value, byref(size)) == 0:
            self._set_source((size.cx, size.cy))
        source_width, source_height = self._source
        scale = self._window.devicePixelRatio()
        rect = self.mapRectToScene(QRectF(0, 0, self.width(), self.height()))
        # DWM draws over the scene and knows nothing of clipping, so the picture is cut to every clipping parent here
        shown_rect = rect
        parent = self.parentItem()
        while parent is not None:
            if parent.clip():
                shown_rect = shown_rect.intersected(
                    parent.mapRectToScene(QRectF(0, 0, parent.width(), parent.height()))
                )
            parent = parent.parentItem()
        cut = (0.0, 0.0, 1.0, 1.0)
        if not shown_rect.isEmpty() and rect.width() > 0 and rect.height() > 0:
            cut = (
                (shown_rect.left() - rect.left()) / rect.width(),
                (shown_rect.top() - rect.top()) / rect.height(),
                (shown_rect.right() - rect.left()) / rect.width(),
                (shown_rect.bottom() - rect.top()) / rect.height(),
            )
        shown = (
            round(shown_rect.left() * scale),
            round(shown_rect.top() * scale),
            round(shown_rect.right() * scale),
            round(shown_rect.bottom() * scale),
            round(cut[0] * source_width),
            round(cut[1] * source_height),
            round(cut[2] * source_width),
            round(cut[3] * source_height),
            self.isVisible() and not shown_rect.isEmpty(),
            round(self._opacity() * 255),
        )
        if shown == self._shown:
            return
        self._shown = shown
        properties = DWM_THUMBNAIL_PROPERTIES()
        properties.dwFlags = (
            DWM_TNP_RECTDESTINATION
            | DWM_TNP_RECTSOURCE
            | DWM_TNP_VISIBLE
            | DWM_TNP_OPACITY
            | DWM_TNP_SOURCECLIENTAREAONLY
        )
        properties.rcDestination = RECT(*shown[:4])
        properties.rcSource = RECT(*shown[4:8])
        properties.fVisible = shown[8]
        properties.opacity = shown[9]
        properties.fSourceClientAreaOnly = False
        DwmUpdateThumbnailProperties(self._handle.value, byref(properties))

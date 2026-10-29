import ctypes
import logging
import weakref
from ctypes import wintypes
from functools import cache
from typing import Any, cast, override

from PyQt6 import sip
from PyQt6.QtCore import (
    QAbstractNativeEventFilter,
    QCoreApplication,
    QEvent,
    QEventLoop,
    QMetaObject,
    QObject,
    QRectF,
    Qt,
    QThread,
    QTimer,
)
from PyQt6.QtGui import QWindow
from winrt.windows.foundation import AsyncStatus, IAsyncAction
from winrt.windows.system import DispatcherQueue, DispatcherQueueController
from winrt.windows.system.interop import create_dispatcher_queue_controller
from winrt.windows.ui.composition import CompositionRoundedRectangleGeometry, Compositor, SpriteVisual
from winrt.windows.ui.composition.interop import create_desktop_window_target

from core.utils.win32.bindings.dwmapi import DwmSetWindowAttribute
from core.utils.win32.bindings.gdi32 import DeleteObject
from core.utils.win32.bindings.kernel32 import GetLastError, GetModuleHandle
from core.utils.win32.bindings.user32 import (
    CreateWindowEx,
    DestroyWindow,
    GetWindow,
    GetWindowLongPtr,
    GetWindowRect,
    IsWindowVisible,
    SetWindowPos,
    user32,
)
from core.utils.win32.composition_region import svg_region
from core.utils.win32.constants import (
    DWMWA_USE_HOSTBACKDROPBRUSH,
    GW_HWNDPREV,
    GWL_EXSTYLE,
    HWND_NOTOPMOST,
    HWND_TOPMOST,
    LWA_ALPHA,
    SWP_HIDEWINDOW,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_SHOWWINDOW,
    WM_WINDOWPOSCHANGED,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_NOREDIRECTIONBITMAP,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    WS_POPUP,
)
from core.utils.win32.structs import MSG, WNDCLASS, WNDPROC

BACKDROP_WINDOW_CLASS = "YasbBackdrop"

_dispatcher_queue: DispatcherQueueController | None = None
_compositor: Compositor | None = None
_shutting_down = False
_backdrops: weakref.WeakSet[BackdropWindow] = weakref.WeakSet()


def compositor() -> Compositor:
    global _compositor, _dispatcher_queue
    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError("The bar compositor must run on the Qt application thread")
    if _shutting_down:
        raise RuntimeError("The bar compositor is shutting down")
    if _compositor is not None:
        return _compositor
    # GetForCurrentThread returns null when absent; its projection stub omits that.
    queue = cast(DispatcherQueue | None, DispatcherQueue.get_for_current_thread())
    if queue is None and _dispatcher_queue is None:
        _dispatcher_queue = create_dispatcher_queue_controller()
    _compositor = Compositor()
    return _compositor


def shutdown_composition() -> None:
    """After all bars close, finish the shared runtime; safe when never initialized."""
    global _compositor, _dispatcher_queue, _shutting_down
    if _shutting_down or (_compositor is None and _dispatcher_queue is None):
        return
    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError("The bar compositor must shut down on the Qt application thread")
    # QML destroys popup windows of widgets only with its engine, after this
    for backdrop in list(_backdrops):
        backdrop.close()
    _shutting_down = True
    if _compositor is not None:
        try:
            _compositor.close()
        except OSError:
            logging.exception("Could not close the shared bar compositor")
        finally:
            _compositor = None
    try:
        if _dispatcher_queue is not None:
            # A current-thread queue cannot finish shutdown if we block its message
            # pump. A short nested Qt loop also works from aboutToQuit, without
            # depending on an asyncio loop that may already be stopping.
            operation = _dispatcher_queue.shutdown_queue_async()
            loop = QEventLoop()

            def completed(_operation: IAsyncAction, _status: AsyncStatus) -> None:
                # Completion can arrive before exec() or on another thread. Posting
                # quit avoids both a lost wakeup and direct cross-thread loop access.
                QMetaObject.invokeMethod(loop, "quit", Qt.ConnectionType.QueuedConnection)

            operation.completed = completed
            if operation.status == AsyncStatus.STARTED:
                loop.exec()
            operation.get_results()
            _dispatcher_queue = None
    except OSError:
        logging.exception("Could not shut down the bar dispatcher queue")


class _BackdropEvents(QAbstractNativeEventFilter):
    def __init__(self, backdrop: BackdropWindow) -> None:
        super().__init__()
        self._backdrop = weakref.ref(backdrop)

    @override
    def nativeEventFilter(self, eventType: Any, message: sip.voidptr | None) -> tuple[bool, sip.voidptr]:
        backdrop = self._backdrop()
        if backdrop is not None and not backdrop.closed and message is not None and eventType == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
            if msg.hwnd == backdrop.bar_hwnd and msg.message == WM_WINDOWPOSCHANGED:
                backdrop.follow()
        return False, sip.voidptr(0)


class BackdropWindow(QObject):
    """A click-through composition surface kept immediately behind its Qt window."""

    def __init__(self, window: QWindow) -> None:
        super().__init__(window)
        self._window = window
        self.bar_hwnd = int(window.winId())
        self.closed = False
        self._syncing = False
        self._area = QRectF()
        self._shapes: list[tuple[QRectF, float]] = []
        self._path = ""
        self._last_render: tuple[object, ...] | None = None
        self._has_region = False
        self._visuals: list[tuple[SpriteVisual, CompositionRoundedRectangleGeometry]] = []
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._update)
        self.hwnd = CreateWindowEx(
            WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_NOREDIRECTIONBITMAP | WS_EX_LAYERED | WS_EX_TRANSPARENT,
            _window_class(),
            None,
            WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            GetModuleHandle(None),
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError(GetLastError())
        try:
            # A layered, transparent window passes mouse input through even in its visual gaps.
            if not user32.SetLayeredWindowAttributes(self.hwnd, 0, 255, LWA_ALPHA):
                raise ctypes.WinError(GetLastError())
            enabled = wintypes.BOOL(True)
            result = DwmSetWindowAttribute(
                self.hwnd, DWMWA_USE_HOSTBACKDROPBRUSH, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
            if result:
                raise OSError(f"Enabling host backdrop brushes failed: {result & 0xFFFFFFFF:#010x}")
            self._brush = compositor().create_host_backdrop_brush()
            self._root = compositor().create_container_visual()
            self._root.clip = compositor().create_inset_clip()
            self._root.opacity = window.opacity()
            self._target = create_desktop_window_target(compositor(), self.hwnd)
            self._target.root = self._root
        except Exception:
            self.closed = True
            DestroyWindow(self.hwnd)
            self.deleteLater()
            raise
        self._native_events = _BackdropEvents(self)
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._native_events)
        window.installEventFilter(self)
        window.opacityChanged.connect(self.set_opacity)
        window.destroyed.connect(self.close)
        _backdrops.add(self)
        self.follow()

    def set_shapes(self, area: QRectF, shapes: list[tuple[QRectF, float]], path: str = "") -> None:
        if self.closed:
            return
        self._area = QRectF(area)
        self._shapes = [(QRectF(rect), radius) for rect, radius in shapes]
        self._path = path
        self._update_timer.start()

    @override
    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self._window and event is not None and event.type() == QEvent.Type.DevicePixelRatioChange:
            self.follow()
        return False

    def _update(self) -> None:
        if self.closed:
            return
        self._sync_geometry()
        try:
            self._render_shapes()
        except OSError, ValueError:
            logging.exception("Could not update the bar backdrop")

    def _render_shapes(self) -> None:
        area = self._area
        scale = self._window.devicePixelRatio()
        bounds = wintypes.RECT()
        if not GetWindowRect(self.bar_hwnd, ctypes.byref(bounds)):
            return
        width, height = bounds.right - bounds.left, bounds.bottom - bounds.top
        key = (
            area.getRect(),
            tuple((rect.getRect(), radius) for rect, radius in self._shapes),
            self._path,
            scale,
            width,
            height,
        )
        if key == self._last_render:
            return
        if self._path:
            region = svg_region(self._path, area, width, height, scale)
            if not user32.SetWindowRgn(self.hwnd, region, True):
                error = ctypes.WinError(GetLastError())
                DeleteObject(region)
                raise error
            self._has_region = True
            self._root.offset = (0, 0, 0)
            self._root.size = (width, height)
            shapes = [(QRectF(0, 0, width / scale, height / scale), 0.0)]
        else:
            if self._has_region:
                user32.SetWindowRgn(self.hwnd, None, True)
                self._has_region = False
            self._root.offset = (area.x() * scale, area.y() * scale, 0)
            self._root.size = (area.width() * scale, area.height() * scale)
            shapes = self._shapes
        while len(self._visuals) > len(shapes):
            sprite, _ = self._visuals.pop()
            self._root.children.remove(sprite)
        for index, (rect, radius) in enumerate(shapes):
            if index == len(self._visuals):
                sprite = compositor().create_sprite_visual()
                sprite.brush = self._brush
                geometry = compositor().create_rounded_rectangle_geometry()
                sprite.clip = compositor().create_geometric_clip(geometry)
                self._visuals.append((sprite, geometry))
                self._root.children.insert_at_top(sprite)
            sprite, geometry = self._visuals[index]
            sprite.offset = (rect.x() * scale, rect.y() * scale, 0)
            sprite.size = (rect.width() * scale, rect.height() * scale)
            geometry.size = sprite.size
            # Capped like a Qt Quick Rectangle's radius
            corner = max(0.0, min(radius, rect.width() / 2, rect.height() / 2)) * scale
            geometry.corner_radius = (corner, corner)
        self._last_render = key

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        _backdrops.discard(self)
        self._update_timer.stop()
        if not sip.isdeleted(self._window):
            self._window.removeEventFilter(self)
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._native_events)
        try:
            # The WinRT setter accepts null, although the projection's stub does not.
            self._target.root = None  # pyright: ignore[reportAttributeAccessIssue]
            self._target.close()
            self._root.children.remove_all()
            self._visuals.clear()
            self._root.close()
            self._brush.close()
        finally:
            DestroyWindow(self.hwnd)
            self.deleteLater()

    def follow(self) -> None:
        if self.closed:
            return
        self._sync_geometry()
        self._update_timer.start()

    def _sync_geometry(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            rect = wintypes.RECT()
            if not GetWindowRect(self.bar_hwnd, ctypes.byref(rect)):
                return
            topmost = bool(GetWindowLongPtr(self.bar_hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
            if topmost != bool(GetWindowLongPtr(self.hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST):
                SetWindowPos(
                    self.hwnd,
                    HWND_TOPMOST if topmost else HWND_NOTOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE,
                )
            visible = IsWindowVisible(self.bar_hwnd)
            current = wintypes.RECT()
            GetWindowRect(self.hwnd, ctypes.byref(current))
            if (
                bytes(rect) == bytes(current)
                and visible == IsWindowVisible(self.hwnd)
                and GetWindow(self.hwnd, GW_HWNDPREV) == self.bar_hwnd
            ):
                return
            flags = SWP_NOACTIVATE | (SWP_SHOWWINDOW if visible else SWP_HIDEWINDOW)
            if not SetWindowPos(
                self.hwnd, self.bar_hwnd, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, flags
            ):
                logging.warning("Could not position the backdrop window: %d", GetLastError())
        finally:
            self._syncing = False

    def set_opacity(self, opacity: float) -> None:
        if not self.closed:
            self._root.opacity = opacity


@cache
def _window_class() -> str:
    procedure = ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p).value
    assert procedure is not None
    window_class = WNDCLASS(
        lpfnWndProc=WNDPROC(procedure),
        hInstance=GetModuleHandle(None),
        lpszClassName=BACKDROP_WINDOW_CLASS,
    )
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError(GetLastError())
    return BACKDROP_WINDOW_CLASS

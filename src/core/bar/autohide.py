import logging
from typing import TYPE_CHECKING, override

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QWindow

from core.bar.appbar import EXCLUDED_WINDOW_CLASS_SUFFIXES, EXCLUDED_WINDOW_CLASSES
from core.utils.win32.bindings.user32 import GetClassName, GetWindowText, IsWindowVisible, MonitorFromWindow, user32
from core.utils.win32.structs import WNDENUMPROC
from core.utils.win32.utils import is_window_maximized

if TYPE_CHECKING:
    from core.bar.window import BarWindow

HIDE_DELAY_MS = 600


class AutoHideZone(QWindow):
    def __init__(self, bar: BarWindow):
        super().__init__()
        self._bar = bar
        self.setFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        # A layered window passes clicks through where it is fully transparent, so the zone keeps a trace of alpha
        self.setOpacity(0.01)

    @override
    def event(self, a0: QEvent | None) -> bool:
        if a0 is not None and a0.type() == QEvent.Type.Enter and self._bar.autohide_manager is not None:
            self._bar.autohide_manager.show_bar()
        return super().event(a0)


class AutoHideManager(QObject):
    def __init__(self, bar: BarWindow, parent: QObject | None = None):
        super().__init__(parent)
        self.bar = bar
        self._zone: AutoHideZone | None = None
        self._hide_timer: QTimer | None = None
        self._enabled = False

    def setup_autohide(self) -> None:
        self._enabled = True
        self._zone = AutoHideZone(self.bar)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_bar)
        self.bar.installEventFilter(self)

        try:
            self.bar.remove_app_bar()
        except Exception as e:
            logging.error("Failed to remove AppBar reservation: %s", e)

        QTimer.singleShot(HIDE_DELAY_MS, self.setup_detection_zone)

    def setup_detection_zone(self) -> None:
        screen = self.bar.screen()
        if not self._enabled or self._zone is None or screen is None:
            return
        area = screen.geometry()
        edge = self.bar.config.edge
        if edge == "top":
            self._zone.setGeometry(area.x(), area.y(), area.width(), 1)
        elif edge == "bottom":
            self._zone.setGeometry(area.x(), area.y() + area.height() - 1, area.width(), 1)
        elif edge == "left":
            self._zone.setGeometry(area.x(), area.y(), 1, area.height())
        else:
            self._zone.setGeometry(area.x() + area.width() - 1, area.y(), 1, area.height())
        self.restart_hide_timer()

    def restart_hide_timer(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.start(HIDE_DELAY_MS)

    def show_bar(self) -> None:
        if self._enabled and not self.bar.isVisible():
            self.bar.show_bar()

    def hide_bar(self) -> None:
        if not self._enabled or not self.bar.isVisible():
            return
        if self._should_stay_visible():
            self.restart_hide_timer()
            return
        self.bar.hide_bar()
        if self._zone is not None:
            self._zone.show()
            self._zone.raise_()

    def _belongs_to_bar(self, window: QWindow) -> bool:
        parent = window.transientParent()
        while parent is not None:
            if parent is self.bar:
                return True
            parent = parent.transientParent()
        return False

    def _should_stay_visible(self) -> bool:
        cursor = QCursor.pos()
        for window in QGuiApplication.topLevelWindows():
            if window is self.bar or window is self._zone or not window.isVisible():
                continue
            if self._belongs_to_bar(window) or window.geometry().contains(cursor):
                return True
        return False

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a0 is self.bar and a1 is not None and self._enabled:
            if a1.type() == QEvent.Type.Enter and self._hide_timer is not None:
                self._hide_timer.stop()
            elif a1.type() == QEvent.Type.Leave and not self.is_mouse_in_safe_zone(QCursor.pos(), self.bar.geometry()):
                self.restart_hide_timer()
        return False

    def is_mouse_in_safe_zone(self, cursor: QPoint, bar: QRect) -> bool:
        """Is the cursor in the gap between the bar and its screen edge?"""
        screen = self.bar.screen()
        if screen is None:
            return False
        area = screen.geometry()
        x = cursor.x() - area.x()
        y = cursor.y() - area.y()
        edge = self.bar.config.edge
        if self.bar.config.vertical:
            if y < 0 or y > area.height():
                return False
            if edge == "left":
                return 0 <= x <= bar.x() - area.x()
            return bar.x() + bar.width() - area.x() <= x <= area.width()
        if x < 0 or x > area.width():
            return False
        if edge == "top":
            return 0 <= y <= bar.y() - area.y()
        return bar.y() + bar.height() - area.y() <= y <= area.height()

    def is_enabled(self) -> bool:
        return self._enabled

    def cleanup(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.stop()
        if self._zone is not None:
            self._zone.hide()
            self._zone.destroy()
            self._zone = None
        self.bar.removeEventFilter(self)
        self._enabled = False

        if self.bar.config.reserve_space:
            try:
                self.bar.update_app_bar()
            except Exception as e:
                logging.error("Failed to restore AppBar reservation: %s", e)


class MaximizedWindowWatcher(QObject):
    """Turns autohide on while any window is maximized on the bar's monitor."""

    def __init__(self, bar: BarWindow, parent: QObject | None = None):
        super().__init__(parent)
        self.bar = bar
        self._active = False
        self._had_autohide_before = False
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    def _has_maximized_window(self) -> bool:
        found = False

        def visit(hwnd: int, _: object) -> bool:
            nonlocal found
            try:
                if not IsWindowVisible(hwnd) or not GetWindowText(hwnd):
                    return True
                class_name = GetClassName(hwnd) or ""
                if class_name in EXCLUDED_WINDOW_CLASSES or class_name.endswith(EXCLUDED_WINDOW_CLASS_SUFFIXES):
                    return True
                if MonitorFromWindow(hwnd) == self.bar.monitor_hwnd and is_window_maximized(hwnd):
                    found = True
                    return False
            except Exception:
                pass
            return True

        user32.EnumWindows(WNDENUMPROC(visit), 0)
        return found

    def _check(self) -> None:
        if not self.bar.monitor_hwnd:
            return
        try:
            maximized = self._has_maximized_window()
        except Exception:
            logging.exception("Failed to check maximized windows")
            return
        if maximized and not self._active:
            self._active = True
            self._had_autohide_before = self.bar.autohide_enabled
            if not self._had_autohide_before:
                self.bar.enable_autohide()
        elif not maximized and self._active:
            self._release()

    def _release(self) -> None:
        self._active = False
        if self._had_autohide_before:
            self._had_autohide_before = False
            return
        self.bar.disable_autohide()

    def cleanup(self) -> None:
        self._timer.stop()
        if self._active:
            self._release()

import ctypes
import ctypes.wintypes
import logging
import os
import winreg
from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, cast, override

import win32gui
import win32process
from PyQt6.QtCore import (
    QAbstractNativeEventFilter,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QAction, QCursor, QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QWidget,
    QWidgetAction,
)
from win32con import HWND_BOTTOM, HWND_NOTOPMOST, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE

from core.utils.controller import exit_application, reload_application
from core.utils.shell_utils import shell_open
from core.utils.utilities import refresh_widget_style
from core.utils.win32.app_bar import APPBAR_CALLBACK_MESSAGE, AppBarNotify
from core.utils.win32.bindings import SetWindowPos
from core.utils.win32.bindings.user32 import KillTimer, RegisterWindowMessage, SetTimer, user32
from core.utils.win32.structs import MSG
from core.utils.win32.utils import apply_qmenu_style

if TYPE_CHECKING:
    import PyQt6.sip as sip

    from core.bar import Bar
    from core.widgets.base import BaseWidget

# Register TaskbarCreated message to detect Explorer restarts
WM_TASKBARCREATED = RegisterWindowMessage("TaskbarCreated")


class GlobalState:
    """Centralized global state for detached widgets and application-wide configurations."""

    _is_dark = False
    _stylesheet: str | None = None
    _tooltip_options: Any = None

    @classmethod
    def is_dark(cls) -> bool:
        return cls._is_dark

    @classmethod
    def set_dark(cls, value: bool):
        cls._is_dark = value

    @classmethod
    def stylesheet(cls) -> str:
        return cls._stylesheet or ""

    @classmethod
    def set_stylesheet(cls, value: str):
        cls._stylesheet = value

    @classmethod
    def tooltip_options(cls) -> Any:
        return cls._tooltip_options

    @classmethod
    def set_tooltip_options(cls, value: Any):
        cls._tooltip_options = value


class BarAnimationManager(QObject):
    """Handles bar show/hide animations."""

    def __init__(self, bar_widget: Bar, parent: QObject | None = None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._animation: QPropertyAnimation | None = None
        self._target_geo: tuple[int, int, int, int] | None = None
        self._pending_action: str | None = None

    def show_bar(self):
        if not self.bar_widget.animation.get("enabled"):
            self.bar_widget.show()
            return
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._pending_action = "show"
            return
        self._pending_action = None
        if self.bar_widget.animation.get("type") == "fade":
            self.start_fade(True)
        else:
            self._start_slide(True)

    def hide_bar(self):
        if not self.bar_widget.animation.get("enabled"):
            self.bar_widget.skip_animation = True
            self.bar_widget.hide()
            self.bar_widget.skip_animation = False
            return
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._pending_action = "hide"
            return
        self._pending_action = None
        if self.bar_widget.animation.get("type") == "fade":
            self.start_fade(False)
        else:
            self._start_slide(False)

    def _stop_animation(self):
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        self._animation = None

    def start_fade(self, show: bool):
        self._stop_animation()
        duration = self.bar_widget.animation.get("duration", 300)
        self._animation = QPropertyAnimation(self.bar_widget, b"windowOpacity")
        self._animation.setDuration(duration)
        self._animation.setStartValue(0.0 if show else 1.0)
        self._animation.setEndValue(1.0 if show else 0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.finished.connect(self._on_show_finished if show else self._on_hide_finished)
        if show:
            self.bar_widget.setWindowOpacity(0.0)
            self.bar_widget.show()
        self._animation.start()

    def _slide_is_blocked(self, hidden: QRect) -> bool:
        """Is another screen sitting where the bar would slide out of view?

        The bar leaves its own screen while it slides, so on stacked monitors it would show up on
        the one next to it. Keeping it clipped means resizing the window on every frame, and DWM
        redraws the blur and the window shadow a step behind that, which is what smears. Nothing
        can clip a blurred window without resizing it, so those bars fade instead.
        """
        return any(screen.geometry().intersects(hidden) for screen in QApplication.screens())

    def _start_slide(self, show: bool):
        self._stop_animation()
        bar = self.bar_widget

        bar.position_bar()
        geo = bar.geometry()
        self._target_geo = (geo.x(), geo.y(), geo.width(), geo.height())

        screen = bar.screen()
        if screen is None:
            self.start_fade(show)
            return
        screen_geo = screen.geometry()
        if bar.alignment["position"] == "top":
            hidden_y = screen_geo.y() - geo.height()
        else:
            hidden_y = screen_geo.y() + screen_geo.height()
        hidden = QRect(geo.x(), hidden_y, geo.width(), geo.height())

        if self._slide_is_blocked(hidden):
            self.start_fade(show)
            return

        resting_pos = geo.topLeft()
        hidden_pos = hidden.topLeft()
        if show:
            bar.move(hidden_pos)

        self._animation = QPropertyAnimation(bar, b"pos", bar)
        self._animation.setDuration(bar.animation.get("duration", 300))
        self._animation.setStartValue(hidden_pos if show else resting_pos)
        self._animation.setEndValue(resting_pos if show else hidden_pos)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.finished.connect(self._on_show_finished if show else self._on_hide_finished)
        self._animation.start()

        if show and not bar.isVisible():
            bar.show()

    def _on_show_finished(self):
        if self._target_geo:
            self.bar_widget.setGeometry(*self._target_geo)
        self._animation = None
        self._process_pending()

        # Check if mouse left during the animation
        autohide_mgr = self.bar_widget.autohide_manager
        if autohide_mgr is not None and autohide_mgr.is_enabled():
            cursor_pos = QCursor.pos()
            bar_geometry = self.bar_widget.geometry()

            # If not in the bar, and not in the safe zone (padding gap), start the timer
            if not bar_geometry.contains(cursor_pos) and not autohide_mgr.is_mouse_in_safe_zone(
                cursor_pos, bar_geometry
            ):
                autohide_mgr.restart_hide_timer()

    def _on_hide_finished(self):
        self.bar_widget.skip_animation = True
        self.bar_widget.hide()
        self.bar_widget.skip_animation = False
        self.bar_widget.setWindowOpacity(1.0)
        self._animation = None
        self._process_pending()

    def _process_pending(self):
        action = self._pending_action
        self._pending_action = None
        if action == "show" and not self.bar_widget.isVisible():
            self.show_bar()
        elif action == "hide" and self.bar_widget.isVisible():
            self.hide_bar()

    def cleanup(self):
        self._pending_action = None
        self._stop_animation()


class AutoHideZone(QFrame):
    """A transparent zone at the edge of the screen to detect when to show the bar"""

    def __init__(self, parent: Bar):
        super().__init__(parent)
        self._bar = parent
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setWindowOpacity(0.01)

    @override
    def enterEvent(self, event: QEnterEvent | None) -> None:
        # Show the parent bar when mouse enters detection zone
        if self._bar.autohide_manager is not None:
            self._bar.autohide_manager.show_bar()


class AutoHideManager(QObject):
    """Manages autohide functionality for bars"""

    def __init__(self, bar_widget: Bar, parent: QObject | None = None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._autohide_delay = 600
        self._detection_zone_height = 1
        self._detection_zone: AutoHideZone | None = None
        self._hide_timer: QTimer | None = None
        self._is_enabled = False

    def setup_autohide(self):
        """Initialize autohide functionality"""
        self._is_enabled = True
        # Set fixed 1px detection zone height
        self._detection_zone_height = 1

        # Create detection zone
        self._detection_zone = AutoHideZone(self.bar_widget)

        # Create hide timer
        self._hide_timer = QTimer(self.bar_widget)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_bar)

        # Install event filter on the bar
        self.bar_widget.installEventFilter(self)

        # Remove reserved screen space when autohide is enabled
        if hasattr(self.bar_widget, "app_bar_manager") and self.bar_widget.app_bar_manager:
            try:
                SystrayAppBarHelper.execute_without_systray_interference(
                    lambda: self.bar_widget.app_bar_manager.remove_appbar()
                )
            except Exception as e:
                logging.error("Failed to remove AppBar reservation: %s", e)

        # Set up detection zone after a short delay
        QTimer.singleShot(self._autohide_delay, self.setup_detection_zone)

    def setup_detection_zone(self):
        """Position and configure the autohide detection zone"""
        screen = self.bar_widget.screen()
        if not self._is_enabled or not self._detection_zone or screen is None:
            return

        screen_geometry = screen.geometry()
        alignment = self.bar_widget.alignment

        if alignment["position"] == "top":
            self._detection_zone.setGeometry(
                screen_geometry.x(), screen_geometry.y(), screen_geometry.width(), self._detection_zone_height
            )
        else:
            self._detection_zone.setGeometry(
                screen_geometry.x(),
                screen_geometry.y() + screen_geometry.height() - self._detection_zone_height,
                screen_geometry.width(),
                self._detection_zone_height,
            )

        self.restart_hide_timer()

    def restart_hide_timer(self) -> None:
        if self._hide_timer:
            self._hide_timer.start(self._autohide_delay)

    def show_bar(self):
        """Show the bar when mouse hovers over detection zone"""
        if not self.bar_widget.isVisible() and self._is_enabled:
            self.bar_widget.show()

    def _is_child_of_bar(self, widget: QObject | None) -> bool:
        """Walk parent chain to check if widget belongs to this bar."""
        p = widget.parent() if widget else None
        while p:
            if p is self.bar_widget:
                return True
            p = p.parent()
        return False

    def _should_stay_visible(self):
        """Check if bar should stay visible because a child popup/menu is open."""
        # Qt::Popup windows (QMenu, PopupWidget)
        if QApplication.activePopupWidget():
            return True
        # Qt::Tool windows that called activateWindow() (SystrayPopup)
        active = QApplication.activeWindow()
        if active and active is not self.bar_widget and self._is_child_of_bar(active):
            return True
        # Check all visible top-level widgets
        cursor_pos = QCursor.pos()
        for w in QApplication.topLevelWidgets():
            if w is self.bar_widget or w is self._detection_zone or not w.isVisible():
                continue
            # Child of bar (parent chain intact) - e.g. SystrayPopup after losing focus
            if self._is_child_of_bar(w):
                return True
            # Cursor is over it (parent chain severed) - e.g. ThumbnailHost
            if w.geometry().contains(cursor_pos):
                return True
        return False

    def hide_bar(self):
        """Hide the bar and show detection zone"""
        if self._is_enabled and self.bar_widget.isVisible():
            if self._should_stay_visible():
                self.restart_hide_timer()
                return
            self.bar_widget.hide()
            if self._detection_zone:
                self._detection_zone.show()
                self._detection_zone.raise_()

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        """Filter bar Enter/Leave events for hide timer"""
        if a0 is self.bar_widget and a1 is not None and self._is_enabled:
            if a1.type() == QEvent.Type.Enter:
                if self._hide_timer:
                    self._hide_timer.stop()
            elif a1.type() == QEvent.Type.Leave:
                cursor_pos = QCursor.pos()
                bar_geometry = self.bar_widget.geometry()

                if self.is_mouse_in_safe_zone(cursor_pos, bar_geometry):
                    return False

                self.restart_hide_timer()
        return False

    def is_mouse_in_safe_zone(self, cursor_pos: QPoint, bar_geometry: QRect) -> bool:
        """Check if mouse is in the gap between bar and detection zone"""
        screen = self.bar_widget.screen()
        if screen is None:
            return False
        screen_geometry = screen.geometry()
        alignment = self.bar_widget.alignment

        # Calculate mouse position relative to screen
        screen_x = cursor_pos.x() - screen_geometry.x()
        screen_y = cursor_pos.y() - screen_geometry.y()

        # Check if mouse is within screen bounds horizontally
        if screen_x < 0 or screen_x > screen_geometry.width():
            return False

        if alignment["position"] == "top":
            bar_top = bar_geometry.y() - screen_geometry.y()
            return 0 <= screen_y <= bar_top
        else:
            bar_bottom = (bar_geometry.y() + bar_geometry.height()) - screen_geometry.y()
            return bar_bottom <= screen_y <= screen_geometry.height()

    def is_enabled(self) -> bool:
        """Check if autohide is enabled"""
        return self._is_enabled

    def cleanup(self):
        """Clean up resources"""
        if self._hide_timer:
            self._hide_timer.stop()
        if self._detection_zone:
            self._detection_zone.hide()
            self._detection_zone.deleteLater()
        self._is_enabled = False

        # Restore reserved screen space when autohide is disabled and only if windows_app_bar was enabled
        if self.bar_widget.window_flags["windows_app_bar"]:
            try:
                SystrayAppBarHelper.execute_without_systray_interference(lambda: self.bar_widget.update_app_bar())
            except Exception as e:
                logging.error("Failed to restore AppBar reservation: %s", e)


class SystrayAppBarHelper:
    """Helper class to manage systray window state during AppBar operations"""

    @staticmethod
    def execute_without_systray_interference(callback: Callable[[], object]) -> None:
        """
        Execute a callback with systray timer temporarily killed.
        This prevents systray from continuously reasserting HWND_TOPMOST every 100ms,
        which interferes with AppBar registration by triggering work area recalculations.
        """
        systray_hwnd = SystrayAppBarHelper._get_systray_hwnd()
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

        try:
            if systray_hwnd:
                # Kill the systray timer (ID 1) to prevent HWND_TOPMOST interference
                KillTimer(systray_hwnd, 1)
                # Demote systray to non-topmost
                SetWindowPos(systray_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)

            callback()

        finally:
            if systray_hwnd:
                # Restore systray to topmost
                SetWindowPos(systray_hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                # Restart the timer (ID 1, 100ms interval)
                SetTimer(systray_hwnd, 1, 100, None)

    @staticmethod
    def _get_systray_hwnd() -> int | None:
        """Get the systray monitor window hwnd if active"""
        try:
            from core.widgets.yasb.systray import SystrayWidget

            return SystrayWidget.systray_monitor_hwnd()
        except Exception:
            pass
        return None


class AppBarManager(QAbstractNativeEventFilter):
    """Central handler for AppBar-related native Windows messages."""

    _instance: AppBarManager | None = None
    _installed = False
    _bars: dict[int, Bar]
    _bar_intended_state: dict[int, bool]
    _swp_flags: int
    _ready: bool
    _reregister_pending: bool

    # Default window classes to exclude from fullscreen detection
    EXCLUDED_WINDOW_CLASSES = {
        "Progman",
        "WorkerW",
        "XamlWindow",
        "Shell_TrayWnd",
        "XamlExplorerHostIslandWindow",
        "CEF-OSC-WIDGET",
        "CEFCLIENT",
    }

    # Suffixes for version-dependent window classes (e.g. Qt653QWindowIcon)
    EXCLUDED_WINDOW_CLASS_SUFFIXES = ("QWindowIcon",)

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._bars = {}
            instance._bar_intended_state = {}  # Track intended visibility (True=visible, False=hidden)
            instance._swp_flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            instance._ready = False  # Enabled after first bar registers
            instance._reregister_pending = False  # Coalesces multiple WM_TASKBARCREATED into one
            cls._instance = instance
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            super().__init__()
            self._initialized = True

    def _ensure_installed(self):
        """Install the native event filter on first use"""
        if not AppBarManager._installed:
            app = QApplication.instance()
            if app:
                app.installNativeEventFilter(self)
                AppBarManager._installed = True

    def register_bar(self, hwnd: int, bar_widget: Bar):
        """Register a bar to receive fullscreen notifications"""
        self._ensure_installed()
        self._bars[hwnd] = bar_widget
        self._bar_intended_state[hwnd] = True  # Initially visible
        self._ready = True

    def unregister_bar(self, hwnd: int):
        """Unregister a bar from receiving fullscreen notifications"""
        self._bars.pop(hwnd, None)
        self._bar_intended_state.pop(hwnd, None)

    def suppress(self):
        """Temporarily suppress WM_TASKBARCREATED handling.
        Used when our own code broadcasts TaskbarCreated (e.g. systray init)."""
        self._ready = False

    def unsuppress(self):
        """Re-enable WM_TASKBARCREATED handling after suppress()."""
        self._ready = True

    @override
    def nativeEventFilter(self, eventType: Any, message: sip.voidptr | None) -> tuple[bool, sip.voidptr | None]:
        """Filter native Windows messages for AppBar fullscreen notifications and Explorer restarts"""
        try:
            if eventType == b"windows_generic_MSG" and message is not None:
                msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents

                # Handle TaskbarCreated message (Explorer restart)
                if msg.message == WM_TASKBARCREATED:
                    # Only handle if fully initialized and not already scheduled.
                    # WM_TASKBARCREATED is broadcast to all top-level windows, so we
                    # coalesce multiple messages into a single deferred re-registration.
                    if self._ready and not self._reregister_pending and self._bars:
                        self._reregister_pending = True
                        QTimer.singleShot(0, self._deferred_reregister)
                    return False, 0  # pyright: ignore[reportReturnType]

                if msg.message == APPBAR_CALLBACK_MESSAGE:
                    hwnd = msg.hwnd
                    notification_code = msg.wParam

                    if hwnd in self._bars and notification_code == AppBarNotify.FullScreenApp:
                        is_fullscreen_opening = bool(msg.lParam)
                        self._handle_fullscreen(hwnd, is_fullscreen_opening)
        except Exception:
            pass

        return False, 0  # pyright: ignore[reportReturnType]

    def _deferred_reregister(self):
        """Deferred handler that runs once per event loop iteration,
        coalescing all WM_TASKBARCREATED messages from the same batch."""
        self._reregister_pending = False
        if not self._ready or not self._bars:
            return

        # Collect bars that actually need re-registration
        bars_to_reregister: list[tuple[Bar, bool]] = []
        needs_systray_workaround = False
        for bw in self._bars.values():
            flags = getattr(bw, "window_flags", {})
            app_bar = flags.get("windows_app_bar", False)
            fullscreen = getattr(bw, "_hide_on_fullscreen", False)
            if not app_bar and not fullscreen:
                continue
            if bw.autohide_manager and bw.autohide_manager.is_enabled():
                continue
            bars_to_reregister.append((bw, app_bar))
            if app_bar:
                needs_systray_workaround = True

        if not bars_to_reregister:
            return

        count = len(bars_to_reregister)
        logging.info("AppBarManager need to re-register %d %s", count, "bar" if count == 1 else "bars")

        def reregister():
            for bw, app_bar in bars_to_reregister:
                try:
                    bw.app_bar_manager.remove_appbar()
                    bw.update_app_bar()
                    reason = "space reservation + fullscreen" if app_bar else "fullscreen detection"
                    logging.info("Re-registered AppBar for %s (%s)", getattr(bw, "bar_id", "?"), reason)
                except Exception as e:
                    logging.error("Failed to re-register bar: %s", e)

        if needs_systray_workaround:
            SystrayAppBarHelper.execute_without_systray_interference(reregister)
        else:
            reregister()

    def _is_foreground_excluded(self) -> bool:
        """Check if the foreground window should be excluded from fullscreen detection."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            # Exclude our own process windows , overlays, modal dialogs and etc.
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == os.getpid():
                return True
            window_class = win32gui.GetClassName(hwnd) or ""
            if window_class in self.EXCLUDED_WINDOW_CLASSES or window_class.endswith(
                self.EXCLUDED_WINDOW_CLASS_SUFFIXES
            ):
                return True
        except Exception:
            pass
        return False

    def _handle_fullscreen(self, hwnd: int, is_fullscreen_opening: bool):
        """Handle ABN_FULLSCREENAPP notification for a bar."""
        bar_widget = self._bars.get(hwnd)
        if not bar_widget:
            return

        # Check if the fullscreen app's window should be excluded
        if is_fullscreen_opening:
            if self._is_foreground_excluded():
                return

        intended_visible = self._bar_intended_state.get(hwnd, True)
        should_hide_bar = getattr(bar_widget, "_hide_on_fullscreen", False)

        # We only need to process if hide_on_fullscreen is enabled
        if not should_hide_bar:
            return

        if is_fullscreen_opening:
            if intended_visible:
                SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, self._swp_flags)
                self._bar_intended_state[hwnd] = False
        else:
            if not intended_visible:
                SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, self._swp_flags)
                self._bar_intended_state[hwnd] = True


class MaximizedWindowWatcher(QObject):
    """Watches for any maximized window on the bar's monitor and toggles autohide accordingly."""

    def __init__(self, bar_widget: Bar, parent: QObject | None = None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._is_autohide_active = False
        self._had_autohide_before = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._check_maximized_windows)
        self._poll_timer.start()

    def _check_maximized_windows(self):
        """Check if any top-level window is maximized on the bar's monitor."""
        try:
            from core.utils.win32.utils import get_monitor_hwnd, is_window_maximized

            bar_monitor = self.bar_widget.monitor_hwnd
            if not bar_monitor:
                return

            has_maximized = False

            def enum_callback(hwnd: int, _: object) -> bool:
                nonlocal has_maximized
                if has_maximized:
                    return False
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    if not win32gui.GetWindowText(hwnd):
                        return True
                    cls_name = win32gui.GetClassName(hwnd) or ""
                    if cls_name in AppBarManager.EXCLUDED_WINDOW_CLASSES:
                        return True
                    if cls_name.endswith(AppBarManager.EXCLUDED_WINDOW_CLASS_SUFFIXES):
                        return True
                    window_monitor = get_monitor_hwnd(hwnd)
                    if window_monitor != bar_monitor:
                        return True
                    if is_window_maximized(hwnd):
                        has_maximized = True
                        return False
                except Exception:
                    pass
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.POINTER(ctypes.c_long))
            callback = WNDENUMPROC(enum_callback)
            user32.EnumWindows(callback, 0)

            if has_maximized and not self._is_autohide_active:
                self._enable_autohide()
            elif not has_maximized and self._is_autohide_active:
                self._disable_autohide()

        except Exception:
            logging.exception("Failed to check maximized windows")

    def _enable_autohide(self):
        """Enable autohide because a maximized window was detected."""
        self._is_autohide_active = True
        # Remember if autohide was already active before we touched it
        manager = self.bar_widget.autohide_manager
        self._had_autohide_before = manager is not None and manager.is_enabled()
        if self._had_autohide_before:
            return
        if manager is None:
            manager = AutoHideManager(self.bar_widget, self.bar_widget)
            self.bar_widget.autohide_manager = manager
        if not manager.is_enabled():
            manager.setup_autohide()

    def _disable_autohide(self):
        """Disable autohide because no maximized windows remain."""
        self._is_autohide_active = False
        # If user already had autohide enabled before, don't disable it
        if self._had_autohide_before:
            self._had_autohide_before = False
            return
        if self.bar_widget.autohide_manager:
            self.bar_widget.autohide_manager.cleanup()
            self.bar_widget.autohide_manager = None
        # Ensure bar is visible
        if not self.bar_widget.isVisible():
            self.bar_widget.show()

    def cleanup(self):
        """Clean up resources."""
        self._poll_timer.stop()
        if self._is_autohide_active:
            self._disable_autohide()


class OsThemeManager(QObject):
    """Manages OS theme detection and applies theme classes to widgets"""

    def __init__(self, target_widget: QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self.target_widget = target_widget
        self._is_dark_theme: bool | None = None

    def detect_os_theme(self) -> bool:
        """Detect if OS is using dark theme"""
        try:
            with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as registry:
                with winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return value == 0
        except Exception as e:
            logging.error("Failed to determine Windows theme: %s", e)
            return False

    def update_theme_class(self):
        """Update the theme class on the target widget"""
        if not self.target_widget:
            return

        is_dark_theme = self.detect_os_theme()
        if is_dark_theme != self._is_dark_theme:
            class_property = self.target_widget.property("class")
            if is_dark_theme:
                class_property += " dark"
            else:
                class_property = class_property.replace(" dark", "")
            self.target_widget.setProperty("class", class_property)
            self._update_styles(self.target_widget)
            self._is_dark_theme = is_dark_theme
            GlobalState.set_dark(is_dark_theme)

    def _update_styles(self, widget: QWidget) -> None:
        """Update styles for widget and its children by unpolishing and re-polishing"""
        refresh_widget_style(widget)
        for child in widget.findChildren(QWidget):
            refresh_widget_style(child)


def _add_action(menu: QMenu, text: str) -> QAction:
    action = QAction(text, menu)
    menu.addAction(action)
    return action


class BarContextMenu:
    """A class to handle the context menu for a bar."""

    def __init__(
        self,
        parent: Bar,
        bar_name: str,
        widgets: dict[str, list[BaseWidget]],
        widget_config_map: dict[str, Any],
        autohide_bar: bool,
    ):
        self.parent = parent
        self._bar_name = bar_name
        self._widgets = widgets
        self._widget_config_map = widget_config_map
        self._autohide_bar = autohide_bar

    def show(self, position: QPoint):
        self._menu = QMenu(self.parent)
        self._menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        apply_qmenu_style(self._menu)
        self._menu.setProperty("class", "context-menu dark" if GlobalState.is_dark() else "context-menu")
        self._menu.aboutToHide.connect(self._on_menu_about_to_hide)

        # Bar info
        bar_info = _add_action(self._menu, f"Bar: {self._bar_name}")
        bar_info.setEnabled(False)

        # Widgets menu
        widgets_menu = QMenu("Active Widgets", self._menu)
        self._menu.addMenu(widgets_menu)
        apply_qmenu_style(widgets_menu)
        widgets_menu.setProperty(
            "class", "context-menu submenu dark" if GlobalState.is_dark() else "context-menu submenu"
        )
        self._populate_widgets_menu(widgets_menu)

        self._menu.addSeparator()

        # System actions
        task_manager = _add_action(self._menu, "Task Manager")
        task_manager.triggered.connect(self._open_task_manager)

        # Screenshot action
        screenshot_action = _add_action(self._menu, "Take Screenshot")
        screenshot_action.triggered.connect(self._take_screenshot)

        self._menu.addSeparator()

        # Bar actions - Check current autohide state dynamically
        current_autohide_enabled = (
            self.parent.autohide_manager is not None and self.parent.autohide_manager.is_enabled()
        )

        if not current_autohide_enabled:
            enable_autohide = _add_action(self._menu, "Enable Auto Hide")
            enable_autohide.triggered.connect(self._enable_autohide)
        else:
            disable_autohide = _add_action(self._menu, "Disable Auto Hide")
            disable_autohide.triggered.connect(self._disable_autohide)

        reload_action = _add_action(self._menu, "Reload Bar")
        reload_action.triggered.connect(partial(reload_application, "Reloading Bar from context menu..."))

        exit_action = _add_action(self._menu, "Exit")
        exit_action.triggered.connect(partial(exit_application, "Exiting Application from context menu..."))

        self._menu.popup(self.parent.mapToGlobal(position))
        self._menu.activateWindow()

    def _on_menu_about_to_hide(self):
        """Called when the context menu is about to hide - restart autohide timer if enabled"""
        try:
            # Check if autohide is enabled and start the hide timer
            manager = self.parent.autohide_manager
            if manager is not None and manager.is_enabled():
                # Start the autohide timer with the configured delay
                manager.restart_hide_timer()

        except Exception as e:
            logging.error("Failed to restart autohide timer: %s", e)

    def _populate_widgets_menu(self, widgets_menu: QMenu) -> None:
        if not any(self._widgets.get(layout) for layout in ["left", "center", "right"]):
            no_widgets = _add_action(widgets_menu, "No active widgets")
            no_widgets.setEnabled(False)
            return

        for i, layout_type in enumerate(["left", "center", "right"]):
            # Layout header
            layout_header = _add_action(widgets_menu, f"{layout_type.title()} Layout")
            layout_header.setEnabled(False)

            # Add widgets or empty message
            if self._widgets.get(layout_type):
                for widget in self._widgets[layout_type]:
                    self._add_widget_checkbox(widgets_menu, widget)
            else:
                no_widgets = _add_action(widgets_menu, "  No active widgets")
                no_widgets.setEnabled(False)
            # Add separator after each layout except the last one
            if i < 2:
                widgets_menu.addSeparator()

    def _add_widget_checkbox(self, menu: QMenu, widget: BaseWidget) -> None:
        checkbox = QCheckBox(self._get_widget_display_name(widget))
        checkbox.setChecked(widget.isVisible())
        checkbox.setProperty("class", "checkbox")
        checkbox.stateChanged.connect(partial(self._toggle_widget, widget))

        # Container with hover effects
        container = QWidget()
        container.setProperty("class", "menu-checkbox")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(checkbox)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Event filter for hover and click
        def event_filter(a0: QObject | None, a1: QEvent | None) -> bool:
            if (
                a1 is not None
                and a1.type() == QEvent.Type.MouseButtonPress
                and cast(QMouseEvent, a1).button() == Qt.MouseButton.LeftButton
            ):
                checkbox.toggle()
                return True
            return False

        container.installEventFilter(container)
        container.eventFilter = event_filter

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)

    def _toggle_widget(self, widget: BaseWidget, enabled: int) -> None:
        try:
            # Store the original show/hide methods if not already stored
            if not hasattr(widget, "_original_show"):
                setattr(widget, "_original_show", widget.show)
                setattr(widget, "_original_hide", widget.hide)
                setattr(widget, "_original_set_visible", widget.setVisible)
            original_show: Callable[[], None] = getattr(widget, "_original_show")
            original_hide: Callable[[], None] = getattr(widget, "_original_hide")
            original_set_visible: Callable[[bool], None] = getattr(widget, "_original_set_visible")

            # Override show and setVisible to respect manual override
            def controlled_show() -> None:
                if not getattr(widget, "_manual_visibility_override", False):
                    original_show()

            def controlled_hide() -> None:
                original_hide()

            def controlled_set_visible(visible: bool) -> None:
                if visible and getattr(widget, "_manual_visibility_override", False):
                    return
                original_set_visible(visible)

            widget.show = controlled_show
            widget.hide = controlled_hide
            widget.setVisible = controlled_set_visible

            # Add a flag to track manual visibility override
            setattr(widget, "_manual_visibility_override", not enabled)
            widget.setVisible(bool(enabled))

        except Exception as e:
            logging.error("Failed to toggle widget %s: %s", self._get_widget_display_name(widget), e)

    def _get_widget_display_name(self, widget: BaseWidget) -> str:
        for layout_type, widget_list in self._widgets.items():
            try:
                index = widget_list.index(widget)
                if (
                    self._widget_config_map
                    and layout_type in self._widget_config_map
                    and index < len(self._widget_config_map[layout_type])
                ):
                    return self._widget_config_map[layout_type][index].replace("_", " ").title()
            except ValueError:
                continue
        return str(widget)

    def _open_task_manager(self):
        try:
            shell_open("taskmgr")
        except Exception as e:
            logging.error("Failed to open Task Manager: %s", e)

    def _take_screenshot(self):
        """Take a screenshot of the bar with proper padding"""
        try:
            # Get bar and screen geometries
            bar_geometry = self.parent.geometry()
            screen = self.parent.screen()
            if screen is None:
                return
            screen_geometry = screen.geometry()

            # Get bar padding information
            bar_padding = self.parent.padding
            bar_alignment = self.parent.alignment

            # Calculate screenshot area with padding
            padding_top = bar_padding.get("top", 0)
            padding_area = 10

            if bar_alignment["position"] == "top":
                # For top bar: start from screen top (y=0) and extend to bar bottom + padding
                screenshot_x = screen_geometry.x()
                screenshot_y = screen_geometry.y()
                screenshot_width = screen_geometry.width()
                screenshot_height = (bar_geometry.y() - screen_geometry.y()) + bar_geometry.height() + padding_area
            else:
                # For bottom bar: start from bar top - padding and extend to screen bottom
                screenshot_x = screen_geometry.x()
                screenshot_y = bar_geometry.y() - padding_top
                screenshot_width = screen_geometry.width()
                screenshot_height = (screen_geometry.y() + screen_geometry.height()) - screenshot_y

            # Take screenshot of the calculated area
            screenshot = screen.grabWindow(
                # 0 is the desktop window
                0,  # pyright: ignore[reportArgumentType]
                screenshot_x,
                screenshot_y,
                screenshot_width,
                screenshot_height,
            )

            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "YASB_Screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"yasb_bar_{self._bar_name}_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)

            # Save the screenshot
            if not screenshot.save(filepath, "PNG"):
                logging.error("Failed to save screenshot")

            self._screenshot_flash()

        except Exception as e:
            logging.error("Failed to take screenshot: %s", e)

    def _screenshot_flash(self):
        """Create a flashing effect on the bar when taking screenshot"""
        try:
            opacity_effect = QGraphicsOpacityEffect()
            self.parent.setGraphicsEffect(opacity_effect)

            self.flash_animation = QPropertyAnimation(opacity_effect, b"opacity")
            self.flash_animation.setDuration(200)
            self.flash_animation.setStartValue(0.2)
            self.flash_animation.setKeyValueAt(0.25, 1.0)
            self.flash_animation.setKeyValueAt(0.5, 0.2)
            self.flash_animation.setEndValue(1.0)

            self.flash_animation.finished.connect(lambda: self.parent.setGraphicsEffect(None))
            self.flash_animation.start()

        except Exception as e:
            logging.error("Failed to create flash effect: %s", e)

    def _enable_autohide(self):
        """Enable autohide functionality for the bar"""
        try:
            manager = self.parent.autohide_manager
            if manager is None:
                # Create autohide manager if it doesn't exist
                manager = AutoHideManager(self.parent, self.parent)
                self.parent.autohide_manager = manager

            # Setup autohide if not already enabled
            if not manager.is_enabled():
                manager.setup_autohide()

        except Exception as e:
            logging.error("Failed to enable autohide: %s", e)

    def _disable_autohide(self):
        """Disable autohide functionality"""
        try:
            if self.parent.autohide_manager:
                self.parent.autohide_manager.cleanup()
                self.parent.autohide_manager = None

            # Ensure bar is visible after disabling autohide
            if not self.parent.isVisible():
                self.parent.show()

        except Exception as e:
            logging.error("Failed to disable autohide: %s", e)


class AutoWidthManager(QObject):
    """Manages auto-width calculation and resize/reposition for bars with width='auto'."""

    def __init__(self, bar_widget: Bar, parent: QObject | None = None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._current_auto_width = 0

    def update(self) -> int:
        """Calculate current auto width from the layout size hint. Returns the new width."""
        layout = self.bar_widget.bar_frame.layout()
        if layout:
            layout.activate()

        requested = max(self.bar_widget.bar_frame.sizeHint().width(), 0)
        available = (
            self.bar_widget.target_screen.geometry().width()
            - self.bar_widget.padding["left"]
            - self.bar_widget.padding["right"]
        )
        new_width = min(requested, available)
        self._current_auto_width = new_width
        return new_width

    @property
    def current_auto_width(self) -> int:
        return self._current_auto_width

    def apply(self, new_width: int) -> None:
        """Resize and reposition the bar using the supplied auto width."""
        if new_width < 0:
            return

        bar_height = self.bar_widget.dimensions["height"]
        screen_geometry = self.bar_widget.target_screen.geometry()
        bar_x, bar_y = self.bar_widget.bar_pos(
            new_width,
            bar_height,
            screen_geometry.width(),
            screen_geometry.height(),
        )

        self.bar_widget.bar_frame.setGeometry(0, 0, new_width, bar_height)
        self.bar_widget.setGeometry(bar_x, bar_y, new_width, bar_height)

    def sync(self) -> None:
        """Ensure auto width matches the layout after a DPI/geometry change."""
        previous_width = self._current_auto_width
        new_width = self.update()

        if new_width != previous_width or self.bar_widget.width() != new_width:
            self.apply(new_width)


class BarCliManager(QObject):
    """Handles CLI show/hide/toggle commands for a bar, including app bar reservation management."""

    def __init__(self, bar_widget: Bar, parent: QObject | None = None):
        super().__init__(parent)
        self.bar_widget = bar_widget

    def handle(self, action: str, screen_name: str) -> None:
        current_screen_matches = not screen_name or self.bar_widget.target_screen.name() == screen_name
        if not current_screen_matches:
            return

        autohide_active = self.bar_widget.autohide_manager and self.bar_widget.autohide_manager.is_enabled()
        manages_app_bar = self.bar_widget.window_flags["windows_app_bar"] and not autohide_active

        if action == "show":
            self.bar_widget.show()
            if manages_app_bar:
                SystrayAppBarHelper.execute_without_systray_interference(self.bar_widget.update_app_bar)
        elif action == "hide":
            if manages_app_bar:
                SystrayAppBarHelper.execute_without_systray_interference(self.bar_widget.try_remove_app_bar)
            self.bar_widget.hide()
        elif action == "toggle":
            if self.bar_widget.isVisible():
                if manages_app_bar:
                    SystrayAppBarHelper.execute_without_systray_interference(self.bar_widget.try_remove_app_bar)
                self.bar_widget.hide()
            else:
                self.bar_widget.show()
                if manages_app_bar:
                    SystrayAppBarHelper.execute_without_systray_interference(self.bar_widget.update_app_bar)

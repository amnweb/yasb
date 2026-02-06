import ctypes
import logging
import os
import subprocess
import winreg
from datetime import datetime
from functools import partial

import win32gui
from PyQt6.QtCore import (
    QAbstractNativeEventFilter,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PyQt6.QtGui import QCursor
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
from win32con import HWND_NOTOPMOST, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE

from core.utils.controller import exit_application, reload_application
from core.utils.utilities import refresh_widget_style
from core.utils.win32.app_bar import APPBAR_CALLBACK_MESSAGE, AppBarNotify
from core.utils.win32.bindings import SetWindowPos
from core.utils.win32.bindings.user32 import KillTimer, RegisterWindowMessage, SetTimer, user32
from core.utils.win32.structs import MSG
from core.utils.win32.utilities import apply_qmenu_style

# Register TaskbarCreated message to detect Explorer restarts
WM_TASKBARCREATED = RegisterWindowMessage("TaskbarCreated")


class BarAnimationManager(QObject):
    """Handles bar show/hide animations."""

    def __init__(self, bar_widget: QWidget, parent=None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._animation = None
        self._target_geo = None
        self._full_height = None
        self._pending_action = None  # 'show' or 'hide' queued while animating

    def show_bar(self):
        if not self.bar_widget._animation.get("enabled"):
            self.bar_widget._skip_animation = True
            self.bar_widget.show()
            self.bar_widget._skip_animation = False
            return

        # If animation running, queue this action
        if self._animation and self._animation.state() == QVariantAnimation.State.Running:
            self._pending_action = "show"
            return

        self._pending_action = None
        if self.bar_widget._animation.get("type") == "fade":
            self._start_fade(True)
        else:
            self._start_slide(True)

    def hide_bar(self):
        if not self.bar_widget._animation.get("enabled"):
            self.bar_widget._skip_animation = True
            self.bar_widget.hide()
            self.bar_widget._skip_animation = False
            return

        # If animation running, queue this action
        if self._animation and self._animation.state() == QVariantAnimation.State.Running:
            self._pending_action = "hide"
            return

        self._pending_action = None
        if self.bar_widget._animation.get("type") == "fade":
            self._start_fade(False)
        else:
            self._start_slide(False)

    def _stop_animation(self):
        if self._animation and self._animation.state() == QVariantAnimation.State.Running:
            self._animation.stop()
        self._animation = None

    def _start_fade(self, show: bool):
        self._stop_animation()
        duration = self.bar_widget._animation.get("duration", 300)
        self._animation = QPropertyAnimation(self.bar_widget, b"windowOpacity")
        self._animation.setDuration(duration)
        self._animation.setStartValue(0.0 if show else 1.0)
        self._animation.setEndValue(1.0 if show else 0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.finished.connect(self._on_show_finished if show else self._on_fade_hide_finished)

        if show:
            self.bar_widget.setWindowOpacity(0.0)
            self.bar_widget.show()
        self._animation.start()

    def _start_slide(self, show: bool):
        self._stop_animation()
        bar = self.bar_widget

        # Recalculate position using bar's existing method
        bar.position_bar()
        geo = bar.geometry()
        self._target_geo = (geo.x(), geo.y(), geo.width(), geo.height())
        self._full_height = geo.height()

        if show:
            bar._bar_frame.resize(geo.width(), geo.height())
            self._update_slide(0.0)
            bar.show()

        self._animation = QVariantAnimation(bar)
        self._animation.setDuration(bar._animation.get("duration", 300))
        self._animation.setStartValue(0.0 if show else 1.0)
        self._animation.setEndValue(1.0 if show else 0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.valueChanged.connect(self._update_slide)
        self._animation.finished.connect(self._on_show_finished if show else self._on_slide_hide_finished)
        self._animation.start()

    def _update_slide(self, value: float):
        h = int(self._full_height * value)
        x, y, w, full_h = self._target_geo
        if self.bar_widget._alignment["position"] == "top":
            new_geo = (x, y, w, max(1, h))
            frame_y = h - full_h
            self.bar_widget.setGeometry(*new_geo)
            self.bar_widget._bar_frame.move(0, frame_y)
        else:
            win_y = y + full_h - h
            new_geo = (x, win_y, w, max(1, h))
            self.bar_widget.setGeometry(*new_geo)
            self.bar_widget._bar_frame.move(0, 0)

    def _on_show_finished(self):
        if self._target_geo:
            x, y, w, h = self._target_geo
            self.bar_widget.setGeometry(x, y, w, h)
        self.bar_widget._bar_frame.move(0, 0)
        self._animation = None
        self._process_pending()

    def _on_fade_hide_finished(self):
        self.bar_widget._skip_animation = True
        self.bar_widget.hide()
        self.bar_widget._skip_animation = False
        self.bar_widget.setWindowOpacity(1.0)
        self._animation = None
        self._process_pending()

    def _on_slide_hide_finished(self):
        self.bar_widget._skip_animation = True
        self.bar_widget.hide()
        self.bar_widget._skip_animation = False
        self._animation = None
        self._process_pending()

    def _process_pending(self):
        if self._pending_action == "show":
            self._pending_action = None
            self.show_bar()
        elif self._pending_action == "hide":
            self._pending_action = None
            self.hide_bar()

    def cleanup(self):
        self._pending_action = None
        self._stop_animation()


class AutoHideZone(QFrame):
    """A transparent zone at the edge of the screen to detect when to show the bar"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setWindowOpacity(0.01)

    def enterEvent(self, event):
        # Show the parent bar when mouse enters detection zone
        if self.parent() and hasattr(self.parent(), "_autohide_manager"):
            self.parent()._autohide_manager.show_bar()


class AutoHideManager(QObject):
    """Manages autohide functionality for bars"""

    def __init__(self, bar_widget, parent=None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._autohide_delay = 600
        self._detection_zone_height = None
        self._detection_zone = None
        self._hide_timer = None
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

        # Register this bar_id as autohide owner globally
        try:
            from core import global_state

            if hasattr(self.bar_widget, "bar_id"):
                global_state.set_autohide_owner_for_bar(self.bar_widget.bar_id, self.bar_widget)
        except Exception:
            pass

        # Remove reserved screen space when autohide is enabled
        if hasattr(self.bar_widget, "app_bar_manager") and self.bar_widget.app_bar_manager:
            try:
                SystrayAppBarHelper.execute_without_systray_interference(
                    lambda: self.bar_widget.app_bar_manager.remove_appbar()
                )
            except Exception as e:
                logging.error(f"Failed to remove AppBar reservation: {e}")

        # Set up detection zone after a short delay
        QTimer.singleShot(self._autohide_delay, self.setup_detection_zone)

    def setup_detection_zone(self):
        """Position and configure the autohide detection zone"""
        if not self._is_enabled or not self._detection_zone:
            return

        screen_geometry = self.bar_widget.screen().geometry()
        alignment = self.bar_widget._alignment

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

        self._hide_timer.start(self._autohide_delay)

    def show_bar(self):
        """Show the bar when mouse hovers over detection zone"""
        if not self.bar_widget.isVisible() and self._is_enabled:
            self.bar_widget.show()

    def hide_bar(self):
        """Hide the bar and show detection zone"""
        if self._is_enabled and self.bar_widget.isVisible():
            self.bar_widget.hide()
            if self._detection_zone:
                self._detection_zone.show()
                self._detection_zone.raise_()

    def eventFilter(self, watched, event):
        """Filter events to detect mouse movement"""
        if watched == self.bar_widget and self._is_enabled:
            if event.type() == QEvent.Type.Enter:
                if self._hide_timer:
                    self._hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                cursor_pos = QCursor.pos()
                bar_geometry = self.bar_widget.geometry()

                # Check if mouse is in the gap between bar and detection zone
                if self._is_mouse_in_safe_zone(cursor_pos, bar_geometry):
                    # Don't start hide timer if mouse is in the safe zone
                    return False

                # Only start timer if mouse is really outside the bar and safe zone
                if not bar_geometry.contains(cursor_pos) and self._hide_timer:
                    self._hide_timer.start(self._autohide_delay)
        return False

    def _is_mouse_in_safe_zone(self, cursor_pos, bar_geometry):
        """Check if mouse is in the gap between bar and detection zone"""
        screen_geometry = self.bar_widget.screen().geometry()
        alignment = self.bar_widget._alignment

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

    def is_enabled(self):
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
        if hasattr(self.bar_widget, "update_app_bar") and self.bar_widget._window_flags["windows_app_bar"]:
            try:
                SystrayAppBarHelper.execute_without_systray_interference(lambda: self.bar_widget.update_app_bar())
            except Exception as e:
                logging.error(f"Failed to restore AppBar reservation: {e}")

        # Unregister global autohide registration for this bar
        try:
            from core.global_state import unset_autohide_owner_for_bar

            if hasattr(self.bar_widget, "bar_id"):
                unset_autohide_owner_for_bar(self.bar_widget.bar_id)
        except Exception:
            pass


class SystrayAppBarHelper:
    """Helper class to manage systray window state during AppBar operations"""

    @staticmethod
    def execute_without_systray_interference(callback):
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
    def _get_systray_hwnd():
        """Get the systray monitor window hwnd if active"""
        try:
            from core.widgets.yasb.systray import SystrayWidget

            if SystrayWidget._systray_instance and hasattr(SystrayWidget._systray_instance, "hwnd"):
                hwnd = SystrayWidget._systray_instance.hwnd
                if hwnd and hwnd != 0:
                    return hwnd
        except Exception:
            pass
        return None


class AppBarManager(QAbstractNativeEventFilter):
    """Central handler for AppBar-related native Windows messages."""

    _instance = None
    _installed = False

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
            cls._instance = super().__new__(cls)
            cls._instance._bars = {}
            cls._instance._bar_intended_state = {}  # Track intended visibility (True=visible, False=hidden)
            cls._instance._swp_flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            cls._instance._ready = False  # Enabled after first bar registers
            cls._instance._reregister_pending = False  # Coalesces multiple WM_TASKBARCREATED into one
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

    def register_bar(self, hwnd: int, bar_widget):
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

    def nativeEventFilter(self, eventType, message):
        """Filter native Windows messages for AppBar fullscreen notifications and Explorer restarts"""
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents

                # Handle TaskbarCreated message (Explorer restart)
                if msg.message == WM_TASKBARCREATED:
                    # Only handle if fully initialized and not already scheduled.
                    # WM_TASKBARCREATED is broadcast to all top-level windows, so we
                    # coalesce multiple messages into a single deferred re-registration.
                    if self._ready and not self._reregister_pending and self._bars:
                        self._reregister_pending = True
                        QTimer.singleShot(0, self._deferred_reregister)
                    return False, 0

                if msg.message == APPBAR_CALLBACK_MESSAGE:
                    hwnd = msg.hwnd
                    notification_code = msg.wParam

                    if hwnd in self._bars and notification_code == AppBarNotify.FullScreenApp:
                        is_fullscreen_opening = bool(msg.lParam)
                        self._handle_fullscreen(hwnd, is_fullscreen_opening)
        except Exception:
            pass

        return False, 0

    def _deferred_reregister(self):
        """Deferred handler that runs once per event loop iteration,
        coalescing all WM_TASKBARCREATED messages from the same batch."""
        self._reregister_pending = False
        if not self._ready or not self._bars:
            return

        # Collect bars that actually need re-registration
        bars_to_reregister = []
        needs_systray_workaround = False
        for bw in self._bars.values():
            flags = getattr(bw, "_window_flags", {})
            app_bar = flags.get("windows_app_bar", False)
            fullscreen = getattr(bw, "_hide_on_fullscreen", False)
            if not app_bar and not fullscreen:
                continue
            if hasattr(bw, "_autohide_manager") and bw._autohide_manager and bw._autohide_manager.is_enabled():
                continue
            if not hasattr(bw, "update_app_bar"):
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
                    if hasattr(bw, "app_bar_manager") and bw.app_bar_manager:
                        bw.app_bar_manager.remove_appbar()
                    bw.update_app_bar()
                    reason = "space reservation + fullscreen" if app_bar else "fullscreen detection"
                    logging.info(f"Re-registered AppBar for {getattr(bw, 'bar_id', '?')} ({reason})")
                except Exception as e:
                    logging.error(f"Failed to re-register bar: {e}")

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
            window_class = win32gui.GetClassName(hwnd)
            if window_class in self.EXCLUDED_WINDOW_CLASSES or window_class.endswith(
                self.EXCLUDED_WINDOW_CLASS_SUFFIXES
            ):
                return True
        except Exception:
            pass
        return False

    def _handle_fullscreen(self, hwnd: int, is_fullscreen_opening: bool):
        """Handle fullscreen notification for a bar"""
        bar_widget = self._bars.get(hwnd)
        if not bar_widget:
            return

        intended_visible = self._bar_intended_state.get(hwnd, True)

        # Check if the fullscreen app's window should be excluded
        if is_fullscreen_opening:
            if self._is_foreground_excluded():
                return

        should_hide_bar = getattr(bar_widget, "_hide_on_fullscreen", False)
        has_autohide = (
            bar_widget._autohide_manager and bar_widget._autohide_manager.is_enabled()
            if hasattr(bar_widget, "_autohide_manager")
            else False
        )

        # Only process if hide_on_fullscreen is enabled
        if not should_hide_bar:
            return

        if is_fullscreen_opening:
            # Only hide if we intend the bar to be visible
            if intended_visible:
                bar_widget._skip_animation = True
                bar_widget.hide()
                bar_widget._skip_animation = False
                self._bar_intended_state[hwnd] = False
                # Also hide detection zone if autohide is active
                if has_autohide and bar_widget._autohide_manager._detection_zone:
                    bar_widget._autohide_manager._detection_zone.hide()
        else:
            # Only show if we intend the bar to be hidden
            if not intended_visible:
                self._bar_intended_state[hwnd] = True
                bar_widget._skip_animation = True
                # Show bar if autohide is not active
                if not has_autohide:
                    bar_widget.show()
                # Re-show detection zone if autohide is active
                if has_autohide and bar_widget._autohide_manager._detection_zone:
                    bar_widget._autohide_manager._detection_zone.show()
                bar_widget._skip_animation = False


class MaximizedWindowWatcher(QObject):
    """Watches for any maximized window on the bar's monitor and toggles autohide accordingly."""

    def __init__(self, bar_widget, parent=None):
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
            from core.utils.win32.utilities import get_monitor_hwnd, is_window_maximized

            bar_monitor = getattr(self.bar_widget, "monitor_hwnd", None)
            if not bar_monitor:
                return

            has_maximized = False

            def enum_callback(hwnd, _):
                nonlocal has_maximized
                if has_maximized:
                    return False
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    if not win32gui.GetWindowText(hwnd):
                        return True
                    cls_name = win32gui.GetClassName(hwnd)
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
        self._had_autohide_before = (
            hasattr(self.bar_widget, "_autohide_manager")
            and self.bar_widget._autohide_manager is not None
            and self.bar_widget._autohide_manager.is_enabled()
        )
        if self._had_autohide_before:
            return
        if not self.bar_widget._autohide_manager:
            self.bar_widget._autohide_manager = AutoHideManager(self.bar_widget, self.bar_widget)
        if not self.bar_widget._autohide_manager.is_enabled():
            self.bar_widget._autohide_manager.setup_autohide()

    def _disable_autohide(self):
        """Disable autohide because no maximized windows remain."""
        self._is_autohide_active = False
        # If user already had autohide enabled before, don't disable it
        if self._had_autohide_before:
            self._had_autohide_before = False
            return
        if hasattr(self.bar_widget, "_autohide_manager") and self.bar_widget._autohide_manager:
            self.bar_widget._autohide_manager.cleanup()
            self.bar_widget._autohide_manager = None
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

    def __init__(self, target_widget: QWidget, parent=None):
        super().__init__(parent)
        self.target_widget = target_widget
        self._is_dark_theme = None

    def detect_os_theme(self) -> bool:
        """Detect if OS is using dark theme"""
        try:
            with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as registry:
                with winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return value == 0
        except Exception as e:
            logging.error(f"Failed to determine Windows theme: {e}")
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

    def _update_styles(self, widget):
        """Update styles for widget and its children by unpolishing and re-polishing"""
        refresh_widget_style(widget)
        for child in widget.findChildren(QWidget):
            refresh_widget_style(child)


class BarContextMenu:
    """A class to handle the context menu for a bar."""

    def __init__(self, parent, bar_name, widgets, widget_config_map, autohide_bar):
        self.parent = parent
        self._bar_name = bar_name
        self._widgets = widgets
        self._widget_config_map = widget_config_map
        self._autohide_bar = autohide_bar

    def show(self, position):
        self._menu = QMenu(self.parent)
        self._menu.setProperty("class", "context-menu")
        self._menu.aboutToHide.connect(self._on_menu_about_to_hide)
        apply_qmenu_style(self._menu)

        # Bar info
        bar_info = self._menu.addAction(f"Bar: {self._bar_name}")
        bar_info.setEnabled(False)

        # Widgets menu
        widgets_menu = self._menu.addMenu("Active Widgets")
        widgets_menu.setProperty("class", "context-menu submenu")
        apply_qmenu_style(widgets_menu)
        self._populate_widgets_menu(widgets_menu)

        self._menu.addSeparator()

        # System actions
        task_manager = self._menu.addAction("Task Manager")
        task_manager.triggered.connect(self._open_task_manager)

        # Screenshot action
        screenshot_action = self._menu.addAction("Take Screenshot")
        screenshot_action.triggered.connect(self._take_screenshot)

        self._menu.addSeparator()

        # Bar actions - Check current autohide state dynamically
        current_autohide_enabled = (
            hasattr(self.parent, "_autohide_manager")
            and self.parent._autohide_manager
            and self.parent._autohide_manager.is_enabled()
        )

        if not current_autohide_enabled:
            enable_autohide = self._menu.addAction("Enable Auto Hide")
            enable_autohide.triggered.connect(self._enable_autohide)
        else:
            disable_autohide = self._menu.addAction("Disable Auto Hide")
            disable_autohide.triggered.connect(self._disable_autohide)

        reload_action = self._menu.addAction("Reload Bar")
        reload_action.triggered.connect(partial(reload_application, "Reloading Bar from context menu..."))

        exit_action = self._menu.addAction("Exit")
        exit_action.triggered.connect(partial(exit_application, "Exiting Application from context menu..."))

        self._menu.popup(self.parent.mapToGlobal(position))
        self._menu.activateWindow()

    def _on_menu_about_to_hide(self):
        """Called when the context menu is about to hide - restart autohide timer if enabled"""
        try:
            # Check if autohide is enabled and start the hide timer
            if (
                hasattr(self.parent, "_autohide_manager")
                and self.parent._autohide_manager
                and self.parent._autohide_manager.is_enabled()
            ):
                # Start the autohide timer with the configured delay
                if self.parent._autohide_manager._hide_timer:
                    self.parent._autohide_manager._hide_timer.start(self.parent._autohide_manager._autohide_delay)

        except Exception as e:
            logging.error(f"Failed to restart autohide timer: {e}")

    def _populate_widgets_menu(self, widgets_menu):
        if not any(self._widgets.get(layout) for layout in ["left", "center", "right"]):
            no_widgets = widgets_menu.addAction("No active widgets")
            no_widgets.setEnabled(False)
            return

        for i, layout_type in enumerate(["left", "center", "right"]):
            # Layout header
            layout_header = widgets_menu.addAction(f"{layout_type.title()} Layout")
            layout_header.setEnabled(False)

            # Add widgets or empty message
            if self._widgets.get(layout_type):
                for widget in self._widgets[layout_type]:
                    self._add_widget_checkbox(widgets_menu, widget)
            else:
                no_widgets = widgets_menu.addAction("  No active widgets")
                no_widgets.setEnabled(False)
            # Add separator after each layout except the last one
            if i < 2:
                widgets_menu.addSeparator()

    def _add_widget_checkbox(self, menu, widget):
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
        def event_filter(obj, event):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                checkbox.toggle()
                return True
            return False

        container.installEventFilter(container)
        container.eventFilter = event_filter

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)

    def _toggle_widget(self, widget, enabled):
        try:
            # Add a flag to track manual visibility override
            widget._manual_visibility_override = not enabled
            widget.setVisible(bool(enabled))

            # Store the original show/hide methods if not already stored
            if not hasattr(widget, "_original_show"):
                widget._original_show = widget.show
                widget._original_hide = widget.hide

            # Override show method to respect manual override
            def controlled_show():
                if not getattr(widget, "_manual_visibility_override", False):
                    widget._original_show()

            def controlled_hide():
                widget._original_hide()

            widget.show = controlled_show
            widget.hide = controlled_hide

        except Exception as e:
            logging.error(f"Failed to toggle widget {self._get_widget_display_name(widget)}: {e}")

    def _get_widget_display_name(self, widget):
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
            subprocess.Popen("taskmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            logging.error(f"Failed to open Task Manager: {e}")

    def _take_screenshot(self):
        """Take a screenshot of the bar with proper padding"""
        try:
            # Get bar and screen geometries
            bar_geometry = self.parent.geometry()
            screen = self.parent.screen()
            screen_geometry = screen.geometry()

            # Get bar padding information
            bar_padding = getattr(self.parent, "_padding", {"top": 0, "bottom": 0, "left": 0, "right": 0})
            bar_alignment = getattr(self.parent, "_alignment", {"position": "top"})

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
                0,  # Desktop window
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
            logging.error(f"Failed to take screenshot: {e}")

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
            logging.error(f"Failed to create flash effect: {e}")

    def _enable_autohide(self):
        """Enable autohide functionality for the bar"""
        try:
            if not hasattr(self.parent, "_autohide_manager") or not self.parent._autohide_manager:
                # Create autohide manager if it doesn't exist
                self.parent._autohide_manager = AutoHideManager(self.parent, self.parent)

            # Setup autohide if not already enabled
            if not self.parent._autohide_manager.is_enabled():
                self.parent._autohide_manager.setup_autohide()

        except Exception as e:
            logging.error(f"Failed to enable autohide: {e}")

    def _disable_autohide(self):
        """Disable autohide functionality"""
        try:
            if hasattr(self.parent, "_autohide_manager") and self.parent._autohide_manager:
                self.parent._autohide_manager.cleanup()
                self.parent._autohide_manager = None

            # Ensure bar is visible after disabling autohide
            if not self.parent.isVisible():
                self.parent.show()

        except Exception as e:
            logging.error(f"Failed to disable autohide: {e}")

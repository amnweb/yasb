import ctypes
import logging
import os
import subprocess
import winreg
from ctypes import wintypes
from datetime import datetime
from functools import partial

import win32gui
from PyQt6.QtCore import QEvent, QObject, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QWidget,
    QWidgetAction,
)

from core.utils.controller import exit_application, reload_application
from core.utils.win32.utilities import dwmapi, get_monitor_hwnd, get_window_rect, qmenu_rounded_corners

DWMWA_CLOAKED = 14
S_OK = 0


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
        self._autohide_delay = 400
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

        # Set up detection zone after a short delay
        QTimer.singleShot(1000, self.setup_detection_zone)

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


class FullscreenManager(QObject):
    """Manages fullscreen detection and bar visibility"""

    # System window classes that should not hide the bar and should be ignored
    # CEF-OSC-WIDGET is added to handle NVIDIA Overlay
    WINDOW_CLASSES = frozenset(
        [
            "Progman",
            "WorkerW",
            "XamlWindow",
            "Shell_TrayWnd",
            "XamlExplorerHostIslandWindow",
            "CEF-OSC-WIDGET",
        ]
    )

    def __init__(self, bar_widget: QWidget, parent=None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self._prev_fullscreen_state = None
        self._cached_screen_data = {}
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._check_fullscreen_for_window)

        try:
            dwmapi.DwmGetWindowAttribute
            self._dwm_available = True
        except (AttributeError, OSError):
            self._dwm_available = False

    def start_monitoring(self):
        try:
            self._timer.start()
        except Exception as e:
            logging.error(f"Failed to start fullscreen polling: {e}")

    def stop_monitoring(self):
        """Stop monitoring for fullscreen applications"""
        try:
            self._timer.stop()
        except Exception as e:
            logging.error(f"Failed to stop fullscreen polling: {e}")

    def is_window_cloaked(self, hwnd):
        """Check if a window is cloaked (hidden by DWM)"""
        if not self._dwm_available:
            return False

        try:
            is_cloaked = wintypes.DWORD(0)
            result = dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(DWMWA_CLOAKED),
                ctypes.byref(is_cloaked),
                ctypes.sizeof(is_cloaked),
            )

            if result != S_OK:
                return False

            return is_cloaked.value != 0
        except (OSError, AttributeError):
            return False

    def _check_fullscreen_for_window(self):
        """Check if the focused window is fullscreen on the bar's screen"""
        if not self.bar_widget:
            return

        # Get the currently focused window first
        focused_hwnd = win32gui.GetForegroundWindow()
        if not focused_hwnd:
            # No focused window, show bar if hidden
            self._prev_fullscreen_state = False
            if not self.bar_widget.isVisible():
                self.bar_widget.show()
            return

        # Early exit if focused window is invisible/minimized
        if not win32gui.IsWindowVisible(focused_hwnd) or win32gui.IsIconic(focused_hwnd):
            self._prev_fullscreen_state = False
            if not self.bar_widget.isVisible():
                self.bar_widget.show()
            return

        # Check monitor early to avoid unnecessary calculations
        try:
            focused_window_monitor = get_monitor_hwnd(focused_hwnd)
            bar_monitor = get_monitor_hwnd(int(self.bar_widget.winId()))

            # If focused window is on different monitor, check if there's a fullscreen window on this monitor
            if focused_window_monitor != bar_monitor:
                # Check if there's any fullscreen window on the bar's monitor
                found_fullscreen = self._check_fullscreen_on_bar_monitor(bar_monitor)

                # Only update visibility if state changed
                if self._prev_fullscreen_state != found_fullscreen:
                    self._prev_fullscreen_state = found_fullscreen
                    if found_fullscreen and self.bar_widget.isVisible():
                        self.bar_widget.hide()
                    elif not found_fullscreen and not self.bar_widget.isVisible():
                        self.bar_widget.show()
                return

            # Use monitor handle as cache key
            cache_key = bar_monitor
        except Exception:
            # If monitor check fails, use screen name as fallback cache key
            cache_key = self.bar_widget.screen().name()

        # Check window class early to filter out system windows
        try:
            class_name = win32gui.GetClassName(focused_hwnd)
            if class_name in self.WINDOW_CLASSES:
                self._prev_fullscreen_state = False
                if not self.bar_widget.isVisible():
                    self.bar_widget.show()
                return
        except Exception:
            # If class name check fails, continue
            pass

        # Check if window is cloaked
        if self.is_window_cloaked(focused_hwnd):
            self._prev_fullscreen_state = False
            if not self.bar_widget.isVisible():
                self.bar_widget.show()
            return

        # Get or calculate cached screen rect for this specific screen
        screen = self.bar_widget.screen()
        screen_geometry = screen.geometry()
        dpi = screen.devicePixelRatio()
        # Check if we have cached data for this screen
        if cache_key not in self._cached_screen_data or self._cached_screen_data[cache_key]["dpi"] != dpi:
            # Calculate and cache screen rect for this screen
            screen_rect = (screen_geometry.x(), screen_geometry.y(), screen_geometry.width(), screen_geometry.height())
            scaled_screen_rect = screen_rect[:2] + tuple(round(dim * dpi) for dim in screen_rect[2:])

            self._cached_screen_data[cache_key] = {"scaled_rect": scaled_screen_rect, "dpi": dpi}

        # Use cached screen rect
        scaled_screen_rect = self._cached_screen_data[cache_key]["scaled_rect"]

        # Get window rect and check if fullscreen
        try:
            rect = get_window_rect(focused_hwnd)
            window_rect = (rect["x"], rect["y"], rect["width"], rect["height"])
            found_fullscreen = window_rect == scaled_screen_rect
        except Exception:
            found_fullscreen = False

        # Only update visibility if state changed
        if self._prev_fullscreen_state != found_fullscreen:
            self._prev_fullscreen_state = found_fullscreen
            if found_fullscreen and self.bar_widget.isVisible():
                self.bar_widget.hide()
            elif not found_fullscreen and not self.bar_widget.isVisible():
                self.bar_widget.show()

    def _check_fullscreen_on_bar_monitor(self, bar_monitor):
        """
        Check if there's any fullscreen window on the bar's monitor (regardless of focus)
        This is used when the focused window is on a different monitor.
        It enumerates all windows and checks if any are fullscreen on the bar's monitor.
        """
        screen = self.bar_widget.screen()
        screen_geometry = screen.geometry()
        dpi = screen.devicePixelRatio()

        # Calculate screen rect for comparison
        screen_rect = (screen_geometry.x(), screen_geometry.y(), screen_geometry.width(), screen_geometry.height())
        scaled_screen_rect = screen_rect[:2] + tuple(round(dim * dpi) for dim in screen_rect[2:])

        def enum_windows_proc(hwnd, lparam):
            try:
                # Skip invisible/minimized windows
                if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                    return True

                # Check if window is on THIS bar's monitor
                window_monitor = get_monitor_hwnd(hwnd)
                if window_monitor != bar_monitor:
                    return True

                # Skip system windows
                class_name = win32gui.GetClassName(hwnd)
                if class_name in self.WINDOW_CLASSES:
                    return True

                # Skip cloaked windows
                if self.is_window_cloaked(hwnd):
                    return True

                # Check if window is fullscreen
                rect = get_window_rect(hwnd)
                window_rect = (rect["x"], rect["y"], rect["width"], rect["height"])

                if window_rect == scaled_screen_rect:
                    # Found a fullscreen window on this bar's monitor and stopping enumeration
                    return False

            except Exception:
                pass

            return True

        try:
            # Enumerate all windows to find fullscreen ones on this bar's monitor
            win32gui.EnumWindows(enum_windows_proc, None)
            return False
        except Exception:
            return True


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
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)


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
        qmenu_rounded_corners(self._menu)

        # Bar info
        bar_info = self._menu.addAction(f"Bar: {self._bar_name}")
        bar_info.setEnabled(False)

        # Widgets menu
        widgets_menu = self._menu.addMenu("Active Widgets")
        widgets_menu.setProperty("class", "context-menu submenu")
        widgets_menu.aboutToShow.connect(lambda: qmenu_rounded_corners(widgets_menu))
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

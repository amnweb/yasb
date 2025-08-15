import atexit
import logging

import win32con
import win32gui
from PIL import Image
from PyQt6.QtCore import QEasingCurve, QMimeData, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_monitor_hwnd, get_monitor_info
from core.utils.win32.window_actions import (
    can_minimize,
    close_application,
    is_owner_root_active,
    minimize_window,
    resolve_base_and_focus,
    restore_window,
    set_foreground,
    show_window,
)
from core.validation.widgets.yasb.taskbar import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

try:
    from core.utils.widgets.taskbar.window_manager import connect_taskbar
except ImportError:
    connect_taskbar = None
    logging.error("Failed to connect_taskbar")


class DraggableAppButton(QFrame):
    """A QFrame subclass that supports left/right reordering within a QHBoxLayout and
    raises its window on external file/text drag hover."""

    HOVER_RAISE_DELAY_MS = 350

    def __init__(self, taskbar_widget: "TaskbarWidget", hwnd: int):
        super().__init__()
        self._taskbar = taskbar_widget
        self._hwnd = hwnd
        self._dragging = False
        self._press_pos = None
        self._press_global_pos = None
        self._lmb_pressed = False
        self.setAcceptDrops(False)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        except Exception:
            pass
        try:
            self.setObjectName(f"yasb-taskbar-btn-{hwnd}")
        except Exception:
            pass

    def _maybe_start_drag(self, event: QMouseEvent) -> bool:
        if self._press_global_pos is None:
            return False
        threshold = max(8, QApplication.startDragDistance())
        moved = (event.globalPosition().toPoint() - self._press_global_pos).manhattanLength()
        if moved >= threshold and self._lmb_pressed:
            self._dragging = True
            try:
                self._taskbar._set_dragging(True)
            except Exception:
                pass
            drag = QDrag(self)
            md = QMimeData()
            md.setText(str(self._hwnd))
            drag.setMimeData(md)
            drag.exec(Qt.DropAction.MoveAction)
            return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._press_global_pos = event.globalPosition().toPoint()
            self._dragging = False
            self._lmb_pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if not self._dragging:
                if not self._maybe_start_drag(event):
                    event.accept()
                    return
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._dragging = False
            self._lmb_pressed = False
            self._press_pos = None
            self._press_global_pos = None
            try:
                self._taskbar._set_dragging(False)
            except Exception:
                pass
            if not was_dragging:
                try:
                    self._taskbar.bring_to_foreground(self._hwnd)
                except Exception:
                    pass
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TaskbarDropWidget(QFrame):
    drag_started = pyqtSignal()
    drag_ended = pyqtSignal()

    def __init__(self, owner: "TaskbarWidget", parent: QWidget | None = None):
        super().__init__(parent)
        self._owner = owner
        self.setAcceptDrops(True)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.dragged_button = None
        self.current_indicator_index = -1
        self._hover_highlight_btn = None
        # External drag hover-to-raise support
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(200)
        self._hover_target_hwnd = None
        self._hover_timer.timeout.connect(self._on_hover_timeout)

    def _on_hover_timeout(self):
        try:
            if self._hover_target_hwnd:
                self._owner.ensure_foreground(self._hover_target_hwnd)
        except Exception:
            pass

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableAppButton):
            self.dragged_button = source
            self.dragged_button.setProperty("dragging", True)
            self.refresh_styles()
            event.acceptProposedAction()
            self.drag_started.emit()
            return
        # External drag (files/text)
        md = event.mimeData()
        if md and (md.hasUrls() or md.hasText()):
            self._update_hover_target(event.position().toPoint())
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableAppButton):
            pos = event.position().toPoint()
            hovered = self._find_button_at(pos)
            if isinstance(hovered, DraggableAppButton) and hovered is not self.dragged_button:
                self._highlight_hover(hovered)
                self.current_indicator_index = self._get_index_from_hover(hovered, source)
            else:
                self._clear_hover_highlight()
                self.current_indicator_index = -1
            event.acceptProposedAction()
            return
        # External drag
        md = event.mimeData()
        if md and (md.hasUrls() or md.hasText()):
            self._update_hover_target(event.position().toPoint())
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.hide_drop_indicator()
        self._clear_hover_highlight()
        self._hover_timer.stop()
        self._hover_target_hwnd = None
        if self.dragged_button:
            self.dragged_button.setProperty("dragging", False)
            self.refresh_styles()
        self.dragged_button = None
        self.current_indicator_index = -1
        event.accept()

    def dropEvent(self, event):
        source = event.source()
        if not isinstance(source, DraggableAppButton):
            self._hover_timer.stop()
            if self._hover_target_hwnd:
                try:
                    self._owner.ensure_foreground(self._hover_target_hwnd)
                except Exception:
                    pass
            self._hover_target_hwnd = None
            event.ignore()
            return

        # Finalize reorder
        self._clear_hover_highlight()
        source.setProperty("dragging", False)
        self.refresh_styles()
        pos = event.position().toPoint()
        # Prefer the index tracked during move; else compute from hovered halves; else fallback
        insert_index = self.current_indicator_index
        if insert_index < 0:
            hovered = self._find_button_at(pos)
            if isinstance(hovered, DraggableAppButton) and hovered is not source:
                insert_index = self._get_index_from_hover(hovered, source)
            else:
                insert_index = self.get_insert_index(pos)

        current_index = -1
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if item and item.widget() is source:
                current_index = i
                break

        if source.parent() == self:
            # Adjust index after removal if moving forward in the list
            adjusted_index = insert_index
            if current_index != -1 and adjusted_index > current_index:
                adjusted_index -= 1
            # If after adjustment it's the same slot, treat as no-op
            if adjusted_index == current_index:
                self.hide_drop_indicator()
                event.acceptProposedAction()
                self.drag_ended.emit()
                return
            self.main_layout.removeWidget(source)
        else:
            source.setParent(self)

        target_index = adjusted_index if source.parent() == self else insert_index
        self.main_layout.insertWidget(target_index, source)
        source.show()
        self.refresh_styles()
        self.hide_drop_indicator()
        self.dragged_button = None
        self.current_indicator_index = -1
        event.acceptProposedAction()
        self.drag_ended.emit()

    def _highlight_hover(self, btn: QFrame):
        if self._hover_highlight_btn is btn:
            return
        self._clear_hover_highlight()
        self._hover_highlight_btn = btn
        try:
            btn.setProperty("_prev_inline_style", btn.styleSheet())
        except Exception:
            pass
        obj = btn.objectName() or ""
        if obj:
            btn.setStyleSheet(f"#{obj} {{ background-color: rgba(255, 255, 255, 0.2); }}")
        btn.update()

    def _clear_hover_highlight(self):
        btn = self._hover_highlight_btn
        if not btn:
            return
        prev = btn.property("_prev_inline_style") or ""
        btn.setStyleSheet(prev)
        btn.setProperty("_prev_inline_style", None)
        btn.update()
        self._hover_highlight_btn = None

    def _find_button_at(self, pos):
        w = self.childAt(pos)
        while w is not None and not isinstance(w, DraggableAppButton):
            w = w.parentWidget()
        return w

    def _update_hover_target(self, pos):
        btn = self._find_button_at(pos)
        if not isinstance(btn, DraggableAppButton):
            self._hover_timer.stop()
            self._hover_target_hwnd = None
            return
        hwnd = btn.property("hwnd") or getattr(btn, "_hwnd", None)
        if not hwnd:
            self._hover_timer.stop()
            self._hover_target_hwnd = None
            return
        self._hover_target_hwnd = int(hwnd)
        self._hover_timer.start(200)

    def get_insert_index(self, drop_position):
        if self.main_layout.count() == 0:
            return 0
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if not item or not item.widget():
                continue
            w = item.widget()
            mid_x = w.geometry().center().x()
            if drop_position.x() < mid_x:
                return i
        return self.main_layout.count()

    def _get_index_from_hover(self, hovered_btn: QFrame, source_btn: QFrame) -> int:
        """Return insertion index based on relative positions:
        - If dragging from left of hovered, insert after hovered (to move right).
        - If dragging from right of hovered, insert before hovered (to move left).
        This makes dropping anywhere on a hovered button perform a move."""
        hovered_idx = -1
        source_idx = -1
        for i in range(self.main_layout.count()):
            w = self.main_layout.itemAt(i).widget()
            if w is hovered_btn:
                hovered_idx = i
            if w is source_btn:
                source_idx = i
        if hovered_idx < 0:
            return 0
        if source_idx < 0:
            # If source isn't in this layout, default to after hovered
            return hovered_idx + 1
        return hovered_idx + 1 if source_idx < hovered_idx else hovered_idx

    def hide_drop_indicator(self):
        # No-op; indicator removed
        self.current_indicator_index = -1

    def refresh_styles(self):
        if style := self.style():
            style.unpolish(self)
            style.polish(self)
        if self.dragged_button and (style := self.dragged_button.style()):
            style.unpolish(self.dragged_button)
            style.polish(self.dragged_button)


class TaskbarWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        icon_size: int,
        animation: dict[str, str] | bool,
        title_label: dict[str, str],
        monitor_exclusive: bool,
        show_only_visible: bool,
        tooltip: bool,
        ignore_apps: dict[str, list[str]],
        container_padding: dict,
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="taskbar-widget")
        self._dpi = None
        self._label_icon_size = icon_size
        if isinstance(animation, bool):
            # Default animation settings if only a boolean is provided to prevent breaking configurations. this should be removed in the future
            self._animation = {"enabled": animation, "type": "fadeInOut", "duration": 200}
        else:
            self._animation = animation
        self._title_label = title_label
        self._tooltip = tooltip
        self._monitor_exclusive = monitor_exclusive
        self._show_only_visible = show_only_visible
        self._ignore_apps = ignore_apps
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._widget_monitor_handle = None

        self._ignore_apps["classes"] = list(set(self._ignore_apps.get("classes", [])))
        self._ignore_apps["processes"] = list(set(self._ignore_apps.get("processes", [])))
        self._ignore_apps["titles"] = list(set(self._ignore_apps.get("titles", [])))

        self._icon_cache = dict()
        self._hwnd_to_widget = {}
        self._window_buttons = {}
        self._suspend_updates = False

        self._widget_container = TaskbarDropWidget(self)
        self._widget_container.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container_layout = self._widget_container.main_layout
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        self._widget_container.drag_started.connect(lambda: self._set_dragging(True))
        self._widget_container.drag_ended.connect(lambda: self._set_dragging(False))

        self.register_callback("toggle_window", self._on_toggle_window)
        self.register_callback("close_app", self._on_close_app)
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        if connect_taskbar:
            self._task_manager = connect_taskbar(self)
            QTimer.singleShot(0, self._refresh_monitor_handle)  # Get monitor handle for this widget
        else:
            logging.error("Shared task manager not available - taskbar functionality will be limited")

        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self._stop_events)
        atexit.register(self._stop_events)

    def _on_window_added(self, hwnd, window_data):
        """Handle window added signal from task manager"""
        # Apply filtering based on widget configuration
        if not self._should_show_window(hwnd, window_data):
            return
        self._add_window_ui(hwnd, window_data)

    def _on_window_removed(self, hwnd, window_data):
        """Handle window removed signal from task manager"""
        # Skip if we don't currently show this hwnd to avoid duplicate removals
        if hwnd in self._window_buttons:
            self._remove_window_ui(hwnd, window_data)

    def _on_window_updated(self, hwnd, window_data):
        """Handle window updated signal from task manager"""
        # Apply filtering - remove if no longer should be shown
        if not self._should_show_window(hwnd, window_data):
            # Avoid duplicate removals if the button is already gone
            if hwnd in self._window_buttons:
                self._remove_window_ui(hwnd, window_data)
            return
        self._update_window_ui(hwnd, window_data)

    def _on_window_monitor_changed(self, hwnd, window_data):
        """Handle window monitor changed signal from task manager"""
        # For monitor exclusive mode, check if window should be shown/hidden
        if self._monitor_exclusive:
            if self._should_show_window(hwnd, window_data):
                # Window moved to our monitor - add if not already present
                if hwnd not in self._window_buttons:
                    self._add_window_ui(hwnd, window_data)
            else:
                # Window moved away from our monitor - remove if present
                if hwnd in self._window_buttons:
                    self._remove_window_ui(hwnd, window_data)
        else:
            # If not monitor exclusive, treat as regular update
            self._update_window_ui(hwnd, window_data)

    def _get_widget_monitor_handle(self):
        """Get the monitor handle for this widget using win32 utilities."""
        if self._widget_monitor_handle is None:
            try:
                self._widget_monitor_handle = get_monitor_hwnd(self.winId())
                try:
                    self._widget_monitor_info = get_monitor_info(self._widget_monitor_handle)
                except Exception:
                    self._widget_monitor_info = None
            except Exception:
                self._widget_monitor_handle = None
        return self._widget_monitor_handle

    def _refresh_monitor_handle(self):
        """Re-check monitor handle after widget is positioned and refresh window list if changed"""
        if not self._monitor_exclusive:
            return

        old_handle = self._widget_monitor_handle
        self._widget_monitor_handle = None  # Force re-detection
        new_handle = self._get_widget_monitor_handle()

        if old_handle != new_handle:
            # Trigger a refresh of the window list with the new monitor handle
            if hasattr(self, "_task_manager") and self._task_manager and hasattr(self._task_manager, "_windows"):
                # Clear current UI
                while self._widget_container_layout.count():
                    child = self._widget_container_layout.takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)
                self._window_buttons.clear()

                # Re-add windows with new monitor filtering
                for hwnd, window in self._task_manager._windows.items():
                    window_data = window.as_dict()
                    self._on_window_added(hwnd, window_data)

    def _should_show_window(self, hwnd, window_data):
        """Determine if a window should be shown based on widget configuration"""
        title = window_data.get("title", "")
        if not title.strip():
            return False

        if self._monitor_exclusive:
            window_monitor = window_data.get("monitor_handle")
            if window_monitor is not None:
                widget_monitor = self._get_widget_monitor_handle()
                if widget_monitor is not None and window_monitor != widget_monitor:
                    return False

        return True

    def _add_window_ui(self, hwnd, window_data):
        """Add window UI element"""
        if self._suspend_updates:
            return
        # Drop any old widget for this hwnd to avoid duplicates
        old = self._hwnd_to_widget.pop(hwnd, None)
        if old is not None:
            try:
                self._widget_container_layout.removeWidget(old)
                old.setParent(None)
                old.deleteLater()
            except Exception:
                pass
        # Reset button state if previously tracked
        self._window_buttons.pop(hwnd, None)

        title = window_data.get("title", "")
        process = window_data.get("process_name", "")
        # If process is explorer.exe (e.g. file explorer), we use the title for caching the icon.
        icon = self._get_app_icon(hwnd, title if process == "explorer.exe" else "")
        self._window_buttons[hwnd] = (title, icon, hwnd, process)

        # Create UI container
        container = self._create_app_container(title, icon, hwnd)
        self._hwnd_to_widget[hwnd] = container
        add_shadow(container, self._label_shadow)

        if self._animation["enabled"]:
            container.setFixedWidth(0)
            self._widget_container_layout.addWidget(container)
            QTimer.singleShot(
                0,
                lambda c=container: self._animate_container(c, start_width=0, end_width=container.sizeHint().width()),
            )
        else:
            self._widget_container_layout.addWidget(container)

    def _remove_window_ui(self, hwnd, window_data):
        """Remove window UI element"""
        if self._suspend_updates:
            return
        # Prefer direct lookup, fallback to scan once
        widget = self._hwnd_to_widget.pop(hwnd, None)
        if widget is None:
            for i in range(self._widget_container_layout.count()):
                w = self._widget_container_layout.itemAt(i).widget()
                if w and w.property("hwnd") == hwnd:
                    widget = w
                    break
        if widget is not None:
            if self._animation["enabled"]:
                self._animate_container(widget, start_width=widget.width(), end_width=0)
            else:
                try:
                    self._widget_container_layout.removeWidget(widget)
                except Exception:
                    pass
                widget.deleteLater()
        # Remove from tracking
        self._window_buttons.pop(hwnd, None)

    def _update_window_ui(self, hwnd, window_data):
        """Update window UI element (focused on the specific widget, no global sweep)."""
        if self._suspend_updates:
            return
        title = window_data.get("title", "")
        process = window_data.get("process_name", "")
        # If process is explorer.exe (e.g. file explorer), we use the title for caching the icon.
        icon = self._get_app_icon(hwnd, title if process == "explorer.exe" else "")
        self._window_buttons[hwnd] = (title, icon, hwnd, process)

        # Direct lookup for the widget
        widget = self._hwnd_to_widget.get(hwnd)
        if widget is None:
            # Fallback scan once and store mapping
            for i in range(self._widget_container_layout.count()):
                w = self._widget_container_layout.itemAt(i).widget()
                if w and w.property("hwnd") == hwnd:
                    widget = w
                    self._hwnd_to_widget[hwnd] = w
                    break
        if widget is None:
            return

        if self._tooltip and title:
            set_tooltip(widget, title, delay=0)

        # Apply class based on state
        try:
            widget.setProperty("class", self._get_container_class(hwnd))
            if style := widget.style():
                style.unpolish(widget)
                style.polish(widget)
        except Exception:
            pass

        layout = widget.layout()
        if not layout:
            return

        try:
            icon_label = layout.itemAt(0).widget()
            if icon_label and icon is not None:
                icon_label.setPixmap(icon)
        except Exception:
            pass

        try:
            if self._title_label["enabled"] and layout.count() > 1:
                title_label = layout.itemAt(1).widget()
                if title_label:
                    formatted_title = self._format_title(title)
                    if title_label.text() != formatted_title:
                        title_label.setText(formatted_title)
                    if self._title_label["show"] == "focused":
                        desired_visible = self._get_title_visibility(hwnd)
                        if desired_visible != title_label.isVisible():
                            title_label.setVisible(desired_visible)
                            layout.activate()
        except Exception:
            pass

        # If this window is marked active by the manager, enforce single foreground class.
        # This handles external changes (like minimizing via Windows taskbar) where only
        # the newly-active window might get an update initially.
        try:
            if bool(window_data.get("is_active")):
                self._clear_others_set_foreground(hwnd)
        except Exception:
            pass

    def _stop_events(self) -> None:
        """Stop the task manager and clean up"""
        if hasattr(self, "_task_manager") and self._task_manager:
            try:
                self._task_manager.stop()
            except Exception as e:
                logging.error(f"Error stopping task manager: {e}")

    def _on_close_app(self) -> None:
        widget = QApplication.instance().widgetAt(QCursor.pos())
        if not widget:
            logging.warning("No widget found under cursor.")
            return

        hwnd = widget.property("hwnd")
        if not hwnd:
            logging.warning("No hwnd found for widget.")
            return

        # Check if the window is valid before attempting to close it
        if win32gui.IsWindow(hwnd):
            close_application(hwnd)
        else:
            logging.warning(f"Invalid window handle: {hwnd}")

    def _get_title_visibility(self, hwnd: int) -> bool:
        """Should title be visible when show=="focused"? Normalize to base owner and use robust active check."""
        try:
            base, _ = resolve_base_and_focus(hwnd)
        except Exception:
            base = hwnd

        # Prefer task manager knowledge on the base window
        try:
            if hasattr(self, "_task_manager") and self._task_manager:
                if base in self._task_manager._windows:
                    app_window = self._task_manager._windows[base]
                    if hasattr(app_window, "is_active") and app_window.is_active:
                        return True
        except Exception:
            pass

        # Then rely on owner/root being active (handles wrappers/child windows)
        try:
            if is_owner_root_active(base):
                return True
        except Exception:
            pass

        # Final fallback to foreground equality using the base window
        try:
            return base == win32gui.GetForegroundWindow()
        except Exception:
            return False

    def _format_title(self, title: str) -> str:
        """Format a window title according to max and min length settings."""
        if len(title) > self._title_label["max_length"]:
            formatted_title = title[: self._title_label["max_length"]] + ".."
        else:
            formatted_title = title

        min_length = self._title_label.get("min_length", 0)
        if len(formatted_title) < min_length:
            formatted_title = formatted_title.ljust(min_length)

        return formatted_title

    def _create_app_container(self, title: str, icon: QPixmap, hwnd: int) -> QFrame:
        """Create a container widget that holds icon and title"""
        container = DraggableAppButton(self, hwnd)
        container.setProperty("class", self._get_container_class(hwnd))
        container.setProperty("hwnd", hwnd)
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon_label = QLabel()
        icon_label.setProperty("class", "app-icon")

        try:
            icon_label.setFixedSize(self._label_icon_size, self._label_icon_size)
        except Exception:
            pass
        if icon is not None:
            icon_label.setPixmap(icon)
        icon_label.setProperty("hwnd", hwnd)
        layout.addWidget(icon_label)

        if self._title_label["enabled"]:
            title_label = QLabel(self._format_title(title))
            title_label.setProperty("class", "app-title")
            title_label.setProperty("hwnd", hwnd)

            try:
                title_label.setSizePolicy(
                    title_label.sizePolicy().horizontalPolicy(), title_label.sizePolicy().verticalPolicy()
                )
            except Exception:
                pass
            layout.addWidget(title_label)
            if self._title_label["show"] == "focused":
                title_label.setVisible(self._get_title_visibility(hwnd))

        if self._tooltip:
            set_tooltip(container, title, delay=0)

        return container

    def _get_container_class(self, hwnd: int) -> str:
        """Get CSS class for the app container based on window active and flashing status."""
        # Check if window is active using task manager data
        if hasattr(self, "_task_manager") and self._task_manager and hwnd in self._task_manager._windows:
            app_window = self._task_manager._windows[hwnd]

            # Check for flashing state first (flashing takes priority over active)
            if hasattr(app_window, "is_flashing") and app_window.is_flashing:
                return "app-container flashing"

            # Then check for active state
            if hasattr(app_window, "is_active") and app_window.is_active:
                return "app-container foreground"

        # Fallback to GetForegroundWindow check
        if hwnd == win32gui.GetForegroundWindow():
            return "app-container foreground"

        return "app-container"

    def _get_app_icon(self, hwnd: int, title: str) -> QPixmap | None:
        """Return a QPixmap for the given window handle, using a DPI-aware cache."""
        try:
            cache_key = (hwnd, title, self._dpi)
            if cache_key in self._icon_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                icon_img = get_window_icon(hwnd)
                if icon_img:
                    self._dpi = self.screen().devicePixelRatio()
                    icon_img = icon_img.resize(
                        (int(self._label_icon_size * self._dpi), int(self._label_icon_size * self._dpi)), Image.LANCZOS
                    ).convert("RGBA")
                    self._icon_cache[cache_key] = icon_img

            if not icon_img:
                return None

            qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            pixmap.setDevicePixelRatio(self._dpi)
            return pixmap

        except Exception:
            if DEBUG:
                logging.exception(f"Failed to get icons for window with HWND {hwnd} ")
            return None

    def _perform_action(self, action: str) -> None:
        widget = QApplication.instance().widgetAt(QCursor.pos())
        if not widget:
            return

        hwnd = widget.property("hwnd")
        if not hwnd or not win32gui.IsWindow(hwnd):
            return

        if action == "toggle":
            if self._animation["enabled"] and not self._suspend_updates:
                AnimationManager.animate(widget, self._animation["type"], self._animation["duration"])
            self.bring_to_foreground(hwnd)
        else:
            logging.warning(f"Unknown action '{action}'.")

    def _on_toggle_window(self) -> None:
        self._perform_action("toggle")

    def _set_dragging(self, active: bool) -> None:
        """Temporarily suspend updates/animations to reduce flicker during drag."""
        self._suspend_updates = active
        try:
            # Expose a dynamic property usable in QSS: .taskbar-widget[dragging="true"]
            self.setProperty("dragging", bool(active))
            if hasattr(self, "_widget_container") and self._widget_container:
                self._widget_container.setProperty("dragging", bool(active))
                # Repolish container to apply QSS that depends on [dragging]
                if style := self._widget_container.style():
                    style.unpolish(self._widget_container)
                    style.polish(self._widget_container)
            # Repolish self as well in case styles cascade from the root widget
            if style := self.style():
                style.unpolish(self)
                style.polish(self)
        except Exception:
            pass

    def _animate_container(self, container, start_width=0, end_width=0, duration=300) -> None:
        """Animate the width of a container widget."""

        animation = QPropertyAnimation(container, b"maximumWidth", container)
        animation.setStartValue(start_width)
        animation.setEndValue(end_width)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.OutCirc)

        if end_width > start_width and not container.graphicsEffect():
            add_shadow(container, self._label_shadow)

        def on_finished():
            if end_width == 0:
                container.setParent(None)
                self._widget_container_layout.removeWidget(container)
                container.deleteLater()
            else:
                # Clear width constraint so future content changes (e.g., focused title show/hide)
                # can naturally resize the container without animations.
                try:
                    container.setMaximumWidth(16777215)
                    container.adjustSize()
                    container.updateGeometry()
                except Exception:
                    pass

        animation.finished.connect(on_finished)
        animation.start()

    def bring_to_foreground(self, hwnd):
        # Defer UI class changes until after the action succeeds
        if not win32gui.IsWindow(hwnd):
            return
        try:
            base, focus_target = resolve_base_and_focus(hwnd)
            is_active = False
            try:
                if hasattr(self, "_task_manager") and self._task_manager and base in self._task_manager._windows:
                    app_window = self._task_manager._windows[base]
                    is_active = bool(getattr(app_window, "is_active", False))
            except Exception:
                is_active = False
            if not is_active:
                is_active = is_owner_root_active(base)

            if win32gui.IsIconic(base):
                restore_window(base)
                set_foreground(focus_target)
                # After successful raise, reflect expected focus immediately
                # try:
                #     self._clear_others_set_foreground(base)
                # except Exception:
                #     pass
                return

            if is_active and can_minimize(base):
                minimize_window(base)
                return

            show_window(base)
            set_foreground(focus_target)
            # After successful raise, reflect expected focus immediately
            # try:
            #     self._clear_others_set_foreground(base)
            # except Exception:
            #     pass
        except Exception as e:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetActiveWindow(hwnd)
            except Exception:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE if win32gui.IsIconic(hwnd) else win32con.SW_SHOW)
                    if DEBUG:
                        logging.warning(f"Could not bring window {hwnd} to foreground: {e}")
                except Exception as final_e:
                    if DEBUG:
                        logging.error(f"Failed to show window {hwnd}: {final_e}")

    def ensure_foreground(self, hwnd):
        # Defer UI class changes until after the action succeeds
        if not win32gui.IsWindow(hwnd):
            return
        try:
            base, focus_target = resolve_base_and_focus(hwnd)
            if win32gui.IsIconic(base):
                win32gui.ShowWindow(base, win32con.SW_RESTORE)
            set_foreground(focus_target)
            # After successful raise, reflect expected focus immediately
            try:
                self._clear_others_set_foreground(base)
            except Exception:
                pass
        except Exception:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetActiveWindow(hwnd)
            except Exception:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE if win32gui.IsIconic(hwnd) else win32con.SW_SHOW)
                except Exception:
                    pass

    def _clear_others_set_foreground(self, target_hwnd: int | None) -> None:
        """Set a single 'foreground' entry; preserve flashing from manager; toggle focused-only titles."""
        try:
            for i in range(self._widget_container_layout.count()):
                w = self._widget_container_layout.itemAt(i).widget()
                if not w:
                    continue
                hwnd = w.property("hwnd")

                # Base class
                new_cls = "app-container"

                # Preserve flashing if manager reports it
                try:
                    if hasattr(self, "_task_manager") and self._task_manager and hwnd in self._task_manager._windows:
                        aw = self._task_manager._windows[hwnd]
                        if getattr(aw, "is_flashing", False):
                            new_cls = "app-container flashing"
                except Exception:
                    pass

                # Target gets 'foreground' (manager usually clears flashing on activation)
                if target_hwnd is not None and hwnd == target_hwnd:
                    new_cls = "app-container foreground"

                if w.property("class") != new_cls:
                    w.setProperty("class", new_cls)
                    if self._title_label.get("enabled") and self._title_label.get("show") == "focused":
                        lay = w.layout()
                        if lay and lay.count() > 1:
                            tlabel = lay.itemAt(1).widget()
                            if tlabel:
                                want_visible = target_hwnd is not None and hwnd == target_hwnd
                                if tlabel.isVisible() != want_visible:
                                    tlabel.setVisible(want_visible)
                                    lay.activate()
                    st = w.style()
                    if st:
                        st.unpolish(w)
                        st.polish(w)
        except Exception:
            pass

import atexit
import logging

import win32con
import win32gui
from PIL import Image
from PyQt6.QtCore import QEasingCurve, QMimeData, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.recycle_bin.recycle_bin_monitor import RecycleBinMonitor
from core.utils.widgets.taskbar.app_menu import show_context_menu
from core.utils.widgets.taskbar.pin_manager import PinManager
from core.utils.widgets.taskbar.thumbnail import TaskbarThumbnailManager
from core.utils.win32.app_icons import get_stock_icon, get_window_icon
from core.utils.win32.constants import KnownCLSID
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


ANIMATION_DURATION_MS = 200


class DraggableAppButton(QFrame):
    """A QFrame subclass that supports left/right reordering within a QHBoxLayout and
    raises its window on external file/text drag hover."""

    def __init__(self, taskbar_widget: "TaskbarWidget", hwnd: int):
        super().__init__()
        self._taskbar = taskbar_widget
        self._hwnd = hwnd
        self._dragging = False
        self._press_pos = None
        self._press_global_pos = None
        self._lmb_pressed = False
        self.setAcceptDrops(False)
        self.setObjectName(f"yasb-taskbar-btn-{hwnd}")

        # Hover preview timer
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(self._taskbar._preview_delay)
        self._preview_timer.timeout.connect(self._on_preview_timeout)

    def enterEvent(self, event):
        try:
            if self._taskbar._preview_enabled and not self._dragging:
                self._preview_timer.start()

        except Exception:
            pass
        try:
            super().enterEvent(event)
        except Exception:
            pass

    def leaveEvent(self, event):
        try:
            self._preview_timer.stop()
            if self._taskbar._preview_enabled:
                self._taskbar.hide_preview()
        except Exception:
            pass
        try:
            super().leaveEvent(event)
        except Exception:
            pass

    def _on_preview_timeout(self):
        try:
            if self._taskbar._preview_enabled and not self._dragging:
                self._taskbar.show_preview_for_hwnd(self._hwnd, self)
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
            try:
                drag.exec(Qt.DropAction.MoveAction)
            finally:
                # Always reset drag state
                self._dragging = False
                try:
                    self._taskbar._set_dragging(False)
                except Exception:
                    pass
                # If cursor still over button after drag, preview again
                try:
                    if self.rect().contains(self.mapFromGlobal(QCursor.pos())) and self._taskbar._preview_enabled:
                        self._preview_timer.start()
                except Exception:
                    pass
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
            else:
                # Drag ended, if pointer still over button, start preview timer
                try:
                    if self.rect().contains(self.mapFromGlobal(QCursor.pos())) and self._taskbar._preview_enabled:
                        self._preview_timer.start()
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
            if source.parent() is not self:
                event.ignore()
                return
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
            if source.parent() is not self:
                event.ignore()
                return
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

        # Ignore drops from other taskbar instances to avoid duplicate handling
        if source.parent() is not self:
            event.ignore()
            self.drag_ended.emit()
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
        count = self.main_layout.count()
        for i in range(count):
            item = self.main_layout.itemAt(i)
            if item and item.widget() is source:
                current_index = i
                break

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

        target_index = adjusted_index
        self.main_layout.insertWidget(target_index, source)
        source.show()
        self.refresh_styles()
        self.hide_drop_indicator()
        self.dragged_button = None
        self.current_indicator_index = -1
        event.acceptProposedAction()

        # Update pinned order if pinned apps were reordered
        try:
            self._owner._update_pinned_order_from_layout()
        except Exception:
            pass

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
        refresh_widget_style(btn)
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
        count = self.main_layout.count()
        if count == 0:
            return 0
        for i in range(count):
            item = self.main_layout.itemAt(i)
            if not item or not item.widget():
                continue
            w = item.widget()
            mid_x = w.geometry().center().x()
            if drop_position.x() < mid_x:
                return i
        return count

    def _get_index_from_hover(self, hovered_btn: QFrame, source_btn: QFrame) -> int:
        """Return insertion index based on relative positions:
        - If dragging from left of hovered, insert after hovered (to move right).
        - If dragging from right of hovered, insert before hovered (to move left).
        This makes dropping anywhere on a hovered button perform a move."""
        hovered_idx = -1
        source_idx = -1
        count = self.main_layout.count()
        for i in range(count):
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
        refresh_widget_style(self, self.dragged_button)


class TaskbarWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        icon_size: int,
        animation: dict[str, str] | bool,
        title_label: dict[str, str],
        monitor_exclusive: bool,
        strict_filtering: bool,
        show_only_visible: bool,
        tooltip: bool,
        ignore_apps: dict[str, list[str]],
        hide_empty: bool,
        container_padding: dict,
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
        preview: dict | None = None,
    ):
        super().__init__(class_name="taskbar-widget")
        self._dpi = None
        self._label_icon_size = icon_size
        self._animation = (
            {"enabled": animation, "type": "fadeInOut", "duration": 200} if isinstance(animation, bool) else animation
        )
        self._title_label = title_label
        self._monitor_exclusive = monitor_exclusive
        self._strict_filtering = strict_filtering
        self._show_only_visible = show_only_visible
        self._ignore_apps = ignore_apps
        self._hide_empty = hide_empty
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._widget_monitor_handle = None
        self._context_menu_open = False

        self._preview_enabled = preview["enabled"]
        self._preview_width = preview["width"]
        self._preview_delay = preview["delay"]
        self._preview_padding = preview["padding"]
        self._preview_margin = preview["margin"]

        self._tooltip = tooltip if not self._preview_enabled else False
        self._tooltip_enabled = tooltip  # Store original tooltip setting for pinned apps

        self._ignore_apps["classes"] = list(set(self._ignore_apps.get("classes", [])))
        self._ignore_apps["processes"] = list(set(self._ignore_apps.get("processes", [])))
        self._ignore_apps["titles"] = list(set(self._ignore_apps.get("titles", [])))

        self._icon_cache = {}
        self._hwnd_to_widget = {}
        self._window_buttons = {}
        self._suspend_updates = False
        self._animating_widgets = {}
        self._flashing_animation = {}  # Track which hwnds are currently flashing
        self._recycle_bin_state = {"is_empty": True}
        self._pending_pinned_recreations = set()  # Track pending placeholder recreations

        # Initialize pin manager for pinned apps functionality
        self._pin_manager = PinManager()

        self._widget_container = TaskbarDropWidget(self)
        self._widget_container.setContentsMargins(0, 0, 0, 0)
        self._widget_container_layout = self._widget_container.main_layout
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        self._widget_container.drag_started.connect(lambda: self._set_dragging(True))
        self._widget_container.drag_ended.connect(lambda: self._set_dragging(False))

        self.register_callback("toggle_window", self._on_toggle_window)
        self.register_callback("close_app", self._on_close_app)
        self.register_callback("context_menu", self._on_context_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self._stop_events)
        atexit.register(self._stop_events)

        if connect_taskbar:
            self._task_manager = None
            self._task_manager_connected = False
        else:
            logging.error("Shared task manager not available - taskbar functionality will be limited")

        if self._preview_enabled:
            self._thumbnail_mgr = TaskbarThumbnailManager(
                self,
                self._preview_width,
                self._preview_delay,
                self._preview_padding,
                self._preview_margin,
                self._animation["enabled"],
            )

        # Initialize pinned apps display flag
        self._pinned_apps_displayed = False

        # Connect to global signal bus for inter-widget communication
        PinManager.get_signal_bus().pinned_apps_changed.connect(self._on_pinned_apps_changed_signal)

    def _load_pinned_apps(self) -> None:
        """Load pinned apps from disk using PinManager."""
        self._pin_manager.load_pinned_apps()

    def _get_app_identifier(self, hwnd: int, window_data: dict) -> tuple[str, dict]:
        """Get a unique identifier for an app and its metadata. Delegates to PinManager."""
        return PinManager.get_app_identifier(hwnd, window_data)

    def _pin_app(self, hwnd: int) -> None:
        """Pin an application to the taskbar (pinned apps are global across all monitors)."""
        try:
            # Get app info from ApplicationWindow (includes process_pid and process_path)
            if not (hasattr(self, "_task_manager") and self._task_manager and hwnd in self._task_manager._windows):
                logging.warning(f"Cannot pin app: window {hwnd} not found in task manager")
                return

            app_window = self._task_manager._windows[hwnd]
            window_data = app_window.as_dict()

            # Get icon for caching
            icon_img = get_window_icon(hwnd)

            # Pin at the end of existing pinned apps (position = number of pinned apps)
            # This puts it after all other pinned apps but before unpinned running apps
            position = len(self._pin_manager.pinned_order)
            unique_id = self._pin_manager.pin_app(hwnd, window_data, icon_img, position=position)

            if unique_id:
                self._update_pinned_status(hwnd, is_pinned=True)

                # Move the widget to the correct position (after all pinned apps)
                widget = self._hwnd_to_widget.get(hwnd)
                if widget:
                    # Remove from current position
                    self._widget_container_layout.removeWidget(widget)

                    # Find the position to insert: after all pinned apps
                    insert_pos = self._find_insert_position_after_pinned()

                    # Insert at the calculated position
                    self._widget_container_layout.insertWidget(insert_pos, widget)

        except Exception as e:
            logging.error(f"Error pinning app: {e}")

    def _unpin_app(self, hwnd: int) -> None:
        """Unpin an application from the taskbar."""
        try:
            # Get window data if needed (only when hwnd is not in running_pinned cache)
            window_data = None
            if hwnd not in self._pin_manager.running_pinned:
                if hasattr(self, "_task_manager") and self._task_manager and hwnd in self._task_manager._windows:
                    app_window = self._task_manager._windows[hwnd]
                    window_data = app_window.as_dict()
                else:
                    logging.warning(f"Cannot unpin app: window {hwnd} not found in task manager")
                    return

            # Unpin using PinManager
            self._pin_manager.unpin_app(hwnd, window_data)
            self._update_pinned_status(hwnd, is_pinned=False)

        except Exception as e:
            logging.error(f"Error unpinning app: {e}")

    def _is_app_pinned(self, hwnd: int) -> bool:
        """Check if an app is pinned."""
        return self._pin_manager.is_app_pinned(hwnd)

    def _get_hwnd_position(self, hwnd: int) -> int:
        """Get the position of a hwnd in the widget layout."""
        count = self._widget_container_layout.count()
        for i in range(count):
            w = self._widget_container_layout.itemAt(i).widget()
            if w and w.property("hwnd") == hwnd:
                return i
        return -1

    def _find_insert_position_after_pinned(self) -> int:
        """Find the position to insert after all pinned apps."""
        insert_pos = 0
        count = self._widget_container_layout.count()
        for i in range(count):
            w = self._widget_container_layout.itemAt(i).widget()
            if not w:
                continue
            w_hwnd = w.property("hwnd")
            # Count all pinned apps (both running and pinned-only)
            if w_hwnd and w_hwnd < 0:  # Pinned-only
                insert_pos = i + 1
            elif w_hwnd and w_hwnd > 0 and w_hwnd in self._pin_manager.running_pinned:  # Running pinned
                insert_pos = i + 1
        return insert_pos

    def _update_pinned_order_from_layout(self) -> None:
        """Update the pinned order based on current layout positions after drag-and-drop.

        Since pinned apps are global, all taskbars share the same order.
        """
        try:
            # Collect pinned apps visible in current layout (in their new order)
            visible_order = []
            count = self._widget_container_layout.count()
            for i in range(count):
                widget = self._widget_container_layout.itemAt(i).widget()
                if not widget:
                    continue

                hwnd = widget.property("hwnd")
                if hwnd and hwnd < 0:  # Pinned-only button
                    unique_id = widget.property("unique_id")
                    if unique_id and unique_id in self._pin_manager.pinned_apps:
                        visible_order.append(unique_id)
                elif hwnd and hwnd > 0:  # Running app
                    # Check if it's a running pinned app
                    unique_id = self._pin_manager.running_pinned.get(hwnd)
                    if unique_id and unique_id in self._pin_manager.pinned_apps and unique_id not in visible_order:
                        visible_order.append(unique_id)

            # Build new complete order from visible order
            # Since pinned apps are now global, we use the visible order directly
            new_order = visible_order

            # Update pinned order using PinManager
            self._pin_manager.update_pinned_order(new_order)
        except Exception as e:
            logging.error(f"Error updating pinned order from layout: {e}")

    def _update_pinned_status(self, hwnd: int, is_pinned: bool) -> None:
        """Update the visual state of a pinned/unpinned app."""
        widget = self._hwnd_to_widget.get(hwnd)
        if not widget:
            return

        widget.setProperty("pinned", is_pinned)
        current_class = widget.property("class") or ""
        if is_pinned and "pinned" not in current_class:
            widget.setProperty("class", f"{current_class} pinned")
        elif not is_pinned and "pinned" in current_class:
            widget.setProperty("class", current_class.replace(" pinned", ""))

        refresh_widget_style(widget)

    def _display_pinned_apps(self) -> None:
        """Display all pinned apps on all taskbars (always shows all pinned apps regardless of monitor_exclusive)."""
        for unique_id in self._pin_manager.pinned_order:
            if unique_id not in self._pin_manager.pinned_apps:
                continue

            metadata = self._pin_manager.pinned_apps[unique_id]
            self._create_pinned_app_button(unique_id, metadata)

            # Start monitoring if Recycle Bin is pinned
            if KnownCLSID.RECYCLE_BIN in unique_id.upper():
                self._rbin_monitor_start()

    def _create_pinned_app_button(self, unique_id: str, metadata: dict) -> None:
        """Create a button for a pinned app that's not currently running."""
        if unique_id in self._pin_manager.running_pinned.values():
            return  # App is already running

        pseudo_hwnd = -(abs(hash(unique_id)) % 1000000000 + 1000000000)
        title = metadata.get("title", "App")

        # Always use _load_cached_icon - it handles Recycle Bin caching internally
        icon = self._load_cached_icon(unique_id)

        container = self._create_pinned_app_container(title, icon, pseudo_hwnd, unique_id)
        self._hwnd_to_widget[pseudo_hwnd] = container

        # Add with animation if enabled
        if self._animation["enabled"]:
            container.setFixedWidth(0)
            self._widget_container_layout.addWidget(container)
            self._animate_container(
                container,
                start_width=0,
                end_width=container.sizeHint().width(),
                duration=ANIMATION_DURATION_MS,
                hwnd=pseudo_hwnd,
            )
        else:
            self._widget_container_layout.addWidget(container)

    def _recreate_pinned_button(self, unique_id: str, position: int = -1) -> None:
        """Recreate pinned button when pinned app closes."""
        # Remove from pending set since we're executing now
        self._pending_pinned_recreations.discard(unique_id)

        if unique_id in self._pin_manager.running_pinned.values():
            return  # App is still running

        if unique_id not in self._pin_manager.pinned_apps:
            return  # App is no longer pinned

        metadata = self._pin_manager.pinned_apps[unique_id]
        pseudo_hwnd = -(abs(hash(unique_id)) % 1000000000 + 1000000000)
        title = metadata.get("title", "App")
        icon = self._load_cached_icon(unique_id)

        container = self._create_pinned_app_container(title, icon, pseudo_hwnd, unique_id)
        self._hwnd_to_widget[pseudo_hwnd] = container

        # Add with animation if enabled
        if self._animation["enabled"]:
            container.setFixedWidth(0)
            if 0 <= position <= self._widget_container_layout.count():
                self._widget_container_layout.insertWidget(position, container)
            else:
                self._widget_container_layout.addWidget(container)
            self._animate_container(
                container,
                start_width=0,
                end_width=container.sizeHint().width(),
                duration=ANIMATION_DURATION_MS,
                hwnd=pseudo_hwnd,
            )
        else:
            if 0 <= position <= self._widget_container_layout.count():
                self._widget_container_layout.insertWidget(position, container)
            else:
                self._widget_container_layout.addWidget(container)

    def _create_pinned_app_container(
        self, title: str, icon: QPixmap | None, pseudo_hwnd: int, unique_id: str
    ) -> QFrame:
        """Create a container widget for a pinned app that's not running."""
        container = DraggableAppButton(self, pseudo_hwnd)
        container.setProperty("class", "app-container")
        container.setProperty("hwnd", pseudo_hwnd)
        container.setProperty("unique_id", unique_id)
        container.setProperty("pinned", True)
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create outer layout with no margins
        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Create inner content wrapper - this holds the actual content (icon + title)
        # and has shadow effects applied, while the outer container handles animations
        content_wrapper = QFrame()

        # Apply shadow effect to content wrapper
        add_shadow(content_wrapper, self._label_shadow)

        content_layout = QHBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        icon_label = QLabel()
        icon_label.setProperty("class", "app-icon")
        try:
            icon_label.setFixedSize(self._label_icon_size, self._label_icon_size)
        except Exception:
            pass
        if icon is not None:
            icon_label.setPixmap(icon)
        icon_label.setProperty("hwnd", pseudo_hwnd)
        content_layout.addWidget(icon_label)

        # Add content wrapper to outer container
        outer_layout.addWidget(content_wrapper)

        # Use original tooltip setting for pinned apps (not affected by preview)
        if self._tooltip_enabled:
            set_tooltip(container, title, delay=0)

        return container

    def _load_cached_icon(self, unique_id: str) -> QPixmap | None:
        """Load a cached icon using PinManager with DPI awareness."""
        # Special handling for Recycle Bin, always generate fresh based on current state
        if KnownCLSID.RECYCLE_BIN in unique_id.upper():
            is_empty = self._recycle_bin_state.get("is_empty", True)
            return self._get_recycle_bin_icon(is_empty)

        # Normal apps use PinManager cache
        dpi = self.screen().devicePixelRatio() if self.screen() else 1.0
        return self._pin_manager.load_cached_icon(unique_id, self._label_icon_size, dpi)

    def _on_recycle_bin_update(self, info: dict) -> None:
        """Update pinned Recycle Bin icons when bin state changes."""
        try:
            is_empty = info.get("num_items", 0) == 0
            self._recycle_bin_state["is_empty"] = is_empty

            # Generate fresh icon for current state
            icon = self._get_recycle_bin_icon(is_empty)
            if not icon:
                return

            # Find and update all Recycle Bin widgets
            recycle_bin_guid = KnownCLSID.RECYCLE_BIN
            for widget in self._hwnd_to_widget.values():
                uid = widget.property("unique_id")
                if uid and recycle_bin_guid in uid.upper():
                    icon_label = self._get_icon_label(widget)
                    if icon_label:
                        icon_label.setPixmap(icon)

        except Exception as e:
            logging.error(f"Error in _on_recycle_bin_update: {e}")

    def _get_recycle_bin_icon(self, is_empty: bool) -> QPixmap | None:
        """Get Recycle Bin icon from Windows stock icons with caching."""
        try:
            # Use a special cache key for Recycle Bin: ("RECYCLE_BIN", is_empty, dpi)
            cache_key = ("RECYCLE_BIN", is_empty, self._dpi)

            # Check if icon is already cached
            if cache_key in self._icon_cache:
                return self._icon_cache[cache_key]

            # Get stock icon (31 = empty, 32 = full)
            icon_img = get_stock_icon(31 if is_empty else 32)
            if not icon_img:
                return None

            dpi = self._dpi
            target_size = int(self._label_icon_size * dpi)
            icon_img = icon_img.resize((target_size, target_size), Image.LANCZOS).convert("RGBA")

            # Convert to QPixmap
            qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            pixmap.setDevicePixelRatio(dpi)

            # Cache the pixmap for future use
            self._icon_cache[cache_key] = pixmap

            return pixmap

        except Exception as e:
            logging.error(f"Error getting recycle bin icon: {e}")
            return None

    def _rbin_monitor_start(self):
        """Start monitoring recycle bin changes."""
        try:
            # Only subscribe if not already subscribed
            if not hasattr(self, "rbin_monitor") or self.rbin_monitor is None:
                self.rbin_monitor = RecycleBinMonitor.get_instance()
                self.rbin_monitor.subscribe(id(self))  # Register this widget as a subscriber
                self.rbin_monitor.bin_updated.connect(self._on_recycle_bin_update, Qt.ConnectionType.UniqueConnection)
        except Exception as e:
            logging.error(f"Error subscribing to recycle bin: {e}")

    def _rbin_monitor_stop(self):
        """Stop monitoring recycle bin changes."""
        try:
            if hasattr(self, "rbin_monitor") and self.rbin_monitor:
                self.rbin_monitor.bin_updated.disconnect(self._on_recycle_bin_update)
                self.rbin_monitor.unsubscribe(id(self))  # Unregister this widget
                self.rbin_monitor = None
        except Exception as e:
            logging.error(f"Error unsubscribing from recycle bin monitor: {e}")

    def show_preview_for_hwnd(self, hwnd: int, anchor_widget: QWidget) -> None:
        try:
            if self._preview_enabled and getattr(self, "_thumbnail_mgr", None):
                self._thumbnail_mgr.show_preview_for_hwnd(hwnd, anchor_widget)
        except Exception:
            pass

    def hide_preview(self) -> None:
        try:
            if getattr(self, "_thumbnail_mgr", None):
                self._thumbnail_mgr.hide_preview()
        except Exception:
            pass

    def showEvent(self, event):
        try:
            super().showEvent(event)
        except Exception:
            pass

        # Cache the DPI when widget is first shown and properly connected to screen
        if self._dpi is None:
            try:
                self._dpi = self.screen().devicePixelRatio() if self.screen() else 1.0
            except Exception:
                self._dpi = 1.0

        # Load and display pinned apps FIRST
        # This ensures pinned apps appear before running windows are added
        try:
            if not getattr(self, "_pinned_apps_displayed", False):
                # Load pinned apps (global across all monitors)
                self._load_pinned_apps()
                self._display_pinned_apps()
                self._pinned_apps_displayed = True
        except Exception as e:
            logging.error(f"Error displaying pinned apps: {e}")

        # Connect to task manager AFTER pinned apps are displayed
        # This ensures running windows are inserted in the correct position
        try:
            if connect_taskbar and not getattr(self, "_task_manager_connected", False):
                try:
                    self._task_manager = connect_taskbar(self)
                    self._task_manager_connected = True
                except Exception as e:
                    logging.error(f"Failed to connect taskbar manager from showEvent: {e}")
        except Exception:
            pass

        try:
            if not self._hwnd_to_widget and not self._pin_manager.pinned_apps and self._hide_empty:
                QTimer.singleShot(0, self._hide_taskbar_widget)
        except Exception:
            pass

    def _on_pinned_apps_changed_signal(self, action: str, unique_id: str) -> None:
        """Handle pinned apps changes from other taskbar instances."""
        try:
            # Reload the file to get the latest data
            self._load_pinned_apps()

            if action == "pin":
                # Start monitoring if Recycle Bin is being pinned
                if KnownCLSID.RECYCLE_BIN in unique_id.upper():
                    self._rbin_monitor_start()

                # Display pinned app (pinned apps are global across all monitors)
                if unique_id in self._pin_manager.pinned_apps:
                    metadata = self._pin_manager.pinned_apps[unique_id]

                    # Check if we have a running window that matches this unique_id
                    found_running = False
                    for hwnd, widget in self._hwnd_to_widget.items():
                        if hwnd > 0:  # Real window (not pseudo)
                            # Get unique_id for this window - use full as_dict() to include process_pid and process_path
                            window_data = {"process_name": "", "title": ""}
                            if (
                                hasattr(self, "_task_manager")
                                and self._task_manager
                                and hwnd in self._task_manager._windows
                            ):
                                app_window = self._task_manager._windows[hwnd]
                                window_data = app_window.as_dict()

                            window_unique_id, _ = self._get_app_identifier(hwnd, window_data)
                            if window_unique_id == unique_id:
                                # This window matches the pinned app
                                self._pin_manager.running_pinned[hwnd] = unique_id
                                self._update_pinned_status(hwnd, is_pinned=True)
                                found_running = True

                                # Move the widget to the correct position (after all pinned apps)
                                self._widget_container_layout.removeWidget(widget)

                                # Find the position to insert: after all pinned apps
                                insert_pos = 0
                                count = self._widget_container_layout.count()
                                for i in range(count):
                                    w = self._widget_container_layout.itemAt(i).widget()
                                    if not w:
                                        continue
                                    w_hwnd = w.property("hwnd")
                                    # Count all pinned apps (both running and pinned-only)
                                    if w_hwnd and w_hwnd < 0:  # Pinned-only
                                        insert_pos = i + 1
                                    elif (
                                        w_hwnd and w_hwnd > 0 and w_hwnd in self._pin_manager.running_pinned
                                    ):  # Running pinned
                                        # Don't count the current widget we're moving
                                        if w_hwnd != hwnd:
                                            insert_pos = i + 1

                                self._widget_container_layout.insertWidget(insert_pos, widget)
                                break

                    if not found_running:
                        # App is not running, create pinned-only button
                        # Check if already displayed using direct lookup
                        already_displayed = False
                        count = self._widget_container_layout.count()
                        for i in range(count):
                            w = self._widget_container_layout.itemAt(i).widget()
                            if w and w.property("unique_id") == unique_id:
                                already_displayed = True
                                break

                        if not already_displayed:
                            # Create the pinned button
                            pseudo_hwnd = -(abs(hash(unique_id)) % 1000000000 + 1000000000)
                            title = metadata.get("title", "App")
                            icon = self._load_cached_icon(unique_id)

                            container = self._create_pinned_app_container(title, icon, pseudo_hwnd, unique_id)
                            self._hwnd_to_widget[pseudo_hwnd] = container

                            # Find the position to insert: after all pinned apps
                            insert_pos = self._find_insert_position_after_pinned()

                            # Add with animation if enabled
                            if self._animation["enabled"]:
                                container.setFixedWidth(0)
                                self._widget_container_layout.insertWidget(insert_pos, container)
                                self._animate_container(
                                    container,
                                    start_width=0,
                                    end_width=container.sizeHint().width(),
                                    duration=ANIMATION_DURATION_MS,
                                    hwnd=pseudo_hwnd,
                                )
                            else:
                                self._widget_container_layout.insertWidget(insert_pos, container)

                            # Show taskbar if it was hidden and hide_empty is enabled
                            if self._hide_empty and len(self._hwnd_to_widget) > 0:
                                self._show_taskbar_widget()

            elif action == "unpin":
                # Stop monitoring if Recycle Bin is being unpinned
                if KnownCLSID.RECYCLE_BIN in unique_id.upper():
                    self._rbin_monitor_stop()

                # Remove the pinned-only button if it exists (pseudo hwnd < 0)
                for pseudo_hwnd, widget in list(self._hwnd_to_widget.items()):
                    if pseudo_hwnd < 0 and widget.property("unique_id") == unique_id:
                        self._hwnd_to_widget.pop(pseudo_hwnd)
                        self._widget_container_layout.removeWidget(widget)
                        widget.deleteLater()
                        break

                # Also update running apps - remove pinned status
                for hwnd in list(self._pin_manager.running_pinned.keys()):
                    if self._pin_manager.running_pinned.get(hwnd) == unique_id:
                        self._pin_manager.running_pinned.pop(hwnd)
                        self._update_pinned_status(hwnd, is_pinned=False)

                # Check if taskbar should be hidden after unpinning
                if self._hide_empty and len(self._hwnd_to_widget) < 1 and not self._pending_pinned_recreations:
                    self._hide_taskbar_widget()

            elif action == "reorder":
                # Rebuild the entire layout in the new order

                # Collect all current widgets (both pinned and running)
                current_widgets = {}  # unique_id or hwnd -> widget

                count = self._widget_container_layout.count()
                for i in range(count):
                    widget = self._widget_container_layout.itemAt(i).widget()
                    if not widget:
                        continue

                    hwnd = widget.property("hwnd")
                    if hwnd and hwnd < 0:  # Pinned-only button
                        unique_id = widget.property("unique_id")
                        if unique_id:
                            current_widgets[unique_id] = widget
                    elif hwnd and hwnd > 0:  # Running app
                        # Check if it's a running pinned app
                        unique_id = self._pin_manager.running_pinned.get(hwnd)
                        if unique_id:
                            current_widgets[unique_id] = widget
                        else:
                            # Not pinned, keep at current position for now
                            pass

                # Remove all widgets from layout (but don't delete them yet)
                while self._widget_container_layout.count():
                    item = self._widget_container_layout.takeAt(0)
                    if item and item.widget():
                        item.widget().setParent(None)

                # Re-add widgets in the new order from pinned_order (global order for all monitors)
                for unique_id in self._pin_manager.pinned_order:
                    if unique_id not in self._pin_manager.pinned_apps:
                        continue

                    metadata = self._pin_manager.pinned_apps[unique_id]

                    # Check if we already have a widget for this app
                    if unique_id in current_widgets:
                        # Re-add existing widget
                        self._widget_container_layout.addWidget(current_widgets[unique_id])
                    else:
                        # Need to create new widget (shouldn't happen often)
                        self._create_pinned_app_button(unique_id, metadata)

                # Re-add unpinned running apps at the end
                for hwnd, widget in self._hwnd_to_widget.items():
                    if hwnd > 0 and hwnd not in self._pin_manager.running_pinned:
                        # This is a running unpinned app
                        if widget.parent() is None:  # Not yet added back
                            self._widget_container_layout.addWidget(widget)

        except Exception as e:
            logging.error(f"Error handling pinned apps signal: {e}")

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
                self._remove_window_ui(hwnd, window_data, immediate=True)
            return
        if hwnd not in self._window_buttons:
            self._add_window_ui(hwnd, window_data)
        else:
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
                    self._remove_window_ui(hwnd, window_data, immediate=True)
        else:
            # If not monitor exclusive, treat as regular update
            if hwnd not in self._window_buttons and self._should_show_window(hwnd, window_data):
                self._add_window_ui(hwnd, window_data)
            else:
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

    def _should_show_window(self, hwnd, window_data):
        """Determine if a window should be shown based on widget configuration"""
        title = window_data.get("title", "")
        if not title.strip():
            return False

        proc = window_data.get("process_name")
        if proc is None:
            return False

        if self._monitor_exclusive:
            window_monitor = window_data.get("monitor_handle")
            # If monitor is unknown (transient), keep existing items but do not add new ones
            if window_monitor is None:
                return hwnd in self._window_buttons
            widget_monitor = self._get_widget_monitor_handle()
            if widget_monitor is not None and window_monitor != widget_monitor:
                return False

        return True

    def _add_window_ui(self, hwnd, window_data):
        """Add window UI element"""
        if self._suspend_updates:
            return

        # Skip if window is already added (prevents duplicate calls)
        if hwnd in self._window_buttons:
            return

        # Check if this is a pinned app
        unique_id, _ = self._get_app_identifier(hwnd, window_data)

        # Pinned apps are global across all monitors
        is_pinned = unique_id in self._pin_manager.pinned_apps

        # If pinned app is starting, remove its pinned-only button and track position
        insert_position = -1
        if is_pinned:
            # Try to find and replace an existing pinned-only button
            found_pinned_button = False
            for pseudo_hwnd, widget in list(self._hwnd_to_widget.items()):
                if pseudo_hwnd < 0 and widget.property("unique_id") == unique_id:
                    insert_position = self._get_hwnd_position(pseudo_hwnd)

                    # Animate removal of pinned-only button if animation is enabled
                    if self._animation["enabled"]:
                        # Cancel any existing animation
                        if pseudo_hwnd in self._animating_widgets:
                            self._animating_widgets.pop(pseudo_hwnd).stop()
                        # Animate shrinking
                        self._animate_container(
                            widget, start_width=widget.width(), end_width=0, duration=ANIMATION_DURATION_MS
                        )
                    else:
                        self._widget_container_layout.removeWidget(widget)
                        widget.deleteLater()

                    del self._hwnd_to_widget[pseudo_hwnd]
                    found_pinned_button = True
                    break

            # If no pinned-only button found, app is already running
            if not found_pinned_button:
                # Find the position of any existing window of this app and insert after it
                last_position = -1
                for existing_hwnd, existing_widget in self._hwnd_to_widget.items():
                    if self._pin_manager.running_pinned.get(existing_hwnd) == unique_id:
                        last_position = self._get_hwnd_position(existing_hwnd)

                if last_position >= 0:
                    # Insert after the last window of this app
                    insert_position = last_position + 1
                elif unique_id in self._pin_manager.pinned_order:
                    # Only use pinned_order position if app is actually pinned on this screen
                    # (For monitor_exclusive mode, is_pinned was already checked above)
                    if is_pinned:
                        desired_position = self._pin_manager.pinned_order.index(unique_id)
                        # Clamp to valid range - if out of range, add at the end
                        current_count = self._widget_container_layout.count()
                        if desired_position <= current_count:
                            insert_position = desired_position
                        # else: leave insert_position as -1 to add at the end

            # Only track as running pinned app if it's pinned on this screen
            self._pin_manager.running_pinned[hwnd] = unique_id

        # Clean up any existing widget/animation for this hwnd
        if hwnd in self._animating_widgets:
            self._animating_widgets.pop(hwnd).stop()
        if hwnd in self._hwnd_to_widget:
            old = self._hwnd_to_widget.pop(hwnd)
            self._widget_container_layout.removeWidget(old)
            old.deleteLater()
        self._window_buttons.pop(hwnd, None)

        # Create the window widget
        title = window_data.get("title", "")
        process = window_data.get("process_name", "")
        icon = self._get_app_icon(hwnd, title if process == "explorer.exe" else "")
        self._window_buttons[hwnd] = (title, icon, hwnd, process)

        container = self._create_app_container(title, icon, hwnd)
        self._hwnd_to_widget[hwnd] = container

        if is_pinned:
            container.setProperty("pinned", True)
            container.setProperty("unique_id", unique_id)
            container.setProperty("class", container.property("class") + " pinned")

        # Insert widget: pinned apps replace their button, unpinned apps go at the end
        position = insert_position if insert_position >= 0 else self._widget_container_layout.count()

        if self._animation["enabled"]:
            container.setFixedWidth(0)
            self._widget_container_layout.insertWidget(position, container)
            self._animate_container(
                container,
                start_width=0,
                end_width=container.sizeHint().width(),
                duration=ANIMATION_DURATION_MS,
                hwnd=hwnd,
            )
        else:
            self._widget_container_layout.insertWidget(position, container)

        if self._hide_empty and len(self._hwnd_to_widget) > 0:
            self._show_taskbar_widget()

    def _remove_window_ui(self, hwnd, window_data, *, immediate: bool = False):
        """Remove window UI element."""
        if self._suspend_updates:
            return

        # Cancel any running animation
        if hwnd in self._animating_widgets:
            self._animating_widgets.pop(hwnd).stop()
            immediate = True

        # Stop any flashing animation
        self._stop_flashing_animation(hwnd)

        # Check if this is a pinned app that needs to be replaced with pinned-only button
        unique_id = self._pin_manager.running_pinned.pop(hwnd, None)
        is_pinned = unique_id and unique_id in self._pin_manager.pinned_apps
        # If process_name is None and it's not a pinned app, just remove immediately
        # Some apps like Nvidia App send remove events with no process info when they close
        if window_data and window_data.get("process_name") is None and not is_pinned:
            widget = self._hwnd_to_widget.pop(hwnd, None)
            if widget:
                self._widget_container_layout.removeWidget(widget)
                widget.deleteLater()
            self._window_buttons.pop(hwnd, None)
            return

        # Save the current position BEFORE removing the widget
        # This ensures pinned button goes back to exact same spot
        current_position = self._get_hwnd_position(hwnd) if is_pinned else -1

        # Remove the widget
        widget = self._hwnd_to_widget.pop(hwnd, None)
        if widget:
            if self._animation["enabled"] and not immediate:
                self._animate_container(widget, start_width=widget.width(), end_width=0)
            else:
                self._widget_container_layout.removeWidget(widget)
                widget.deleteLater()

        self._window_buttons.pop(hwnd, None)

        # If pinned app closed, recreate its pinned-only button
        # Only recreate if NO other windows of this app are still running
        if is_pinned:
            # Check if any other windows of the same app are still running
            other_windows_exist = unique_id in self._pin_manager.running_pinned.values()

            if not other_windows_exist and unique_id not in self._pending_pinned_recreations:
                # Recreate pinned button (pinned apps are global across all monitors)
                # Use the position where the window was removed from
                # This preserves the exact layout position
                position = current_position if current_position >= 0 else -1

                if position >= 0:
                    # Mark as pending to prevent duplicate scheduling
                    self._pending_pinned_recreations.add(unique_id)
                    delay = ANIMATION_DURATION_MS if self._animation["enabled"] and not immediate else 0
                    QTimer.singleShot(
                        delay,
                        lambda uid=unique_id, pos=position: self._recreate_pinned_button(uid, pos),
                    )

        # Only hide taskbar if no widgets left AND no pending pinned recreations (from any previous events)
        if self._hide_empty and len(self._hwnd_to_widget) < 1 and not self._pending_pinned_recreations:
            self._hide_taskbar_widget()

    def _update_window_ui(self, hwnd, window_data):
        """Update window UI element (focused on the specific widget, no global sweep)."""
        if self._suspend_updates:
            return

        # Skip updates for Recycle Bin to prevent identity loss during navigation
        # unique_id = self._pin_manager.running_pinned.get(hwnd)
        # if unique_id and KnownCLSID.RECYCLE_BIN in unique_id.upper():
        #     return

        title = window_data.get("title", "")
        process = window_data.get("process_name", "")
        title_wrapper = None
        title_label = None
        # If process is explorer.exe (e.g. file explorer), we use the title for caching the icon.
        icon = self._get_app_icon(hwnd, title if process == "explorer.exe" else "")
        self._window_buttons[hwnd] = (title, icon, hwnd, process)

        # Direct lookup for the widget
        widget = self._hwnd_to_widget.get(hwnd)
        if widget is None:
            # Fallback scan once and store mapping
            count = self._widget_container_layout.count()
            for i in range(count):
                w = self._widget_container_layout.itemAt(i).widget()
                if w and w.property("hwnd") == hwnd:
                    widget = w
                    self._hwnd_to_widget[hwnd] = w
                    break
        if widget is None:
            return

        layout = widget.layout()
        if not layout:
            return

        # Check if window is flashing and start/stop animation accordingly
        is_flashing = window_data.get("is_flashing", False)
        if is_flashing and hwnd not in self._flashing_animation:
            # Start flashing animation
            self._start_flashing_animation(hwnd)
        elif not is_flashing and hwnd in self._flashing_animation:
            # Stop flashing animation if it's no longer flashing
            self._stop_flashing_animation(hwnd)

        # Update icon using helper method
        if icon:
            icon_label = self._get_icon_label(widget)
            if icon_label:
                icon_label.setPixmap(icon)

        try:
            if self._title_label["enabled"]:
                title_wrapper = self._get_title_wrapper(widget)
                title_label = self._get_title_label(title_wrapper)
                if title_label:
                    formatted_title = self._format_title(title)
                    if title_label.text() != formatted_title:
                        title_label.setText(formatted_title)
                if self._title_label["show"] == "focused" and title_wrapper:
                    if not self._context_menu_open:
                        desired_visible = self._get_title_visibility(hwnd)
                        if desired_visible != title_wrapper.isVisible():
                            self._animate_or_set_title_visible(title_wrapper, desired_visible)
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

        # Repolish the widget to apply any style changes
        try:
            widget.setProperty("class", self._get_container_class(hwnd))
            refresh_widget_style(widget, title_wrapper, title_label)
        except Exception:
            pass

        # Update the tooltip if enabled
        if self._tooltip and title:
            set_tooltip(widget, title, delay=0)

    def _refresh_title_visibility(self, hwnd: int) -> None:
        if not (self._title_label.get("enabled") and self._title_label.get("show") == "focused"):
            return
        container = self._hwnd_to_widget.get(hwnd)
        if not container:
            return
        title_wrapper = self._get_title_wrapper(container)
        if not title_wrapper:
            return
        desired_visible = self._get_title_visibility(hwnd)
        if desired_visible == title_wrapper.isVisible():
            return
        self._animate_or_set_title_visible(title_wrapper, desired_visible)
        try:
            layout = container.layout()
            if layout:
                layout.activate()
        except Exception:
            pass

    def _show_taskbar_widget(self):
        """Show the taskbar widget if hidden."""
        try:
            if self.isVisible():
                return
        except Exception:
            pass
        try:
            self.show()
        except Exception:
            pass

    def _hide_taskbar_widget(self):
        """Hide the taskbar widget and its preview if shown."""
        already_hidden = False
        try:
            already_hidden = self.isHidden()
        except Exception:
            pass
        if already_hidden:
            try:
                self.hide_preview()
            except Exception:
                pass
            return
        try:
            self.hide()
        except Exception:
            pass
        try:
            self.hide_preview()
        except Exception:
            pass

    def _stop_events(self) -> None:
        """Stop the task manager and clean up"""
        # Clean up any running animations
        for hwnd, animation in list(self._animating_widgets.items()):
            try:
                animation.stop()
                animation.deleteLater()
            except Exception:
                pass
        self._animating_widgets.clear()

        # Clean up preview via manager
        try:
            self._thumbnail_mgr.stop()
        except Exception:
            pass

        if hasattr(self, "_task_manager") and self._task_manager:
            try:
                self._task_manager.stop()
            except Exception as e:
                logging.error(f"Error stopping task manager: {e}")

    def _on_close_app(self) -> None:
        self.hide_preview()
        widget = QApplication.instance().widgetAt(QCursor.pos())
        if not widget:
            logging.warning("No widget found under cursor.")
            return

        hwnd = widget.property("hwnd")
        if not hwnd:
            logging.warning("No hwnd found for widget.")
            return

        # Don't close pinned-only buttons (negative hwnd = placeholder for pinned apps not running)
        if hwnd < 0:
            return

        # Check if the window is valid before attempting to close it
        if win32gui.IsWindow(hwnd):
            close_application(hwnd)
        else:
            logging.warning(f"Invalid window handle: {hwnd}, removing stale UI.")
            # Proactively remove any stale UI for this invalid handle
            try:
                self._remove_window_ui(hwnd, {}, immediate=True)
            except Exception:
                pass

    def _on_context_menu(self) -> None:
        """Handle context menu callback."""
        self.hide_preview()
        widget = QApplication.instance().widgetAt(QCursor.pos())
        if not widget:
            return

        hwnd = widget.property("hwnd")
        if not hwnd:
            return

        # Remove hover state from the button
        container = self._hwnd_to_widget.get(hwnd)
        if container:
            container.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
            container.update()

        self._show_context_menu(hwnd, QCursor.pos())

    def _show_context_menu(self, hwnd: int, pos) -> None:
        """Show context menu for a taskbar button."""
        menu = show_context_menu(self, hwnd, pos)
        if not menu:
            self._context_menu_open = False
            return

        self._context_menu_open = True

        def _handle_hide():
            self._context_menu_open = False
            if self._title_label.get("enabled") and self._title_label.get("show") == "focused":
                for taskbar_hwnd in list(self._hwnd_to_widget.keys()):
                    if taskbar_hwnd > 0:
                        self._refresh_title_visibility(taskbar_hwnd)
            else:
                self._refresh_title_visibility(hwnd)

        menu.aboutToHide.connect(_handle_hide)

    def _unpin_pinned_only_app(self, unique_id: str, pseudo_hwnd: int) -> None:
        """Unpin an app that's not currently running."""
        try:
            if unique_id in self._pin_manager.pinned_apps:
                # Directly remove from pinned apps data structures
                del self._pin_manager.pinned_apps[unique_id]
                self._pin_manager.pinned_order.remove(unique_id)
                self._pin_manager.delete_cached_icon(unique_id)
                self._pin_manager.save_pinned_apps()

                # Notify other taskbar instances
                PinManager.get_signal_bus().pinned_apps_changed.emit("unpin", unique_id)

                # Remove the widget from this taskbar
                widget = self._hwnd_to_widget.pop(pseudo_hwnd, None)
                if widget:
                    try:
                        self._widget_container_layout.removeWidget(widget)
                        widget.deleteLater()
                    except Exception:
                        pass

                # Check if taskbar should be hidden after unpinning
                if self._hide_empty and len(self._hwnd_to_widget) < 1 and not self._pending_pinned_recreations:
                    self._hide_taskbar_widget()

        except Exception as e:
            logging.error(f"Error unpinning pinned-only app: {e}")

    def _get_title_visibility(self, hwnd: int) -> bool:
        """Should title be visible when show=="focused"? Normalize to base owner."""
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

        # Create outer layout with no margins
        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Create inner content wrapper - this holds the actual content (icon + title)
        # and has shadow effects applied, while the outer container handles animations
        content_wrapper = QFrame()

        # Apply shadow effect to content wrapper
        add_shadow(content_wrapper, self._label_shadow)

        content_layout = QHBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        icon_label = QLabel()
        icon_label.setProperty("class", "app-icon")
        try:
            icon_label.setFixedSize(self._label_icon_size, self._label_icon_size)
        except Exception:
            pass
        if icon is not None:
            icon_label.setPixmap(icon)
        icon_label.setProperty("hwnd", hwnd)
        content_layout.addWidget(icon_label)

        if self._title_label["enabled"]:
            # Wrap the label to animate only wrapper width and reduce reflow
            title_wrapper = QFrame()
            title_wrapper.setProperty("hwnd", hwnd)
            tw_layout = QHBoxLayout(title_wrapper)
            tw_layout.setContentsMargins(0, 0, 0, 0)
            tw_layout.setSpacing(0)
            try:
                title_wrapper.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            except Exception:
                pass

            title_label = QLabel(self._format_title(title))
            title_label.setProperty("class", "app-title")
            title_label.setProperty("hwnd", hwnd)
            try:
                title_label.setSizePolicy(QSizePolicy.Policy.Preferred, title_label.sizePolicy().verticalPolicy())
            except Exception:
                pass

            tw_layout.addWidget(title_label)
            content_layout.addWidget(title_wrapper)

            if self._title_label["show"] == "focused":
                initial_visible = self._get_title_visibility(hwnd)
                title_wrapper.setVisible(initial_visible)
                if not initial_visible:
                    try:
                        title_wrapper.setMaximumWidth(0)
                    except Exception:
                        pass

        # Add content wrapper to outer container
        outer_layout.addWidget(content_wrapper)

        if self._tooltip:
            set_tooltip(container, title, delay=0)

        return container

    def _start_flashing_animation(self, hwnd: int):
        """Start flashing animation for a window using AnimationManager."""
        widget = self._hwnd_to_widget.get(hwnd)
        if not widget:
            return

        # Track that this hwnd is flashing
        self._flashing_animation[hwnd] = True
        AnimationManager.start_animation(
            widget, animation_type="fadeInOut", animation_duration=800, repeat_interval=2000, timeout=14000
        )

    def _stop_flashing_animation(self, hwnd: int):
        """Stop flashing animation for a window."""
        if hwnd in self._flashing_animation:
            self._flashing_animation.pop(hwnd)
            widget = self._hwnd_to_widget.get(hwnd)
            if widget:
                AnimationManager.stop_animation(widget)

    def _get_container_class(self, hwnd: int) -> str:
        """Get CSS class for the app container based on window active and flashing status."""
        base_class = "app-container"

        # Check if window is active using task manager data
        if hasattr(self, "_task_manager") and self._task_manager and hwnd in self._task_manager._windows:
            app_window = self._task_manager._windows[hwnd]

            # Check for flashing state first (flashing takes priority over active)
            if hasattr(app_window, "is_flashing") and app_window.is_flashing:
                return f"{base_class} flashing"

            # Then check for active state
            if hasattr(app_window, "is_active") and app_window.is_active:
                return f"{base_class} foreground"

        # Fallback to GetForegroundWindow check
        if hwnd == win32gui.GetForegroundWindow():
            return f"{base_class} foreground"

        # Not active, not flashing - just running
        return f"{base_class} running"

    def _get_app_icon(self, hwnd: int, title: str) -> QPixmap | None:
        """Return a QPixmap for the given window handle, using a DPI-aware cache."""
        try:
            # Check if this is a Recycle Bin window - use monitored state instead of window icon
            unique_id = self._pin_manager.running_pinned.get(hwnd)
            if unique_id and KnownCLSID.RECYCLE_BIN in unique_id.upper():
                # Use the cached icon based on Recycle Bin monitor's state
                is_empty = self._recycle_bin_state.get("is_empty", True)
                return self._get_recycle_bin_icon(is_empty)

            cache_key = (hwnd, title, self._dpi)
            if cache_key in self._icon_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                icon_img = get_window_icon(hwnd)
                if icon_img:
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
        if active:
            self.hide_preview()

    def bring_to_foreground(self, hwnd):
        """Bring the specified window to the foreground, restoring if minimized. For pinned apps, launch them."""
        # Stop flashing animation if this window was flashing
        if hwnd > 0:  # Only for real windows (not pinned apps)
            self._stop_flashing_animation(hwnd)

        # Add click animation feedback
        if self._animation["enabled"] and not self._suspend_updates:
            widget = self._hwnd_to_widget.get(hwnd)
            if widget:
                try:
                    AnimationManager.animate(widget, "fadeInOut", 200)
                except Exception:
                    pass

        # Check if this is a pinned app that's not running (negative hwnd)
        if hwnd < 0:
            self._launch_pinned_app(hwnd)
            return

        if not win32gui.IsWindow(hwnd):
            return
        try:
            self.hide_preview()

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
                set_foreground(base)
                try:
                    QTimer.singleShot(0, lambda h=focus_target or base: set_foreground(h))
                except Exception:
                    pass
                return

            if is_active and can_minimize(base):
                minimize_window(base)
                return

            show_window(base)
            set_foreground(base)

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

    def _launch_pinned_app(self, unique_id_or_hwnd: int | str, extra_arguments: str = "") -> None:
        """Launch a pinned application using PinManager with optional extra arguments."""
        try:
            # Determine if we received unique_id (str) or pseudo_hwnd (int)
            if isinstance(unique_id_or_hwnd, str):
                unique_id = unique_id_or_hwnd
            else:
                # It's a pseudo_hwnd, look up the widget
                widget = self._hwnd_to_widget.get(unique_id_or_hwnd)
                if not widget:
                    return
                unique_id = widget.property("unique_id")
                if not unique_id:
                    return

            # Launch using PinManager with optional arguments
            self._pin_manager.launch_pinned_app(unique_id, extra_arguments=extra_arguments)
        except Exception as e:
            logging.error(f"Error launching pinned app: {e}")

    def ensure_foreground(self, hwnd):
        """When we use dragging file ensure the window is in foreground."""
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
            count = self._widget_container_layout.count()
            for i in range(count):
                w = self._widget_container_layout.itemAt(i).widget()
                if not w:
                    continue
                hwnd = w.property("hwnd")

                # Skip pinned-not-running apps (negative hwnd)
                if hwnd and hwnd < 0:
                    continue

                # Base class for running apps
                new_cls = "app-container running"

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
                        title_wrapper = self._get_title_wrapper(w)
                        if title_wrapper:
                            want_visible = target_hwnd is not None and hwnd == target_hwnd
                            if title_wrapper.isVisible() != want_visible:
                                self._animate_or_set_title_visible(title_wrapper, want_visible)
                                try:
                                    w.layout().activate()
                                except Exception:
                                    pass
                    refresh_widget_style(w)
        except Exception:
            pass

    def _get_icon_label(self, container: QWidget) -> QLabel | None:
        """Get the icon label widget from a container, navigating through the content_wrapper structure."""
        try:
            if not container:
                return None
            outer_layout = container.layout()
            if not outer_layout or outer_layout.count() < 1:
                return None
            # Get content_wrapper (first child of outer_layout)
            content_wrapper = outer_layout.itemAt(0).widget()
            if not content_wrapper:
                return None
            content_layout = content_wrapper.layout()
            if content_layout and content_layout.count() > 0:
                icon_label = content_layout.itemAt(0).widget()
                if isinstance(icon_label, QLabel):
                    return icon_label
        except Exception:
            pass
        return None

    def _get_title_wrapper(self, container: QWidget) -> QWidget | None:
        """Get the title wrapper widget from a container, navigating through the content_wrapper structure."""
        try:
            if not container:
                return None
            outer_layout = container.layout()
            if not outer_layout or outer_layout.count() < 1:
                return None
            # Get content_wrapper (first child of outer_layout)
            content_wrapper = outer_layout.itemAt(0).widget()
            if not content_wrapper:
                return None
            content_layout = content_wrapper.layout()
            if content_layout and content_layout.count() > 1:
                title_wrapper = content_layout.itemAt(1).widget()
                if isinstance(title_wrapper, QWidget):
                    return title_wrapper
        except Exception:
            pass
        return None

    def _get_title_label(self, container: QWidget) -> QLabel | None:
        try:
            lay = container.layout()
            if lay and lay.count() > 0:
                lbl = lay.itemAt(0).widget()
                if isinstance(lbl, QLabel):
                    return lbl
        except Exception:
            pass
        return None

    def _animate_container(self, container, start_width=0, end_width=0, duration=300, hwnd=None) -> None:
        """Animate the width of a container widget."""
        animation = QPropertyAnimation(container, b"maximumWidth", container)
        animation.setStartValue(start_width)
        animation.setEndValue(end_width)
        animation.setDuration(duration)

        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        # Track animation for add operations
        if hwnd is not None and end_width > start_width:
            self._animating_widgets[hwnd] = animation

        def on_finished():
            # Remove from tracking if this was an add animation
            if hwnd is not None:
                self._animating_widgets.pop(hwnd, None)

            if end_width == 0:
                container.setParent(None)
                self._widget_container_layout.removeWidget(container)
                container.deleteLater()

                # Check if we should hide taskbar after animation completes
                # Don't hide if there are pending pinned recreations scheduled
                if self._hide_empty and len(self._hwnd_to_widget) < 1 and not self._pending_pinned_recreations:
                    self._hide_taskbar_widget()
            else:
                # Clear width constraint so future content changes (e.g., focused title)
                try:
                    container.setMaximumWidth(16777215)
                    container.adjustSize()
                    container.updateGeometry()
                except Exception:
                    pass

        animation.finished.connect(on_finished)
        animation.start()

    def _animate_or_set_title_visible(self, label: QWidget, visible: bool, duration: int = 200) -> None:
        """Animate the title label's width when toggling visibility."""
        try:
            if not self._animation["enabled"]:
                label.setVisible(visible)
                label.setMaximumWidth(16777215 if visible else 0)
                parent = label.parentWidget()
                if parent and parent.layout():
                    parent.layout().activate()
                return

            # Cancel any running animation on this label
            try:
                running = getattr(label, "_yasb_title_anim", None)
                if running is not None:
                    running.stop()
                    running.deleteLater()
            except Exception:
                pass

            start_width = label.maximumWidth() if label.maximumWidth() != 16777215 else label.width()
            end_width = label.sizeHint().width() if visible else 0

            # Ensure label is visible before animating in
            if visible and not label.isVisible():
                label.setVisible(True)

            anim = QPropertyAnimation(label, b"maximumWidth", label)
            anim.setStartValue(start_width)
            anim.setEndValue(end_width)
            anim.setDuration(duration)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

            def _finish():
                try:
                    if not visible:
                        label.setVisible(False)
                        label.setMaximumWidth(0)
                    else:
                        # Clear width constraint to allow natural resizing later
                        label.setMaximumWidth(16777215)
                    setattr(label, "_yasb_title_anim", None)
                    parent = label.parentWidget()
                    if parent and parent.layout():
                        parent.layout().activate()
                except Exception:
                    pass

            anim.finished.connect(_finish)
            setattr(label, "_yasb_title_anim", anim)
            anim.start()
        except Exception:
            # Fallback to immediate toggle
            try:
                label.setVisible(visible)
                if not visible:
                    label.setMaximumWidth(0)
                else:
                    label.setMaximumWidth(16777215)
                parent = label.parentWidget()
                if parent and parent.layout():
                    parent.layout().activate()
            except Exception:
                pass

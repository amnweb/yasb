"""Systray container widget and systray icon widget"""

import ctypes as ct
from ctypes import byref
from dataclasses import dataclass
from typing import override

from PyQt6.QtCore import (
    QMimeData,
    QPoint,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QMouseEvent,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
)
from win32con import (
    WM_LBUTTONDBLCLK,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
)

import core.utils.widgets.systray.utils as utils
from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.utils.widgets.systray.systray_monitor import IconData
from core.utils.widgets.systray.utils import pack_i32
from core.utils.win32.bindings import (
    AllowSetForegroundWindow,
    GetWindowThreadProcessId,
    IsWindow,
    SendNotifyMessage,
)
from core.utils.win32.constants import (
    NIN_CONTEXTMENU,
    NIN_SELECT,
)


@dataclass
class IconState:
    is_pinned: bool = False
    index: int = 0

    @staticmethod
    def from_dict(d: dict[str, str | bool | None]):
        state = IconState()
        state.is_pinned = bool(d["is_pinned"])
        state.index = int(str(d["index"]))
        return state


class IconWidget(QPushButton):
    pinned_changed = pyqtSignal(object)
    icon_moved = pyqtSignal(object)
    pin_modifier_key = Qt.KeyboardModifier.AltModifier
    icon_size = 16
    enable_tooltips = True
    _drag_in_progress = False

    def __init__(self):
        super().__init__()
        self.data: IconData | None = None
        self.last_cursor_pos = QPoint()
        self.setProperty("class", "button")
        self.setIconSize(QSize(self.icon_size, self.icon_size))
        self.scaled_pixmap = None
        self.is_pinned = False
        self.lmb_pressed = False
        self.ignore_next_release = False

    def update_scaled_pixmap(self):
        """Pre-compute the scaled pixmap."""
        if self.data is not None and self.data.icon_image is not None:
            self.scaled_pixmap = self.data.icon_image.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.scaled_pixmap = None

    @override
    def mousePressEvent(self, e: QMouseEvent | None) -> None:
        if e is None:
            return
        mouse_button = e.button()
        if mouse_button == Qt.MouseButton.LeftButton:
            self.last_cursor_pos = e.pos()
            if e.modifiers() & self.pin_modifier_key:
                self.pinned_changed.emit(self)
            else:
                self.lmb_pressed = True
                self.update_scaled_pixmap()
        return super().mousePressEvent(e)

    @override
    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is None:
            return super().mouseMoveEvent(a0)

        # Only start drag if left mouse button is pressed and moved more than 10 pixels
        if self.lmb_pressed and (a0.pos() - self.last_cursor_pos).manhattanLength() > 10:
            IconWidget._drag_in_progress = True
            # Dim the icon while it is being dragged
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.3)
            self.setGraphicsEffect(effect)
            try:
                drag = QDrag(self)
                if self.scaled_pixmap is not None:
                    drag.setPixmap(self.scaled_pixmap)
                mime_data = QMimeData()
                mime_data.setText(self.text())
                drag.setMimeData(mime_data)
                result = drag.exec(Qt.DropAction.MoveAction)
                if result == Qt.DropAction.IgnoreAction:
                    # Drag was cancelled when dropped outside
                    # of any valid drop target notify parent
                    parent = self.parent()
                    if isinstance(parent, DropWidget):
                        parent.drag_ended.emit()
            finally:
                self.setGraphicsEffect(None)
                self.lmb_pressed = False
                IconWidget._drag_in_progress = False

        return super().mouseMoveEvent(a0)

    @override
    def mouseReleaseEvent(self, e: QMouseEvent | None) -> None:
        if e is None:
            return super().mouseReleaseEvent(e)
        if self.ignore_next_release:
            self.ignore_next_release = False
            return super().mouseReleaseEvent(e)
        self.lmb_pressed = False
        btn = e.button()
        if btn == Qt.MouseButton.LeftButton and (self.last_cursor_pos - e.pos()).manhattanLength() > 8:
            return super().mouseReleaseEvent(e)
        if btn == Qt.MouseButton.LeftButton:
            self.send_action(WM_LBUTTONDOWN)
            self.send_action(WM_LBUTTONUP)
        elif btn == Qt.MouseButton.RightButton:
            self.send_action(WM_RBUTTONDOWN)
            self.send_action(WM_RBUTTONUP)
        elif btn == Qt.MouseButton.MiddleButton:
            self.send_action(WM_MBUTTONDOWN)
            self.send_action(WM_MBUTTONUP)
        return super().mouseReleaseEvent(e)

    @override
    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is None:
            return super().mouseDoubleClickEvent(a0)
        self.ignore_next_release = True
        self.send_action(WM_LBUTTONDBLCLK)
        return super().mouseDoubleClickEvent(a0)

    def send_action(self, action: int):
        """Send a mouse action to the tray icon process"""
        if self.data is None or not IsWindow(self.data.hWnd):
            return

        is_mouse_click = action in {
            WM_LBUTTONDOWN,
            WM_RBUTTONDOWN,
            WM_MBUTTONDOWN,
            WM_LBUTTONUP,
            WM_RBUTTONUP,
            WM_MBUTTONUP,
            WM_LBUTTONDBLCLK,
        }
        if is_mouse_click:
            process_id = ct.c_ulong(0)
            GetWindowThreadProcessId(self.data.hWnd, byref(process_id))
            AllowSetForegroundWindow(process_id.value)
        self.send_notify_message(action)

        if self.data.uVersion >= 3:
            if action == WM_LBUTTONUP:
                self.send_notify_message(NIN_SELECT)
            elif action == WM_RBUTTONUP:
                self.send_notify_message(NIN_CONTEXTMENU)
            else:
                return

    def send_notify_message(self, message: int):
        """Send a notify message to the tray icon process"""
        if self.data is None or self.data.uCallbackMessage == 0:
            return
        if self.data.uVersion > 3:
            cursor_pos = utils.cursor_position()
            wparam = pack_i32(cursor_pos[0], cursor_pos[1])
            lparam = pack_i32(message, self.data.uID)
        else:
            wparam = self.data.uID
            lparam = pack_i32(message, 0)
        # NOTE: Some icons (Epic Games Store) fail to receive the message if the app was already
        # present before the system tray widget was created. No idea why.
        SendNotifyMessage(self.data.hWnd, self.data.uCallbackMessage, wparam, lparam)

    def update_icon(self):
        """Update the icon and tooltip of the icon widget"""
        if not self.data or self.data.hIcon == 0:
            return
        if self.enable_tooltips:
            set_tooltip(self, self.data.szTip or self.data.exe, delay=50)
        icon = self.data.icon_image
        if icon:
            self.setIcon(QIcon(icon))


class DropWidget(QFrame):
    """Drop target container for systray icons."""

    drag_started = pyqtSignal(int)
    drag_ended = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, *, grid_cols: int = 0):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._grid_cols = grid_cols

        if grid_cols > 0:
            self.main_layout = QGridLayout(self)
        else:
            self.main_layout = QHBoxLayout(self)
            self.setMaximumHeight(32)

        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.dragged_button: IconWidget | None = None
        self._hover_btn: IconWidget | None = None

    @staticmethod
    def _set_class(widget: QWidget, name: str, add: bool):
        """Add or remove a CSS class and refresh the widget style."""
        cls = (widget.property("class") or "").split()
        if add:
            if name not in cls:
                cls.append(name)
        else:
            if name in cls:
                cls.remove(name)
        widget.setProperty("class", " ".join(cls))
        refresh_widget_style(widget)

    @override
    def dragEnterEvent(self, a0: QDragEnterEvent | None):
        if a0 is None:
            return
        source = a0.source()
        if isinstance(source, IconWidget):
            self.dragged_button = source
            self._set_class(source, "dragging", True)
            a0.acceptProposedAction()
            self.drag_started.emit(source.width())

    @override
    def dragMoveEvent(self, a0: QDragMoveEvent | None):
        if a0 is None or not isinstance(a0.source(), IconWidget):
            return
        hovered = self._find_icon_at(a0.position().toPoint())
        if isinstance(hovered, IconWidget) and hovered is not self.dragged_button:
            self._highlight_hover(hovered)
        else:
            self._clear_hover_highlight()
        a0.acceptProposedAction()
        self.drag_started.emit(self.dragged_button.width() if self.dragged_button else 0)

    @override
    def dragLeaveEvent(self, a0: QDragLeaveEvent | None):
        if a0 is None:
            return
        self._clear_hover_highlight()
        if self.dragged_button:
            self._set_class(self.dragged_button, "dragging", False)
            self.dragged_button = None

    @override
    def dropEvent(self, a0: QDropEvent | None):
        if a0 is None:
            return
        source = a0.source()
        if not isinstance(source, IconWidget):
            return
        self._set_class(source, "dragging", False)
        self._clear_hover_highlight()

        if self._grid_cols:
            self._drop_grid(source, a0)
        else:
            self._drop_inline(source, a0)

    def _drop_inline(self, source: IconWidget, a0: QDropEvent):
        drop_position = a0.position().toPoint()
        insert_index = self.get_insert_index(drop_position)

        button_current_index = -1
        for i in range(self.main_layout.count()):
            if (w := self.main_layout.itemAt(i)) and w.widget() == source:
                button_current_index = i
                break

        if source.parent() == self:
            if insert_index == button_current_index or insert_index == button_current_index + 1:
                a0.acceptProposedAction()
                self.drag_ended.emit()
                return
            if button_current_index != -1 and insert_index > button_current_index:
                insert_index -= 1
            self.main_layout.removeWidget(source)
        else:
            source.setParent(self)

        self.main_layout.insertWidget(insert_index, source)
        source.show()
        self.dragged_button = None
        a0.acceptProposedAction()
        self.drag_ended.emit()
        source.icon_moved.emit(source)

    def _drop_grid(self, source: IconWidget, a0: QDropEvent):
        icons = self._get_all_icons()
        hovered = self._find_icon_at(a0.position().toPoint())

        def _insert_index(target: IconWidget) -> int:
            """Return insert index: after target if cursor is on its right half."""
            idx = icons.index(target)
            if a0.position().toPoint().x() >= target.geometry().center().x():
                idx += 1
            return idx

        if source in icons:
            # Reorder within grid
            if isinstance(hovered, IconWidget) and hovered is not source and hovered in icons:
                icons.remove(source)
                idx = _insert_index(hovered)
                # Clamp after removal shifted indices
                idx = min(idx, len(icons))
                icons.insert(idx, source)
        else:
            # Cross-container drop (from pinned bar into grid)
            source.setParent(self)
            if isinstance(hovered, IconWidget) and hovered in icons:
                icons.insert(_insert_index(hovered), source)
            else:
                icons.append(source)

        self.relayout_grid(icons)
        self.dragged_button = None
        a0.acceptProposedAction()
        self.drag_ended.emit()
        source.icon_moved.emit(source)

    def get_insert_index(self, drop_position: QPoint) -> int:
        if self.main_layout.count() == 0:
            return 0
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if not item or not item.widget():
                continue
            if drop_position.x() < item.widget().geometry().center().x():
                return i
        return self.main_layout.count()

    def add_icon_to_grid(self, icon: IconWidget):
        count = len(self._get_all_icons())
        cols = self._grid_cols
        self.main_layout.addWidget(icon, count // cols, count % cols)

    def relayout_grid(self, icons: list[IconWidget] | None = None):
        if icons is None:
            icons = self._get_all_icons()
        layout = self.main_layout
        for icon in icons:
            layout.removeWidget(icon)
        for r in range(layout.rowCount()):
            layout.setRowMinimumHeight(r, 0)
            layout.setRowStretch(r, 0)
        for c in range(layout.columnCount()):
            layout.setColumnMinimumWidth(c, 0)
            layout.setColumnStretch(c, 0)
        cols = self._grid_cols
        for idx, icon in enumerate(icons):
            layout.addWidget(icon, idx // cols, idx % cols)
            icon.show()
        layout.invalidate()

    def _get_all_icons(self) -> list[IconWidget]:
        return [
            item.widget()
            for i in range(self.main_layout.count())
            if (item := self.main_layout.itemAt(i)) is not None
            and item.widget() is not None
            and isinstance(item.widget(), IconWidget)
        ]

    def _find_icon_at(self, pos: QPoint):
        w = self.childAt(pos)
        while w is not None and not isinstance(w, IconWidget):
            w = w.parentWidget()
        return w

    def _highlight_hover(self, btn: IconWidget):
        if self._hover_btn is btn:
            return
        self._clear_hover_highlight()
        self._hover_btn = btn
        self._set_class(btn, "drag-over", True)

    def _clear_hover_highlight(self):
        if self._hover_btn:
            self._set_class(self._hover_btn, "drag-over", False)
            self._hover_btn = None

    def set_drop_target_style(self, active: bool):
        """Show or hide a visual drop-target indicator on this container."""
        self._set_class(self, "drop-target", active)

    def refresh_styles(self):
        if self.dragged_button is not None:
            refresh_widget_style(self.dragged_button)

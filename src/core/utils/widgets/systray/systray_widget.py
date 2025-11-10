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

    def __init__(self):
        super().__init__()
        self.data: IconData | None = None
        self.last_cursor_pos = QPoint()
        self.setProperty("class", "button")
        self.setProperty("dragging", False)
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
            drag = QDrag(self)
            if self.scaled_pixmap is not None:
                drag.setPixmap(self.scaled_pixmap)
            mime_data = QMimeData()
            mime_data.setText(self.text())
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.MoveAction)

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
            set_tooltip(self, self.data.szTip or self.data.exe, delay=0)
        icon = self.data.icon_image
        if icon:
            self.setIcon(QIcon(icon))


class DropWidget(QFrame):
    drag_started = pyqtSignal()
    drag_ended = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        # Use a horizontal layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setMaximumHeight(32)
        self.setLayout(self.main_layout)

        # Create the drop indicator but don't add it to the layout
        self.drop_indicator = QFrame(self)
        self.drop_indicator.setFixedSize(4, 32)
        self.drop_indicator.setStyleSheet("background: #FF5500; border-radius: 2px;")
        self.drop_indicator.hide()

        # Track the dragged button
        self.dragged_button: IconWidget | None = None

        # Keep track of the indicator's position to avoid unnecessary updates
        self.current_indicator_index = -1

    @override
    def dragEnterEvent(self, a0: QDragEnterEvent | None):
        if a0 is None:
            return

        source = a0.source()
        if isinstance(source, IconWidget):
            self.dragged_button = source
            self.dragged_button.setProperty("dragging", True)
            self.refresh_styles()
            a0.acceptProposedAction()

            self.drag_started.emit()

    @override
    def dragMoveEvent(self, a0: QDragMoveEvent | None):
        if a0 is None or not isinstance(a0.source(), IconWidget):
            return

        drop_position = a0.position().toPoint()
        insert_index = self.get_insert_index(drop_position)

        # Only update indicator if position has changed
        if insert_index != self.current_indicator_index:
            self.update_drop_indicator(insert_index)
            self.current_indicator_index = insert_index

        a0.acceptProposedAction()

        self.drag_started.emit()

    @override
    def dragLeaveEvent(self, a0: QDragLeaveEvent | None):
        if a0 is None:
            return

        self.hide_drop_indicator()

        if self.dragged_button:
            self.dragged_button.setProperty("dragging", False)
            self.refresh_styles()
            self.dragged_button = None

        self.current_indicator_index = -1

    @override
    def dropEvent(self, a0: QDropEvent | None):
        if a0 is None:
            return

        source = a0.source()
        if not isinstance(source, IconWidget):
            return

        source.setProperty("dragging", False)
        self.refresh_styles()
        drop_position = a0.position().toPoint()
        insert_index = self.get_insert_index(drop_position)

        # Only move the button if it's coming from another parent or the position is different
        button_current_index = -1
        for i in range(self.main_layout.count()):
            if (w := self.main_layout.itemAt(i)) and w.widget() == source:
                button_current_index = i
                break

        # If the button is already in this layout
        if source.parent() == self:
            # If it would be placed at the same index or right after itself, do nothing
            if insert_index == button_current_index or insert_index == button_current_index + 1:
                self.hide_drop_indicator()
                a0.acceptProposedAction()
                self.drag_ended.emit()
                return

            # Adjust index if moving within the same parent and to a later position
            if button_current_index != -1 and insert_index > button_current_index:
                insert_index -= 1

            # Remove it from its current position
            self.main_layout.removeWidget(source)
        else:
            # Set this as the new parent
            source.setParent(self)

        # Insert at the new position
        self.main_layout.insertWidget(insert_index, source)

        # Show the button and update styles
        source.show()
        self.refresh_styles()

        # Hide the indicator and reset tracking
        self.hide_drop_indicator()
        self.dragged_button = None
        self.current_indicator_index = -1

        a0.acceptProposedAction()

        self.drag_ended.emit()

        source.icon_moved.emit(source)

    def get_insert_index(self, drop_position: QPoint) -> int:
        """
        Find the position in the layout to insert the button
        """
        # If there are no items, insert at the beginning
        if self.main_layout.count() == 0:
            return 0

        # Calculate insertion position based on mouse position relative to widgets
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if not item or not item.widget():
                continue

            widget = item.widget()
            if not widget:
                continue
            widget_center = widget.geometry().center().x()

            # If mouse is to the left of this widget's center, insert before it
            if drop_position.x() < widget_center:
                return i

        # If we get here, insert at the end
        return self.main_layout.count()

    def update_drop_indicator(self, index: int):
        """
        Update the drop indicator's position without removing/re-adding it to the layout.
        """
        self.drop_indicator.show()

        # Calculate the position for the indicator
        if self.main_layout.count() == 0:
            # If empty, position in the middle
            x = self.rect().center().x()
            self.drop_indicator.move(
                x - self.drop_indicator.width() // 2,
                (self.height() - self.drop_indicator.height()) // 2,
            )
        elif index >= self.main_layout.count():
            # Position after the last widget
            item = self.main_layout.itemAt(self.main_layout.count() - 1)
            if not item:
                return
            last_widget = item.widget()
            if last_widget:
                x = last_widget.geometry().right() + self.main_layout.spacing() // 2
                self.drop_indicator.move(
                    x - self.drop_indicator.width() // 2,
                    (self.height() - self.drop_indicator.height()) // 2,
                )
        else:
            # Position before the widget at the current index
            item = self.main_layout.itemAt(index)
            if not item:
                return
            widget = item.widget()
            if widget:
                x = widget.geometry().left() - self.main_layout.spacing() // 2
                self.drop_indicator.move(
                    x - self.drop_indicator.width() // 2,
                    (self.height() - self.drop_indicator.height()) // 2,
                )

    def hide_drop_indicator(self):
        """
        Hide the drop indicator without affecting the layout.
        """
        self.drop_indicator.hide()
        self.current_indicator_index = -1

    def refresh_styles(self):
        """
        Refresh styles for the widget and dragged button.
        """
        if self.dragged_button is not None:
            refresh_widget_style(self, self.dragged_button)

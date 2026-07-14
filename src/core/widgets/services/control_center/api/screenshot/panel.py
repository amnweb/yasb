"""Per-monitor freeze overlay panel."""

from typing import TYPE_CHECKING

import win32api
import win32con
import win32gui
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.widgets.services.control_center.api.screenshot.capture import ScreenFreeze
from core.widgets.services.control_center.api.screenshot.constants import HANDLE, UI

if TYPE_CHECKING:
    from core.widgets.services.control_center.api.screenshot.overlay import Overlay


class ScreenPanel(QWidget):
    """Freeze overlay on a single QScreen (widget geometry is logical)."""

    def __init__(self, freeze: ScreenFreeze, controller: Overlay):
        super().__init__()
        self.freeze = freeze
        self.ctrl = controller
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(freeze.geo)
        self._pin()

    def _pin(self) -> None:
        try:
            hwnd = int(self.winId())
            ex = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32api.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex | win32con.WS_EX_TOOLWINDOW)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    def _event_physical(self, e) -> QPoint:
        """Mouse -> Win32 physical pixels (selection / crop space)."""
        return self.ctrl.local_to_physical(self.freeze, e.position().toPoint())

    def _sel_local(self):
        """Physical selection -> this panel's local paint coordinates."""
        return self.ctrl.physical_to_local_rect(self.freeze, self.ctrl.sel)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_press(self._event_physical(e))

    def mouseMoveEvent(self, e):
        self.ctrl.on_move(self._event_physical(e))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_release(self._event_physical(e))

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_double_click()

    def keyPressEvent(self, e):
        self.ctrl.on_key(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.drawPixmap(0, 0, self.freeze.pixmap)

        dim = QColor(0, 0, 0, 120)
        local_geo = self.rect()
        r = self._sel_local()

        if r.isEmpty() and self.ctrl.sel.isEmpty():
            p.fillRect(local_geo, dim)
            return

        if r.isEmpty() or not r.intersects(local_geo):
            p.fillRect(local_geo, dim)
            return

        top = max(0, r.top())
        bottom = min(local_geo.height(), r.bottom() + 1)
        left = max(0, r.left())
        right = min(local_geo.width(), r.right() + 1)
        if top > 0:
            p.fillRect(0, 0, local_geo.width(), top, dim)
        if bottom < local_geo.height():
            p.fillRect(0, bottom, local_geo.width(), local_geo.height() - bottom, dim)
        if left > 0 and bottom > top:
            p.fillRect(0, top, left, bottom - top, dim)
        if right < local_geo.width() and bottom > top:
            p.fillRect(right, top, local_geo.width() - right, bottom - top, dim)

        p.setPen(QPen(QColor(UI["accent"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r.adjusted(0, 0, -1, -1))
        p.setBrush(QBrush(QColor(UI["accent"])))
        for hr in self.ctrl.handles_local_on(self):
            if hr.intersects(local_geo.adjusted(-HANDLE, -HANDLE, HANDLE, HANDLE)):
                p.drawRect(hr)
        # Badge on the panel that owns the physical top-left of the selection
        if self.freeze.physical.adjusted(-1, -1, 1, 1).contains(self.ctrl.sel.topLeft()):
            self.ctrl.draw_size_badge(p, r)

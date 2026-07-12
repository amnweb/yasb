"""Multi-monitor region select overlay (physical-pixel selection)."""

from PyQt6.QtCore import QObject, QPoint, QRect, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap

from core.widgets.services.control_center.api.screenshot.capture import ScreenFreeze
from core.widgets.services.control_center.api.screenshot.constants import (
    HANDLE,
    MIN_SIZE,
    SNAP,
    UI,
    export_pixmap,
)
from core.widgets.services.control_center.api.screenshot.crop import (
    crop_selection,
    local_to_physical,
    physical_to_local_rect,
)
from core.widgets.services.control_center.api.screenshot.editor import open_editor
from core.widgets.services.control_center.api.screenshot.panel import ScreenPanel
from core.widgets.services.control_center.api.screenshot.toolbar import ScreenshotToolbar


class Overlay(QObject):
    """Multi-monitor selector: one panel per screen, physical-pixel selection."""

    def __init__(self, freezes: list[ScreenFreeze]):
        super().__init__()
        if not freezes:
            raise ValueError("freezes must be non-empty")

        self._freezes = freezes
        # Selection is always in Win32 physical pixels (not Qt logical DIPs).
        self.sel = QRect()
        self.mode = None
        self.anchor = QPoint()
        self.origin_sel = QRect()
        self._toolbar: ScreenshotToolbar | None = None
        self._toolbar_host: ScreenPanel | None = None
        self._panels: list[ScreenPanel] = []
        self._editor = None
        self._exiting = False

        virt = freezes[0].physical
        for f in freezes[1:]:
            virt = virt.united(f.physical)
        self._virt = virt
        self._screen_phys = [QRect(f.physical) for f in freezes]

        for f in freezes:
            self._panels.append(ScreenPanel(f, self))

    def show(self) -> None:
        for p in self._panels:
            p.show()
            p.raise_()

    def activateWindow(self) -> None:
        if self._panels:
            self._panels[0].activateWindow()
            self._panels[0].setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def raise_(self) -> None:
        for p in self._panels:
            p.raise_()

    def close(self) -> None:
        self._exiting = True
        self._close_toolbar()
        for p in list(self._panels):
            try:
                p.close()
            except Exception:
                pass
        self._panels.clear()
        self.deleteLater()

    def local_to_physical(self, f: ScreenFreeze, local: QPoint) -> QPoint:
        return local_to_physical(f, local)

    def physical_to_local_rect(self, f: ScreenFreeze, phys: QRect) -> QRect:
        return physical_to_local_rect(f, phys)

    def _monitor_edges(self) -> tuple[list[int], list[int]]:
        xs: list[int] = []
        ys: list[int] = []
        for m in self._screen_phys:
            xs.extend([m.left(), m.left() + m.width()])
            ys.extend([m.top(), m.top() + m.height()])
        return xs, ys

    def _snap_coord(self, value: int, edges: list[int]) -> int:
        for e in edges:
            if abs(value - e) <= SNAP:
                return e
        return value

    def _snap_point(self, p: QPoint) -> QPoint:
        xs, ys = self._monitor_edges()
        return QPoint(self._snap_coord(p.x(), xs), self._snap_coord(p.y(), ys))

    def _snap_rect(self, r: QRect) -> QRect:
        xs, ys = self._monitor_edges()
        left = self._snap_coord(r.left(), xs)
        top = self._snap_coord(r.top(), ys)
        right_ex = self._snap_coord(r.right() + 1, xs)
        bottom_ex = self._snap_coord(r.bottom() + 1, ys)
        out = QRect(QPoint(left, top), QPoint(right_ex - 1, bottom_ex - 1)).normalized()
        if out.width() < MIN_SIZE:
            out.setWidth(MIN_SIZE)
        if out.height() < MIN_SIZE:
            out.setHeight(MIN_SIZE)
        return out

    def handles_local_on(self, panel: ScreenPanel) -> list[QRect]:
        """Selection handles in a panel's local coordinates."""
        lr = self.physical_to_local_rect(panel.freeze, self.sel)
        if lr.isEmpty():
            return []
        x, y, w, h = lr.x(), lr.y(), lr.width(), lr.height()
        m, s = HANDLE // 2, HANDLE
        return [
            QRect(x - m, y - m, s, s),
            QRect(x + w // 2 - m, y - m, s, s),
            QRect(x + w - m, y - m, s, s),
            QRect(x + w - m, y + h // 2 - m, s, s),
            QRect(x + w - m, y + h - m, s, s),
            QRect(x + w // 2 - m, y + h - m, s, s),
            QRect(x - m, y + h - m, s, s),
            QRect(x - m, y + h // 2 - m, s, s),
        ]

    def _handles_physical(self) -> dict[str, QRect]:
        r = self.sel
        if r.isEmpty():
            return {}
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        m, s = HANDLE // 2, HANDLE
        return {
            "nw": QRect(x - m, y - m, s, s),
            "n": QRect(x + w // 2 - m, y - m, s, s),
            "ne": QRect(x + w - m, y - m, s, s),
            "e": QRect(x + w - m, y + h // 2 - m, s, s),
            "se": QRect(x + w - m, y + h - m, s, s),
            "s": QRect(x + w // 2 - m, y + h - m, s, s),
            "sw": QRect(x - m, y + h - m, s, s),
            "w": QRect(x - m, y + h // 2 - m, s, s),
        }

    def _hit(self, p: QPoint) -> str | None:
        for name, hr in self._handles_physical().items():
            if hr.contains(p):
                return name
        if not self.sel.isEmpty() and self.sel.contains(p):
            return "move"
        return None

    def _cursor_for(self, hit: str | None):
        return {
            "n": Qt.CursorShape.SizeVerCursor,
            "s": Qt.CursorShape.SizeVerCursor,
            "e": Qt.CursorShape.SizeHorCursor,
            "w": Qt.CursorShape.SizeHorCursor,
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "move": Qt.CursorShape.SizeAllCursor,
        }.get(hit, Qt.CursorShape.CrossCursor)

    def _set_cursors(self, hit: str | None) -> None:
        cur = self._cursor_for(hit)
        for p in self._panels:
            p.setCursor(cur)

    def _refresh(self) -> None:
        for p in self._panels:
            p.update()

    def _clamp(self) -> None:
        r, s = self._virt, self.sel
        if s.width() > r.width():
            s.setWidth(r.width())
        if s.height() > r.height():
            s.setHeight(r.height())
        if s.left() < r.left():
            s.moveLeft(r.left())
        if s.top() < r.top():
            s.moveTop(r.top())
        if s.right() > r.right():
            s.moveRight(r.right())
        if s.bottom() > r.bottom():
            s.moveBottom(r.bottom())
        self.sel = s

    def on_press(self, gpos: QPoint) -> None:
        hit = self._hit(gpos)
        self.origin_sel = QRect(self.sel)
        if hit:
            self.mode = hit
            self.anchor = gpos
        else:
            self.mode = "create"
            self._close_toolbar()
            p = self._snap_point(gpos)
            self.anchor = p
            self.sel = QRect(p, p)
        self._refresh()

    def on_move(self, gpos: QPoint) -> None:
        if self.mode is None:
            self._set_cursors(self._hit(gpos))
            return
        if self.mode == "create":
            p = self._snap_point(gpos)
            self.sel = self._snap_rect(QRect(self.anchor, p).normalized())
        elif self.mode == "move":
            self.sel = self._snap_rect(self.origin_sel.translated(gpos - self.anchor))
            self._clamp()
        else:
            self._resize(self._snap_point(gpos))
            self.sel = self._snap_rect(self.sel)
        self._align_toolbar()
        self._refresh()

    def on_release(self, gpos: QPoint) -> None:
        if self.mode is not None:
            if self.sel.width() < MIN_SIZE or self.sel.height() < MIN_SIZE:
                if self.mode == "create":
                    self.sel = QRect()
                    self._close_toolbar()
            elif not self.sel.isEmpty():
                self.sel = self._snap_rect(self.sel)
                self._clamp()
                self._show_toolbar()
            self.mode = None
            self._refresh()
        self._set_cursors(self._hit(gpos))

    def on_double_click(self) -> None:
        self._finish("copy")

    def on_key(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self._finish("cancel")
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish("copy")
        elif e.key() == Qt.Key.Key_C and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._finish("copy")
        elif e.key() == Qt.Key.Key_S and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._finish("save")

    def _resize(self, p: QPoint) -> None:
        s = QRect(self.origin_sel)
        m = self.mode or ""
        if "n" in m:
            s.setTop(p.y())
        if "s" in m:
            s.setBottom(p.y())
        if "w" in m:
            s.setLeft(p.x())
        if "e" in m:
            s.setRight(p.x())
        s = s.normalized()
        if s.width() < MIN_SIZE:
            s.setWidth(MIN_SIZE)
        if s.height() < MIN_SIZE:
            s.setHeight(MIN_SIZE)
        self.sel = s
        self._clamp()

    def _crop(self) -> QPixmap | None:
        return crop_selection(self._freezes, self.sel)

    def _finish(self, action: str) -> None:
        if self._exiting:
            return
        if action == "cancel":
            self.close()
            return
        crop = self._crop()
        if crop is None:
            return
        if action == "edit":
            self._open_editor(crop)
            return
        if action == "copy":
            export_pixmap(crop, save=False)
            self.close()
        elif action == "save":
            if export_pixmap(crop, save=True):
                self.close()
            # Save dialog cancelled -> stay open

    def _open_editor(self, crop: QPixmap) -> None:
        self._close_toolbar()
        self._editor = open_editor(crop)
        self.close()

    def _host_for_toolbar(self) -> ScreenPanel | None:
        if not self._panels:
            return None
        if self.sel.isEmpty():
            return self._panels[0]
        c = self.sel.center()
        for p in self._panels:
            if p.freeze.physical.contains(c):
                return p
        best, area = self._panels[0], -1
        for p in self._panels:
            inter = self.sel.intersected(p.freeze.physical)
            a = inter.width() * inter.height()
            if a > area:
                best, area = p, a
        return best

    def _show_toolbar(self) -> None:
        host = self._host_for_toolbar()
        if host is None:
            return
        if self._toolbar is None or self._toolbar_host is not host:
            self._close_toolbar()
            self._toolbar = ScreenshotToolbar(host, self._finish)
            self._toolbar_host = host
        self._toolbar.adjustSize()
        self._toolbar.resize(self._toolbar.sizeHint())
        self._align_toolbar()

    def _align_toolbar(self) -> None:
        if self._toolbar is None or self.sel.isEmpty():
            return
        host = self._toolbar_host or self._host_for_toolbar()
        if host is None:
            return
        if host is not self._toolbar_host:
            self._show_toolbar()
            return
        self._toolbar.adjustSize()
        tw = max(self._toolbar.width(), self._toolbar.sizeHint().width())
        th = max(self._toolbar.height(), self._toolbar.sizeHint().height())
        margin = 10
        r = self.physical_to_local_rect(host.freeze, self.sel)
        if r.isEmpty():
            return
        area = host.rect()
        tx = r.x() + (r.width() - tw) // 2
        tx = max(area.left() + margin, min(tx, area.right() - tw - margin + 1))
        ty = r.y() + r.height() + margin
        if ty + th > area.bottom() - margin + 1:
            ty = r.y() - th - margin
            if ty < area.top() + margin:
                ty = min(
                    max(area.top() + margin, r.bottom() - th - margin),
                    area.bottom() - th - margin + 1,
                )
        tx = max(area.left() + margin, min(tx, max(area.left() + margin, area.right() - tw - margin + 1)))
        ty = max(area.top() + margin, min(ty, max(area.top() + margin, area.bottom() - th - margin + 1)))
        self._toolbar.setGeometry(int(tx), int(ty), int(tw), int(th))
        self._toolbar.show()
        self._toolbar.raise_()

    def _close_toolbar(self) -> None:
        if self._toolbar is not None:
            self._toolbar.deleteLater()
            self._toolbar = None
        self._toolbar_host = None

    def draw_size_badge(self, p: QPainter, r: QRect) -> None:
        """Draw size label; text is physical pixels (export size)."""
        if r.width() < 1 or r.height() < 1 or self.sel.isEmpty():
            return
        text = f"{self.sel.width()} x {self.sel.height()}"
        font = QFont(p.font())
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        fm = QFontMetrics(font)
        pad_x, pad_y = 8, 4
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        bw, bh = tw + pad_x * 2, th + pad_y * 2
        inset = 6
        bx = r.left() + inset
        by = r.top() + inset
        if bx + bw > r.right() - 2:
            bx = max(r.left() + 2, r.right() - bw - 2)
        if by + bh > r.bottom() - 2:
            by = max(r.top() + 2, r.bottom() - bh - 2)
        badge = QRect(bx, by, bw, bh)
        p.setPen(QPen(QColor(UI["border"]), 1))
        p.setBrush(QBrush(QColor(UI["bg"])))
        p.drawRoundedRect(badge, 6, 6)
        p.setPen(QColor(UI["text"]))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

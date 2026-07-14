from dataclasses import dataclass
from typing import Literal

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.ui.components.button import Button
from core.ui.components.slider import Slider
from core.ui.theme import get_tokens
from core.ui.views.view_base import ViewBase
from core.utils.tooltip import set_tooltip
from core.widgets.services.control_center.api.screenshot.constants import export_pixmap
from core.widgets.services.control_center.api.screenshot.editor_tools import (
    apply_blur_region,
    draw_arrow,
    draw_ellipse_stroke,
    draw_pen_segment,
    draw_rect_stroke,
)
from core.widgets.services.control_center.api.screenshot.icons import (
    SVG_ARROW,
    SVG_BLUR,
    SVG_CIRCLE,
    SVG_CLEAR_ALL,
    SVG_COPY,
    SVG_CROP,
    SVG_HIGHLIGHT,
    SVG_PEN,
    SVG_RECT,
    SVG_REDO,
    SVG_SAVE,
    SVG_UNDO,
    svg_to_icon,
)

_DEFAULT_COLOR = "#ffffff"
_DEFAULT_STROKE = 3
_MIN_STROKE = 1
_MAX_STROKE = 40
_DEFAULT_BLUR = 5
_MIN_BLUR = 1
_MAX_BLUR = 20
# Highlighter: fixed transparency (size uses same stroke_width as pen).
_HIGHLIGHT_ALPHA = 80
_MIN_CROP = 8
# Rect/circle: avoid collapsed drags with fat pens (looks like a thick line).
_MIN_SHAPE = 4
_HISTORY_MAX = 80
# Compact palette for the popup (rows of 6).
_PALETTE = [
    "#ff3b30",
    "#ff9500",
    "#ffcc00",
    "#34c759",
    "#00c7be",
    "#007aff",
    "#5856d6",
    "#af52de",
    "#ff2d55",
    "#a2845e",
    "#8e8e93",
    "#1c1c1e",
    "#ffffff",
    "#000000",
    "#64d2ff",
    "#30d158",
    "#ffd60a",
    "#ff453a",
]

PointXY = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FreehandOp:
    style: Literal["pen", "highlight"]
    points: tuple[PointXY, ...]
    color: str
    width: int


@dataclass(frozen=True, slots=True)
class ArrowOp:
    a: PointXY
    b: PointXY
    color: str
    width: int


@dataclass(frozen=True, slots=True)
class RectOp:
    a: PointXY
    b: PointXY
    color: str
    width: int


@dataclass(frozen=True, slots=True)
class CircleOp:
    a: PointXY
    b: PointXY
    color: str
    width: int


@dataclass(frozen=True, slots=True)
class BlurOp:
    x: int
    y: int
    w: int
    h: int
    strength: int


@dataclass(frozen=True, slots=True)
class CropOp:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class ClearOp:
    """Reset to the original image (undoable)."""


EditOp = FreehandOp | ArrowOp | RectOp | CircleOp | BlurOp | CropOp | ClearOp


class _FramelessPopup(QFrame):
    """Floating panel chrome for color and stroke options (child of the editor)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        t = get_tokens()
        bg = t.get(
            "solid_bg_quinary",
            t.get("solid_bg_tertiary", t.get("layer_on_mica_tertiary", "#333333")),
        )
        border = t.get("control_stroke_default", "#3f3f3f")
        text = t.get("text_primary", "#f0f0f0")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._panel = QFrame(self)
        self._panel.setObjectName("editorPopupPanel")
        self._panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._panel.setStyleSheet(
            f"""
            QFrame#editorPopupPanel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#editorPopupPanel QLabel {{
                color: {text};
                background: transparent;
                border: none;
            }}
            """
        )
        outer.addWidget(self._panel)
        self._body = QVBoxLayout(self._panel)
        self._body.setContentsMargins(8, 8, 8, 8)
        self._body.setSpacing(6)


class _ColorChip(QPushButton):
    """Solid color chip for the palette grid and toolbar."""

    def __init__(self, color: str | QColor, size: int = 26, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color)
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_color(self, color: QColor | str) -> None:
        c = QColor(color)
        if c.isValid():
            self._color = c
            self.update()

    def color(self) -> QColor:
        return QColor(self._color)

    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        radius = r.width() // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawRoundedRect(r, radius, radius)
        t = get_tokens()
        if self._hover:
            accent = QColor(t.get("accent_fill_default", "#00aeff"))
            p.setPen(QPen(accent, 2))
        else:
            p.setPen(QPen(QColor(128, 128, 128, 115), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, radius, radius)
        p.end()


class _ColorPopup(_FramelessPopup):
    """Color grid popup."""

    colorPicked = pyqtSignal(QColor)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        cols = 6
        for i, hex_c in enumerate(_PALETTE):
            b = _ColorChip(hex_c, size=26, parent=self._panel)
            b.clicked.connect(lambda _=False, c=hex_c: self._pick(c))
            grid.addWidget(b, i // cols, i % cols)
        self._body.addLayout(grid)

    def _pick(self, hex_c: str) -> None:
        self.colorPicked.emit(QColor(hex_c))
        self.close()


class _PopupToggleHost(QObject):
    """Shows/hides a flyout above an anchor widget; closes on outside click."""

    def __init__(self, anchor: QWidget):
        super().__init__(anchor)
        self._anchor = anchor
        self._popup: _FramelessPopup | None = None
        self._filter_installed = False

    def is_open(self) -> bool:
        return self._popup is not None and self._popup.isVisible()

    def close(self) -> None:
        self._remove_filter()
        if self._popup is not None:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None

    def reanchor(self) -> None:
        if self._popup is None or not self._popup.isVisible():
            return
        self._place(self._popup)

    def show_popup(self, popup: _FramelessPopup) -> None:
        self.close()
        popup.destroyed.connect(self._on_destroyed)
        popup.adjustSize()
        self._place(popup)
        popup.show()
        popup.raise_()
        self._popup = popup
        self._install_filter()

    def _place(self, popup: _FramelessPopup) -> None:
        parent = popup.parentWidget()
        if parent is None:
            return
        popup.adjustSize()
        sh = popup.sizeHint()
        pw = max(sh.width(), popup.width())
        ph = max(sh.height(), popup.height())
        popup.resize(pw, ph)
        top_left = self._anchor.mapTo(parent, QPoint(0, 0))
        x = top_left.x()
        y = top_left.y() - ph - 6
        x = max(0, min(x, max(0, parent.width() - pw)))
        y = max(0, min(y, max(0, parent.height() - ph)))
        popup.move(x, y)

    def toggle(self, factory) -> None:
        if self.is_open():
            self.close()
            return
        self.show_popup(factory())

    def _on_destroyed(self, _obj=None) -> None:
        self._remove_filter()
        self._popup = None

    def _install_filter(self) -> None:
        if self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_filter(self) -> None:
        if not self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._filter_installed = False

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if event is None or self._popup is None or not self._popup.isVisible():
            return False
        if event.type() != QEvent.Type.MouseButtonPress:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        gp = event.globalPosition().toPoint()
        pr = QRect(self._popup.mapToGlobal(QPoint(0, 0)), self._popup.size())
        if pr.contains(gp):
            return False
        ar = QRect(self._anchor.mapToGlobal(QPoint(0, 0)), self._anchor.size())
        if ar.contains(gp):
            return False
        self.close()
        return False


class ColorSwatchButton(_ColorChip):
    """Toolbar color control."""

    colorChanged = pyqtSignal(QColor)

    def __init__(self, color: str | QColor = _DEFAULT_COLOR, parent: QWidget | None = None):
        super().__init__(color, size=18, parent=parent)
        self._host = _PopupToggleHost(self)
        set_tooltip(self, "Color")
        self.clicked.connect(self._toggle_popup)

    def set_color(self, color: QColor | str) -> None:
        super().set_color(color)

    def close_popup(self) -> None:
        self._host.close()

    def is_popup_open(self) -> bool:
        return self._host.is_open()

    def reanchor_popup(self) -> None:
        self._host.reanchor()

    def _toggle_popup(self) -> None:
        def factory():
            popup = _ColorPopup(self.window())
            popup.colorPicked.connect(self._on_picked)
            return popup

        self._host.toggle(factory)

    def _on_picked(self, color: QColor) -> None:
        self.set_color(color)
        self.colorChanged.emit(QColor(color))
        self._host.close()


class _SliderPopup(_FramelessPopup):
    """Popup with YASB Slider (stroke size, blur strength, …)."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        value: int,
        *,
        minimum: int,
        maximum: int,
        label: str,
        suffix: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._body.setContentsMargins(12, 10, 12, 10)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lbl = QLabel(label, self._panel)
        lay.addWidget(lbl)
        self._slider = Slider(
            minimum=minimum,
            maximum=maximum,
            value=max(minimum, min(maximum, value)),
            suffix=suffix,
            parent=self._panel,
        )
        self._slider.setMinimumWidth(140)
        self._slider.setMaximumWidth(180)
        self._slider.valueChanged.connect(self.valueChanged.emit)
        lay.addWidget(self._slider)
        self._body.addLayout(lay)


class EditorCanvas(QWidget):
    """Zoomable canvas: draws base + annotation layer; emits strokes in image coords."""

    tool_finished = pyqtSignal()
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._original = QPixmap()
        self._base = QPixmap()
        self._layer = QPixmap()
        self._ops: list[EditOp] = []
        self._redo_ops: list[EditOp] = []
        self._stroke_temp = QPixmap()
        self.tool = "pen"
        self.color = QColor(_DEFAULT_COLOR)
        self.stroke_width = _DEFAULT_STROKE
        self.blur_strength = _DEFAULT_BLUR
        self._zoom = 1.0
        self._drawing = False
        self._panning = False
        self._pan_last_global = QPoint()
        self._start = QPoint()
        self._current = QPoint()
        self._points: list[QPoint] = []
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_image(self, pm: QPixmap) -> None:
        self._original = QPixmap(pm)
        self._original.setDevicePixelRatio(1.0)
        self._ops.clear()
        self._redo_ops.clear()
        self._stroke_temp = QPixmap()
        self._rebuild()

    def set_zoom(self, zoom: float, *, anchor_global: QPoint | None = None) -> None:
        """Set zoom. ``anchor_global`` pins that screen point; otherwise viewport center."""
        old_z = self._zoom if self._zoom > 0.01 else 1.0
        new_z = max(0.25, min(4.0, float(zoom)))
        if abs(new_z - old_z) < 1e-6:
            return

        sa = self._scroll_area()
        vp = sa.viewport() if sa is not None else None
        img_anchor: QPointF | None = None
        vp_anchor: QPoint | None = None

        if vp is not None and not self._base.isNull() and self.width() > 0 and self.height() > 0:
            if anchor_global is not None:
                vp_anchor = vp.mapFromGlobal(anchor_global)
            else:
                vp_anchor = QPoint(vp.width() // 2, vp.height() // 2)
            vp_anchor = QPoint(
                max(0, min(max(0, vp.width() - 1), vp_anchor.x())),
                max(0, min(max(0, vp.height() - 1), vp_anchor.y())),
            )
            canvas_pt = self.mapFrom(vp, vp_anchor)
            if not self.rect().contains(canvas_pt):
                canvas_pt = QPoint(self.width() // 2, self.height() // 2)
            img_anchor = QPointF(canvas_pt.x() / old_z, canvas_pt.y() / old_z)

        self._zoom = new_z
        self._relayout()

        if sa is None or vp is None or img_anchor is None or vp_anchor is None:
            return
        target_x = int(round(img_anchor.x() * new_z))
        target_y = int(round(img_anchor.y() * new_z))
        h = sa.horizontalScrollBar()
        v = sa.verticalScrollBar()
        h.setValue(target_x - vp_anchor.x())
        v.setValue(target_y - vp_anchor.y())

    def zoom(self) -> float:
        return self._zoom

    def image_size(self) -> QSize:
        if self._base.isNull():
            return QSize(1, 1)
        return self._base.size()

    def _relayout(self) -> None:
        if self._base.isNull():
            self.setFixedSize(1, 1)
            return
        w = max(1, int(round(self._base.width() * self._zoom)))
        h = max(1, int(round(self._base.height() * self._zoom)))
        self.setFixedSize(w, h)
        self.update()

    def composite(self) -> QPixmap:
        out = QPixmap(self._base.size())
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawPixmap(0, 0, self._base)
        p.drawPixmap(0, 0, self._layer)
        p.end()
        return out

    def _empty_layer(self, size: QSize) -> QPixmap:
        layer = QPixmap(size)
        layer.setDevicePixelRatio(1.0)
        layer.fill(Qt.GlobalColor.transparent)
        return layer

    def _commit_op(self, op: EditOp) -> None:
        self._ops.append(op)
        if len(self._ops) > _HISTORY_MAX:
            # Drop oldest; rebuild so canvas still matches remaining ops.
            self._ops.pop(0)
            self._rebuild()
        self._redo_ops.clear()

    def _apply_op(self, op: EditOp) -> None:
        """Apply one op to current base/layer (image coords)."""
        if isinstance(op, FreehandOp):
            pts = [QPoint(x, y) for x, y in op.points]
            if not pts:
                return
            color = QColor(op.color)
            if op.style == "highlight":
                temp = self._empty_layer(self._base.size())
                for i in range(1, len(pts)):
                    self._draw_freehand_to(temp, pts[i - 1], pts[i], color=color, width=op.width, alpha=None)
                if len(pts) == 1:
                    self._draw_freehand_to(temp, pts[0], pts[0], color=color, width=op.width, alpha=None)
                lp = QPainter(self._layer)
                lp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                lp.setOpacity(_HIGHLIGHT_ALPHA / 255.0)
                lp.drawPixmap(0, 0, temp)
                lp.end()
            else:
                if len(pts) == 1:
                    self._draw_freehand_to(self._layer, pts[0], pts[0], color=color, width=op.width, alpha=None)
                else:
                    for i in range(1, len(pts)):
                        self._draw_freehand_to(self._layer, pts[i - 1], pts[i], color=color, width=op.width, alpha=None)
            return

        if isinstance(op, ArrowOp):
            lp = QPainter(self._layer)
            lp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            draw_arrow(lp, QPoint(*op.a), QPoint(*op.b), QColor(op.color), op.width)
            lp.end()
            return

        if isinstance(op, RectOp):
            lp = QPainter(self._layer)
            draw_rect_stroke(lp, QPoint(*op.a), QPoint(*op.b), QColor(op.color), op.width)
            lp.end()
            return

        if isinstance(op, CircleOp):
            lp = QPainter(self._layer)
            draw_ellipse_stroke(lp, QPoint(*op.a), QPoint(*op.b), QColor(op.color), op.width)
            lp.end()
            return

        if isinstance(op, BlurOp):
            r = QRect(op.x, op.y, op.w, op.h)
            apply_blur_region(self._layer, self.composite(), r, strength=op.strength)
            return

        if isinstance(op, CropOp):
            r = QRect(op.x, op.y, op.w, op.h)
            bounds = QRect(0, 0, self._base.width(), self._base.height())
            r = r.intersected(bounds)
            if r.width() < 1 or r.height() < 1:
                return
            self._base = self._base.copy(r)
            self._base.setDevicePixelRatio(1.0)
            self._layer = self._layer.copy(r)
            self._layer.setDevicePixelRatio(1.0)
            return

        if isinstance(op, ClearOp):
            self._base = QPixmap(self._original)
            self._base.setDevicePixelRatio(1.0)
            self._layer = self._empty_layer(self._base.size())

    def _rebuild(self) -> None:
        """Rebuild base+layer from original + command list."""
        if self._original.isNull():
            self._base = QPixmap()
            self._layer = QPixmap()
            self._relayout()
            return
        self._base = QPixmap(self._original)
        self._base.setDevicePixelRatio(1.0)
        self._layer = self._empty_layer(self._base.size())
        for op in self._ops:
            self._apply_op(op)
        self._clear_stroke_temp()
        self._relayout()

    def undo(self) -> None:
        if not self._ops:
            return
        self._redo_ops.append(self._ops.pop())
        if len(self._redo_ops) > _HISTORY_MAX:
            self._redo_ops.pop(0)
        self._rebuild()
        self.tool_finished.emit()

    def redo(self) -> None:
        if not self._redo_ops:
            return
        self._ops.append(self._redo_ops.pop())
        if len(self._ops) > _HISTORY_MAX:
            self._ops.pop(0)
        self._rebuild()
        self.tool_finished.emit()

    def clear_all(self) -> None:
        """Reset to the image as opened (all strokes, crops). Undoable."""
        if self._original.isNull():
            return
        self._commit_op(ClearOp())
        self._apply_op(self._ops[-1])
        self._clear_stroke_temp()
        self._relayout()
        self.tool_finished.emit()

    def _to_img(self, pos: QPoint) -> QPoint:
        z = self._zoom if self._zoom > 0.01 else 1.0
        return QPoint(int(pos.x() / z), int(pos.y() / z))

    def _to_disp(self, img_pt: QPoint) -> QPoint:
        return QPoint(int(img_pt.x() * self._zoom), int(img_pt.y() * self._zoom))

    def _shape_min_side(self) -> int:
        """Minimum width/height so a thick stroke doesn't collapse into a line."""
        return max(_MIN_SHAPE, (self.stroke_width + 1) // 2)

    def _drag_shape_ok(self, a: QPoint, b: QPoint) -> bool:
        r = QRect(a, b).normalized()
        m = self._shape_min_side()
        return r.width() >= m and r.height() >= m

    def _ensure_stroke_temp(self) -> None:
        if self._stroke_temp.isNull() or self._stroke_temp.size() != self._base.size():
            self._stroke_temp = QPixmap(self._base.size())
            self._stroke_temp.setDevicePixelRatio(1.0)
            self._stroke_temp.fill(Qt.GlobalColor.transparent)

    def _clear_stroke_temp(self) -> None:
        if not self._stroke_temp.isNull():
            self._stroke_temp.fill(Qt.GlobalColor.transparent)

    def _commit_highlight_stroke(self) -> None:
        """Bake one highlighter stroke onto the layer with a single opacity pass."""
        if self._stroke_temp.isNull():
            return
        lp = QPainter(self._layer)
        lp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        lp.setOpacity(_HIGHLIGHT_ALPHA / 255.0)
        lp.drawPixmap(0, 0, self._stroke_temp)
        lp.end()
        self._clear_stroke_temp()

    def _draw_freehand_to(
        self,
        target: QPixmap,
        a: QPoint,
        b: QPoint,
        *,
        alpha: int | None,
        color: QColor | None = None,
        width: int | None = None,
    ) -> None:
        """Draw segment(s); interpolate when the cursor jumps so fast moves stay solid."""
        c = color if color is not None else self.color
        w = width if width is not None else self.stroke_width
        dx = b.x() - a.x()
        dy = b.y() - a.y()
        dist = (dx * dx + dy * dy) ** 0.5
        step = max(1.0, w * 0.35)
        lp = QPainter(target)
        if dist <= step:
            draw_pen_segment(lp, a, b, c, w, alpha=alpha)
        else:
            n = int(dist / step) + 1
            prev = a
            for i in range(1, n + 1):
                t = i / n
                cur = QPoint(int(a.x() + dx * t), int(a.y() + dy * t))
                draw_pen_segment(lp, prev, cur, c, w, alpha=alpha)
                prev = cur
        lp.end()

    def _pt(self, p: QPoint) -> PointXY:
        return (int(p.x()), int(p.y()))

    def _scroll_area(self) -> QScrollArea | None:
        w = self.parentWidget()
        while w is not None:
            if isinstance(w, QScrollArea):
                return w
            w = w.parentWidget()
        return None

    def _ctrl_held(self, modifiers: Qt.KeyboardModifier | Qt.KeyboardModifiers) -> bool:
        return bool(modifiers & Qt.KeyboardModifier.ControlModifier)

    def _update_nav_cursor(self, modifiers: Qt.KeyboardModifier | Qt.KeyboardModifiers) -> None:
        if self._panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._ctrl_held(modifiers) and not self._drawing:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _end_pan(self, modifiers: Qt.KeyboardModifier | Qt.KeyboardModifiers | None = None) -> None:
        if not self._panning:
            return
        self._panning = False
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()
        mods = modifiers if modifiers is not None else QApplication.keyboardModifiers()
        self._update_nav_cursor(mods)

    def _pan_by(self, delta: QPoint) -> None:
        sa = self._scroll_area()
        if sa is None or delta.isNull():
            return
        h = sa.horizontalScrollBar()
        v = sa.verticalScrollBar()
        nx = max(h.minimum(), min(h.maximum(), h.value() - delta.x()))
        ny = max(v.minimum(), min(v.maximum(), v.value() - delta.y()))
        if nx == h.value() and ny == v.value():
            return
        h.setValue(nx)
        v.setValue(ny)

    def wheelEvent(self, e):
        if self._ctrl_held(e.modifiers()):
            delta = e.angleDelta().y()
            if delta == 0:
                e.ignore()
                return
            step = 1.1 if delta > 0 else 1 / 1.1
            self.set_zoom(self._zoom * step, anchor_global=e.globalPosition().toPoint())
            self.zoom_changed.emit(self._zoom)
            self._update_nav_cursor(e.modifiers())
            e.accept()
            return
        super().wheelEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Control, Qt.Key.Key_Meta):
            self._update_nav_cursor(e.modifiers() | Qt.KeyboardModifier.ControlModifier)
            e.accept()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() in (Qt.Key.Key_Control, Qt.Key.Key_Meta):
            if self._panning and not (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._end_pan(e.modifiers())
            else:
                self._update_nav_cursor(e.modifiers())
            e.accept()
            return
        super().keyReleaseEvent(e)

    def enterEvent(self, e):
        self._update_nav_cursor(QApplication.keyboardModifiers())
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self._panning:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._base.isNull():
            return
        if self._ctrl_held(e.modifiers()):
            self._panning = True
            self._pan_last_global = e.globalPosition().toPoint()
            self.grabMouse()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            e.accept()
            return
        p = self._to_img(e.position().toPoint())
        self._drawing = True
        self._start = p
        self._current = p
        self._points = [p]
        if self.tool == "highlight":
            self._ensure_stroke_temp()
            self._clear_stroke_temp()
        self.update()

    def mouseMoveEvent(self, e):
        if self._panning:
            global_pos = e.globalPosition().toPoint()
            delta = global_pos - self._pan_last_global
            if not delta.isNull():
                self._pan_last_global = global_pos
                self._pan_by(delta)
            e.accept()
            return
        if not self._drawing:
            self._update_nav_cursor(e.modifiers())
            return
        p = self._to_img(e.position().toPoint())
        self._current = p
        if self.tool in ("pen", "highlight") and self._points:
            prev = self._points[-1]
            self._points.append(p)
            if self.tool == "highlight":
                self._ensure_stroke_temp()
                self._draw_freehand_to(self._stroke_temp, prev, p, alpha=None)
            else:
                self._draw_freehand_to(self._layer, prev, p, alpha=None)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._panning:
            self._end_pan(e.modifiers())
            e.accept()
            return
        if e.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        self._drawing = False
        p = self._to_img(e.position().toPoint())
        self._current = p
        w = self.stroke_width
        color_name = self.color.name(QColor.NameFormat.HexRgb)

        if self.tool == "pen":
            if self._points:
                prev = self._points[-1]
                self._points.append(p)
                self._draw_freehand_to(self._layer, prev, p, alpha=None)
            pts = tuple(self._pt(q) for q in self._points)
            if pts:
                self._commit_op(FreehandOp(style="pen", points=pts, color=color_name, width=w))
        elif self.tool == "highlight":
            if self._points:
                self._ensure_stroke_temp()
                self._draw_freehand_to(self._stroke_temp, self._points[-1], p, alpha=None)
                self._points.append(p)
            pts = tuple(self._pt(q) for q in self._points)
            self._commit_highlight_stroke()
            if pts:
                self._commit_op(FreehandOp(style="highlight", points=pts, color=color_name, width=w))
        elif self.tool == "arrow":
            if (p - self._start).manhattanLength() >= self._shape_min_side():
                op = ArrowOp(a=self._pt(self._start), b=self._pt(p), color=color_name, width=w)
                self._commit_op(op)
                self._apply_op(op)
        elif self.tool == "rect":
            if self._drag_shape_ok(self._start, p):
                op = RectOp(a=self._pt(self._start), b=self._pt(p), color=color_name, width=w)
                self._commit_op(op)
                self._apply_op(op)
        elif self.tool == "circle":
            if self._drag_shape_ok(self._start, p):
                op = CircleOp(a=self._pt(self._start), b=self._pt(p), color=color_name, width=w)
                self._commit_op(op)
                self._apply_op(op)
        elif self.tool == "blur":
            r = QRect(self._start, p).normalized()
            if r.width() >= 4 and r.height() >= 4:
                op = BlurOp(x=r.x(), y=r.y(), w=r.width(), h=r.height(), strength=self.blur_strength)
                self._commit_op(op)
                self._apply_op(op)
        elif self.tool == "crop":
            r = QRect(self._start, p).normalized()
            bounds = QRect(0, 0, self._base.width(), self._base.height())
            r = r.intersected(bounds)
            if r.width() >= _MIN_CROP and r.height() >= _MIN_CROP:
                op = CropOp(x=r.x(), y=r.y(), w=r.width(), h=r.height())
                self._commit_op(op)
                self._apply_op(op)
                self._relayout()
                self.tool_finished.emit()
        self._points = []
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        t = get_tokens()
        bg = QColor(t.get("layer_alt", "#2c2c2c"))
        dirty = e.rect()
        p.fillRect(dirty, bg)
        if self._base.isNull():
            return

        smooth = not self._panning
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)

        z = self._zoom if self._zoom > 0.01 else 1.0
        src = QRect(
            max(0, int(dirty.x() / z)),
            max(0, int(dirty.y() / z)),
            min(self._base.width(), int((dirty.width() + z) / z) + 1),
            min(self._base.height(), int((dirty.height() + z) / z) + 1),
        )
        src = src.intersected(QRect(0, 0, self._base.width(), self._base.height()))
        if src.isEmpty():
            return
        dest = QRect(
            int(round(src.x() * z)),
            int(round(src.y() * z)),
            max(1, int(round(src.width() * z))),
            max(1, int(round(src.height() * z))),
        )
        p.drawPixmap(dest, self._base, src)
        if not self._layer.isNull():
            p.drawPixmap(dest, self._layer, src)

        if self._drawing and self.tool == "highlight" and not self._stroke_temp.isNull():
            p.setOpacity(_HIGHLIGHT_ALPHA / 255.0)
            p.drawPixmap(dest, self._stroke_temp, src)
            p.setOpacity(1.0)

        if self._drawing and self.tool in ("arrow", "rect", "circle", "blur", "crop"):
            a = self._to_disp(self._start)
            b = self._to_disp(self._current)
            sel = QRect(a, b).normalized()
            if self.tool == "crop":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 110))
                if sel.top() > 0:
                    p.fillRect(0, 0, self.width(), sel.top(), p.brush().color())
                if sel.bottom() + 1 < self.height():
                    p.fillRect(0, sel.bottom() + 1, self.width(), self.height() - sel.bottom() - 1, p.brush().color())
                if sel.height() > 0 and sel.left() > 0:
                    p.fillRect(0, sel.top(), sel.left(), sel.height(), p.brush().color())
                if sel.height() > 0 and sel.right() + 1 < self.width():
                    p.fillRect(
                        sel.right() + 1, sel.top(), self.width() - sel.right() - 1, sel.height(), p.brush().color()
                    )
                p.setPen(QPen(self.color, 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(sel)
            elif self.tool == "blur":
                p.setPen(QPen(self.color, 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(sel)
            elif self.tool == "arrow":
                if (self._current - self._start).manhattanLength() >= self._shape_min_side():
                    preview_w = max(1, int(round(self.stroke_width * self._zoom)))
                    draw_arrow(p, a, b, self.color, preview_w)
            elif self.tool == "circle":
                if self._drag_shape_ok(self._start, self._current):
                    preview_w = max(1, int(round(self.stroke_width * self._zoom)))
                    draw_ellipse_stroke(p, a, b, self.color, preview_w)
            elif self.tool == "rect":
                if self._drag_shape_ok(self._start, self._current):
                    preview_w = max(1, int(round(self.stroke_width * self._zoom)))
                    draw_rect_stroke(p, a, b, self.color, preview_w)


class ScreenshotEditorDialog(ViewBase, QDialog):
    """Editor window for a captured screenshot."""

    def __init__(self, image: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self._tool_btns: dict[str, Button] = {}
        self._stroke_host: _PopupToggleHost | None = None
        self._stroke_popup_tool: str | None = None
        self._zoom_auto = True
        self._applying_auto_zoom = False

        self.setWindowTitle("Edit Screenshot")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(800, 360)
        self.build_view()
        self.build_app_icon()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.horizontalScrollBar().setSingleStep(1)
        self._scroll.verticalScrollBar().setSingleStep(1)
        vp = self._scroll.viewport()
        vp.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        vp.setAutoFillBackground(True)
        self._canvas = EditorCanvas(self)
        self._canvas.set_image(image)
        self._canvas.tool_finished.connect(self._on_canvas_changed)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom)
        self._scroll.setWidget(self._canvas)
        root.addWidget(self._scroll, stretch=1)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.setContentsMargins(0, 0, 0, 0)

        self._tool_svgs = {
            "pen": SVG_PEN,
            "highlight": SVG_HIGHLIGHT,
            "arrow": SVG_ARROW,
            "rect": SVG_RECT,
            "circle": SVG_CIRCLE,
            "blur": SVG_BLUR,
            "crop": SVG_CROP,
        }
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        for key, tip in (
            ("pen", "Pen"),
            ("highlight", "Highlighter"),
            ("arrow", "Arrow"),
            ("rect", "Rectangle"),
            ("circle", "Circle"),
            ("blur", "Blur"),
            ("crop", "Crop"),
        ):
            b = self._make_icon_button(self._tool_svgs[key], tip, checkable=True)
            b.clicked.connect(lambda _=False, k=key: self._on_tool_clicked(k))
            self._tool_btns[key] = b
            self._tool_group.addButton(b)
            bar.addWidget(b)

        bar.addSpacing(8)
        self._color_btn = ColorSwatchButton(_DEFAULT_COLOR, parent=self)
        self._color_btn.colorChanged.connect(self._on_color_picked)
        self._color_btn.clicked.connect(self._close_stroke_popup)
        bar.addWidget(self._color_btn)

        bar.addSpacing(12)
        self._zoom = Slider(minimum=25, maximum=400, value=100, suffix="%", parent=self)
        self._zoom.setMinimumWidth(160)
        self._zoom.setMaximumWidth(180)
        self._zoom.valueChanged.connect(self._on_zoom)
        self._zoom.labelClicked.connect(self._reset_zoom)
        set_tooltip(self._zoom, "Zoom (Ctrl+scroll)")
        bar.addWidget(self._zoom)

        bar.addStretch(1)

        self._btn_undo = self._make_icon_button(SVG_UNDO, "Undo (Ctrl+Z)")
        self._btn_undo.clicked.connect(self._canvas.undo)
        bar.addWidget(self._btn_undo)

        self._btn_redo = self._make_icon_button(SVG_REDO, "Redo (Ctrl+Y)")
        self._btn_redo.clicked.connect(self._canvas.redo)
        bar.addWidget(self._btn_redo)

        self._btn_clear = self._make_icon_button(SVG_CLEAR_ALL, "Clear all edits")
        self._btn_clear.clicked.connect(self._canvas.clear_all)
        bar.addWidget(self._btn_clear)

        self._btn_copy = self._make_icon_button(SVG_COPY, "Copy to clipboard")
        self._btn_copy.clicked.connect(self._copy)
        bar.addWidget(self._btn_copy)

        self._btn_save = self._make_icon_button(SVG_SAVE, "Save as")
        self._btn_save.clicked.connect(self._save)
        bar.addWidget(self._btn_save)

        self._action_svgs: list[tuple[Button, str]] = [
            (self._btn_undo, SVG_UNDO),
            (self._btn_redo, SVG_REDO),
            (self._btn_clear, SVG_CLEAR_ALL),
            (self._btn_copy, SVG_COPY),
            (self._btn_save, SVG_SAVE),
        ]

        root.addLayout(bar)

        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._on_app_theme_changed)

        self._set_tool("pen")
        self._canvas.color = QColor(_DEFAULT_COLOR)
        self._canvas.stroke_width = _DEFAULT_STROKE
        self._canvas.blur_strength = _DEFAULT_BLUR
        self._fit_window()
        self._update_title()

    def _update_title(self) -> None:
        sz = self._canvas.image_size()
        self.setWindowTitle(f"Edit Screenshot - {sz.width()} x {sz.height()}")

    def _icon_dpr(self) -> float:
        return float(self.devicePixelRatioF())

    def _make_icon_button(self, svg: str, tip: str, *, checkable: bool = False) -> Button:
        t = get_tokens()
        text = t.get("text_primary", "#f0f0f0")
        b = Button("", variant="subtle", padding="6,6,6,6", parent=self)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setIcon(svg_to_icon(svg, 16, text, dpr=self._icon_dpr()))
        b.setIconSize(QSize(16, 16))
        if checkable:
            b.setCheckable(True)
        set_tooltip(b, tip)
        return b

    def _on_app_theme_changed(self) -> None:
        self._refresh_toolbar_icons()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._refresh_toolbar_icons()
        wh = self.windowHandle()
        if wh is not None:
            try:
                wh.screenChanged.disconnect(self._refresh_toolbar_icons)
            except TypeError:
                pass
            wh.screenChanged.connect(self._refresh_toolbar_icons)

    def _refresh_toolbar_icons(self) -> None:
        t = get_tokens()
        text = t.get("text_primary", "#f0f0f0")
        on_accent = t.get("text_on_accent_primary", "#0a0a0a")
        dpr = self._icon_dpr()
        tool = getattr(self._canvas, "tool", "pen")
        for k, b in self._tool_btns.items():
            svg = self._tool_svgs.get(k)
            if svg is None:
                continue
            checked = k == tool
            b.setIcon(svg_to_icon(svg, 16, on_accent if checked else text, dpr=dpr))
        for b, svg in getattr(self, "_action_svgs", ()):
            b.setIcon(svg_to_icon(svg, 16, text, dpr=dpr))

    def _close_stroke_popup(self) -> None:
        if self._stroke_host is not None:
            self._stroke_host.close()
            self._stroke_host = None
        self._stroke_popup_tool = None

    def _toggle_tool_option_popup(self, tool: str) -> None:
        """Show/hide size or blur-strength slider above the tool button."""
        btn = self._tool_btns.get(tool)
        if btn is None:
            return
        if self._stroke_host is not None and self._stroke_host.is_open() and self._stroke_popup_tool == tool:
            self._close_stroke_popup()
            return
        self._close_stroke_popup()
        self._color_btn.close_popup()
        host = _PopupToggleHost(btn)
        self._stroke_host = host
        self._stroke_popup_tool = tool

        if tool == "blur":

            def factory():
                popup = _SliderPopup(
                    self._canvas.blur_strength,
                    minimum=_MIN_BLUR,
                    maximum=_MAX_BLUR,
                    label="Blur",
                    suffix="",
                    parent=self,
                )
                popup.valueChanged.connect(self._on_blur_strength)
                return popup

        else:

            def factory():
                popup = _SliderPopup(
                    self._canvas.stroke_width,
                    minimum=_MIN_STROKE,
                    maximum=_MAX_STROKE,
                    label="Size",
                    suffix="px",
                    parent=self,
                )
                popup.valueChanged.connect(self._on_stroke_width)
                return popup

        host.show_popup(factory())

    def _on_stroke_width(self, value: int) -> None:
        self._canvas.stroke_width = max(_MIN_STROKE, min(_MAX_STROKE, int(value)))

    def _on_blur_strength(self, value: int) -> None:
        self._canvas.blur_strength = max(_MIN_BLUR, min(_MAX_BLUR, int(value)))

    def _on_tool_clicked(self, tool: str) -> None:
        if tool == self._canvas.tool and tool in (
            "pen",
            "highlight",
            "arrow",
            "rect",
            "circle",
            "blur",
        ):
            self._set_tool(tool)
            self._toggle_tool_option_popup(tool)
            return
        self._close_stroke_popup()
        self._set_tool(tool)

    def _leave_auto_zoom(self) -> None:
        self._zoom_auto = False

    def _fit_zoom_pct_for_size(self, view_w: int, view_h: int) -> int:
        """Zoom percent to fit image in view, clamped to 25-100."""
        img = self._canvas.image_size()
        iw = max(1, img.width())
        ih = max(1, img.height())
        vw = max(1, view_w)
        vh = max(1, view_h)
        scale = min(1.0, vw / iw, vh / ih)
        return max(25, min(100, int(scale * 100)))

    def _apply_auto_zoom(self) -> None:
        if not self._zoom_auto or self._applying_auto_zoom:
            return
        vp = self._scroll.viewport().size()
        if vp.width() < 32 or vp.height() < 32:
            return
        pct = self._fit_zoom_pct_for_size(vp.width(), vp.height())
        if pct == self._zoom.value() and abs(self._canvas.zoom() * 100 - pct) < 0.5:
            return
        self._applying_auto_zoom = True
        try:
            self._zoom.blockSignals(True)
            self._zoom.set_value(pct)
            self._zoom.blockSignals(False)
            self._canvas.set_zoom(pct / 100.0)
        finally:
            self._applying_auto_zoom = False

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if getattr(self, "_scroll", None) is not None:
            self._apply_auto_zoom()
        host = getattr(self, "_stroke_host", None)
        if host is not None:
            host.reanchor()
        color_btn = getattr(self, "_color_btn", None)
        if color_btn is not None:
            color_btn.reanchor_popup()

    def _fit_window(self) -> None:
        """Size and center the window on the cursor's monitor; start in auto-fit."""
        self._zoom_auto = True
        screens = QGuiApplication.screens()
        cursor = QCursor.pos()
        mon = screens[0].availableGeometry() if screens else QRect(0, 0, 1200, 800)
        for s in screens:
            if s.geometry().contains(cursor):
                mon = s.availableGeometry()
                break
        img = self._canvas.image_size()
        pad_w, pad_h = 48, 120
        max_w = max(400, mon.width() - 80)
        max_h = max(300, mon.height() - 80)
        pct = self._fit_zoom_pct_for_size(max_w - pad_w, max_h - pad_h)
        self._applying_auto_zoom = True
        try:
            self._zoom.blockSignals(True)
            self._zoom.set_value(pct)
            self._zoom.blockSignals(False)
            self._canvas.set_zoom(pct / 100.0)
        finally:
            self._applying_auto_zoom = False
        win_w = min(max_w, int(img.width() * self._canvas.zoom()) + pad_w)
        win_h = min(max_h, int(img.height() * self._canvas.zoom()) + pad_h)
        self.resize(max(480, win_w), max(360, win_h))
        x = mon.x() + max(0, (mon.width() - self.width()) // 2)
        y = mon.y() + max(0, (mon.height() - self.height()) // 2)
        self.move(x, y)

    def _on_zoom(self, value: int) -> None:
        if not self._applying_auto_zoom:
            self._leave_auto_zoom()
        self._canvas.set_zoom(value / 100.0)

    def _reset_zoom(self) -> None:
        self._leave_auto_zoom()
        if self._zoom.value() == 100:
            self._canvas.set_zoom(1.0)
            return
        self._zoom.set_value(100)

    def _on_canvas_zoom(self, zoom: float) -> None:
        if not self._applying_auto_zoom:
            self._leave_auto_zoom()
        pct = int(round(zoom * 100))
        self._zoom.blockSignals(True)
        self._zoom.set_value(pct)
        self._zoom.blockSignals(False)

    def _on_canvas_changed(self) -> None:
        self._update_title()
        if self._zoom_auto:
            self._apply_auto_zoom()

    def _set_tool(self, tool: str) -> None:
        self._canvas.tool = tool
        for k, b in self._tool_btns.items():
            b.setChecked(k == tool)
        self._refresh_toolbar_icons()
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)

    def _on_color_picked(self, color: QColor) -> None:
        self._close_stroke_popup()
        self._canvas.color = QColor(color)

    def _copy(self) -> None:
        self._close_stroke_popup()
        self._color_btn.close_popup()
        export_pixmap(self._canvas.composite(), save=False, parent=self)

    def _save(self) -> None:
        self._close_stroke_popup()
        self._color_btn.close_popup()
        export_pixmap(self._canvas.composite(), save=True, parent=self)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Control, Qt.Key.Key_Meta):
            self._canvas._update_nav_cursor(e.modifiers() | Qt.KeyboardModifier.ControlModifier)
        if e.key() == Qt.Key.Key_Escape:
            if self._stroke_host is not None and self._stroke_host.is_open():
                self._close_stroke_popup()
                return
            if self._color_btn.is_popup_open():
                self._color_btn.close_popup()
                return
            self.close()
        elif e.key() == Qt.Key.Key_Z and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._canvas.redo()
            else:
                self._canvas.undo()
        elif e.key() == Qt.Key.Key_Y and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._canvas.redo()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._copy()
        elif e.key() == Qt.Key.Key_C and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._copy()
        elif e.key() == Qt.Key.Key_S and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._save()
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() in (Qt.Key.Key_Control, Qt.Key.Key_Meta):
            self._canvas._update_nav_cursor(e.modifiers())
        super().keyReleaseEvent(e)


# Keep a strong ref so the dialog isn't GC'd when the capture overlay closes.
_editor_ref: ScreenshotEditorDialog | None = None


def open_editor(crop: QPixmap, parent: QWidget | None = None) -> ScreenshotEditorDialog:
    """Show the screenshot editor window for the given crop."""
    global _editor_ref
    if _editor_ref is not None:
        try:
            _editor_ref.close()
        except Exception:
            pass
        _editor_ref = None

    dlg = ScreenshotEditorDialog(crop, parent=parent)

    def _clear(_obj=None, _dlg=dlg):
        global _editor_ref
        if _editor_ref is _dlg:
            _editor_ref = None

    dlg.destroyed.connect(_clear)
    _editor_ref = dlg
    dlg.show()
    dlg.activateWindow()
    dlg.raise_()
    return dlg

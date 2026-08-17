from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton, QVBoxLayout, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

_DURATION = 90
_RADIUS = 4.0
_ITEM_HEIGHT = 36
_INDICATOR_WIDTH = 3
_INDICATOR_HEIGHT = 16
_TRANSPARENT = QColor(0, 0, 0, 0)
_MENU_RADIUS = 8
_OPEN_MS = 90
_REVEAL_MS = 200
_SHADOW_MARGIN = 24
_SHADOW_BLUR = 28
_SHADOW_DY = 6
_SHADOW_ALPHA = 110

# Token keys for trigger states: (bg_key, border_key)
_TRIGGER_MAP = {
    "normal": ("control_fill_default", "control_stroke_default"),
    "hover": ("control_fill_secondary", "control_stroke_default"),
}
_PROPS = ("bg", "border")


def _resolve(t: dict[str, str], key: str) -> QColor:
    return QColor(t[key])


class _DropDownItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, key: str, label: str, tokens: dict, parent=None) -> None:
        super().__init__(parent)
        self._key = key
        self._label = label
        self._tokens = tokens
        self._selected = False
        self._bg = QColor(_TRANSPARENT)

        self.setFixedHeight(_ITEM_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(14)
        self.setFont(font)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def enterEvent(self, event) -> None:
        self._bg = _resolve(self._tokens, "subtle_fill_secondary")
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._bg = QColor(_TRANSPARENT)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._key)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 2, -4, -2).toRectF()

        # Hover background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Accent indicator for selected item
        if self._selected:
            indicator_rect = QRectF(
                rect.left() + 4,
                rect.center().y() - _INDICATOR_HEIGHT / 2,
                _INDICATOR_WIDTH,
                _INDICATOR_HEIGHT,
            )
            p.setBrush(_resolve(self._tokens, "accent_fill_default"))
            p.drawRoundedRect(indicator_rect, 1.5, 1.5)

        # Text
        p.setPen(_resolve(self._tokens, "text_primary"))
        p.setFont(self.font())
        p.drawText(rect.adjusted(16, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)
        p.end()


class _DropDownPopup(QWidget):
    itemSelected = pyqtSignal(str)

    def __init__(self, items: list[tuple[str, str]], current: str, tokens: dict, trigger: QWidget) -> None:
        super().__init__(
            trigger, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAutoFillBackground(False)

        bg = tokens["dropdown_menu_bg_solid"]
        self._reveal = 1.0
        self._menu_top = 0
        self._selected_index = 0

        self._container = QWidget(self)
        self._container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._container.setStyleSheet(f"background-color: {bg}; border-radius: {_MENU_RADIUS}px;")
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(_SHADOW_BLUR)
        self._shadow.setOffset(0, _SHADOW_DY)
        self._shadow.setColor(QColor(0, 0, 0, _SHADOW_ALPHA))
        self._container.setGraphicsEffect(self._shadow)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(0)

        for key, label in items:
            item = _DropDownItem(key, label, tokens, self._container)
            item.set_selected(key == current)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)

        self._container.setFixedSize(trigger.width(), self._container.sizeHint().height())
        self.setFixedWidth(trigger.width() + _SHADOW_MARGIN * 2)

    @pyqtProperty(float)
    def reveal(self) -> float:
        return self._reveal

    @reveal.setter
    def reveal(self, value: float) -> None:
        self._reveal = value
        menu_h = self._container.height()
        sel_top = 4 + self._selected_index * _ITEM_HEIGHT
        sel_bottom = sel_top + _ITEM_HEIGHT
        top = sel_top * (1.0 - value)
        bottom = sel_bottom + (menu_h - sel_bottom) * value
        self.setGeometry(
            self.x(),
            int(self._menu_top + top) - _SHADOW_MARGIN,
            self.width(),
            int(bottom - top) + _SHADOW_MARGIN * 2,
        )
        self._container.move(_SHADOW_MARGIN, _SHADOW_MARGIN - int(top))

    def show_at(self, trigger: QWidget, current_index: int) -> None:
        self._selected_index = current_index
        item_offset = current_index * _ITEM_HEIGHT + 4
        x_offset = trigger.width() - self._container.width()
        pos = trigger.mapToGlobal(QPoint(x_offset - _SHADOW_MARGIN, -item_offset - _SHADOW_MARGIN))
        self._menu_top = pos.y() + _SHADOW_MARGIN

        self.move(pos)
        self.setWindowOpacity(0.0)
        self.reveal = 0.0
        self.show()

        group = QParallelAnimationGroup(self)

        opacity = QPropertyAnimation(self, b"windowOpacity")
        opacity.setDuration(_OPEN_MS)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        group.addAnimation(opacity)

        unfold = QPropertyAnimation(self, b"reveal")
        unfold.setDuration(_REVEAL_MS)
        unfold.setStartValue(0.0)
        unfold.setEndValue(1.0)
        unfold.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(unfold)

        self._anim = group
        group.start()

    def mousePressEvent(self, event) -> None:
        if not self._container.geometry().contains(event.pos()):
            self.close()
            return
        super().mousePressEvent(event)

    def _on_item_clicked(self, key: str) -> None:
        self.itemSelected.emit(key)
        self.close()


# Trigger button


class DropDown(QPushButton):
    currentChanged = pyqtSignal(str)

    def __init__(self, items: list[tuple[str, str]] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = items or []
        self._current = self._items[0][0] if self._items else ""
        self._popup: _DropDownPopup | None = None

        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(14)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        fm = QFontMetrics(font)
        longest = max((fm.horizontalAdvance(label) for _, label in self._items), default=40)
        self.setFixedWidth(longest + 12 + 32 + 12)

        self._theme_key = theme_key()
        t = get_tokens()
        self._tokens = t
        self._build_states(t)
        self._apply_state("normal")

        self._anim_group = QParallelAnimationGroup(self)
        for name in _PROPS:
            anim = QPropertyAnimation(self, name.encode())
            anim.setDuration(_DURATION)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            setattr(self, f"_anim_{name}", anim)
            self._anim_group.addAnimation(anim)

        self.clicked.connect(self._toggle_popup)
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_states(self, t: dict[str, str]) -> None:
        self._states = {
            state: {"bg": _resolve(t, keys[0]), "border": _resolve(t, keys[1])} for state, keys in _TRIGGER_MAP.items()
        }

    def _apply_state(self, state: str) -> None:
        target = self._states[state]
        self._bg = QColor(target["bg"])
        self._border = QColor(target["border"])

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        t = get_tokens()
        self._tokens = t
        self._build_states(t)
        self._anim_group.stop()
        self._apply_state("normal")
        self.update()

    # Animated properties

    @pyqtProperty(QColor)
    def bg(self) -> QColor:
        return self._bg

    @bg.setter
    def bg(self, c: QColor) -> None:
        self._bg = c
        self.update()

    @pyqtProperty(QColor)
    def border(self) -> QColor:
        return self._border

    @border.setter
    def border(self, c: QColor) -> None:
        self._border = c
        self.update()

    def _animate_to(self, state: str) -> None:
        target = self._states.get(state, self._states["normal"])
        self._anim_group.stop()
        for name in _PROPS:
            anim: QPropertyAnimation = getattr(self, f"_anim_{name}")
            anim.setStartValue(getattr(self, f"_{name}"))
            anim.setEndValue(target[name])
        self._anim_group.start()

    def enterEvent(self, event) -> None:
        self._animate_to("hover")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to("normal")
        super().leaveEvent(event)

    def set_current(self, key: str) -> None:
        if key != self._current:
            self._current = key
            self.update()
            self.currentChanged.emit(key)

    def current(self) -> str:
        return self._current

    def _current_label(self) -> str:
        for key, label in self._items:
            if key == self._current:
                return label
        return ""

    def _toggle_popup(self) -> None:
        if self._popup and self._popup.isVisible():
            self._popup.close()
            self._popup = None
            return
        self._popup = _DropDownPopup(self._items, self._current, self._tokens, self)
        self._popup.itemSelected.connect(self._on_popup_selected)
        self._popup.destroyed.connect(self._on_popup_destroyed)
        current_index = next((i for i, (k, _) in enumerate(self._items) if k == self._current), 0)
        self._popup.show_at(self, current_index)

    def _on_popup_selected(self, key: str) -> None:
        self.set_current(key)
        self._popup = None

    def _on_popup_destroyed(self) -> None:
        self._popup = None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().toRectF()

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Border: light at the top grading to the stronger bottom edge, as Button paints it.
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0, _resolve(self._tokens, "control_stroke_secondary"))
        grad.setColorAt(1, self._border)
        p.setPen(QPen(QBrush(grad), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS - 0.5, _RADIUS - 0.5)

        # Text (current selection)
        p.setPen(_resolve(self._tokens, "text_primary"))
        p.setFont(self.font())
        p.drawText(
            rect.adjusted(12, 0, -28, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._current_label(),
        )

        # Chevron
        p.setPen(
            QPen(
                _resolve(self._tokens, "text_secondary"),
                1.4,
                cap=Qt.PenCapStyle.RoundCap,
                join=Qt.PenJoinStyle.RoundJoin,
            )
        )
        cx, cy = rect.right() - 16, rect.center().y()
        p.drawPolyline([QPointF(cx - 3, cy - 0.8), QPointF(cx, cy + 2), QPointF(cx + 3, cy - 0.8)])

        p.end()

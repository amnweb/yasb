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
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

_DURATION = 150
_RADIUS = 4.0
_ITEM_HEIGHT = 36
_INDICATOR_WIDTH = 3
_INDICATOR_HEIGHT = 16
_TRANSPARENT = QColor(0, 0, 0, 0)

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

        self._anim = QPropertyAnimation(self, b"bg")
        self._anim.setDuration(_DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    @pyqtProperty(QColor)
    def bg(self) -> QColor:
        return self._bg

    @bg.setter
    def bg(self, c: QColor) -> None:
        self._bg = c
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._bg)
        self._anim.setEndValue(_resolve(self._tokens, "subtle_fill_secondary"))
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._bg)
        self._anim.setEndValue(QColor(_TRANSPARENT))
        self._anim.start()
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
        p.drawText(rect.adjusted(20, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)
        p.end()


def _is_transparency_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "EnableTransparency")
            return value == 1
    except Exception:
        return False


class _DropDownPopup(QWidget):
    itemSelected = pyqtSignal(str)

    def __init__(self, items: list[tuple[str, str]], current: str, tokens: dict, trigger: QWidget) -> None:
        super().__init__(
            trigger, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        bg = tokens["dropdown_menu_bg"] if _is_transparency_enabled() else tokens["dropdown_menu_bg_solid"]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = QWidget(self)
        container.setStyleSheet(f"background-color: {bg}; border-radius: {int(_RADIUS + 2)}px;")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(0)

        for key, label in items:
            item = _DropDownItem(key, label, tokens, self)
            item.set_selected(key == current)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)

        self.setFixedWidth(trigger.width())

    def show_at(self, trigger: QWidget, current_index: int) -> None:
        item_offset = current_index * _ITEM_HEIGHT + 4
        x_offset = trigger.width() - self.width()
        pos = trigger.mapToGlobal(QPoint(x_offset, -item_offset))
        self.move(pos)
        self.show()
        from core.utils.win32.backdrop import enable_blur

        enable_blur(int(self.winId()), RoundCorners=True, RoundCornersType="normal", BorderColor="None")

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
        current_index = next((i for i, (k, _) in enumerate(self._items) if k == self._current), 0)
        self._popup.show_at(self, current_index)

    def _on_popup_selected(self, key: str) -> None:
        self.set_current(key)
        self._popup = None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1).toRectF()

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Border
        p.setPen(QPen(self._border, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Bottom border
        p.setPen(QPen(_resolve(self._tokens, "control_stroke_secondary"), 1.0))
        p.drawLine(
            QPointF(rect.left() + _RADIUS, rect.bottom()),
            QPointF(rect.right() - _RADIUS, rect.bottom()),
        )

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

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFrame, QWidget

from core.ui.theme import get_tokens, theme_key

_DURATION = 100
_RADIUS = 4.0
_PROPS = ("bg", "border")

# Token keys per visual state: (bg_key, border_key)
_TOKEN_MAP = {
    "normal": ("card_bg_default", "card_stroke_default"),
    "hover": ("card_bg_tertiary", "card_stroke_default"),
    "selected": ("accent_fill_default", "accent_fill_default"),
}


def _resolve(t: dict[str, str], key: str) -> QColor:
    return QColor(t[key])


class Card(QFrame):
    """Card with custom-painted background, border, and animated hover/selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected = False
        self._theme_key = theme_key()
        self._build_states(get_tokens())
        self._apply_state("normal")

        self._anim_group = QParallelAnimationGroup(self)
        for name in _PROPS:
            anim = QPropertyAnimation(self, name.encode())
            anim.setDuration(_DURATION)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            setattr(self, f"_anim_{name}", anim)
            self._anim_group.addAnimation(anim)

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_states(self, t: dict[str, str]) -> None:
        self._states = {
            state: {"bg": _resolve(t, keys[0]), "border": _resolve(t, keys[1])} for state, keys in _TOKEN_MAP.items()
        }
        self._accent_fg = t["text_on_accent_primary"]

    def _apply_state(self, state: str) -> None:
        target = self._states[state]
        self._bg = QColor(target["bg"])
        self._border = QColor(target["border"])

    def _current_state(self) -> str:
        return "selected" if self._selected else "normal"

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_states(get_tokens())
        self._anim_group.stop()
        self._apply_state(self._current_state())
        self._update_child_colors()
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

    # Selection
    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._animate_to(self._current_state())
        self._update_child_colors()

    def is_selected(self) -> bool:
        return self._selected

    def _update_child_colors(self) -> None:
        from core.ui.components.text_block import TextBlock

        color = self._accent_fg if self._selected else None
        for label in self.findChildren(TextBlock):
            label.set_color_override(color)

    def enterEvent(self, event) -> None:
        if not self._selected:
            self._animate_to("hover")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(self._current_state())
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1).toRectF()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)
        p.setPen(QPen(self._border, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)
        p.end()

from collections.abc import Callable
from typing import Any, override

import PyQt6.QtCore as QtCore
from PyQt6.QtCore import QEasingCurve, QEvent, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt
from PyQt6.QtGui import QColor, QEnterEvent, QFont, QFontMetrics, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from core.ui.theme import FONT_FAMILIES, FONT_WEIGHTS, get_tokens, theme_key

# pyqtProperty exists at runtime but is missing from the PyQt6 type stubs
pyqtProperty: Callable[..., Any] = getattr(QtCore, "pyqtProperty")

_DURATION = 83
_RADIUS = 4.0
_TRANSPARENT = QColor(0, 0, 0, 0)
_DEFAULT_PADDING = (8, 4, 8, 4)
_PROPS = ("bg", "fg")

# Token keys per state: (bg_key, fg_key)
# None = transparent
_TOKEN_MAP = {
    "normal": (None, "accent_text_primary"),
    "hover": ("subtle_fill_secondary", "accent_text_secondary"),
    "pressed": ("subtle_fill_tertiary", "accent_text_tertiary"),
    "disabled": (None, "accent_text_disabled"),
}


def _resolve(t: dict[str, str], key: str | None) -> QColor:
    return QColor(t[key]) if key else QColor(_TRANSPARENT)


def _parse_padding(value: str | None, default: tuple[int, ...]) -> tuple[int, ...]:
    if value is None:
        return default
    parts = [int(v.strip()) for v in value.split(",")]
    match len(parts):
        case 4:
            return tuple(parts)
        case 2:
            return (parts[0], parts[1], parts[0], parts[1])
        case 1:
            return (parts[0],) * 4
        case _:
            return default


class Link(QPushButton):
    """Animated hyperlink button.

    Args:
        text: Button label.
        padding: ``"l,t,r,b"`` | ``"h,v"`` | ``"all"``. Default ``"8,4,8,4"``.
        font_family: Comma-separated family names.
        font_size: Pixel size. Default ``14``.
        font_weight: ``"thin"`` | ``"light"`` | ``"normal"`` | ``"medium"`` | ``"demibold"`` | ``"bold"`` | Default ``"normal"``.
        parent: Parent widget.
    """

    def __init__(
        self,
        text: str = "",
        padding: str | None = None,
        font_family: str | None = None,
        font_size: int | None = None,
        font_weight: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._padding = _parse_padding(padding, _DEFAULT_PADDING)

        font = QFont()
        if font_family is not None:
            font.setFamilies([f.strip() for f in font_family.split(",")])
        else:
            font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(font_size if font_size is not None else 14)
        font.setWeight(FONT_WEIGHTS.get((font_weight or "normal").lower(), QFont.Weight.Normal))
        self.setFont(font)

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

        app = QApplication.instance()
        if app:
            app.paletteChanged.connect(self._on_theme_changed)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

    def _build_states(self, t: dict[str, str]) -> None:
        self._states = {
            state: {"bg": _resolve(t, keys[0]), "fg": _resolve(t, keys[1])} for state, keys in _TOKEN_MAP.items()
        }

    def _apply_state(self, state: str) -> None:
        target = self._states[state]
        self._bg = QColor(target["bg"])
        self._fg = QColor(target["fg"])

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_states(get_tokens())
        self._anim_group.stop()
        self._apply_state("normal" if self.isEnabled() else "disabled")
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        pl, pt, pr, pb = self._padding
        return QSize(fm.horizontalAdvance(self.text()) + pl + pr, fm.height() + pt + pb)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # Animated properties

    def _get_bg(self) -> QColor:
        return self._bg

    def _set_bg(self, c: QColor) -> None:
        self._bg = c
        self.update()

    bg: QColor = pyqtProperty(QColor, _get_bg, _set_bg)

    def _get_fg(self) -> QColor:
        return self._fg

    def _set_fg(self, c: QColor) -> None:
        self._fg = c
        self.update()

    fg: QColor = pyqtProperty(QColor, _get_fg, _set_fg)

    def _animate_to(self, state: str) -> None:
        target = self._states.get(state, self._states["normal"])
        self._anim_group.stop()
        for name in _PROPS:
            anim: QPropertyAnimation = getattr(self, f"_anim_{name}")
            anim.setStartValue(getattr(self, f"_{name}"))
            anim.setEndValue(target[name])
        self._anim_group.start()

    @override
    def enterEvent(self, event: QEnterEvent | None) -> None:
        if self.isEnabled():
            self._animate_to("hover")
        super().enterEvent(event)

    @override
    def leaveEvent(self, a0: QEvent | None) -> None:
        if self.isEnabled():
            self._animate_to("normal")
        super().leaveEvent(a0)

    @override
    def mousePressEvent(self, e: QMouseEvent | None) -> None:
        if self.isEnabled():
            self._animate_to("pressed")
        super().mousePressEvent(e)

    @override
    def mouseReleaseEvent(self, e: QMouseEvent | None) -> None:
        if self.isEnabled():
            self._animate_to("hover" if e is not None and self.rect().contains(e.pos()) else "normal")
        super().mouseReleaseEvent(e)

    @override
    def changeEvent(self, e: QEvent | None) -> None:
        super().changeEvent(e)
        if e is not None and e.type() == e.Type.EnabledChange:
            self._animate_to("normal" if self.isEnabled() else "disabled")

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1).toRectF()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(r, _RADIUS, _RADIUS)

        p.setPen(self._fg)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()

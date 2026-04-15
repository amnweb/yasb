from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from core.ui.theme import FONT_FAMILIES, FONT_WEIGHTS, get_tokens, theme_key

_DURATION = 83
_RADIUS = 4.0
_TRANSPARENT = QColor(0, 0, 0, 0)
_DEFAULT_PADDING = (11, 5, 11, 6)
_PROPS = ("bg", "fg", "border", "border_top")

_VARIANTS = {
    "default": {
        "normal": ("control_fill_default", "text_primary", "control_stroke_default", "control_stroke_secondary"),
        "hover": ("control_fill_secondary", "text_primary", "control_stroke_default", "control_stroke_secondary"),
        "pressed": ("control_fill_tertiary", "text_secondary", "control_stroke_default", "control_stroke_default"),
        "disabled": ("control_fill_disabled", "text_disabled", None, None),
    },
    "accent": {
        "normal": (
            "accent_fill_default",
            "text_on_accent_primary",
            "control_stroke_on_accent_secondary",
            "control_stroke_on_accent_default",
        ),
        "hover": (
            "accent_fill_secondary",
            "text_on_accent_primary",
            "control_stroke_on_accent_secondary",
            "control_stroke_on_accent_default",
        ),
        "pressed": (
            "accent_fill_tertiary",
            "text_on_accent_secondary",
            "control_stroke_on_accent_default",
            "control_stroke_on_accent_default",
        ),
        "disabled": ("control_fill_disabled", "text_disabled", None, None),
    },
    "subtle": {
        "normal": (None, "text_primary", None, None),
        "hover": ("subtle_fill_secondary", "text_primary", None, None),
        "pressed": ("subtle_fill_tertiary", "text_secondary", None, None),
        "disabled": ("subtle_fill_disabled", "text_disabled", None, None),
    },
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


class Button(QPushButton):
    """Animated button with variant-based color states.

    Args:
        text: Button label.
        variant: ``"default"``, ``"accent"``, or ``"subtle"``.
        padding: ``"l,t,r,b"`` | ``"h,v"`` | ``"all"``. Default ``"11,5,11,6"``.
        font_family: Comma-separated family names.
        font_size: Pixel size. Default ``13``.
        font_weight: ``"thin"`` | ``"light"`` | ``"normal"`` | ``"medium"`` | ``"demibold"`` | ``"bold"`` | Default ``"normal"``.
        parent: Parent widget.
    """

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
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

        self._variant = variant
        self._theme_key = theme_key()
        self._build_states(variant, get_tokens())
        self._apply_state("normal")

        self._anim_group = QParallelAnimationGroup(self)
        for name in _PROPS:
            anim = QPropertyAnimation(self, name.encode())
            anim.setDuration(_DURATION)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            setattr(self, f"_anim_{name}", anim)
            self._anim_group.addAnimation(anim)

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_states(self, variant: str, t: dict[str, str]) -> None:
        raw = _VARIANTS.get(variant, _VARIANTS["default"])
        self._states = {
            s: {
                "bg": _resolve(t, k[0]),
                "fg": _resolve(t, k[1]),
                "border": _resolve(t, k[2]),
                "border_top": _resolve(t, k[3]),
            }
            for s, k in raw.items()
        }

    def _apply_state(self, state: str) -> None:
        target = self._states[state]
        self._bg = QColor(target["bg"])
        self._fg = QColor(target["fg"])
        self._border = QColor(target["border"])
        self._border_top = QColor(target["border_top"])

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._build_states(variant, get_tokens())
        self._animate_to("normal" if self.isEnabled() else "disabled")

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_states(self._variant, get_tokens())
        self._anim_group.stop()
        self._apply_state("normal" if self.isEnabled() else "disabled")
        self.update()

    # Size

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        pad_l, pad_t, pad_r, pad_b = self._padding
        return QSize(fm.horizontalAdvance(self.text()) + pad_l + pad_r + 2, fm.height() + pad_t + pad_b + 2)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # Animated properties

    @pyqtProperty(QColor)
    def bg(self) -> QColor:
        return self._bg

    @bg.setter
    def bg(self, c: QColor) -> None:
        self._bg = c
        self.update()

    @pyqtProperty(QColor)
    def fg(self) -> QColor:
        return self._fg

    @fg.setter
    def fg(self, c: QColor) -> None:
        self._fg = c
        self.update()

    @pyqtProperty(QColor)
    def border(self) -> QColor:
        return self._border

    @border.setter
    def border(self, c: QColor) -> None:
        self._border = c
        self.update()

    @pyqtProperty(QColor)
    def border_top(self) -> QColor:
        return self._border_top

    @border_top.setter
    def border_top(self, c: QColor) -> None:
        self._border_top = c
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
        if self.isEnabled():
            self._animate_to("hover")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.isEnabled():
            self._animate_to("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.isEnabled():
            self._animate_to("pressed")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.isEnabled():
            self._animate_to("hover" if self.rect().contains(event.pos()) else "normal")
        super().mouseReleaseEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self._animate_to("normal" if self.isEnabled() else "disabled")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().toRectF()

        # Fill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(r, _RADIUS, _RADIUS)

        # 1px border inside, on top of the fill
        if self._border.alpha() or self._border_top.alpha():
            grad = QLinearGradient(0, 0, 0, r.height())
            grad.setColorAt(0, self._border_top)
            grad.setColorAt(1, self._border)
            p.setPen(QPen(QBrush(grad), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS - 0.5, _RADIUS - 0.5)

        # Text
        p.setPen(self._fg)
        p.setFont(self.font())
        pad_l, pad_t, pad_r, pad_b = self._padding
        p.drawText(
            self.rect().adjusted(pad_l, pad_t, -pad_r, -pad_b),
            Qt.AlignmentFlag.AlignCenter,
            self.text(),
        )
        p.end()

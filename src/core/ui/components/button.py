from PyQt6 import sip
from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from core.ui.theme import FONT_FAMILIES, FONT_WEIGHTS, get_tokens, theme_key
from core.utils.qobject import is_valid_qobject

_DURATION = 83
_RADIUS = 4.0
_TRANSPARENT = QColor(0, 0, 0, 0)
_DEFAULT_PADDING = (11, 5, 11, 6)
_ICON_TEXT_GAP = 6
_PROPS = ("bg", "fg", "border", "border_top")

_ACCENT_CHECKED = (
    "accent_fill_default",
    "text_on_accent_primary",
    "control_stroke_on_accent_secondary",
    "control_stroke_on_accent_default",
)
_ACCENT_CHECKED_HOVER = (
    "accent_fill_secondary",
    "text_on_accent_primary",
    "control_stroke_on_accent_secondary",
    "control_stroke_on_accent_default",
)
_ACCENT_CHECKED_PRESSED = (
    "accent_fill_tertiary",
    "text_on_accent_secondary",
    "control_stroke_on_accent_default",
    "control_stroke_on_accent_default",
)

_VARIANTS = {
    "default": {
        "normal": ("control_fill_default", "text_primary", "control_stroke_default", "control_stroke_secondary"),
        "hover": ("control_fill_secondary", "text_primary", "control_stroke_default", "control_stroke_secondary"),
        "pressed": ("control_fill_tertiary", "text_secondary", "control_stroke_default", "control_stroke_default"),
        "disabled": ("control_fill_disabled", "text_disabled", None, None),
        "checked": _ACCENT_CHECKED,
        "checked_hover": _ACCENT_CHECKED_HOVER,
        "checked_pressed": _ACCENT_CHECKED_PRESSED,
    },
    "accent": {
        "normal": _ACCENT_CHECKED,
        "hover": _ACCENT_CHECKED_HOVER,
        "pressed": _ACCENT_CHECKED_PRESSED,
        "disabled": ("control_fill_disabled", "text_disabled", None, None),
        "checked": _ACCENT_CHECKED,
        "checked_hover": _ACCENT_CHECKED_HOVER,
        "checked_pressed": _ACCENT_CHECKED_PRESSED,
    },
    "subtle": {
        "normal": (None, "text_primary", None, None),
        "hover": ("subtle_fill_secondary", "text_primary", None, None),
        "pressed": ("subtle_fill_tertiary", "text_secondary", None, None),
        "disabled": ("subtle_fill_disabled", "text_disabled", None, None),
        "checked": _ACCENT_CHECKED,
        "checked_hover": _ACCENT_CHECKED_HOVER,
        "checked_pressed": _ACCENT_CHECKED_PRESSED,
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
        text: Button label. Empty string is fine with ``setIcon``.
        variant: ``"default"``, ``"accent"``, or ``"subtle"``.
        padding: ``"l,t,r,b"`` | ``"h,v"`` | ``"all"``. Default ``"11,5,11,6"``.
        font_family: Comma-separated family names.
        font_size: Pixel size. Default ``14``.
        font_weight: ``"thin"`` | ``"light"`` | ``"normal"`` | ``"medium"`` | ``"demibold"`` | ``"bold"``.
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

        self.toggled.connect(self._on_toggled)
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
        target = self._states.get(state, self._states["normal"])
        self._bg = QColor(target["bg"])
        self._fg = QColor(target["fg"])
        self._border = QColor(target["border"])
        self._border_top = QColor(target["border_top"])

    def _interaction_state(self, hovering: bool) -> str:
        if not self.isEnabled():
            return "disabled"
        if self.isCheckable() and self.isChecked():
            return "checked_hover" if hovering else "checked"
        return "hover" if hovering else "normal"

    def _press_state(self) -> str:
        if self.isCheckable() and self.isChecked():
            return "checked_pressed"
        return "pressed"

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._build_states(variant, get_tokens())
        state = self._interaction_state(self.underMouse()) if self.isEnabled() else "disabled"
        self._animate_to(state)

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_states(self._variant, get_tokens())
        self._anim_group.stop()
        state = self._interaction_state(self.underMouse()) if self.isEnabled() else "disabled"
        self._apply_state(state)
        self.update()

    def _on_toggled(self, _checked: bool) -> None:
        if not is_valid_qobject(self) or not self.isEnabled():
            return
        self._animate_to(self._interaction_state(self.underMouse()))

    def setIcon(self, icon: QIcon) -> None:
        super().setIcon(icon)
        self.updateGeometry()
        self.update()

    def setIconSize(self, size: QSize) -> None:
        super().setIconSize(size)
        self.updateGeometry()
        self.update()

    # Size

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        pad_l, pad_t, pad_r, pad_b = self._padding
        text = self.text()
        tw = fm.horizontalAdvance(text) if text else 0
        th = fm.height() if text else 0

        icon = self.icon()
        if not icon.isNull():
            isz = self.iconSize()
            iw, ih = isz.width(), isz.height()
        else:
            iw = ih = 0

        gap = _ICON_TEXT_GAP if iw and tw else 0
        w = pad_l + pad_r + iw + gap + tw + 2
        h = pad_t + pad_b + max(th, ih, 0) + 2
        return QSize(max(1, w), max(1, h))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # Animated properties

    @pyqtProperty(QColor)
    def bg(self) -> QColor:
        return self._bg

    @bg.setter
    def bg(self, c: QColor) -> None:
        self._bg = c
        if not sip.isdeleted(self):
            self.update()

    @pyqtProperty(QColor)
    def fg(self) -> QColor:
        return self._fg

    @fg.setter
    def fg(self, c: QColor) -> None:
        self._fg = c
        if not sip.isdeleted(self):
            self.update()

    @pyqtProperty(QColor)
    def border(self) -> QColor:
        return self._border

    @border.setter
    def border(self, c: QColor) -> None:
        self._border = c
        if not sip.isdeleted(self):
            self.update()

    @pyqtProperty(QColor)
    def border_top(self) -> QColor:
        return self._border_top

    @border_top.setter
    def border_top(self, c: QColor) -> None:
        self._border_top = c
        if not sip.isdeleted(self):
            self.update()

    def _animate_to(self, state: str) -> None:
        if not is_valid_qobject(self):
            return
        target = self._states.get(state, self._states["normal"])
        self._anim_group.stop()
        for name in _PROPS:
            anim: QPropertyAnimation = getattr(self, f"_anim_{name}")
            anim.setStartValue(getattr(self, f"_{name}"))
            anim.setEndValue(target[name])
        self._anim_group.start()

    def enterEvent(self, event) -> None:
        if is_valid_qobject(self) and self.isEnabled():
            self._animate_to(self._interaction_state(True))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if is_valid_qobject(self) and self.isEnabled():
            self._animate_to(self._interaction_state(False))
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.isEnabled():
            self._animate_to(self._press_state())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        # clicked may destroy this widget (e.g. Cancel closes the host overlay).
        super().mouseReleaseEvent(event)
        if not is_valid_qobject(self):
            return
        if self.isEnabled():
            hovering = self.rect().contains(event.position().toPoint())
            self._animate_to(self._interaction_state(hovering))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if not is_valid_qobject(self):
            return
        if event.type() == event.Type.EnabledChange:
            if self.isEnabled():
                self._animate_to(self._interaction_state(self.underMouse()))
            else:
                self._animate_to("disabled")

    def paintEvent(self, _event) -> None:
        if sip.isdeleted(self):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().toRectF()

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

        pad_l, pad_t, pad_r, pad_b = self._padding
        content = self.rect().adjusted(pad_l, pad_t, -pad_r, -pad_b)
        text = self.text()
        icon = self.icon()
        has_icon = not icon.isNull()
        has_text = bool(text)

        mode = QIcon.Mode.Disabled if not self.isEnabled() else QIcon.Mode.Normal
        state = QIcon.State.On if (self.isCheckable() and self.isChecked()) else QIcon.State.Off

        if has_icon and has_text:
            isz = self.iconSize()
            fm = QFontMetrics(self.font())
            tw = fm.horizontalAdvance(text)
            total_w = isz.width() + _ICON_TEXT_GAP + tw
            x0 = content.x() + max(0, (content.width() - total_w) // 2)
            iy = content.y() + max(0, (content.height() - isz.height()) // 2)
            self._draw_icon(p, QRect(x0, iy, isz.width(), isz.height()), mode, state)
            p.setPen(self._fg)
            p.setFont(self.font())
            text_rect = QRect(
                x0 + isz.width() + _ICON_TEXT_GAP,
                content.y(),
                max(0, content.right() - (x0 + isz.width() + _ICON_TEXT_GAP) + 1),
                content.height(),
            )
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        elif has_icon:
            isz = self.iconSize()
            ix = content.x() + max(0, (content.width() - isz.width()) // 2)
            iy = content.y() + max(0, (content.height() - isz.height()) // 2)
            self._draw_icon(p, QRect(ix, iy, isz.width(), isz.height()), mode, state)
        elif has_text:
            p.setPen(self._fg)
            p.setFont(self.font())
            p.drawText(content, Qt.AlignmentFlag.AlignCenter, text)

        p.end()

    def _draw_icon(
        self,
        p: QPainter,
        target: QRect,
        mode: QIcon.Mode,
        state: QIcon.State,
    ) -> None:
        icon = self.icon()
        if icon.isNull() or target.isEmpty():
            return
        dev = p.device()
        dpr = float(dev.devicePixelRatioF()) if dev is not None else float(self.devicePixelRatioF())
        pm: QPixmap = icon.pixmap(target.size(), dpr, mode, state)
        if pm.isNull():
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawPixmap(target, pm)

import math
from typing import Literal

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QAbstractButton, QApplication, QLineEdit, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

_HEIGHT = 32
_RADIUS = 4.0
_PAD_LEFT = 10
_PAD_RIGHT = 6
_ICON_SIZE = 14
_ICON_GAP = 8
_BUTTON_WIDTH = 30
_BUTTON_MARGIN = 4
_GLYPH_HALF = 4
_FOCUS_LINE = 2
# QLineEdit draws its text 2 px inside the text margins.
_QT_TEXT_INSET = 2


class _ClearButton(QAbstractButton):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.tokens = get_tokens()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = QRectF(self.rect()).adjusted(0, _BUTTON_MARGIN, -_BUTTON_MARGIN, -_BUTTON_MARGIN)
        if self.isDown() or self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.tokens["subtle_fill_tertiary" if self.isDown() else "subtle_fill_secondary"]))
            p.drawRoundedRect(inner, _RADIUS, _RADIUS)
        # Centre on a device pixel: 45° lines through pixel corners smear over two pixels.
        dpr = self.devicePixelRatioF()
        cx = (math.floor(inner.center().x() * dpr) + 0.5) / dpr
        cy = (math.floor(inner.center().y() * dpr) + 0.5) / dpr
        half = (round(_GLYPH_HALF * dpr) + 0.5) / dpr
        color = QColor(self.tokens["text_tertiary" if self.isDown() else "text_secondary"])
        p.setPen(QPen(color, 1.0, cap=Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(cx - half, cy - half), QPointF(cx + half, cy + half))
        p.drawLine(QPointF(cx - half, cy + half), QPointF(cx + half, cy - half))
        p.end()


class TextBox(QLineEdit):
    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        icon_svg: str | None = None,
        icon_position: Literal["left", "right"] = "left",
        height: int = _HEIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._icon_svg = icon_svg
        self._icon_right = icon_position == "right"
        self._icon_pixmap: QPixmap | None = None
        self._icon_key: tuple[float, int] | None = None

        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(14)
        self.setFont(font)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(height)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self._clear_button = _ClearButton(self)
        self._clear_button.clicked.connect(self._on_clear_clicked)

        self._theme_key = theme_key()
        self._apply_theme()
        self._update_clear_button()
        self.textChanged.connect(self._update_clear_button)
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _apply_theme(self) -> None:
        t = get_tokens()
        self._tokens = t
        self._clear_button.tokens = t
        self._icon_pixmap = None
        self.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; padding: 0px; color: {t['text_primary']};"
            f" placeholder-text-color: {t['text_secondary']}; }}"
            f"QLineEdit:disabled {{ color: {t['text_disabled']}; placeholder-text-color: {t['text_disabled']}; }}"
        )

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._apply_theme()
        self._clear_button.update()
        self.update()

    def _on_clear_clicked(self) -> None:
        self.clear()
        self.textEdited.emit("")

    def _content_right(self) -> int:
        if self._icon_svg and self._icon_right:
            return self.width() - _PAD_LEFT - _ICON_SIZE - _BUTTON_MARGIN
        return self.width()

    def _update_clear_button(self) -> None:
        visible = bool(self.text()) and self.hasFocus() and self.isEnabled() and not self.isReadOnly()
        right = self._content_right()
        self._clear_button.setGeometry(right - _BUTTON_WIDTH, 0, _BUTTON_WIDTH, self.height())
        self._clear_button.setVisible(visible)
        left = _PAD_LEFT + _ICON_SIZE + _ICON_GAP if self._icon_svg and not self._icon_right else _PAD_LEFT
        reserved = self.width() - right + (_BUTTON_WIDTH if visible else 0) + _PAD_RIGHT
        self.setTextMargins(left - _QT_TEXT_INSET, 0, reserved - _QT_TEXT_INSET, 0)

    def _icon(self, dpr: float) -> QPixmap:
        color = QColor(self._tokens["text_disabled" if not self.isEnabled() else "text_secondary"])
        key = (dpr, color.rgba())
        if self._icon_pixmap is None or self._icon_key != key:
            size = round(_ICON_SIZE * dpr)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            renderer = QSvgRenderer(self._icon_svg.encode("utf-8"))
            renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
            painter.end()
            pixmap.setDevicePixelRatio(dpr)
            self._icon_pixmap, self._icon_key = pixmap, key
        return self._icon_pixmap

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._update_clear_button()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._update_clear_button()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_clear_button()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self._update_clear_button()

    def paintEvent(self, event) -> None:
        t = self._tokens
        enabled, focused = self.isEnabled(), self.hasFocus()
        if not enabled:
            fill = t["control_fill_disabled"]
        elif focused:
            fill = t["control_fill_secondary"] if self._theme_key == "dark" else t["control_fill_input_active"]
        elif self.underMouse():
            fill = t["control_fill_secondary"]
        else:
            fill = t["control_fill_default"]

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        shape = QPainterPath()
        shape.addRoundedRect(rect, _RADIUS, _RADIUS)
        p.fillPath(shape, QColor(fill))

        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0, QColor(t["control_stroke_secondary"]))
        grad.setColorAt(1, QColor(t["control_stroke_default"]))
        p.setPen(QPen(QBrush(grad), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS - 0.5, _RADIUS - 0.5)
        if enabled and focused:
            line = QPainterPath()
            line.addRect(QRectF(0, rect.height() - _FOCUS_LINE, rect.width(), _FOCUS_LINE))
            p.fillPath(shape.intersected(line), QColor(t["accent_fill_default"]))

        if self._icon_svg:
            x = self.width() - _PAD_LEFT - _ICON_SIZE if self._icon_right else _PAD_LEFT
            y = (self.height() - _ICON_SIZE) / 2
            p.drawPixmap(QPointF(x, y), self._icon(self.devicePixelRatioF()))
        p.end()
        super().paintEvent(event)

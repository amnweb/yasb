from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

from core.ui.components.button import _DEFAULT_PADDING, Button
from core.ui.theme import FONT_FAMILIES, get_tokens

_ITEM_HEIGHT = 36
_ITEM_RADIUS = 4.0
_ITEM_PADDING = 12
_ICON_SIZE = 16
_ICON_GAP = 12
_SEPARATOR_HEIGHT = 9
_MENU_RADIUS = 8
_MENU_GAP = 4
_OPEN_MS = 160
_SHADOW_MARGIN = 24
_SHADOW_BLUR = 28
_SHADOW_DY = 6
_SHADOW_ALPHA = 110
_CHEVRON_WIDTH = 8
_CHEVRON_GAP = 8

MenuItem = tuple[str, str] | tuple[str, str, str] | None


def _tinted_svg(svg: str, color: QColor, size: int, dpr: float) -> QPixmap:
    side = round(size * dpr)
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, side, side))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class _MenuItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, key: str, label: str, icon_svg: str, icon_column: bool, tokens: dict, parent=None) -> None:
        super().__init__(parent)
        self._key = key
        self._label = label
        self._icon_svg = icon_svg
        self._icon_column = icon_column
        self._tokens = tokens
        self._hovered = False
        self._icon: QPixmap | None = None
        self.setFixedHeight(_ITEM_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(14)
        self.setFont(font)

    def _text_left(self) -> int:
        return 4 + _ITEM_PADDING + (_ICON_SIZE + _ICON_GAP if self._icon_column else 0)

    def sizeHint(self) -> QSize:
        width = self._text_left() + QFontMetrics(self.font()).horizontalAdvance(self._label) + _ITEM_PADDING * 2 + 4
        return QSize(width, _ITEM_HEIGHT)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._key)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 2, -4, -2).toRectF()
        if self._hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self._tokens["subtle_fill_secondary"]))
            p.drawRoundedRect(rect, _ITEM_RADIUS, _ITEM_RADIUS)
        text_color = QColor(self._tokens["text_primary"])
        if self._icon_svg:
            if self._icon is None or self._icon.devicePixelRatio() != self.devicePixelRatioF():
                self._icon = _tinted_svg(self._icon_svg, text_color, _ICON_SIZE, self.devicePixelRatioF())
            p.drawPixmap(4 + _ITEM_PADDING, (self.height() - _ICON_SIZE) // 2, self._icon)
        p.setPen(text_color)
        p.setFont(self.font())
        p.drawText(
            QRectF(self._text_left(), 0, self.width() - self._text_left(), self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._label,
        )
        p.end()


class _Separator(QWidget):
    def __init__(self, tokens: dict, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(tokens["divider_stroke_default"])
        self.setFixedHeight(_SEPARATOR_HEIGHT)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(QRect(0, self.height() // 2, self.width(), 1), self._color)
        p.end()


class _MenuFlyout(QWidget):
    triggered = pyqtSignal(str)

    def __init__(self, items: list[MenuItem], tokens: dict, trigger: QWidget) -> None:
        super().__init__(
            trigger, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._trigger = trigger
        self._reveal = 1.0
        self._upward = False
        self._menu_rect = QRect()

        self._container = QWidget(self)
        self._container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._container.setStyleSheet(
            f"background-color: {tokens['dropdown_menu_bg_solid']}; border-radius: {_MENU_RADIUS}px;"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(_SHADOW_BLUR)
        shadow.setOffset(0, _SHADOW_DY)
        shadow.setColor(QColor(0, 0, 0, _SHADOW_ALPHA))
        self._container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(0)
        icon_column = any(item is not None and len(item) > 2 and item[2] for item in items)
        for item in items:
            if item is None:
                layout.addWidget(_Separator(tokens, self._container))
                continue
            key, label, *rest = item
            entry = _MenuItem(key, label, rest[0] if rest else "", icon_column, tokens, self._container)
            entry.clicked.connect(self._on_item_clicked)
            layout.addWidget(entry)

        hint = self._container.sizeHint()
        self._container.setFixedSize(max(hint.width(), trigger.width()), hint.height())

    @pyqtProperty(float)
    def reveal(self) -> float:
        return self._reveal

    @reveal.setter
    def reveal(self, value: float) -> None:
        self._reveal = value
        menu = self._menu_rect
        visible = max(1, round(menu.height() * value))
        hidden = menu.height() - visible if self._upward else 0
        self.setGeometry(
            menu.left() - _SHADOW_MARGIN,
            menu.top() + hidden - _SHADOW_MARGIN,
            menu.width() + _SHADOW_MARGIN * 2,
            visible + _SHADOW_MARGIN * 2,
        )
        self._container.move(_SHADOW_MARGIN, _SHADOW_MARGIN - hidden)

    def popup(self) -> None:
        trigger = self._trigger
        size = self._container.size()
        below = trigger.mapToGlobal(QPoint(0, trigger.height() + _MENU_GAP))
        window = trigger.window()
        window_right = window.mapToGlobal(QPoint(window.width(), 0)).x()
        x = below.x()
        if x + size.width() > window_right:
            x = trigger.mapToGlobal(QPoint(trigger.width(), 0)).x() - size.width()
        y = below.y()
        screen = trigger.screen().availableGeometry()
        self._upward = y + size.height() > screen.bottom()
        if self._upward:
            y = trigger.mapToGlobal(QPoint(0, -_MENU_GAP)).y() - size.height()
        self._menu_rect = QRect(QPoint(x, y), size)

        self.setWindowOpacity(0.0)
        self.reveal = 0.0
        self.show()

        group = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(_OPEN_MS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        group.addAnimation(fade)
        unfold = QPropertyAnimation(self, b"reveal", self)
        unfold.setDuration(_OPEN_MS)
        unfold.setStartValue(0.0)
        unfold.setEndValue(1.0)
        unfold.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(unfold)
        self._animation = group
        group.start()

    def mousePressEvent(self, event) -> None:
        if not self._container.geometry().contains(event.position().toPoint()):
            # Qt replays the closing click to the widget under it; on the trigger that would reopen the menu.
            if self._trigger.rect().contains(self._trigger.mapFromGlobal(event.globalPosition().toPoint())):
                self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
            self.close()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _on_item_clicked(self, key: str) -> None:
        self.close()
        self.triggered.emit(key)


class DropDownButton(Button):
    """Button that opens a menu of actions, like WinUI's DropDownButton with a MenuFlyout.

    Args:
        text: Button label. Empty for an icon-only button.
        icon_svg: SVG markup drawn in the button's text color.
        items: ``(key, label)`` or ``(key, label, icon_svg)`` per entry, ``None`` for a separator.
        variant: ``"default"``, ``"accent"``, or ``"subtle"``.
        chevron: Draw the down arrow that marks the button as a menu.
    """

    triggered = pyqtSignal(str)

    def __init__(
        self,
        text: str = "",
        icon_svg: str | None = None,
        items: list[MenuItem] | None = None,
        variant: str = "default",
        chevron: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        left, top, right, bottom = _DEFAULT_PADDING
        if chevron:
            right += _CHEVRON_GAP + _CHEVRON_WIDTH
        super().__init__(text, variant=variant, padding=f"{left},{top},{right},{bottom}", parent=parent)
        self._icon_svg = icon_svg
        self._items = items or []
        self._chevron = chevron
        self._menu: _MenuFlyout | None = None
        if icon_svg:
            self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            self._update_icon()
        self.clicked.connect(self._toggle_menu)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        left, top, right, bottom = self._padding
        return QSize(hint.width(), top + bottom + QFontMetrics(self.font()).height() + 2)

    def _update_icon(self) -> None:
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        self.setIcon(QIcon(_tinted_svg(self._icon_svg, QColor(get_tokens()["text_primary"]), _ICON_SIZE, dpr)))

    def _on_theme_changed(self) -> None:
        super()._on_theme_changed()
        if self._icon_svg:
            self._update_icon()

    def _toggle_menu(self) -> None:
        if self._menu is not None:
            self._menu.close()
            return
        self._menu = _MenuFlyout(self._items, get_tokens(), self)
        self._menu.triggered.connect(self.triggered.emit)
        self._menu.destroyed.connect(self._on_menu_closed)
        self._menu.popup()

    def _on_menu_closed(self) -> None:
        self._menu = None
        hovering = self.isVisible() and self.rect().contains(self.mapFromGlobal(QCursor.pos()))
        self._animate_to(self._interaction_state(hovering))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._chevron:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self._fg, 1.4, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        cx = self.width() - _DEFAULT_PADDING[2] - _CHEVRON_WIDTH / 2
        cy = self.height() / 2
        p.drawPolyline([QPointF(cx - 3, cy - 1.5), QPointF(cx, cy + 1.5), QPointF(cx + 3, cy - 1.5)])
        p.end()

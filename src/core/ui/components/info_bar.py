from enum import Enum

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

_RADIUS = 4.0
_ICON_CIRCLE_R = 8.0
_MIN_HEIGHT = 52
_CONTENT_LEFT = 16
_ICON_MARGIN_RIGHT = 18
_PANEL_MARGIN_RIGHT = 18
_ICON_AREA_W = _CONTENT_LEFT + _ICON_CIRCLE_R * 2 + _ICON_MARGIN_RIGHT


class InfoBarSeverity(Enum):
    INFORMATIONAL = "informational"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# Maps severity (bg_token, icon_bg_token)
_SEVERITY_TOKENS = {
    InfoBarSeverity.INFORMATIONAL: ("system_attention_bg", "accent_fill_default"),
    InfoBarSeverity.SUCCESS: ("system_success_bg", "system_success"),
    InfoBarSeverity.WARNING: ("system_caution_bg", "system_caution"),
    InfoBarSeverity.ERROR: ("system_critical_bg", "system_critical"),
}


def _draw_info_glyph(p: QPainter, cx: float, cy: float, r: float) -> None:
    """Draw info 'i' glyph."""
    fg = p.pen().color()
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fg)
    # Dot
    dot_r = r * 0.1
    p.drawEllipse(QPointF(cx, cy - r * 0.45), dot_r, dot_r)
    # Bar
    bar_x = cx - r * 0.0667
    bar_y = cy - r * 0.12
    bar_w = r * 0.1333
    bar_h = r * 0.6667
    p.drawRect(QRectF(bar_x, bar_y, bar_w, bar_h))
    p.restore()


def _draw_success_glyph(p: QPainter, cx: float, cy: float, r: float) -> None:
    """Draw checkmark glyph."""
    path = QPainterPath()
    path.moveTo(cx - r * 0.36, cy + r * 0.02)
    path.lineTo(cx - r * 0.06, cy + r * 0.32)
    path.lineTo(cx + r * 0.40, cy - r * 0.28)
    pen = QPen(p.pen().color(), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.save()
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.restore()


def _draw_warning_glyph(p: QPainter, cx: float, cy: float, r: float) -> None:
    """Draw exclamation mark flipped info icon."""
    fg = p.pen().color()
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fg)
    # Bar (top)
    bar_x = cx - r * 0.0667
    bar_y = cy - r * 0.55
    bar_w = r * 0.1333
    bar_h = r * 0.6667
    p.drawRect(QRectF(bar_x, bar_y, bar_w, bar_h))
    # Dot (bottom)
    dot_r = r * 0.1
    p.drawEllipse(QPointF(cx, cy + r * 0.45), dot_r, dot_r)
    p.restore()


def _draw_error_glyph(p: QPainter, cx: float, cy: float, r: float) -> None:
    """Draw 'x' glyph."""
    offset = r * 0.30
    pen = QPen(p.pen().color(), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.save()
    p.setPen(pen)
    p.drawLine(QPointF(cx - offset, cy - offset), QPointF(cx + offset, cy + offset))
    p.drawLine(QPointF(cx + offset, cy - offset), QPointF(cx - offset, cy + offset))
    p.restore()


_GLYPH_DRAWERS = {
    InfoBarSeverity.INFORMATIONAL: _draw_info_glyph,
    InfoBarSeverity.SUCCESS: _draw_success_glyph,
    InfoBarSeverity.WARNING: _draw_warning_glyph,
    InfoBarSeverity.ERROR: _draw_error_glyph,
}


class InfoBar(QFrame):
    """Inline notification bar with severity icon, title, and message.

    Args:
        title: Bold heading text (e.g. "Title").
        message: The notification text.
        severity: One of ``InfoBarSeverity`` values. Default is informational.
        parent: Parent widget.
    """

    def __init__(
        self,
        title: str = "",
        message: str = "",
        severity: InfoBarSeverity = InfoBarSeverity.INFORMATIONAL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._severity = severity
        self._theme_key = theme_key()
        self._build_colors(get_tokens())

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(_MIN_HEIGHT)
        self.setContentsMargins(0, 0, 0, 0)
        self._update_stylesheet()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(int(_ICON_AREA_W), 14, _PANEL_MARGIN_RIGHT, 14)
        layout.setSpacing(18)

        self._title_label: QLabel | None = None
        if title:
            title_font = QFont()
            title_font.setFamilies(list(FONT_FAMILIES))
            title_font.setPixelSize(14)
            title_font.setWeight(QFont.Weight.DemiBold)
            self._title_label = QLabel(title)
            self._title_label.setFont(title_font)
            self._title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._title_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            layout.addWidget(self._title_label)

        msg_font = QFont()
        msg_font.setFamilies(list(FONT_FAMILIES))
        msg_font.setPixelSize(13)

        self._msg_label = QLabel(message)
        self._msg_label.setFont(msg_font)
        self._msg_label.setWordWrap(True)
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._msg_label)

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_colors(self, t: dict[str, str]) -> None:
        bg_key, icon_bg_key = _SEVERITY_TOKENS[self._severity]
        self._bg_color = QColor(t[bg_key])
        self._icon_bg_color = QColor(t[icon_bg_key])
        self._icon_fg_color = QColor(t["text_inverse"])
        self._border_color = QColor(t["card_stroke_default"])
        self._fg_color = t["text_primary"]

    def _update_stylesheet(self) -> None:
        self.setStyleSheet(f"QLabel{{background:transparent;color:{self._fg_color}}}")

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_colors(get_tokens())
        self._update_stylesheet()
        self.update()

    def set_severity(self, severity: InfoBarSeverity) -> None:
        self._severity = severity
        self._build_colors(get_tokens())
        self._update_stylesheet()
        self.update()

    def set_title(self, title: str) -> None:
        if self._title_label:
            self._title_label.setText(title)

    def set_message(self, message: str) -> None:
        self._msg_label.setText(message)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1).toRectF()

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg_color)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Border
        p.setPen(QPen(self._border_color, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Filled circle icon background
        icon_cx = rect.x() + _CONTENT_LEFT + _ICON_CIRCLE_R
        icon_cy = rect.center().y()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._icon_bg_color)
        p.drawEllipse(QPointF(icon_cx, icon_cy), _ICON_CIRCLE_R, _ICON_CIRCLE_R)

        # Glyph in inverse color
        p.setPen(QPen(self._icon_fg_color, 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        drawer = _GLYPH_DRAWERS.get(self._severity, _draw_info_glyph)
        drawer(p, icon_cx, icon_cy, _ICON_CIRCLE_R)

        p.end()

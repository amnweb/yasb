from __future__ import annotations

import logging
import math
import os
import re
import time
from collections.abc import Callable
from typing import Any, Literal, override

import PyQt6.QtGui as QtGui
from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QEnterEvent,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.lyrics import LyricsWidgetConfig
from core.widgets.services.lyrics.engine import BreakRow, LyricRow, Row, SyncEngine, SyncStatus
from core.widgets.services.lyrics.karaoke_label import KaraokeLabel
from core.widgets.services.lyrics.models import Hit, Lane, Line, Lyrics, Word
from core.widgets.services.lyrics.session import PlaybackSnapshot, TrackInfo

try:
    from core.widgets.services.lyrics.note_icons import (
        create_two_tone_note_pixmap,
        get_two_tone_colors,
        paint_two_tone_note,
    )
except Exception:
    from core.widgets.services.lyrics.note_icons import (
        create_two_tone_note_pixmap,
        get_two_tone_colors,
        paint_two_tone_note,
    )

logger = logging.getLogger("core.widgets.services.lyrics.popup")


AMBIENT_BLOBS_SPECS: list[tuple[float, float, float, float, float, float, float]] = [
    (0.24, 0.30, 0.70, 7.5, 0.0, 0.22, 0.18),
    (0.76, 0.26, 0.65, 6.0, 1.7, 0.20, 0.24),
    (0.50, 0.65, 0.80, 9.0, 3.4, 0.25, 0.16),
    (0.15, 0.75, 0.60, 5.5, 5.1, 0.18, 0.22),
    (0.82, 0.70, 0.55, 7.0, 2.5, 0.20, 0.20),
]

BLUR_PRESCALE_SIZE = (96, 96)  # Downscale resolution before blur (e.g. (96, 96); lower = softer, higher = sharper)
BLUR_RADIUS = 9.0  # Gaussian blur radius in pixels (lower = clearer cover art, higher = more diffuse)

AMBIENT_SPEED = 0.2  # Drift animation speed multiplier (e.g. 1.5 = 50% faster, 0.7 = slower)
AMBIENT_BLOB_OPACITY = 0.8  # Blob color vibrancy multiplier (higher = more vivid color clouds)


PIN_SVG_PATH = (
    "M9.828.722a.5.5 0 0 1 .354.146l4.95 4.95a.5.5 0 0 1 0 .707c-.48.48-1.072.588-1.503.588"
    "c-.177 0-.335-.018-.46-.039l-3.134 3.134a6 6 0 0 1 .16 1.013c.046.702-.032 1.687-.72 2.375"
    "a.5.5 0 0 1-.707 0l-2.829-2.828l-3.182 3.182c-.195.195-1.219.902-1.414.707s.512-1.22.707-1.414"
    "l3.182-3.182l-2.828-2.829a.5.5 0 0 1 0-.707c.688-.688 1.673-.767 2.375-.72a6 6 0 0 1 1.013.16"
    "l3.134-3.133a3 3 0 0 1-.04-.461c0-.43.108-1.022.589-1.503a.5.5 0 0 1 .353-.146"
)


def parse_css_color(val: str) -> QColor | None:
    """Parses hex, rgb, rgba, or CSS color string into a valid QColor with alpha."""
    if not val:
        return None
    val = val.strip().rstrip(";")
    m = re.match(r"rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", val, re.I)
    if m:
        r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        alpha = int(round(a * 255)) if a <= 1.0 else int(min(255, a))
        return QColor(r, g, b, alpha)
    m = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", val, re.I)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return QColor(r, g, b)
    if val.startswith("#") and len(val) == 9:
        r = int(val[1:3], 16)
        g = int(val[3:5], 16)
        b = int(val[5:7], 16)
        a = int(val[7:9], 16)
        return QColor(r, g, b, a)
    col = QColor(val)
    if col.isValid():
        return col
    return None


def resolve_yasb_theme_data(widget: QWidget | None = None) -> dict[str, Any]:
    """Resolves active YASB theme colors, bar background (tint + transparency), and faint border."""
    accent: QColor | None = None
    secondary: QColor | None = None
    bg_color: QColor | None = None
    border_color: QColor | None = None
    border_width: float = 1.0

    bar_class_names = ["yasb-bar", "bar"]
    css: str | None = None

    if widget is not None:
        try:
            cur: QWidget | None = widget
            bar_w: QWidget | None = None
            while cur is not None:
                if hasattr(cur, "bar_frame") or hasattr(cur, "bar_id"):
                    bar_w = cur
                    break
                if hasattr(cur, "window") and cur.window() is not cur:
                    win = cur.window()
                    if hasattr(win, "bar_frame") or hasattr(win, "bar_id"):
                        bar_w = win
                        break
                cur_parent = cur.parent() if hasattr(cur, "parent") else None
                cur = cur_parent if isinstance(cur_parent, QWidget) else None

            if bar_w is not None:
                if hasattr(bar_w, "styleSheet") and bar_w.styleSheet():
                    css = bar_w.styleSheet()
                bar_frame = getattr(bar_w, "bar_frame", None)
                if bar_frame is not None:
                    bc = getattr(bar_frame, "bordercolor", None)
                    if isinstance(bc, QColor) and bc.isValid() and bc.alpha() > 0:
                        border_color = bc
                    bw = getattr(bar_frame, "borderwidth", None)
                    if isinstance(bw, (int, float)) and bw > 0:
                        border_width = float(bw)
                cfg = getattr(bar_w, "config", None)
                if cfg and hasattr(cfg, "class_name") and cfg.class_name:
                    if cfg.class_name not in bar_class_names:
                        bar_class_names.insert(0, cfg.class_name)
        except Exception:
            pass

    if not css:
        try:
            from core.config import get_stylesheet

            css = get_stylesheet()
        except Exception:
            pass

    if css:
        for cls in bar_class_names:
            for m in re.finditer(rf"\.{re.escape(cls)}\b[^{{]*\{{([^}}]*)\}}", css):
                block = m.group(1)
                if not bg_color:
                    bg_m = re.search(r"background(?:-color)?\s*:\s*([^;]+);", block)
                    if bg_m:
                        parsed = parse_css_color(bg_m.group(1))
                        if parsed and parsed.isValid():
                            bg_color = parsed
                if not border_color:
                    bcol_m = re.search(r"(?:qproperty-)?border-?color\s*:\s*([^;]+);", block)
                    if bcol_m:
                        parsed = parse_css_color(bcol_m.group(1))
                        if parsed and parsed.isValid() and parsed.alpha() > 0:
                            border_color = parsed
                    else:
                        b_m = re.search(r"border\s*:\s*([^;]+);", block)
                        if b_m:
                            c_m = re.search(r"(rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,8}\b)", b_m.group(1))
                            if c_m:
                                parsed = parse_css_color(c_m.group(1))
                                if parsed and parsed.isValid() and parsed.alpha() > 0:
                                    border_color = parsed
                if border_width <= 1.0:
                    bw_m = re.search(r"(?:qproperty-)?border-?width\s*:\s*([^;]+);", block)
                    if bw_m:
                        try:
                            border_width = float(bw_m.group(1).replace("px", "").strip())
                        except Exception:
                            pass
                    else:
                        b_m = re.search(r"border\s*:\s*([^;]+);", block)
                        if b_m:
                            w_m = re.search(r"([\d.]+)px", b_m.group(1))
                            if w_m:
                                try:
                                    border_width = float(w_m.group(1))
                                except Exception:
                                    pass

        m = re.search(r"\.lyrics-widget\.break\s+\.label\b[^{]*\{[^}]*color\s*:\s*([^;]+);", css)
        if m:
            col = parse_css_color(m.group(1))
            if col and col.isValid():
                accent = col
        if not accent:
            m = re.search(r"\.lyrics-popup\s+\.follow-pill\b[^{]*\{[^}]*background(?:-color)?\s*:\s*([^;]+);", css)
            if m:
                col = parse_css_color(m.group(1))
                if col and col.isValid():
                    accent = col

    # Fallback to reading styles.css and yasb_colors.css
    cfg_dir = None
    try:
        import settings

        cfg_dir = settings.DEFAULT_CONFIG_DIRECTORY
    except Exception:
        pass
    if not cfg_dir:
        cfg_dir = os.path.expanduser("~/.config/yasb")

    css_files = [os.path.join(cfg_dir, "yasb_colors.css"), os.path.join(cfg_dir, "styles.css")]
    raw_vars: dict[str, str] = {}
    for p in css_files:
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    c = f.read()
                c = re.sub(r"/\*.*?\*/", "", c, flags=re.DOTALL)
                c = re.sub(r"//.*", "", c)
                for m in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);", c):
                    raw_vars[f"--{m.group(1).strip()}"] = m.group(2).strip()
            except Exception:
                pass

    resolved_vars = dict(raw_vars)
    for _ in range(10):
        changed = False
        for k, v in list(resolved_vars.items()):

            def repl(match: re.Match[str]) -> str:
                nonlocal changed
                var_key = match.group(1).strip()
                if var_key in resolved_vars:
                    changed = True
                    return resolved_vars[var_key]
                return match.group(0)

            new_v = re.sub(r"var\((--[\w-]+)\)", repl, v)
            if new_v != v:
                resolved_vars[k] = new_v
                changed = True
        if not changed:
            break

    if not accent:
        for acc_key in ("--accent", "--yasb-accent"):
            val = resolved_vars.get(acc_key)
            if val:
                col = parse_css_color(val)
                if col and col.isValid():
                    accent = col
                    break

    if not bg_color:
        for bg_key in ("--background-glass", "--background", "--yasb-background"):
            val = resolved_vars.get(bg_key)
            if val:
                col = parse_css_color(val)
                if col and col.isValid():
                    bg_color = col
                    break

    if not border_color:
        val = resolved_vars.get("--border")
        if val:
            col = parse_css_color(val)
            if col and col.isValid() and col.alpha() > 0:
                border_color = col

    # Fallback to winrt or QPalette
    if not accent or not accent.isValid():
        try:
            import winrt.windows.ui.viewmanagement as viewmanagement  # type: ignore

            colour = viewmanagement.UISettings().get_color_value(viewmanagement.UIColorType.ACCENT)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
            accent = QColor(colour.r, colour.g, colour.b)  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
        except Exception:
            pass

    if not accent or not accent.isValid():
        app_inst = QApplication.instance()
        if isinstance(app_inst, QApplication):
            palette = app_inst.palette()
            c = palette.color(QPalette.ColorRole.Highlight)
            if c.isValid() and (c.red() != 0 or c.green() != 0 or c.blue() != 0):
                accent = c

    if not accent or not accent.isValid():
        accent = QColor(208, 171, 249)

    hsv = QtGui.QColor.getHsv(accent)
    h, s, v = (hsv[0] or 0, hsv[1] or 0, hsv[2] or 0) if hsv else (0, 0, 0)
    hsv_sec = QColor.fromHsv(h, max(30, int(s * 0.7)), max(30, int(v * 0.6)))
    secondary = QColor(hsv_sec.red(), hsv_sec.green(), hsv_sec.blue())

    if not bg_color or not bg_color.isValid():
        bg_color = QColor(25, 15, 11, 166)

    return {
        "accent": accent,
        "secondary": secondary,
        "background": bg_color,
        "border_color": border_color,
        "border_width": border_width,
    }


def _render_pin_icon(color_hex: str, size: int = 12) -> QIcon:
    svg_data = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 16 16">'
        f'<path d="M0 0h16v16H0z" fill="none" />'
        f'<path fill="{color_hex}" d="{PIN_SVG_PATH}" />'
        f"</svg>"
    ).encode()
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _format_time(ms: int) -> str:
    total = max(0, int(ms // 1000))
    minutes, seconds = divmod(total, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _render_transport_icon(kind: str, color: QColor, size: int = 16) -> QIcon:
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(float(scale))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    s = float(size)

    if kind == "play":
        painter.drawPolygon(
            QPolygonF([QPointF(0.30 * s, 0.16 * s), QPointF(0.30 * s, 0.84 * s), QPointF(0.86 * s, 0.50 * s)])
        )
    elif kind == "pause":
        painter.drawRoundedRect(QRectF(0.24 * s, 0.18 * s, 0.18 * s, 0.64 * s), 0.05 * s, 0.05 * s)
        painter.drawRoundedRect(QRectF(0.58 * s, 0.18 * s, 0.18 * s, 0.64 * s), 0.05 * s, 0.05 * s)
    elif kind == "next":
        painter.drawPolygon(
            QPolygonF([QPointF(0.12 * s, 0.20 * s), QPointF(0.12 * s, 0.80 * s), QPointF(0.66 * s, 0.50 * s)])
        )
        painter.drawRoundedRect(QRectF(0.72 * s, 0.20 * s, 0.14 * s, 0.60 * s), 0.05 * s, 0.05 * s)
    elif kind == "prev":
        painter.drawPolygon(
            QPolygonF([QPointF(0.88 * s, 0.20 * s), QPointF(0.88 * s, 0.80 * s), QPointF(0.34 * s, 0.50 * s)])
        )
        painter.drawRoundedRect(QRectF(0.14 * s, 0.20 * s, 0.14 * s, 0.60 * s), 0.05 * s, 0.05 * s)
    painter.end()
    return QIcon(pixmap)


_WAVE_LAYERS = (
    (2.6, 1.6, 1.00, 0.0, 2.2),
    (3.2, 2.0, 0.82, 1.8, 2.0),
    (2.1, 1.3, 0.68, 3.6, 2.4),
)


def _wave_profile(u: float, phase: float, layer: int) -> float:
    u_clamped = max(0.0, min(1.0, u))
    if u_clamped <= 0.0 or u_clamped >= 1.0:
        return 0.0

    speed, freq, share, offset, power = _WAVE_LAYERS[layer % len(_WAVE_LAYERS)]
    theta = freq * 2.0 * math.pi * u_clamped - speed * phase + offset
    crest = (0.5 + 0.5 * math.sin(theta)) ** power
    emerge = math.sin(math.pi * (u_clamped**0.8)) ** 0.9
    decay = 1.0 - 0.65 * (u_clamped**1.4)
    swell = 0.88 + 0.12 * math.sin(speed * 0.5 * phase + offset)
    return share * emerge * decay * crest * swell


def _lift_color(color: QColor) -> QColor:
    c = QColor(color)
    lightness = c.lightness()
    if lightness < 110:
        return c.lighter(min(300, int(100 * 130 / max(25, lightness))))
    return c


class PopupProgressBar(QWidget):
    """Playback progress bar for the popup header with line and wave styles."""

    seek_requested = pyqtSignal(float)  # fraction 0..1, emitted when the mouse is released
    preview_changed = pyqtSignal(float)  # fraction while dragging

    _LINE_HEIGHT = 16
    _WAVE_HEIGHT = 38
    _WAVE_THUMB_R = 8.0
    _WAVE_TRACK_H = 7.0
    _PAUSED_AMPLITUDE = 0.12

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self._LINE_HEIGHT)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._fraction = 0.0
        self._seekable = False
        self._dragging = False
        self._hover = False
        self._hold_until = 0.0
        self._color = QColor(208, 171, 249)
        self._style = "line"
        self._pad = 6.0
        self._amp = 1.0  # wave height factor: eases to a low swell while paused
        self._phase = 0.0
        self._last_tick = time.monotonic()
        base = QColor(208, 171, 249)
        self._layer_colors = [base, base.lighter(130), base.lighter(165)]

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def set_accent(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def set_style(self, style: str) -> None:
        self._style = "wave" if style == "wave" else "line"
        wave = self._style == "wave"
        self._pad = self._WAVE_THUMB_R + 2.0 if wave else 6.0
        self.setFixedHeight(self._WAVE_HEIGHT if wave else self._LINE_HEIGHT)
        self.update()

    def set_palette(self, primary: QColor, secondary: QColor | None = None) -> None:
        """Album colours for the three wave layers."""
        first = _lift_color(primary)
        if secondary is None or not secondary.isValid():
            secondary = primary
        second = _lift_color(secondary)
        distance = (
            abs(first.red() - second.red()) + abs(first.green() - second.green()) + abs(first.blue() - second.blue())
        )
        if distance < 40:
            second = first.lighter(130)
            third = first.lighter(165)
        else:
            third = QColor(
                (first.red() + second.red()) // 2,
                (first.green() + second.green()) // 2,
                (first.blue() + second.blue()) // 2,
            ).lighter(118)
        self._layer_colors = [first, second, third]
        self.update()

    def tick(self, playing: bool) -> None:
        if self._style != "wave":
            return
        now = time.monotonic()
        dt = max(0.0, min(0.1, now - self._last_tick))
        self._last_tick = now
        target = 1.0 if playing else self._PAUSED_AMPLITUDE
        self._amp += (target - self._amp) * min(1.0, dt * 5.0)
        if playing:
            self._phase += dt
        if playing or abs(self._amp - target) > 0.005:
            self.update()

    def set_seekable(self, seekable: bool) -> None:
        if seekable == self._seekable:
            return
        self._seekable = seekable
        self.setCursor(Qt.CursorShape.PointingHandCursor if seekable else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_fraction(self, fraction: float) -> None:
        if self._dragging or time.monotonic() < self._hold_until:
            return
        value = max(0.0, min(1.0, fraction))
        if abs(value - self._fraction) > 1e-4:
            self._fraction = value
            self.update()

    def _fraction_at(self, x: float) -> float:
        span = max(1.0, float(self.width()) - 2.0 * self._pad)
        return max(0.0, min(1.0, (x - self._pad) / span))

    @override
    def enterEvent(self, event: QEnterEvent | None) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    @override
    def leaveEvent(self, a0: Any) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(a0)

    @override
    def mousePressEvent(self, a0: Any) -> None:
        if a0 is not None and self._seekable and a0.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._fraction = self._fraction_at(a0.position().x())
            self.preview_changed.emit(self._fraction)
            self.update()
            a0.accept()
            return
        super().mousePressEvent(a0)

    @override
    def mouseMoveEvent(self, a0: Any) -> None:
        if a0 is not None and self._dragging:
            self._fraction = self._fraction_at(a0.position().x())
            self.preview_changed.emit(self._fraction)
            self.update()
            a0.accept()
            return
        super().mouseMoveEvent(a0)

    @override
    def mouseReleaseEvent(self, a0: Any) -> None:
        if a0 is not None and self._dragging and a0.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._fraction = self._fraction_at(a0.position().x())
            self._hold_until = time.monotonic() + 0.7
            self.update()
            self.seek_requested.emit(self._fraction)
            a0.accept()
            return
        super().mouseReleaseEvent(a0)

    @override
    def paintEvent(self, a0: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._style == "wave":
            self._paint_wave(painter)
        else:
            self._paint_line(painter)
        painter.end()

    def _paint_line(self, painter: QPainter) -> None:
        pad = self._pad
        active = self._seekable and (self._hover or self._dragging)
        width = float(self.width()) - 2.0 * pad
        cy = self.height() / 2.0
        thickness = 6.0 if active else 4.0

        painter.setBrush(QColor(255, 255, 255, 50))
        painter.drawRoundedRect(QRectF(pad, cy - thickness / 2.0, width, thickness), thickness / 2.0, thickness / 2.0)

        fill_x = pad + width * self._fraction
        if fill_x > pad:
            painter.setBrush(self._color)
            painter.drawRoundedRect(
                QRectF(pad, cy - thickness / 2.0, fill_x - pad, thickness), thickness / 2.0, thickness / 2.0
            )
        if active:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(QPointF(fill_x, cy), 5.5, 5.5)

    def _paint_wave(self, painter: QPainter) -> None:
        pad = self._pad
        radius = self._WAVE_THUMB_R
        track_h = self._WAVE_TRACK_H
        active = self._seekable and (self._hover or self._dragging)
        width = float(self.width()) - 2.0 * pad
        cy = float(self.height()) - radius - 2.0
        top = cy - track_h / 2.0
        fill_x = pad + width * self._fraction
        played = fill_x - pad
        c0, c1, c2 = self._layer_colors

        painter.setBrush(QColor(255, 255, 255, 70))
        painter.drawRoundedRect(QRectF(pad, top, width, track_h), track_h / 2.0, track_h / 2.0)

        scale = self._amp * min(1.0, played / 90.0)
        max_h = (top - 3.0) * 0.70
        if scale > 0.01 and played > 4.0 and max_h > 4.0:
            steps = max(16, min(96, int(played / 4.0)))
            layer_draw_order = (
                (2, c2.lighter(112), 160),
                (1, c1.lighter(108), 185),
                (0, c0, 230),
            )
            for layer, color, alpha in layer_draw_order:
                path = QPainterPath()
                path.moveTo(pad, top + 1.0)
                for k in range(steps + 1):
                    u = k / steps
                    path.lineTo(pad + played * u, top - max_h * scale * _wave_profile(u, self._phase, layer))
                path.lineTo(fill_x, top + 1.0)
                path.closeSubpath()
                fill = QColor(color)
                fill.setAlpha(alpha)
                painter.setBrush(fill)
                painter.drawPath(path)

        if played > 0.0:
            painter.setBrush(c0)
            painter.drawRoundedRect(QRectF(pad, top, played, track_h), track_h / 2.0, track_h / 2.0)

        r = radius + (1.5 if active else 0.0)
        glow = QRadialGradient(QPointF(fill_x, cy), r * 2.3)
        glow_inner = QColor(c0)
        glow_inner.setAlpha(110 if active else 70)
        glow_outer = QColor(c0)
        glow_outer.setAlpha(0)
        glow.setColorAt(0.0, glow_inner)
        glow.setColorAt(1.0, glow_outer)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(fill_x, cy), r * 2.3, r * 2.3)
        painter.setBrush(c0)
        painter.drawEllipse(QPointF(fill_x, cy), r, r)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QPointF(fill_x, cy), r - 3.0, r - 3.0)


class AmbientContentFrame(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        ambient_enabled: bool = True,
        background_style: str = "ambient",
        accent: str = "album_art",
    ):
        super().__init__(parent)
        self.ambient_enabled = ambient_enabled
        self.accent = accent
        valid_styles = ("ambient", "blur", "gradient", "inherit", "black")
        self.background_style = background_style if background_style in valid_styles else "ambient"

        self._bar_bg_color: QColor | None = None
        self._bar_border_color: QColor | None = None
        self._bar_border_width: float = 1.0

        self._current_primary = QColor(68, 54, 96)
        self._current_secondary = QColor(44, 70, 96)
        self._target_primary = QColor(68, 54, 96)
        self._target_secondary = QColor(44, 70, 96)
        self._blurred_pixmap: QPixmap | None = None

        self._last_tick_time = time.monotonic()
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)  # ~30 FPS
        self._anim_timer.timeout.connect(self._on_anim_tick)

        self.update_bar_style()

    def update_bar_style(self) -> None:
        """Resolves bar background color (tint & transparency) and faint border from YASB bar."""
        try:
            theme_data = resolve_yasb_theme_data(self)
            if theme_data.get("background") and theme_data["background"].isValid():
                self._bar_bg_color = theme_data["background"]
            if theme_data.get("border_color") and theme_data["border_color"].isValid():
                self._bar_border_color = theme_data["border_color"]
            if theme_data.get("border_width", 0) > 0:
                self._bar_border_width = float(theme_data["border_width"])
            if self.accent == "yasb":
                if theme_data.get("accent") and theme_data["accent"].isValid():
                    self._target_primary = theme_data["accent"]
                    self._current_primary = theme_data["accent"]
                if theme_data.get("secondary") and theme_data["secondary"].isValid():
                    self._target_secondary = theme_data["secondary"]
                    self._current_secondary = theme_data["secondary"]
            self.update()
        except Exception as e:
            logger.debug("Failed to update bar style: %s", e)

    def set_cover_art(self, thumbnail_bytes: bytes | None) -> None:
        """Load album art for the blur background."""
        if thumbnail_bytes:
            try:
                import io

                from PIL import Image, ImageFilter

                with Image.open(io.BytesIO(thumbnail_bytes)) as pil_img:
                    pil_img = pil_img.convert("RGB")
                    small = pil_img.resize(BLUR_PRESCALE_SIZE, Image.Resampling.BILINEAR)
                    blurred = small.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
                    buf = io.BytesIO()
                    blurred.save(buf, format="BMP")
                    pix = QPixmap()
                    if pix.loadFromData(buf.getvalue()):
                        self._blurred_pixmap = pix.scaled(
                            128, 128, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                        )
                        self.update()
                        return
            except Exception:
                pass

            pix = QPixmap()
            if pix.loadFromData(thumbnail_bytes):
                stage1 = pix.scaled(
                    36, 36, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                stage2 = stage1.scaled(
                    20, 20, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self._blurred_pixmap = stage2.scaled(
                    128, 128, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.update()
                return

        self._blurred_pixmap = None
        self.update()

    def set_target_palette(
        self, primary_rgb: tuple[int, int, int] | None, secondary_rgb: tuple[int, int, int] | None
    ) -> None:
        if primary_rgb:
            self._target_primary = QColor(*primary_rgb)
        if secondary_rgb:
            self._target_secondary = QColor(*secondary_rgb)
        elif primary_rgb:
            self._target_secondary = QColor(*primary_rgb)

        if self.background_style != "ambient" or not self._anim_timer.isActive():
            self._current_primary = self._target_primary
            self._current_secondary = self._target_secondary
            self.update()

    def start_animation(self) -> None:
        if self.background_style == "ambient" and not self._anim_timer.isActive():
            self._last_tick_time = time.monotonic()
            self._anim_timer.start()

    def stop_animation(self) -> None:
        if self._anim_timer.isActive():
            self._anim_timer.stop()

    def _on_anim_tick(self) -> None:
        now = time.monotonic()
        dt = max(0.001, min(0.1, now - self._last_tick_time))
        self._last_tick_time = now

        wash_factor = min(1.0, dt / 0.8)
        self._current_primary = self._lerp_color(self._current_primary, self._target_primary, wash_factor)
        self._current_secondary = self._lerp_color(self._current_secondary, self._target_secondary, wash_factor)

        self.update()

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, factor: float) -> QColor:
        r = int(c1.red() + (c2.red() - c1.red()) * factor)
        g = int(c1.green() + (c2.green() - c1.green()) * factor)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * factor)
        return QColor(r, g, b)

    @override
    def paintEvent(self, a0: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w = float(rect.width())
        h = float(rect.height())
        radius_corner = 14.0

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), radius_corner, radius_corner)
        painter.setClipPath(clip_path)

        if self.background_style == "inherit":
            bar_bg = self._bar_bg_color
            if not bar_bg or not bar_bg.isValid():
                bar_bg = QColor(25, 15, 11, 166)
            painter.fillRect(rect, bar_bg)

            b_col = self._bar_border_color
            if b_col and b_col.isValid() and b_col.alpha() > 0 and self._bar_border_width > 0:
                bw = max(1.0, float(self._bar_border_width))
                border_pen = QPen(b_col, bw)
                painter.setPen(border_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                inset = bw / 2.0
                painter.drawRoundedRect(
                    QRectF(rect).adjusted(inset, inset, -inset, -inset), radius_corner, radius_corner
                )
            return

        elif self.background_style == "black":
            painter.fillRect(rect, QColor(0, 0, 0))

        elif self.background_style == "gradient":
            painter.fillRect(rect, QColor(10, 10, 16))
            grad = QLinearGradient(0.0, 0.0, w, h)
            p_col = self._current_primary
            if self.accent == "yasb":
                grad.setColorAt(0.0, QColor(p_col.red(), p_col.green(), p_col.blue(), 210))
                grad.setColorAt(1.0, QColor(0, 0, 0, 240))
            else:
                s_col = self._current_secondary
                grad.setColorAt(0.0, QColor(p_col.red(), p_col.green(), p_col.blue(), 190))
                grad.setColorAt(1.0, QColor(s_col.red(), s_col.green(), s_col.blue(), 230))
            painter.fillRect(rect, grad)

            scrim = QLinearGradient(0.0, 0.0, 0.0, h)
            scrim.setColorAt(0.0, QColor(8, 8, 14, 90))
            scrim.setColorAt(1.0, QColor(4, 4, 10, 140))
            painter.fillRect(rect, scrim)

        elif self.background_style == "blur":
            painter.fillRect(rect, QColor(14, 14, 20))
            if self._blurred_pixmap:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(rect, self._blurred_pixmap)
            else:
                grad = QRadialGradient(QPointF(w / 2.0, h / 2.0), min(w, h) * 0.75)
                grad.setColorAt(
                    0.0,
                    QColor(
                        self._current_primary.red(), self._current_primary.green(), self._current_primary.blue(), 90
                    ),
                )
                grad.setColorAt(1.0, QColor(14, 14, 20))
                painter.fillRect(rect, grad)

            scrim = QLinearGradient(0.0, 0.0, 0.0, h)
            scrim.setColorAt(0.0, QColor(8, 8, 14, 120))
            scrim.setColorAt(0.5, QColor(6, 6, 12, 150))
            scrim.setColorAt(1.0, QColor(4, 4, 10, 180))
            painter.fillRect(rect, scrim)

        else:
            painter.fillRect(rect, QColor(14, 14, 20))
            now = time.monotonic() * AMBIENT_SPEED
            for i, (base_x, base_y, diam, period, phase, amp_x, amp_y) in enumerate(AMBIENT_BLOBS_SPECS):
                angle = (2.0 * math.pi * (now / period)) + phase
                cx = (base_x + amp_x * math.sin(angle)) * w
                cy = (base_y + amp_y * math.cos(angle)) * h
                radius = diam * min(w, h) * 0.45

                base_col = self._current_primary if (i % 2 == 0) else self._current_secondary

                grad = QRadialGradient(QPointF(cx, cy), radius)
                c_a1 = int(min(255, 130 * AMBIENT_BLOB_OPACITY))
                c_a2 = int(min(255, 65 * AMBIENT_BLOB_OPACITY))
                c_a3 = int(min(255, 20 * AMBIENT_BLOB_OPACITY))
                grad.setColorAt(0.0, QColor(base_col.red(), base_col.green(), base_col.blue(), c_a1))
                grad.setColorAt(0.45, QColor(base_col.red(), base_col.green(), base_col.blue(), c_a2))
                grad.setColorAt(0.80, QColor(base_col.red(), base_col.green(), base_col.blue(), c_a3))
                grad.setColorAt(1.0, QColor(base_col.red(), base_col.green(), base_col.blue(), 0))

                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(cx, cy), radius, radius)

            shade_col = QColor(12, 12, 18, 100)
            painter.setBrush(QBrush(shade_col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(rect), radius_corner, radius_corner)

        rim_color = (
            self._bar_border_color
            if (self._bar_border_color and self._bar_border_color.isValid() and self._bar_border_color.alpha() > 0)
            else QColor(255, 255, 255, 24)
        )
        border_pen = QPen(rim_color, 1.0)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), radius_corner, radius_corner)


class ElidedLabel(QLabel):
    """
    QLabel that automatically elides text with '...' when it doesn't fit,
    preventing overflow collisions with neighboring buttons and widgets.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    @override
    def setText(self, a0: str | None) -> None:
        self._full_text = a0 if a0 is not None else ""
        self._update_elided_text()

    @override
    def text(self) -> str:
        return self._full_text

    @override
    def resizeEvent(self, a0: Any) -> None:
        super().resizeEvent(a0)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        metrics = QFontMetrics(self.font())
        available_width = max(self.width() - 4, 0)
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available_width)
        super().setText(elided)


class InstrumentalNotesWidget(QWidget):
    """
    Renders a three-note instrumental indicator using two-tone vector SVG notes.
    """

    def __init__(self, parent: QWidget | None = None, font_scale: float = 1.0) -> None:
        super().__init__(parent)
        self.font_scale = font_scale
        self.note_size = max(18, int(22.0 * font_scale))
        self.gap = max(8, int(10.0 * font_scale))
        self._progress = 0.0
        self._state = "upcoming"
        self._primary_color: QColor | None = None
        self._secondary_color: QColor | None = None
        total_w = 3 * self.note_size + 2 * self.gap
        self.setMinimumSize(total_w, int(self.note_size * 1.5))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_progress(
        self,
        progress: float,
        state: str = "active",
        accent_color: QColor | None = None,
        secondary_color: QColor | None = None,
    ) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self._state = state
        if accent_color:
            self._primary_color = accent_color
        if secondary_color:
            self._secondary_color = secondary_color
        self.update()

    def set_palette_colors(self, primary: QColor | None, secondary: QColor | None = None) -> None:
        self._primary_color = primary
        self._secondary_color = secondary
        self.update()

    def set_album_art_color(self, color: QColor | None) -> None:
        if color:
            self._primary_color = color
            self.update()

    @override
    def mousePressEvent(self, a0: Any) -> None:
        if a0:
            a0.ignore()

    @override
    def paintEvent(self, a0: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total_w = 3 * self.note_size + 2 * self.gap
        start_x = (self.width() - total_w) / 2.0
        start_y = (self.height() - self.note_size) / 2.0

        col1, col2 = get_two_tone_colors(self._primary_color, self._secondary_color)
        variants: list[Literal["single", "beamed"]] = ["single", "beamed", "single"]

        ahead_stroke = QColor(255, 255, 255, 75)
        ahead_fill = QColor(255, 255, 255, 40)
        past_stroke = QColor(255, 255, 255, 45)
        past_fill = QColor(255, 255, 255, 25)

        for i in range(3):
            nx = start_x + i * (self.note_size + self.gap)
            ny = start_y
            rect = QRectF(nx, ny, float(self.note_size), float(self.note_size))
            note_p = max(0.0, min(1.0, self._progress * 3.0 - float(i)))

            if self._state == "past":
                paint_two_tone_note(
                    painter,
                    rect,
                    variant=variants[i],
                    stroke_color=past_stroke,
                    fill_color=past_fill,
                    fill_opacity=0.20,
                    opacity=0.45,
                )
            elif self._state == "active":
                s_r = int(ahead_stroke.red() + (col1.red() - ahead_stroke.red()) * note_p)
                s_g = int(ahead_stroke.green() + (col1.green() - ahead_stroke.green()) * note_p)
                s_b = int(ahead_stroke.blue() + (col1.blue() - ahead_stroke.blue()) * note_p)
                s_a = int(ahead_stroke.alpha() + (col1.alpha() - ahead_stroke.alpha()) * note_p)
                cur_stroke = QColor(s_r, s_g, s_b, s_a)

                f_r = int(ahead_fill.red() + (col2.red() - ahead_fill.red()) * note_p)
                f_g = int(ahead_fill.green() + (col2.green() - ahead_fill.green()) * note_p)
                f_b = int(ahead_fill.blue() + (col2.blue() - ahead_fill.blue()) * note_p)
                f_a = int(ahead_fill.alpha() + (col2.alpha() - ahead_fill.alpha()) * note_p)
                cur_fill = QColor(f_r, f_g, f_b, f_a)

                paint_two_tone_note(
                    painter,
                    rect,
                    variant=variants[i],
                    stroke_color=cur_stroke,
                    fill_color=cur_fill,
                    fill_opacity=0.20 + 0.15 * note_p,
                    opacity=0.55 + 0.45 * note_p,
                )
            else:
                paint_two_tone_note(
                    painter,
                    rect,
                    variant=variants[i],
                    stroke_color=ahead_stroke,
                    fill_color=ahead_fill,
                    fill_opacity=0.20,
                    opacity=0.55,
                )
        painter.end()


def wrap_plain_text(text: str, max_width: int, fm: QFontMetrics) -> list[str]:
    """Wraps plain text into multiple lines fitting within max_width."""
    if not text or fm.horizontalAdvance(text) <= max_width:
        return [text] if text else []

    if " " in text:
        tokens = text.split(" ")
        n = len(tokens)
        best_split = None
        min_penalty = float("inf")
        for i in range(1, n):
            t1 = " ".join(tokens[:i])
            t2 = " ".join(tokens[i:])
            adv1 = fm.horizontalAdvance(t1)
            adv2 = fm.horizontalAdvance(t2)
            if adv1 <= max_width and adv2 <= max_width:
                diff = abs(adv1 - adv2)
                ratio_penalty = 0 if adv1 >= adv2 else 20
                orphan_penalty = 0
                if i == 1:
                    orphan_penalty += 200
                if (n - i) == 1:
                    orphan_penalty += 200
                penalty = diff + ratio_penalty + orphan_penalty
                if penalty < min_penalty:
                    min_penalty = penalty
                    best_split = [t1, t2]
        if best_split is not None:
            return best_split

        lines: list[str] = []
        curr = ""
        for token in tokens:
            cand = f"{curr} {token}".strip() if curr else token
            if fm.horizontalAdvance(cand) <= max_width or not curr:
                curr = cand
            else:
                lines.append(curr)
                curr = token
        if curr:
            lines.append(curr)

        if len(lines) >= 2:
            last_tokens = lines[-1].split(" ")
            prev_tokens = lines[-2].split(" ")
            if len(last_tokens) == 1 and len(prev_tokens) >= 3:
                new_prev = " ".join(prev_tokens[:-1])
                new_last = prev_tokens[-1] + " " + lines[-1]
                if fm.horizontalAdvance(new_last) <= max_width:
                    lines[-2] = new_prev
                    lines[-1] = new_last
        return lines

    lines = []
    curr = ""
    for ch in text:
        cand = curr + ch
        if fm.horizontalAdvance(cand) <= max_width or not curr:
            curr = cand
        else:
            lines.append(curr)
            curr = ch
    if curr:
        lines.append(curr)
    return lines


def wrap_karaoke_words(
    text: str,
    words: list[Word] | None,
    max_width: int,
    fm: QFontMetrics,
) -> list[tuple[str, list[Word]]]:
    """
    Wraps text and associated Word objects into sub-lines that each fit within max_width.
    Returns list of (sub_line_text, sub_line_words).
    """
    if not text:
        return []

    if not words:
        lines = wrap_plain_text(text, max_width, fm)
        return [(l, []) for l in lines]

    if fm.horizontalAdvance(text) <= max_width or len(words) <= 1:
        return [(text, words)]

    words_joined = "".join(w.text for w in words).replace(" ", "")
    text_clean = text.replace(" ", "")
    is_direct_match = words_joined == text_clean

    if is_direct_match:
        n = len(words)
        best_split = None
        min_penalty = float("inf")
        for i in range(1, n):
            w1_words = words[:i]
            w2_words = words[i:]
            t1 = "".join(x.text for x in w1_words).strip()
            t2 = "".join(x.text for x in w2_words).strip()
            adv1 = fm.horizontalAdvance(t1)
            adv2 = fm.horizontalAdvance(t2)
            if adv1 <= max_width and adv2 <= max_width:
                diff = abs(adv1 - adv2)
                ratio_penalty = 0 if adv1 >= adv2 else 20
                orphan_penalty = 0
                if len(w1_words) == 1:
                    orphan_penalty += 200
                if len(w2_words) == 1:
                    orphan_penalty += 200
                penalty = diff + ratio_penalty + orphan_penalty
                if penalty < min_penalty:
                    min_penalty = penalty
                    best_split = [(t1, w1_words), (t2, w2_words)]

        if best_split is not None:
            return best_split

        sub_lines: list[tuple[str, list[Word]]] = []
        curr_words: list[Word] = []

        for w in words:
            cand_words = curr_words + [w]
            cand_text = "".join(x.text for x in cand_words).strip()
            cand_w = fm.horizontalAdvance(cand_text)

            if cand_w <= max_width or not curr_words:
                curr_words.append(w)
            else:
                sub_text = "".join(x.text for x in curr_words).strip()
                sub_lines.append((sub_text, list(curr_words)))
                curr_words = [w]

        if curr_words:
            sub_text = "".join(x.text for x in curr_words).strip()
            sub_lines.append((sub_text, list(curr_words)))

        if len(sub_lines) >= 2 and len(sub_lines[-1][1]) == 1 and len(sub_lines[-2][1]) >= 3:
            _, prev_w = sub_lines[-2]
            _, last_w = sub_lines[-1]
            borrowed = prev_w[-1]
            new_prev_w = prev_w[:-1]
            new_last_w = [borrowed] + last_w
            new_prev_t = "".join(x.text for x in new_prev_w).strip()
            new_last_t = "".join(x.text for x in new_last_w).strip()
            if fm.horizontalAdvance(new_last_t) <= max_width:
                sub_lines[-2] = (new_prev_t, new_prev_w)
                sub_lines[-1] = (new_last_t, new_last_w)

        return sub_lines
    else:
        plain_lines = wrap_plain_text(text, max_width, fm)
        if len(plain_lines) <= 1:
            return [(text, words)]

        total_chars = max(1, sum(len(l) for l in plain_lines))
        sub_lines = []
        w_idx = 0
        n_words = len(words)

        for l_idx, line_str in enumerate(plain_lines):
            if l_idx == len(plain_lines) - 1:
                assigned_words = words[w_idx:]
            else:
                share = len(line_str) / total_chars
                count = max(1, int(round(share * n_words)))
                end_idx = min(n_words, w_idx + count)
                assigned_words = words[w_idx:end_idx]
                w_idx = end_idx
            sub_lines.append((line_str, assigned_words))

        return sub_lines


class LyricsRowWidget(QFrame):
    """
    Renders an individual lyrics row (lead, counter, secondary, romanized, translation, or break).
    Implements lyric typography, focus fading, press feedback, duet panning,
    and wavy countdown indicators.
    """

    def __init__(
        self,
        row: Row,
        row_index: int,
        parent: QWidget | None = None,
        on_seek: Callable[[int], None] | None = None,
        font_scale: float = 1.0,
        show_background: bool = True,
        romanize: bool | list[str] = True,
        instrumental_notes: bool = True,
        focus_distance_fade: bool = True,
        alignment: str = "left",
        duet_panning: bool = True,
        syllable_physics: bool = True,
        wrap_width: int | None = None,
    ):
        super().__init__(parent)
        self.row = row
        self.row_index = row_index
        self.on_seek = on_seek
        self.font_scale = font_scale
        self.show_background = show_background
        if isinstance(romanize, bool):
            self.romanize_enabled = romanize
        else:
            self.romanize_enabled = len(romanize) > 0
        self.instrumental_notes = instrumental_notes
        self.focus_distance_fade = focus_distance_fade
        self.alignment_mode = alignment
        self.duet_panning = duet_panning
        self.syllable_physics = syllable_physics
        self.wrap_width = wrap_width or 340

        self._state = ""  # Start uninitialized so initial set_row_state triggers full configuration
        self._is_pressed = False
        self._is_hovered = False
        self._target_distance_blur = 0.0
        self._current_album_color: QColor | None = None

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self.setProperty("class", "lyrics-row upcoming")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 3, 12, 3)
        self._layout.setSpacing(2)

        self._inner_container = QWidget(self)
        self._inner_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._inner_container.setStyleSheet("background-color: transparent;")
        self._inner_layout = QVBoxLayout(self._inner_container)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(2)
        self._layout.addWidget(self._inner_container)

        base_pt = max(9.0, 13.0 * self.font_scale)
        self._notes_widget: InstrumentalNotesWidget | None = None
        self._main_label = KaraokeLabel(self._inner_container)
        self._main_label.setProperty("class", "row-main-text")
        init_font = QFont(self._main_label.font())
        init_font.setPointSizeF(base_pt)
        init_font.setBold(False)
        self._main_label.setFont(init_font)
        self._main_label.set_auto_scroll(False)
        if self.syllable_physics:
            self._main_label.set_syllable_physics(True)
        self._main_labels: list[KaraokeLabel] = [self._main_label]
        self._sub_lines: list[tuple[str, list[Word]]] = []

        if isinstance(row, BreakRow):
            row_align = Qt.AlignmentFlag.AlignHCenter
            self._main_label.hide()
            self._notes_widget = InstrumentalNotesWidget(self._inner_container, font_scale=self.font_scale)
            self._inner_layout.addWidget(self._notes_widget)
        else:
            base_align = Qt.AlignmentFlag.AlignLeft
            if self.alignment_mode == "right":
                base_align = Qt.AlignmentFlag.AlignRight
            elif self.alignment_mode == "center":
                base_align = Qt.AlignmentFlag.AlignHCenter

            if self.duet_panning:
                voice = getattr(row.line, "voice", "lead")
                if voice in ("counter", "v2", "right"):
                    row_align = Qt.AlignmentFlag.AlignRight
                elif voice in ("v1000", "group", "all", "bg", "chorus"):
                    row_align = Qt.AlignmentFlag.AlignHCenter
                elif voice in ("v1", "left", "lead"):
                    row_align = Qt.AlignmentFlag.AlignLeft
                else:
                    row_align = base_align
            else:
                row_align = base_align

            self._row_alignment = row_align | Qt.AlignmentFlag.AlignVCenter

            main_t, _, _ = self._get_display_texts()
            base_pt = max(9.0, 13.0 * self.font_scale)
            measure_font = QFont(self._main_label.font())
            measure_font.setPointSizeF(base_pt)
            fm = QFontMetrics(measure_font)
            words = row.line.words if row.line.words else None

            self._sub_lines = wrap_karaoke_words(main_t, words, self.wrap_width, fm)
            if not self._sub_lines:
                self._sub_lines = [(main_t, words or [])]

            self._main_label.setAlignment(self._row_alignment)
            self._inner_layout.addWidget(self._main_label)

            for _ in range(1, len(self._sub_lines)):
                sub_lbl = KaraokeLabel(self._inner_container)
                sub_lbl.setProperty("class", "row-main-text")
                sub_lbl.setFont(init_font)
                sub_lbl.set_auto_scroll(False)
                if self.syllable_physics:
                    sub_lbl.set_syllable_physics(True)
                sub_lbl.setAlignment(self._row_alignment)
                self._main_labels.append(sub_lbl)
                self._inner_layout.addWidget(sub_lbl)

        self._secondary_labels: list[tuple[KaraokeLabel, Lane, str, list[Word] | None]] = []
        self._secondary_label: KaraokeLabel | QLabel | None = None
        if isinstance(row, LyricRow) and row.line.secondary and self.show_background:
            for lane in row.line.secondary:
                if not lane.text:
                    continue
                lane_fmt = (
                    lane.text.strip()
                    if lane.text.strip().startswith("(") and lane.text.strip().endswith(")")
                    else f"({lane.text.strip()})"
                )

                sec_words: list[Word] | None = None
                if lane.words:
                    lane_sec_words: list[Word] = []
                    for w in lane.words:
                        lane_sec_words.append(Word(start_ms=w.start_ms, end_ms=w.end_ms, text=w.text))
                    if not lane.text.strip().startswith("(") and lane_fmt.startswith("(") and lane_sec_words:
                        lane_sec_words[0] = Word(
                            lane_sec_words[0].start_ms, lane_sec_words[0].end_ms, f"({lane_sec_words[0].text}"
                        )
                        lane_sec_words[-1] = Word(
                            lane_sec_words[-1].start_ms, lane_sec_words[-1].end_ms, f"{lane_sec_words[-1].text})"
                        )
                    sec_words = lane_sec_words
                else:
                    lane_start = lane.start_ms
                    lane_end = lane.end_ms if lane.end_ms is not None else (lane_start + 1500)
                    words_list = lane_fmt.split()
                    if words_list:
                        total_chars = max(1, sum(len(w) for w in words_list))
                        total_dur = max(len(words_list) * 200, lane_end - lane_start)
                        cur_start = lane_start
                        sec_words = []
                        for i, w_str in enumerate(words_list):
                            w_dur = max(150, int((len(w_str) / total_chars) * total_dur))
                            w_end = cur_start + w_dur
                            text_token = f"{w_str} " if i < len(words_list) - 1 else w_str
                            sec_words.append(Word(start_ms=cur_start, end_ms=w_end, text=text_token))
                            cur_start = w_end

                sec_lbl = KaraokeLabel(self._inner_container)
                sec_lbl.setText(lane_fmt)
                sec_lbl.set_auto_scroll(False)
                sec_lbl.setProperty("class", "row-secondary-text")
                sec_font = QFont(init_font)
                sec_font.setPointSizeF(max(8.0, base_pt * 0.82))
                sec_font.setItalic(True)
                sec_font.setBold(False)
                sec_lbl.setFont(sec_font)
                sec_lbl.setAlignment(self._row_alignment)
                if self.syllable_physics:
                    sec_lbl.set_syllable_physics(True)
                self._secondary_labels.append((sec_lbl, lane, lane_fmt, sec_words))
                self._inner_layout.addWidget(sec_lbl)

            if self._secondary_labels:
                self._secondary_label = self._secondary_labels[0][0]

        self._romanized_label: QLabel | None = None
        self._translation_label: QLabel | None = None

        if isinstance(row, LyricRow):
            _, sub_text, trans_text = self._get_display_texts()
            if sub_text:
                self._romanized_label = QLabel(sub_text, self._inner_container)
                self._romanized_label.setWordWrap(True)
                self._romanized_label.setProperty("class", "row-romanized-text")
                self._romanized_label.setAlignment(self._row_alignment)
                sub_font = self._romanized_label.font()
                sub_font.setPointSizeF(max(7.5, 9.5 * self.font_scale))
                sub_font.setBold(False)
                self._romanized_label.setFont(sub_font)
                self._inner_layout.addWidget(self._romanized_label)

            if trans_text:
                self._translation_label = QLabel(trans_text, self._inner_container)
                self._translation_label.setWordWrap(True)
                self._translation_label.setProperty("class", "row-translation-text")
                self._translation_label.setAlignment(self._row_alignment)
                trans_font = self._translation_label.font()
                trans_font.setPointSizeF(max(7.5, 9.5 * self.font_scale))
                trans_font.setBold(False)
                self._translation_label.setFont(trans_font)
                self._inner_layout.addWidget(self._translation_label)

        self._init_content()

    def _get_display_texts(self) -> tuple[str, str | None, str | None]:
        if not isinstance(self.row, LyricRow):
            return ("", None, None)
        line = self.row.line
        main_t = line.text
        sub_t = line.romanized if self.romanize_enabled else None
        trans_t = getattr(line, "translation", None)
        return (main_t, sub_t, trans_t)

    def set_album_art_color(self, color: QColor | None) -> None:
        self.set_palette_colors(color, None)

    def set_palette_colors(self, primary: QColor | None, secondary: QColor | None = None) -> None:
        self._current_album_color = primary
        self._current_album_secondary = secondary
        if self._notes_widget:
            self._notes_widget.set_palette_colors(primary, secondary)
        for lbl in self._main_labels:
            if hasattr(lbl, "set_album_art_palette"):
                lbl.set_album_art_palette(primary, secondary)
            elif hasattr(lbl, "set_album_art_color"):
                lbl.set_album_art_color(primary)
        for sec_lbl, _, _, _ in self._secondary_labels:
            if hasattr(sec_lbl, "set_album_art_palette"):
                sec_lbl.set_album_art_palette(primary, secondary)
            elif hasattr(sec_lbl, "set_album_art_color"):
                sec_lbl.set_album_art_color(primary)

    def _init_content(self) -> None:
        self.set_row_state("upcoming")

    def set_focus_distance(self, distance: int | None) -> None:
        """Adjusts depth-of-field alpha based on row distance from the active line."""
        if not self.focus_distance_fade:
            self._opacity_effect.setOpacity(1.0)
            return

        if distance is None or distance == 0:
            target_opacity = 1.0
        elif distance == 1:
            target_opacity = 0.40
        elif distance == 2:
            target_opacity = 0.25
        elif distance == 3:
            target_opacity = 0.15
        else:
            target_opacity = 0.08

        self._target_distance_opacity = target_opacity
        if self._is_hovered:
            self._opacity_effect.setOpacity(0.85)
        else:
            self._opacity_effect.setOpacity(target_opacity)

    def set_row_state(self, state: str, status: SyncStatus | None = None) -> None:
        is_state_change = self._state != state
        self._state = state

        if isinstance(self.row, BreakRow):
            progress = status.break_progress if status and status.is_break else 0.0
            if self._notes_widget:
                self._notes_widget.set_progress(
                    progress=progress,
                    state=state,
                    accent_color=self._current_album_color,
                    secondary_color=getattr(self, "_current_album_secondary", None),
                )

            target_class = "lyrics-row row-break active" if state == "active" else "lyrics-row row-break"
            if self.property("class") != target_class:
                self.setProperty("class", target_class)
                refresh_widget_style(self)
            return

        # LyricRow
        base_pt = max(9.0, 13.0 * self.font_scale)
        font = self._main_label.font()

        if state == "active":
            target_class = "lyrics-row row-active"
            if is_state_change:
                font.setPointSizeF(base_pt)
                font.setBold(True)
                for lbl in self._main_labels:
                    lbl.setFont(font)
                    lbl.animate_scale(1.18, duration_ms=280)

            if self.row.line.words and status:
                for idx, (sub_t, sub_w) in enumerate(self._sub_lines):
                    self._main_labels[idx].set_karaoke_data(
                        text=sub_t,
                        words=sub_w,
                        position_ms=status.effective_position_ms,
                        is_active=True,
                        state="active",
                    )
            elif is_state_change:
                for idx, (sub_t, _) in enumerate(self._sub_lines):
                    self._main_labels[idx].set_plain_text(sub_t, state="active")

            if self._secondary_labels:
                if is_state_change:
                    sec_font = self._main_label.font()
                    sec_font.setPointSizeF(max(8.0, base_pt * 0.82))
                    sec_font.setItalic(True)
                    sec_font.setBold(False)
                    for sec_lbl, _lane, lane_fmt, _ in self._secondary_labels:
                        sec_lbl.setFont(sec_font)
                for sec_lbl, _lane, lane_fmt, sec_words in self._secondary_labels:
                    if sec_words and status:
                        sec_lbl.set_karaoke_data(
                            text=lane_fmt,
                            words=sec_words,
                            position_ms=status.effective_position_ms,
                            is_active=True,
                            state="active",
                        )
                    elif is_state_change:
                        sec_lbl.set_plain_text(lane_fmt, state="active")
        elif state == "past":
            if not is_state_change:
                return
            target_class = "lyrics-row row-past"
            font.setPointSizeF(base_pt)
            font.setBold(False)
            for lbl in self._main_labels:
                lbl.setFont(font)
                lbl.animate_scale(1.0, duration_ms=240)

            for idx, (sub_t, _) in enumerate(self._sub_lines):
                self._main_labels[idx].set_plain_text(sub_t, state="past")

            if self._secondary_labels:
                sec_font = self._main_label.font()
                sec_font.setPointSizeF(max(8.0, base_pt * 0.82))
                sec_font.setItalic(True)
                sec_font.setBold(False)
                for sec_lbl, _lane, lane_fmt, _ in self._secondary_labels:
                    sec_lbl.setFont(sec_font)
                    sec_lbl.set_plain_text(lane_fmt, state="past")
        else:
            if not is_state_change:
                return
            target_class = "lyrics-row row-upcoming"
            font.setPointSizeF(base_pt)
            font.setBold(False)
            for lbl in self._main_labels:
                lbl.setFont(font)
                lbl.animate_scale(1.0, duration_ms=240)

            for idx, (sub_t, _) in enumerate(self._sub_lines):
                self._main_labels[idx].set_plain_text(sub_t, state="upcoming")

            if self._secondary_labels:
                sec_font = self._main_label.font()
                sec_font.setPointSizeF(max(8.0, base_pt * 0.82))
                sec_font.setItalic(True)
                sec_font.setBold(False)
                for sec_lbl, _lane, lane_fmt, _ in self._secondary_labels:
                    sec_lbl.setFont(sec_font)
                    sec_lbl.set_plain_text(lane_fmt, state="upcoming")

        if is_state_change and self.property("class") != target_class:
            self.setProperty("class", target_class)
            refresh_widget_style(
                self,
                *self._main_labels,
                *(lbl for lbl, _, _, _ in self._secondary_labels),
                self._romanized_label,
                self._translation_label,
            )

    @override
    def enterEvent(self, event: QEnterEvent | None) -> None:
        self._is_hovered = True
        if self.focus_distance_fade:
            self._opacity_effect.setOpacity(0.85)
        super().enterEvent(event)

    @override
    def leaveEvent(self, a0: Any) -> None:
        self._is_hovered = False
        if self.focus_distance_fade:
            self._opacity_effect.setOpacity(getattr(self, "_target_distance_opacity", 1.0))
        super().leaveEvent(a0)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            # Add a small pressed-state offset.
            self._layout.setContentsMargins(6, 4, 10, 2)
            self.update()
        super().mousePressEvent(a0)

    @override
    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if self._is_pressed:
            self._is_pressed = False
            self._layout.setContentsMargins(4, 3, 12, 3)
            self.update()

        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            if self.on_seek:
                start_ms = self.row.start_ms
                self.on_seek(start_ms)
            a0.accept()
            return
        super().mouseReleaseEvent(a0)


class LyricsScrollView(QScrollArea):
    user_scrolled = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setProperty("class", "lyrics-scroll-area")
        viewport = self.viewport()
        if viewport is not None:
            viewport.setStyleSheet("background: transparent; border: none;")
        self.setStyleSheet("background: transparent; border: none;")

        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._scroll_anim.setDuration(320)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @override
    def wheelEvent(self, a0: QWheelEvent | None) -> None:
        if a0:
            if self._scroll_anim.state() == QPropertyAnimation.State.Running:
                self._scroll_anim.stop()
            self.user_scrolled.emit()
        super().wheelEvent(a0)

    def scroll_to_widget(self, target: QWidget, animated: bool = True, center: bool = False) -> None:
        vbar = self.verticalScrollBar()
        if not vbar or not target:
            return

        viewport = self.viewport()
        viewport_h = viewport.height() if viewport is not None else 0
        if center:
            target_y = target.y() + (target.height() // 2) - (viewport_h // 2)
        else:
            target_y = target.y() - int(viewport_h * 0.28)
        target_y = max(0, min(target_y, vbar.maximum()))

        if animated:
            if self._scroll_anim.state() == QPropertyAnimation.State.Running:
                self._scroll_anim.stop()
            self._scroll_anim.setStartValue(vbar.value())
            self._scroll_anim.setEndValue(target_y)
            self._scroll_anim.start()
        else:
            vbar.setValue(target_y)


class LyricsPopup(PopupWidget):
    seek_requested = pyqtSignal(int)
    cycle_hit_requested = pyqtSignal()
    retry_requested = pyqtSignal()
    play_pause_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    next_requested = pyqtSignal()

    # Defaults live on the class because Qt can deliver a resize before __init__ finishes.
    _collapsed: bool = False
    _in_resize: bool = False
    _user_pos_args: tuple[str, str, int, int] | None = None
    _last_playing: bool | None = None
    _expanded_applied: bool = True  # the constructor already sized the popup to the configured height

    def __init__(self, parent: QWidget, config: LyricsWidgetConfig):
        popup_opts = config.popup
        super().__init__(
            parent,
            blur=False,
            round_corners=True,
            round_corners_type="normal",
            border_color="system",
            persistent=True,
            pinnable=True,
        )
        self.config = config
        self.popup_config = popup_opts

        self.setFixedSize(popup_opts.width, popup_opts.height)
        self.setProperty("class", "lyrics-popup")

        self._current_track: TrackInfo | None = None
        self._active_lyrics: Lyrics | None = None
        self._hits: list[Hit] = []
        self._hit_index: int = 0
        self._current_status: SyncStatus | None = None
        self._engine: SyncEngine | None = None
        self._state: str = "idle"

        self._row_widgets: list[LyricsRowWidget] = []
        self._last_active_row: int | None = None
        self._is_following: bool = True
        self._current_album_color: QColor | None = None
        self._current_album_secondary: QColor | None = None

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(6000)
        self._idle_timer.timeout.connect(self._resume_follow)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(33)
        self._tick_timer.timeout.connect(self._on_popup_tick)

        self._build_ui()

        use_yasb_accent = getattr(self.config, "accent", "album_art") == "yasb"
        if use_yasb_accent:
            p_col, s_col = self._resolve_yasb_palette()
            self._current_album_color = p_col
            self._current_album_secondary = s_col
            self._update_follow_pill_style(p_col)
            self._update_pin_button_style(getattr(self, "_pinned", False))
            if hasattr(self, "_content_frame"):
                self._content_frame.set_target_palette(
                    (p_col.red(), p_col.green(), p_col.blue()),
                    (s_col.red(), s_col.green(), s_col.blue()),
                )

    def _theme_widget(self) -> QWidget:
        """Widget used to resolve bar theme data: the parent bar when available."""
        parent = self.parent()
        return parent if isinstance(parent, QWidget) else self

    def _resolve_yasb_palette(self) -> tuple[QColor, QColor]:
        """Resolves active YASB accent and secondary colors."""
        theme_data = resolve_yasb_theme_data(self._theme_widget())
        accent = theme_data.get("accent")
        secondary = theme_data.get("secondary")
        if accent and accent.isValid() and secondary and secondary.isValid():
            return accent, secondary
        p = accent if (accent and accent.isValid()) else QColor(208, 171, 249)
        hsv = QtGui.QColor.getHsv(p)
        h, s, v = (hsv[0] or 0, hsv[1] or 0, hsv[2] or 0) if hsv else (0, 0, 0)
        hsv_sec = QColor.fromHsv(h, max(30, int(s * 0.7)), max(30, int(v * 0.6)))
        return p, QColor(hsv_sec.red(), hsv_sec.green(), hsv_sec.blue())

    def setPosition(
        self,
        alignment: str = "left",
        direction: str = "down",
        offset_left: int = 0,
        offset_top: int = 0,
    ) -> None:
        """Positions the popup relative to its parent, capping height and inverting alignment."""
        if self._in_resize and self._user_pos_args is not None:
            if getattr(self, "_pinned", False):
                return
            alignment, direction, offset_left, offset_top = self._user_pos_args
        else:
            self._user_pos_args = (alignment, direction, offset_left, offset_top)
        off_h = offset_left
        off_v = max(0, offset_top)

        parent_widget = self.parent() if hasattr(self, "parent") else None
        screen = None
        if parent_widget and isinstance(parent_widget, QWidget):
            screen = QApplication.screenAt(parent_widget.mapToGlobal(parent_widget.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()

        screen_h = screen.geometry().height() if screen else 1000
        max_h = min(1000, max(200, screen_h - off_v))
        if self._collapsed:
            target_h = max(80, min(self._collapsed_height(), max_h))
        else:
            configured_h = getattr(self.popup_config, "height", self.height())
            target_h = max(200, min(configured_h, max_h))

        if self.height() != target_h:
            self.setFixedSize(self.width(), target_h)
            if hasattr(self, "_popup_content") and self._popup_content:
                self._popup_content.setGeometry(0, 0, self.width(), target_h)

        align_target = alignment
        if alignment == "left":
            align_target = "right"
        elif alignment == "right":
            align_target = "left"

        super().setPosition(
            alignment=align_target,
            direction=direction,
            offset_left=off_h,
            offset_top=off_v,
        )

    def _update_artwork_fallback(self) -> None:
        """Renders two-tone vector note icon in the header artwork area when no cover art is loaded."""
        col1, col2 = get_two_tone_colors(self._current_album_color, self._current_album_secondary)
        pix = create_two_tone_note_pixmap(size=28, variant="beamed", stroke_color=col1, fill_color=col2)
        self._art_label.setPixmap(pix)

    def _update_msg_icon(self) -> None:
        """Renders large two-tone vector note icon in the status message view."""
        col1, col2 = get_two_tone_colors(self._current_album_color, self._current_album_secondary)
        pix = create_two_tone_note_pixmap(size=44, variant="beamed", stroke_color=col1, fill_color=col2)
        self._msg_icon.setPixmap(pix)

    def _apply_artwork(self, thumbnail_bytes: bytes | None) -> None:
        """Renders anti-aliased, high-DPI clipped rounded cover art into header and updates blur frame."""
        if thumbnail_bytes:
            pix = QPixmap()
            if pix.loadFromData(thumbnail_bytes):
                size = 44
                dpr = (
                    float(self._art_label.devicePixelRatioF()) if hasattr(self._art_label, "devicePixelRatioF") else 1.0
                )
                dpr = max(1.0, dpr)
                phys_size = max(1, int(round(size * dpr)))
                rounded = QPixmap(phys_size, phys_size)
                rounded.fill(Qt.GlobalColor.transparent)
                p = QPainter(rounded)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                path = QPainterPath()
                radius = 8.0 * dpr
                path.addRoundedRect(0.0, 0.0, float(phys_size), float(phys_size), radius, radius)
                p.setClipPath(path)
                scaled = pix.scaled(
                    phys_size,
                    phys_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                sw = scaled.width()
                sh = scaled.height()
                sx = max(0, (sw - phys_size) // 2)
                sy = max(0, (sh - phys_size) // 2)
                p.drawPixmap(0, 0, phys_size, phys_size, scaled, sx, sy, phys_size, phys_size)
                p.end()
                rounded.setDevicePixelRatio(dpr)
                self._art_label.setPixmap(rounded)
                self._content_frame.set_cover_art(thumbnail_bytes)

                use_yasb_accent = getattr(self.config, "accent", "album_art") == "yasb"
                if use_yasb_accent:
                    p_col, s_col = self._resolve_yasb_palette()
                    self._current_album_color = p_col
                    self._current_album_secondary = s_col
                    self._content_frame.set_target_palette(
                        (p_col.red(), p_col.green(), p_col.blue()),
                        (s_col.red(), s_col.green(), s_col.blue()),
                    )
                    self._update_follow_pill_style(p_col)
                    self._update_pin_button_style(getattr(self, "_pinned", False))
                    for row_w in self._row_widgets:
                        row_w.set_palette_colors(p_col, s_col)
                else:
                    try:
                        from core.widgets.services.lyrics.color import extract_color_palette

                        palette = extract_color_palette(thumbnail_bytes)
                        if palette:
                            self._content_frame.set_target_palette(palette[0], palette[1])
                            self._current_album_color = QColor(*palette[0])
                            self._current_album_secondary = QColor(*palette[1])
                            self._update_follow_pill_style(self._current_album_color)
                            for row_w in self._row_widgets:
                                row_w.set_palette_colors(self._current_album_color, self._current_album_secondary)
                        else:
                            self._current_album_color = None
                            self._current_album_secondary = None
                            self._update_follow_pill_style(None)
                            for row_w in self._row_widgets:
                                row_w.set_palette_colors(None, None)
                    except Exception:
                        pass
                return

        self._update_artwork_fallback()
        self._content_frame.set_cover_art(None)
        use_yasb_accent = getattr(self.config, "accent", "album_art") == "yasb"
        if use_yasb_accent:
            p_col, s_col = self._resolve_yasb_palette()
            self._current_album_color = p_col
            self._current_album_secondary = s_col
            self._content_frame.set_target_palette(
                (p_col.red(), p_col.green(), p_col.blue()),
                (s_col.red(), s_col.green(), s_col.blue()),
            )
            self._update_follow_pill_style(p_col)
            self._update_pin_button_style(getattr(self, "_pinned", False))
            for row_w in self._row_widgets:
                row_w.set_palette_colors(p_col, s_col)
        else:
            self._current_album_color = None
            self._current_album_secondary = None
            self._update_follow_pill_style(None)
            for row_w in self._row_widgets:
                row_w.set_palette_colors(None, None)

    def set_palette_colors(self, primary: QColor | None, secondary: QColor | None = None) -> None:
        """Updates dominant and secondary album art palette colors across popup and row widgets."""
        self._current_album_color = primary
        self._current_album_secondary = secondary
        self._update_follow_pill_style(primary)
        self._update_pin_button_style(getattr(self, "_pinned", False))
        if hasattr(self, "_content_frame"):
            if primary and secondary:
                self._content_frame.set_target_palette(
                    (primary.red(), primary.green(), primary.blue()),
                    (secondary.red(), secondary.green(), secondary.blue()),
                )
            elif primary:
                self._content_frame.set_target_palette(
                    (primary.red(), primary.green(), primary.blue()),
                    (primary.red(), primary.green(), primary.blue()),
                )
            else:
                self._content_frame.set_target_palette(None, None)
        if self._current_track is None or not self._current_track.thumbnail_bytes:
            self._update_artwork_fallback()
        if self._state in ("searching", "not-found", "idle"):
            self._update_msg_icon()
        for row_w in self._row_widgets:
            row_w.set_palette_colors(primary, secondary)

    def _update_follow_pill_style(self, color: QColor | None) -> None:
        self._update_transport_style()
        if not hasattr(self, "_follow_pill"):
            return
        if not color or not color.isValid():
            self._follow_pill.setStyleSheet("")
            return

        r, g, b = color.red(), color.green(), color.blue()
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = "rgba(15, 15, 20, 0.95)" if lum > 150 else "rgba(255, 255, 255, 0.95)"

        hr = min(255, int(r * 1.15)) if lum < 180 else max(0, int(r * 0.85))
        hg = min(255, int(g * 1.15)) if lum < 180 else max(0, int(g * 0.85))
        hb = min(255, int(b * 1.15)) if lum < 180 else max(0, int(b * 0.85))

        self._follow_pill.setStyleSheet(
            f"QPushButton.follow-pill {{"
            f" background-color: rgb({r}, {g}, {b});"
            f" color: {text_color};"
            f" border: 1px solid rgba(255, 255, 255, 0.25);"
            f" border-radius: 16px;"
            f" font-size: 11px;"
            f" font-weight: 700;"
            f" padding: 5px 16px;"
            f"}}"
            f"QPushButton.follow-pill:hover {{"
            f" background-color: rgb({hr}, {hg}, {hb});"
            f" color: {text_color};"
            f"}}"
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        bg_style = getattr(self.popup_config, "background_style", "ambient")
        ambient_enabled = bg_style == "ambient"
        accent_mode = getattr(self.config, "accent", "album_art")
        self._content_frame = AmbientContentFrame(
            self,
            ambient_enabled=ambient_enabled,
            background_style=bg_style,
            accent=accent_mode,
        )
        self._content_frame.setProperty("class", "popup-container")
        root_layout.addWidget(self._content_frame)

        main_layout = QVBoxLayout(self._content_frame)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        header_frame = QFrame(self)
        header_frame.setProperty("class", "popup-header")
        header_outer = QVBoxLayout(header_frame)
        header_outer.setContentsMargins(6, 6, 8, 8)
        header_outer.setSpacing(6)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_outer.addLayout(header_layout)

        self._art_label = QLabel(header_frame)
        self._art_label.setProperty("class", "header-artwork")
        self._art_label.setFixedSize(44, 44)
        self._art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_label.setContentsMargins(0, 0, 0, 0)
        self._art_label.setStyleSheet("padding: 0px; margin: 0px; border: none; background: transparent;")
        self._update_artwork_fallback()
        header_layout.addWidget(self._art_label)

        meta_col = QVBoxLayout()
        meta_col.setContentsMargins(0, 0, 0, 0)
        meta_col.setSpacing(2)

        self._title_label = ElidedLabel("No Track Playing", header_frame)
        self._title_label.setProperty("class", "header-title")

        self._artist_label = ElidedLabel("", header_frame)
        self._artist_label.setProperty("class", "header-artist")

        meta_col.addWidget(self._title_label)
        meta_col.addWidget(self._artist_label)
        header_layout.addLayout(meta_col, 1)

        self._pin_btn = QPushButton(header_frame)
        self._pin_btn.setProperty("class", "header-btn pin-btn")
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.setToolTip("Pin window on top")
        self._pin_btn.clicked.connect(self._toggle_pinned)
        self._update_pin_button_style(False)
        header_layout.addWidget(self._pin_btn)

        self._close_btn = QPushButton("✕", header_frame)
        self._close_btn.setProperty("class", "header-btn close-btn")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.clicked.connect(self.hide_animated)
        header_layout.addWidget(self._close_btn)

        self._build_transport_controls(header_frame, header_outer)
        self._header_frame = header_frame
        main_layout.addWidget(header_frame)

        self._stack_host = QWidget(self)
        self._stack_host.setStyleSheet("background: transparent; border: none;")
        self._stack_layout = QStackedLayout(self._stack_host)

        self._scroll_view = LyricsScrollView(self)
        self._scroll_view.user_scrolled.connect(self._on_user_scrolled)

        self._rows_container = QWidget()
        self._rows_container.setProperty("class", "rows-container")
        self._rows_container.setStyleSheet("background: transparent; border: none;")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 4, 0, 4)
        self._rows_layout.setSpacing(3)
        self._rows_layout.addStretch(1)

        self._scroll_view.setWidget(self._rows_container)
        self._stack_layout.addWidget(self._scroll_view)

        self._message_frame = QFrame(self)
        self._message_frame.setProperty("class", "popup-message-frame")
        msg_layout = QVBoxLayout(self._message_frame)
        msg_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_layout.setSpacing(12)

        self._msg_icon = QLabel(self._message_frame)
        self._msg_icon.setProperty("class", "message-icon")
        self._msg_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_msg_icon()

        self._msg_text = QLabel("Loading...", self._message_frame)
        self._msg_text.setProperty("class", "message-text")
        self._msg_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._retry_btn = QPushButton("Retry Search", self._message_frame)
        self._retry_btn.setProperty("class", "retry-btn")
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        self._retry_btn.hide()

        msg_layout.addWidget(self._msg_icon)
        msg_layout.addWidget(self._msg_text)
        msg_layout.addWidget(self._retry_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._stack_layout.addWidget(self._message_frame)
        main_layout.addWidget(self._stack_host, 1)

        self._follow_pill = QPushButton("Back to Current Line", self)
        self._follow_pill.setProperty("class", "follow-pill")
        self._follow_pill.clicked.connect(self._resume_follow)
        self._follow_pill.hide()
        self._update_follow_pill_style(getattr(self, "_current_album_color", None))

        footer_frame = QFrame(self)
        self._footer_frame = footer_frame
        footer_frame.setProperty("class", "popup-footer")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(8, 4, 8, 4)
        footer_layout.setSpacing(6)

        self._source_label = QLabel("LrcLib", footer_frame)
        self._source_label.setProperty("class", "footer-source")
        footer_layout.addWidget(self._source_label, 1)

        self._prev_hit_btn = QPushButton("◀", footer_frame)
        self._prev_hit_btn.setProperty("class", "footer-btn hit-btn")
        self._prev_hit_btn.setFixedSize(22, 22)
        self._prev_hit_btn.clicked.connect(self.cycle_hit_requested.emit)

        self._hit_count_label = QLabel("1/1", footer_frame)
        self._hit_count_label.setProperty("class", "footer-hit-count")

        self._next_hit_btn = QPushButton("▶", footer_frame)
        self._next_hit_btn.setProperty("class", "footer-btn hit-btn")
        self._next_hit_btn.setFixedSize(22, 22)
        self._next_hit_btn.clicked.connect(self.cycle_hit_requested.emit)

        footer_layout.addWidget(self._prev_hit_btn)
        footer_layout.addWidget(self._hit_count_label)
        footer_layout.addWidget(self._next_hit_btn)

        main_layout.addWidget(footer_frame)
        self._update_transport_style()

    def _build_transport_controls(self, header_frame: QFrame, header_outer: QVBoxLayout) -> None:
        self._controls_frame = QFrame(header_frame)
        self._controls_frame.setProperty("class", "header-controls")
        self._controls_frame.setStyleSheet("background: transparent; border: none;")
        col = QVBoxLayout(self._controls_frame)
        col.setContentsMargins(4, 0, 4, 0)
        col.setSpacing(2)

        self._progress_container = QWidget(self._controls_frame)
        self._progress_container.setProperty("class", "progress-container")
        self._progress_container.setStyleSheet("background: transparent; border: none;")
        prog_col = QVBoxLayout(self._progress_container)
        prog_col.setContentsMargins(0, 0, 0, 0)
        prog_col.setSpacing(2)

        label_style = (
            "QLabel { color: rgba(255, 255, 255, 0.65); font-size: 11px; background: transparent; border: none; }"
        )
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(6)
        self._elapsed_label = QLabel("0:00", self._progress_container)
        self._elapsed_label.setProperty("class", "time-label elapsed")
        self._elapsed_label.setStyleSheet(label_style)
        self._elapsed_label.setMinimumWidth(34)
        self._elapsed_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        wave = getattr(self.popup_config, "progress_style", "line") == "wave"
        self._progress_bar = PopupProgressBar(self._progress_container)
        self._progress_bar.set_style("wave" if wave else "line")
        self._progress_bar.setProperty("class", "progress-bar")
        self._progress_bar.seek_requested.connect(self._on_progress_seek)
        self._progress_bar.preview_changed.connect(self._on_progress_preview)
        self._total_label = QLabel("--:--", self._progress_container)
        self._total_label.setProperty("class", "time-label total")
        self._total_label.setStyleSheet(label_style)
        self._total_label.setMinimumWidth(34)
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if wave:
            prog_col.addWidget(self._progress_bar)
            times_row = QHBoxLayout()
            times_row.setContentsMargins(6, 0, 6, 0)
            times_row.addWidget(self._elapsed_label)
            times_row.addStretch(1)
            times_row.addWidget(self._total_label)
            prog_col.addLayout(times_row)
        else:
            progress_row.addWidget(self._elapsed_label)
            progress_row.addWidget(self._progress_bar, 1)
            progress_row.addWidget(self._total_label)
            prog_col.addLayout(progress_row)

        col.addWidget(self._progress_container)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(14)
        self._prev_btn = QPushButton(self._controls_frame)
        self._prev_btn.setProperty("class", "media-btn prev-btn")
        self._prev_btn.setFixedSize(30, 30)
        self._prev_btn.setIconSize(QSize(16, 16))
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.setToolTip("Previous")
        self._prev_btn.clicked.connect(self.prev_requested.emit)
        self._play_btn = QPushButton(self._controls_frame)
        self._play_btn.setProperty("class", "media-btn play-btn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setIconSize(QSize(18, 18))
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.clicked.connect(self.play_pause_requested.emit)
        self._next_btn = QPushButton(self._controls_frame)
        self._next_btn.setProperty("class", "media-btn next-btn")
        self._next_btn.setFixedSize(30, 30)
        self._next_btn.setIconSize(QSize(16, 16))
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setToolTip("Next")
        self._next_btn.clicked.connect(self.next_requested.emit)
        button_row.addStretch(1)
        button_row.addWidget(self._prev_btn)
        button_row.addWidget(self._play_btn)
        button_row.addWidget(self._next_btn)
        button_row.addStretch(1)
        col.addLayout(button_row)

        header_outer.addWidget(self._controls_frame)
        self._controls_frame.setVisible(False)

    def _update_transport_style(self) -> None:
        if not hasattr(self, "_play_btn"):
            return
        accent = self._current_album_color
        if accent is None or not accent.isValid():
            accent = QColor(208, 171, 249)
        lum = 0.299 * accent.red() + 0.587 * accent.green() + 0.114 * accent.blue()
        on_accent = QColor(15, 15, 20) if lum > 150 else QColor(255, 255, 255)
        hex_accent = accent.name()
        light = hex_accent if lum >= 60 else "#FFFFFF"

        self._progress_bar.set_accent(accent)
        self._progress_bar.set_palette(accent, getattr(self, "_current_album_secondary", None))
        flat = (
            "QPushButton { background: transparent; border: 1px solid transparent; border-radius: 15px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 0.14); }"
            "QPushButton:disabled { background: transparent; }"
        )
        for btn, kind in ((self._prev_btn, "prev"), (self._next_btn, "next")):
            btn.setStyleSheet(flat)
            btn.setIcon(_render_transport_icon(kind, QColor(255, 255, 255, 235), 16))
        base = QColor(light)
        hover = base.darker(112).name() if base.lightness() > 150 else base.lighter(118).name()
        self._play_btn.setStyleSheet(
            f"QPushButton {{ background: {light}; border: 1px solid {light}; border-radius: 18px; }}"
            f"QPushButton:hover {{ background: {hover}; border: 1px solid {hover}; }}"
            "QPushButton:disabled { background: rgba(255, 255, 255, 0.18); border: 1px solid transparent; }"
        )
        self._play_icon_color = on_accent if light != "#FFFFFF" else QColor(15, 15, 20)
        self._update_play_icon()

    def _update_play_icon(self) -> None:
        if not hasattr(self, "_play_btn"):
            return
        color = getattr(self, "_play_icon_color", QColor(15, 15, 20))
        playing = bool(self._last_playing)
        self._play_btn.setIcon(_render_transport_icon("pause" if playing else "play", color, 18))
        self._play_btn.setToolTip("Pause" if playing else "Play")

    def _resolve_duration(self) -> int:
        if self._current_track and self._current_track.duration_ms is not None and self._current_track.duration_ms > 0:
            return int(self._current_track.duration_ms)

        hit = self._hits[self._hit_index] if (self._hits and 0 <= self._hit_index < len(self._hits)) else None
        hit_dur = int(hit.duration_s * 1000) if (hit and hit.duration_s is not None and hit.duration_s > 0) else 0
        engine_dur = int(self._engine.total_duration_ms) if (self._engine and self._engine.total_duration_ms > 0) else 0
        dur = hit_dur or engine_dur or (self._active_lyrics.span_ms() if self._active_lyrics else 0) or 0
        if dur > 0 and self._current_track and not self._current_track.duration_ms:
            self._current_track.duration_ms = dur
        return max(0, dur)

    def _update_transport(self, status: SyncStatus) -> None:
        snapshot = self._engine.snapshot if self._engine else None
        duration = self._resolve_duration()
        has_duration = duration > 0

        if hasattr(self, "_progress_container"):
            was_visible = not self._progress_container.isHidden()
            if was_visible != has_duration:
                self._progress_container.setVisible(has_duration)
                if self._collapsed:
                    self._apply_height()
        self._progress_bar.setVisible(has_duration)

        position = max(0, int(status.position_ms))
        if duration > 0:
            position = min(position, duration)
        self._progress_bar.set_fraction(position / duration if duration > 0 else 0.0)
        self._progress_bar.set_seekable(has_duration)

        if not self._progress_bar.is_dragging:
            elapsed_txt = _format_time(position)
            if elapsed_txt != self._elapsed_label.text():
                self._elapsed_label.setText(elapsed_txt)
        total_txt = _format_time(duration) if duration > 0 else "--:--"
        if total_txt != self._total_label.text():
            self._total_label.setText(total_txt)

        playing = bool(snapshot and snapshot.status == "playing")
        self._progress_bar.tick(playing)
        if playing != self._last_playing:
            self._last_playing = playing
            self._update_play_icon()

    def _on_progress_seek(self, fraction: float) -> None:
        duration = self._resolve_duration()
        if duration > 0:
            self.seek_requested.emit(int(fraction * duration))

    def _on_progress_preview(self, fraction: float) -> None:
        duration = self._resolve_duration()
        if duration > 0:
            self._elapsed_label.setText(_format_time(int(fraction * duration)))

    def _collapsed_height(self) -> int:
        header = getattr(self, "_header_frame", None)
        if header is None:
            return 140
        header.ensurePolished()
        layout = header.layout()
        if layout is not None:
            layout.activate()
        content_layout = self._content_frame.layout()
        margins = content_layout.contentsMargins() if content_layout is not None else None
        pad = (margins.top() + margins.bottom()) if margins else 24
        return pad + header.sizeHint().height()

    def _set_collapsed(self, collapsed: bool) -> None:
        if collapsed != self._collapsed:
            self._collapsed = collapsed
            self._stack_host.setVisible(not collapsed)
            self._footer_frame.setVisible(not collapsed)
            if collapsed:
                self._follow_pill.hide()
        self._apply_height()

    def _apply_height(self) -> None:
        if self._collapsed:
            target_h = max(80, self._collapsed_height())
            self._expanded_applied = False
        else:
            if self._expanded_applied:
                return
            target_h = max(200, int(getattr(self.popup_config, "height", self.height())))
            self._expanded_applied = True
        if self.height() == target_h:
            return
        if self._user_pos_args is not None and not getattr(self, "_pinned", False):
            self.setPosition(*self._user_pos_args)
        else:
            self.setFixedSize(self.width(), target_h)

    def sync_data(
        self,
        track: TrackInfo | None,
        hits: list[Hit],
        hit_index: int,
        active_lyrics: Lyrics | None,
        engine: SyncEngine | None,
        state: str,
    ) -> None:
        """Called when widget data updates or before showing the popup."""
        lyrics_changed = self._active_lyrics != active_lyrics or self._current_track != track
        self._current_track = track
        self._hits = hits
        self._hit_index = hit_index
        self._active_lyrics = active_lyrics
        self._engine = engine
        self._state = state
        if self._engine is not None:
            self._update_transport(self._engine.tick())

        self._controls_frame.setVisible(track is not None)
        for btn in (self._prev_btn, self._play_btn, self._next_btn):
            btn.setEnabled(track is not None)

        if track:
            self._title_label.setText(track.title)
            self._artist_label.setText(track.artist)

            self._apply_artwork(track.thumbnail_bytes)
        else:
            self._title_label.setText("No Track Playing")
            self._artist_label.setText("")
            self._apply_artwork(None)
            self._content_frame.set_cover_art(None)
            use_yasb_accent = getattr(self.config, "accent", "album_art") == "yasb"
            if not use_yasb_accent:
                self._current_album_color = None
                self._current_album_secondary = None
                self._update_follow_pill_style(None)
                for row_w in self._row_widgets:
                    row_w.set_palette_colors(None, None)
            else:
                p_col, s_col = self._resolve_yasb_palette()
                self._current_album_color = p_col
                self._current_album_secondary = s_col
                self._update_follow_pill_style(p_col)
                for row_w in self._row_widgets:
                    row_w.set_palette_colors(p_col, s_col)

        if hits and len(hits) > hit_index:
            hit = hits[hit_index]
            source_txt = f"Lyrics from {hit.source}"
            if hit.writers:
                source_txt += f" • {', '.join(hit.writers[:2])}"
            self._source_label.setText(source_txt)
            self._hit_count_label.setText(f"{hit_index + 1}/{len(hits)}")
            self._prev_hit_btn.setEnabled(len(hits) > 1)
            self._next_hit_btn.setEnabled(len(hits) > 1)
        else:
            self._source_label.setText("")
            self._hit_count_label.setText("0/0")
            self._prev_hit_btn.setEnabled(False)
            self._next_hit_btn.setEnabled(False)

        if state == "searching":
            self._stack_layout.setCurrentIndex(0)
            self._apply_height()
            return
        elif state == "not-found":
            self._set_collapsed(True)
            self._stack_layout.setCurrentIndex(1)
            self._update_msg_icon()
            self._msg_text.setText("No lyrics available")
            self._retry_btn.show()
            return
        elif state == "failed":
            self._set_collapsed(True)
            self._stack_layout.setCurrentIndex(1)
            self._msg_icon.setText("⚠")
            self._msg_text.setText("Failed to retrieve lyrics")
            self._retry_btn.show()
            return

        self._stack_layout.setCurrentIndex(0)
        if lyrics_changed or not self._row_widgets:
            self._rebuild_rows()
        self._set_collapsed(not self._row_widgets)

    def _rebuild_rows(self) -> None:
        for row_w in self._row_widgets:
            self._rows_layout.removeWidget(row_w)
            row_w.deleteLater()
        self._row_widgets.clear()
        self._last_active_row = None

        viewport_w = int(getattr(self.popup_config, "width", self.width())) - 24
        if hasattr(self, "_scroll_view"):
            vp = self._scroll_view.viewport()
            if vp is not None and vp.width() > 100:
                viewport_w = vp.width()
        wrap_width = max(180, min(viewport_w - 48, int((viewport_w - 16) * 0.88)))

        if self._active_lyrics and getattr(self.popup_config, "romanize", True):
            try:
                from core.widgets.services.lyrics.romanize import romanize_lyrics

                romanize_lyrics(self._active_lyrics, target_scripts=None)
            except Exception as e:
                logger.debug("Failed to romanize lyrics in popup: %s", e)

        if not self._engine or not self._engine.rows:
            if self._active_lyrics and self._active_lyrics.plain:
                lines = self._active_lyrics.plain.strip().splitlines()
                romanized_plain: list[str | None] = [None] * len(lines)
                if getattr(self.popup_config, "romanize", True):
                    try:
                        from core.widgets.services.lyrics.romanize import detect_writing_system, romanize_text

                        system = detect_writing_system(lines)
                        if system:
                            romanized_plain = [romanize_text(t, system=system) for t in lines]
                    except Exception as e:
                        logger.debug("Failed to romanize plain lyrics: %s", e)

                r_idx = len(self._row_widgets)
                for idx, line_text in enumerate(lines):
                    line = Line(start_ms=0, end_ms=None, text=line_text, romanized=romanized_plain[idx])
                    row = LyricRow(line_index=0, line=line, start_ms=0, end_ms=0)
                    row_w = LyricsRowWidget(
                        row=row,
                        row_index=r_idx + idx,
                        parent=self._rows_container,
                        on_seek=lambda ms, r=r_idx + idx: self._on_row_clicked(r, ms),
                        font_scale=self.popup_config.font_scale,
                        instrumental_notes=True,
                        focus_distance_fade=True,
                        alignment=getattr(self.popup_config, "alignment", "center"),
                        duet_panning=True,
                        romanize=getattr(self.popup_config, "romanize", True),
                        syllable_physics=True,
                        wrap_width=wrap_width,
                    )
                    self._rows_layout.insertWidget(len(self._row_widgets), row_w)
                    if hasattr(self, "_current_album_color") and self._current_album_color:
                        row_w.set_palette_colors(
                            self._current_album_color, getattr(self, "_current_album_secondary", None)
                        )
                    self._row_widgets.append(row_w)
            return

        for idx, row in enumerate(self._engine.rows):
            row_w = LyricsRowWidget(
                row=row,
                row_index=idx,
                parent=self._rows_container,
                on_seek=lambda ms, r=idx: self._on_row_clicked(r, ms),
                font_scale=self.popup_config.font_scale,
                show_background=True,
                romanize=getattr(self.popup_config, "romanize", True),
                instrumental_notes=True,
                focus_distance_fade=True,
                alignment=getattr(self.popup_config, "alignment", "center"),
                duet_panning=True,
                syllable_physics=True,
                wrap_width=wrap_width,
            )
            if hasattr(self, "_current_album_color") and self._current_album_color:
                row_w.set_palette_colors(self._current_album_color, getattr(self, "_current_album_secondary", None))
            self._rows_layout.insertWidget(idx, row_w)
            self._row_widgets.append(row_w)

    def _on_row_clicked(self, row_index: int, start_ms: int) -> None:
        """Called when user clicks on a lyric row: seeks playback, centers row, and resumes follow."""
        self.seek_requested.emit(start_ms)

        self._is_following = True
        self._idle_timer.stop()
        self._follow_pill.hide()

        self._last_active_row = row_index

        if self._engine and self._engine.snapshot:
            snap = self._engine.snapshot
            new_snap = PlaybackSnapshot(
                position_ms=start_ms,
                rate=snap.rate,
                status=snap.status,
                wall_time=time.time(),
                can_seek=snap.can_seek,
            )
            self._engine.update_snapshot(new_snap)

        if 0 <= row_index < len(self._row_widgets):
            target_w = self._row_widgets[row_index]
            self._scroll_view.scroll_to_widget(target_w, animated=True, center=True)

        playback_state = (
            "paused"
            if (self._engine and self._engine.snapshot and self._engine.snapshot.status == "paused")
            else "playing"
        )
        fake_status = SyncStatus(
            position_ms=start_ms,
            effective_position_ms=start_ms,
            state=playback_state,
            active_row_index=row_index,
        )
        self._current_status = fake_status

        for idx, row_w in enumerate(self._row_widgets):
            if idx < row_index:
                state = "past"
            elif idx == row_index:
                state = "active"
            else:
                state = "upcoming"

            row_w.set_row_state(state, status=fake_status)
            dist = abs(idx - row_index)
            row_w.set_focus_distance(dist)

    def _on_popup_tick(self) -> None:
        if not self.isVisible() or not self._engine:
            return

        status = self._engine.tick()
        self._current_status = status
        self._update_transport(status)
        active_idx = (
            status.break_row_index
            if (status.is_break and status.break_row_index is not None)
            else status.active_row_index
        )

        for idx, row_w in enumerate(self._row_widgets):
            if active_idx is None:
                state = "upcoming"
            elif idx < active_idx:
                state = "past"
            elif idx == active_idx:
                state = "active"
            else:
                state = "upcoming"

            row_w.set_row_state(state, status=status)
            dist = abs(idx - active_idx) if active_idx is not None else None
            row_w.set_focus_distance(dist)

        if self._is_following and active_idx is not None and active_idx != self._last_active_row:
            self._last_active_row = active_idx
            if active_idx < len(self._row_widgets):
                target_w = self._row_widgets[active_idx]
                self._scroll_view.scroll_to_widget(target_w, animated=True)

    def _on_user_scrolled(self) -> None:
        """Called when user manually moves scrollbar; pauses auto-follow."""
        self._is_following = False
        self._follow_pill.show()
        self._position_follow_pill()
        self._idle_timer.start()

    def _resume_follow(self) -> None:
        """Resumes auto-following the active line."""
        self._is_following = True
        self._idle_timer.stop()
        self._follow_pill.hide()
        active_idx = (
            self._current_status.break_row_index
            if (
                self._current_status
                and self._current_status.is_break
                and self._current_status.break_row_index is not None
            )
            else (self._current_status.active_row_index if self._current_status else None)
        )
        if active_idx is None:
            active_idx = self._last_active_row
        if active_idx is not None and active_idx < len(self._row_widgets):
            self._scroll_view.scroll_to_widget(self._row_widgets[active_idx], animated=True, center=True)

    def _position_follow_pill(self) -> None:
        pill_w = 148
        pill_h = 32
        x = (self.width() - pill_w) // 2
        y = self.height() - 74
        self._follow_pill.setGeometry(x, y, pill_w, pill_h)
        self._follow_pill.raise_()

    def _update_pin_button_style(self, pinned: bool) -> None:
        if not hasattr(self, "_pin_btn"):
            return
        accent_hex = (
            self._current_album_color.name()
            if (self._current_album_color and self._current_album_color.isValid())
            else "#D0ABF9"
        )
        if pinned:
            self._pin_btn.setIcon(_render_pin_icon("#FFFFFF", size=12))
            self._pin_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {accent_hex};
                    border: 1px solid {accent_hex};
                    border-radius: 4px;
                    padding: 2px;
                }}
            """)
        else:
            self._pin_btn.setIcon(_render_pin_icon("#AAAAAA", size=12))
            self._pin_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.12);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                }
            """)

    def _toggle_pinned(self) -> None:
        new_pinned = not getattr(self, "_pinned", False)
        if hasattr(self, "set_pinned"):
            self.set_pinned(new_pinned)
        else:
            self._pinned = new_pinned
        self._update_pin_button_style(new_pinned)

    @override
    def showEvent(self, a0: Any) -> None:
        super().showEvent(a0)
        self._is_following = True
        self._follow_pill.hide()
        if hasattr(self, "_content_frame"):
            self._content_frame.update_bar_style()
        if getattr(self.config, "accent", "album_art") == "yasb":
            p_col, s_col = self._resolve_yasb_palette()
            self.set_palette_colors(p_col, s_col)
        self._content_frame.start_animation()
        if self._collapsed:
            self._apply_height()
        self._tick_timer.start(33)
        self._on_popup_tick()
        if self._current_status and self._current_status.active_row_index is not None:
            idx = self._current_status.active_row_index
            if idx < len(self._row_widgets):
                self._scroll_view.scroll_to_widget(self._row_widgets[idx], animated=False)

    @override
    def hideEvent(self, a0: Any) -> None:
        self._tick_timer.stop()
        self._idle_timer.stop()
        self._content_frame.stop_animation()
        super().hideEvent(a0)

    @override
    def resizeEvent(self, a0: Any) -> None:
        self._in_resize = True
        try:
            super().resizeEvent(a0)
        finally:
            self._in_resize = False
        if self._follow_pill.isVisible():
            self._position_follow_pill()

import ctypes
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import traceback
import urllib.request
from dataclasses import dataclass
from html import escape as html_escape
from urllib.parse import urlencode

import certifi
from PyQt6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextDocument,
)
from PyQt6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxyFactory,
    QNetworkReply,
    QNetworkRequest,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from winmica import BackdropType, EnableMica, is_mica_supported

from core.ui.color_tokens import BUTTON_COLOR_TOKENS
from core.ui.style import apply_button_style, is_dark_palette
from core.utils.utilities import is_windows_10
from settings import DEFAULT_CONFIG_DIRECTORY, IS_FROZEN

SCRIPT_PATH = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(os.path.abspath(__file__))
UI_FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI"]
UI_FONT_CSS = "'Segoe UI Variable Text', 'Segoe UI'"

QNetworkProxyFactory.setUseSystemConfiguration(True)

DEFAULT_THEME_INDEX_URLS = [
    "https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes.json",
    "https://api.yasb.dev/yasb-themes/themes.json",
]

DEFAULT_THEME_INSTALL_URLS = [
    "https://raw.githubusercontent.com/amnweb/yasb-themes/main/themes/{theme_id}",
    "https://api.yasb.dev/yasb-themes/themes/{theme_id}",
]

README_LINK_COLOR = "#58a6ff"
REPORT_TEXT_COLOR = "#ff6b6b"
REPORT_BG_COLOR = "rgba(255,107,107,0.18)"
REPORT_HOVER_BG_COLOR = "rgba(255,107,107,0.28)"

SIDEBAR_WIDTH = 240
HEADER_HEIGHT = 52
PILL_WIDTH = 3
PILL_HEIGHT = 16
PILL_MARGIN = 8
LIST_ITEM_HEIGHT = 42

SPINNER_CYCLE_MS = 1600
SPINNER_ROTATION_MS = 2600
DETAIL_FADE_MS = 350
PILL_ANIMATION_MS = 200
SMOOTH_SCROLL_DURATION_MS = 180
SMOOTH_SCROLL_STEP = 84
SCROLLBAR_WIDTH = 8

CODE_BLOCK_PLACEHOLDER = "\x00CB{index}\x00"
INLINE_CODE_PLACEHOLDER = "\x01IC{index}\x01"
CODE_BLOCK_PREFIX = "\x00CB"


@dataclass(frozen=True)
class ThemePalette:
    dark: bool
    text: str
    header_background: str
    sidebar_background: str
    footer_background: str
    search_background: str
    search_focus_background: str
    scrollbar_handle: str
    count_text: str
    selection_background: str
    code_background: str
    content_background: str
    muted_text: str
    disabled_text: str
    disabled_badge_text: str
    disabled_badge_background: str
    disabled_selected_background: str


class _MarkdownPatterns:
    """Compiled regular expressions used by the README preprocessor and Markdown renderer."""

    IMG_GH_BLOB = re.compile(r"!\[(.*?)\]\(https?://github\.com/([^/]+)/([^/]+)/blob/([^)]+)\)")
    IMG_TAG_GH = re.compile(
        r'<img([^>]*?)src=["\']https?://github\.com/([^/]+)/([^/]+)/blob/([^"\']+)(["\'])', re.IGNORECASE
    )
    HTML_WRAPPERS = re.compile(r"</?(?:div|span|center|section|article|figure|figcaption|p)[^>]*>", re.IGNORECASE)
    INDENT_INLINE = re.compile(r"^[ \t]+(<(?:img|br|a|hr).*)$", re.IGNORECASE | re.MULTILINE)
    IMG_SIZE_ATTR = re.compile(r'\s*(?:width|height)=["\'][^"\']*["\']', re.IGNORECASE)

    MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    MD_BOLD_EM = re.compile(r"\*{3}(.+?)\*{3}")
    MD_BOLD = re.compile(r"\*{2}(.+?)\*{2}")
    MD_BOLD_U = re.compile(r"__(.+?)__")
    MD_EM_STAR = re.compile(r"(?<!\w)\*(.+?)\*(?!\w)")
    MD_EM_UNDER = re.compile(r"(?<!\w)_(.+?)_(?!\w)")
    MD_STRIKE = re.compile(r"~~(.+?)~~")

    CODE_FENCE = re.compile(r"```\w*\n(.*?)```", re.DOTALL)
    CODE_INLINE = re.compile(r"`([^`\n]+)`")
    HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$")
    HEADING_FENCE = re.compile(r"^#{1,6}\s")
    HR = re.compile(r"^[-*_](?:\s*[-*_]){2,}\s*$")
    TABLE_SEP = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
    UL_ITEM = re.compile(r"^[-*+]\s")
    UL_ITEM_ALL = re.compile(r"^\s*[-*+]\s")
    UL_STRIP = re.compile(r"^\s*[-*+]\s+")
    OL_ITEM = re.compile(r"^\d+[.)]\s")
    OL_ITEM_ALL = re.compile(r"^\s*\d+[.)]\s")
    OL_STRIP = re.compile(r"^\s*\d+[.)]\s+")
    BQ_START = re.compile(r"^>")
    BQ_PREFIX = re.compile(r"^>\s?")


def _text_color() -> str:
    return "#f0f0f0" if is_dark_palette() else "#1a1a1a"


def _theme_key() -> str:
    return "dark" if is_dark_palette() else "light"


def _ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(UI_FONT_FAMILIES)
    f.setPointSize(size)
    f.setWeight(weight)
    return f


def _network_request(url: str, referer: str = "") -> QNetworkRequest:
    req = QNetworkRequest(QUrl(url))
    req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    if referer:
        req.setRawHeader(b"Referer", referer.encode())
    return req


def _app_icon() -> QIcon:
    return QIcon(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png"))


def _run_yasbc(cmd: str):
    subprocess.run(
        ["yasbc", cmd],
        creationflags=subprocess.CREATE_NO_WINDOW,
        capture_output=True,
    )


def _make_btn(text: str, variant: str, width: int = 0, slot=None) -> QPushButton:
    btn = QPushButton(text)
    apply_button_style(btn, variant)
    if width:
        btn.setFixedWidth(width)
    if slot:
        btn.clicked.connect(slot)
    return btn


def _build_palette() -> ThemePalette:
    dark = is_dark_palette()
    return ThemePalette(
        dark=dark,
        text=_text_color(),
        header_background="transparent",
        sidebar_background="transparent",
        footer_background="transparent",
        search_background="rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.04)",
        search_focus_background="rgba(255,255,255,0.09)" if dark else "rgba(0,0,0,0.07)",
        scrollbar_handle="rgba(255,255,255,0.12)" if dark else "rgba(0,0,0,0.15)",
        count_text="rgba(255,255,255,0.35)" if dark else "rgba(0,0,0,0.35)",
        selection_background="rgba(255,255,255,0.15)" if dark else "rgba(0,0,0,0.10)",
        code_background="rgba(0,0,0,0.08)" if dark else "rgba(0,0,0,0.06)",
        content_background="rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.06)",
        muted_text="rgba(255,255,255,0.8)" if dark else "rgba(0,0,0,0.6)",
        disabled_text="rgba(255,255,255,0.3)" if dark else "rgba(0,0,0,0.3)",
        disabled_badge_text="rgba(255,255,255,0.4)" if dark else "rgba(0,0,0,0.4)",
        disabled_badge_background="rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.07)",
        disabled_selected_background="rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.04)",
    )


def _button_tokens(variant: str) -> dict[str, str]:
    return BUTTON_COLOR_TOKENS[_theme_key()][variant]


def _sidebar_list_style(text_color: str, scrollbar_handle: str) -> str:
    return (
        f"QListWidget {{ background: transparent; border: none; outline: none;"
        f" padding: 6px 0; color: {text_color}; }}"
        f"QListWidget::item {{ padding: 0; border: none; background: transparent;"
        f" color: {text_color}; margin: 0; }}"
        f"QListWidget::item:selected {{ background: transparent; border: none; }}"
        f"QListWidget::item:hover:!selected {{ background: transparent; }}"
        f"QScrollBar:vertical {{ border: none; background: transparent; width: {SCROLLBAR_WIDTH}px; margin: 6px 1px 6px 0; }}"
        f"QScrollBar::handle:vertical {{ background: {scrollbar_handle}; border-radius: 4px; min-height: 28px; }}"
        f"QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.24); }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}"
    )


def _search_box_style(text_color: str, background: str, focus_background: str) -> str:
    return (
        f"QLineEdit {{ border: none; border-radius: 4px; background: {background}; color: {text_color};"
        f"min-height: 32px; max-height: 32px; outline: none;"
        f"padding: 0px 14px; font-family: {UI_FONT_CSS}; font-size: 10pt; }}"
        f"QLineEdit:focus {{ background: {focus_background}; }}"
    )


def _readme_browser_styles(text_color: str, selection_background: str, code_background: str) -> tuple[str, str]:
    widget_style = (
        f"QTextBrowser {{ background: transparent; border: none; color: {text_color};"
        f" padding: 0; selection-background-color: {selection_background}; }}"
    )
    document_style = (
        f"body {{ color: {text_color}; margin: 0; padding: 0; }}"
        f"h1, h2, h3, h4 {{ margin-top: 14px; margin-bottom: 4px; color: {text_color}; }}"
        f"p {{ margin: 4px 0; }}"
        f"a {{ color: {README_LINK_COLOR}; text-decoration: none; }}"
        f"img {{ max-width: 100%; height: auto; display: block; margin: 6px 0; }}"
        f"code {{ background: {code_background}; padding: 10px 4px; border-radius: 3px;"
        f" font-family: 'Consolas', monospace; }}"
        f"pre {{ background: {code_background}; padding: 8px; border-radius: 6px; white-space: pre-wrap; }}"
        f"ul, ol {{ margin: 4px 0; padding-left: 20px; }}"
        f"li {{ margin: 2px 0; }}"
    )
    return widget_style, document_style


def _report_button_style() -> str:
    return (
        f"QPushButton {{ color: {REPORT_TEXT_COLOR}; background: {REPORT_BG_COLOR}; border-radius: 8px;"
        " border: none; padding: 0px 8px; margin-top: 4px; min-height: 16px; max-height: 16px; }"
        f"QPushButton:hover {{ background: {REPORT_HOVER_BG_COLOR}; }}"
    )


def _readme_scroll_style() -> str:
    return (
        "QScrollArea { background: transparent; border: none; }"
        f"QScrollBar:vertical {{ border: none; background: transparent; width: {SCROLLBAR_WIDTH}px; margin: 8px 2px 8px 0; }}"
        "QScrollBar::handle:vertical { background: rgba(255,255,255,0.16); border-radius: 4px; min-height: 28px; }"
        "QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.24); }"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }"
    )


class SmoothScrollFilter(QObject):
    """Animate wheel scrolling so dense content feels closer to a browser or editor."""

    def __init__(
        self,
        scroll_bar,
        parent: QObject | None = None,
        *,
        step: int = SMOOTH_SCROLL_STEP,
        duration: int = SMOOTH_SCROLL_DURATION_MS,
    ):
        super().__init__(parent)
        self._scroll_bar = scroll_bar
        self._step = step
        self._animation = QPropertyAnimation(scroll_bar, b"value", self)
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel or not self._scroll_bar.isVisible():
            return super().eventFilter(watched, event)

        pixel_delta = event.pixelDelta().y()
        angle_delta = event.angleDelta().y()
        if pixel_delta == 0 and angle_delta == 0:
            return super().eventFilter(watched, event)

        if pixel_delta:
            scroll_delta = pixel_delta
        else:
            scroll_delta = int((angle_delta / 120) * self._step)

        anchor = (
            self._animation.endValue()
            if self._animation.state() == QPropertyAnimation.State.Running
            else self._scroll_bar.value()
        )
        target = max(self._scroll_bar.minimum(), min(self._scroll_bar.maximum(), int(anchor - scroll_delta)))
        if target == self._scroll_bar.value() and self._animation.state() != QPropertyAnimation.State.Running:
            return True

        self._animation.stop()
        self._animation.setStartValue(self._scroll_bar.value())
        self._animation.setEndValue(target)
        self._animation.start()
        return True


def _replace_placeholders(html: str, placeholders: list[str], template: str) -> str:
    for index, value in enumerate(placeholders):
        html = html.replace(template.format(index=index), value)
    return html


def _preprocess_readme(text: str) -> str:
    """Strip block-level HTML wrappers and rewrite GitHub blob URLs to raw URLs."""
    text = _MarkdownPatterns.IMG_GH_BLOB.sub(r"![\1](https://raw.githubusercontent.com/\2/\3/\4)", text)
    text = _MarkdownPatterns.IMG_TAG_GH.sub(r"<img\1src=\5https://raw.githubusercontent.com/\2/\3/\4\5", text)
    text = _MarkdownPatterns.HTML_WRAPPERS.sub("", text)
    text = _MarkdownPatterns.INDENT_INLINE.sub(r"\1", text)
    # Strip width/height attributes from <img> tags so CSS max-width:100% controls sizing
    text = re.sub(
        r"(<img\b)([^>]*?)>",
        lambda m: m.group(1) + _MarkdownPatterns.IMG_SIZE_ATTR.sub("", m.group(2)) + ">",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _md_inline(text: str) -> str:
    """Convert inline Markdown (bold, italic, links, images) to HTML."""
    text = _MarkdownPatterns.MD_IMG.sub(r'<img src="\2" alt="\1">', text)
    text = _MarkdownPatterns.MD_LINK.sub(r'<a href="\2">\1</a>', text)
    text = _MarkdownPatterns.MD_BOLD_EM.sub(r"<strong><em>\1</em></strong>", text)
    text = _MarkdownPatterns.MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MarkdownPatterns.MD_BOLD_U.sub(r"<strong>\1</strong>", text)
    text = _MarkdownPatterns.MD_EM_STAR.sub(r"<em>\1</em>", text)
    text = _MarkdownPatterns.MD_EM_UNDER.sub(r"<em>\1</em>", text)
    text = _MarkdownPatterns.MD_STRIKE.sub(r"<del>\1</del>", text)
    return text


def _md_table(lines: list[str]) -> str:
    """Convert Markdown table lines into an HTML <table>."""

    def _cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    headers = _cells(lines[0])
    rows = [_cells(ln) for ln in lines[2:] if ln.strip()]
    html = "<table><thead><tr>" + "".join(f"<th>{_md_inline(h)}</th>" for h in headers) + "</tr></thead>"
    if rows:
        html += (
            "<tbody>"
            + "".join("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            + "</tbody>"
        )
    return html + "</table>"


def _md_to_html(src: str) -> str:
    """Minimal Markdown-to-HTML converter for QTextBrowser rendering."""
    src = src.replace("\r\n", "\n")
    code_blocks: list[str] = []

    def _stash_code(m: re.Match) -> str:
        code = html_escape(m.group(1).rstrip("\n"))
        code_blocks.append(f"<pre><code>{code}</code></pre>")
        return CODE_BLOCK_PLACEHOLDER.format(index=len(code_blocks) - 1)

    src = _MarkdownPatterns.CODE_FENCE.sub(_stash_code, src)
    inline_codes: list[str] = []

    def _stash_ic(m: re.Match) -> str:
        inline_codes.append(f"<code>{html_escape(m.group(1))}</code>")
        return INLINE_CODE_PLACEHOLDER.format(index=len(inline_codes) - 1)

    src = _MarkdownPatterns.CODE_INLINE.sub(_stash_ic, src)

    lines = src.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # Code block placeholder
        if stripped.startswith(CODE_BLOCK_PREFIX):
            out.append(stripped)
            i += 1
            continue
        # Heading
        hm = _MarkdownPatterns.HEADING.match(stripped)
        if hm:
            lvl = len(hm.group(1))
            out.append(f"<h{lvl}>{_md_inline(hm.group(2))}</h{lvl}>")
            i += 1
            continue
        # Horizontal rule
        if _MarkdownPatterns.HR.match(stripped):
            out.append("<hr>")
            i += 1
            continue
        # Table
        if "|" in stripped and i + 1 < n and _MarkdownPatterns.TABLE_SEP.match(lines[i + 1].strip()):
            tlines: list[str] = []
            while i < n and "|" in lines[i]:
                tlines.append(lines[i])
                i += 1
            out.append(_md_table(tlines))
            continue
        # Blockquote
        if _MarkdownPatterns.BQ_START.match(stripped):
            bq: list[str] = []
            while i < n and _MarkdownPatterns.BQ_START.match(lines[i].strip()):
                bq.append(_MarkdownPatterns.BQ_PREFIX.sub("", lines[i], count=1))
                i += 1
            out.append(f"<blockquote>{_md_to_html(chr(10).join(bq))}</blockquote>")
            continue
        # Unordered list
        if _MarkdownPatterns.UL_ITEM.match(stripped):
            items: list[str] = []
            while i < n and _MarkdownPatterns.UL_ITEM_ALL.match(lines[i]):
                items.append(_MarkdownPatterns.UL_STRIP.sub("", lines[i], count=1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ul>")
            continue
        # Ordered list
        if _MarkdownPatterns.OL_ITEM.match(stripped):
            items = []
            while i < n and _MarkdownPatterns.OL_ITEM_ALL.match(lines[i]):
                items.append(_MarkdownPatterns.OL_STRIP.sub("", lines[i], count=1))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ol>")
            continue
        # Paragraph collect consecutive non-blank, non-block lines
        para: list[str] = []
        while (
            i < n
            and lines[i].strip()
            and not _MarkdownPatterns.HEADING_FENCE.match(lines[i].strip())
            and not _MarkdownPatterns.BQ_START.match(lines[i].strip())
            and not _MarkdownPatterns.HR.match(lines[i].strip())
            and not (_MarkdownPatterns.UL_ITEM.match(lines[i].strip()) and not para)
            and not (_MarkdownPatterns.OL_ITEM.match(lines[i].strip()) and not para)
            and not lines[i].strip().startswith(CODE_BLOCK_PREFIX)
        ):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>" + "<br>".join(_md_inline(p) for p in para) + "</p>")

    html = "\n".join(out)
    html = _replace_placeholders(html, code_blocks, CODE_BLOCK_PLACEHOLDER)
    return _replace_placeholders(html, inline_codes, INLINE_CODE_PLACEHOLDER)


class Spinner(QWidget):
    def __init__(self, size=24, color="#FFFFFF", pen_width=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = QColor(color)
        self._pen_width = pen_width if pen_width is not None else max(2, size // 10)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

    @staticmethod
    def _ease(t):
        if t < 0.5:
            return 4 * t * t * t
        p = 2 * t - 2
        return 0.5 * p * p * p + 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self._pen_width / 2.0 + 1.0
        rect = self.rect().toRectF().adjusted(m, m, -m, -m)
        pen = QPen(self._color)
        pen.setWidthF(self._pen_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap if self._pen_width <= 10 else Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        ms = self._elapsed.elapsed()
        cycle = ms / SPINNER_CYCLE_MS
        phase = cycle % 1.0
        accum = (int(cycle) * 260.0) % 360.0
        base_rot = (ms / SPINNER_ROTATION_MS) * 360.0 % 360.0

        if phase < 0.5:
            e = self._ease(phase * 2.0)
            span, start = 10 + 260 * e, accum
        else:
            e = self._ease((phase - 0.5) * 2.0)
            span, start = 270 - 260 * e, accum + 260 * e

        painter.drawArc(rect, int(-(start + base_rot) * 16), int(-span * 16))
        painter.end()


class AnimatedSplashTitle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._yasb_font = _ui_font(64, QFont.Weight.Bold)
        self._reborn_font = _ui_font(64, QFont.Weight.Light)
        self._color = QColor(_text_color())
        self._gap = 6

        ym = QFontMetricsF(self._yasb_font)
        rm = QFontMetricsF(self._reborn_font)
        self._yw = ym.horizontalAdvance("YASB")
        self._rw = rm.horizontalAdvance("Reborn")
        self.setFixedSize(int(self._yw + self._gap + self._rw + 80), int(max(ym.height(), rm.height()) + 18))
        self._progress = 0.0

    def reset_animation(self):
        self._progress = 0.0
        self.update()

    def set_progress(self, p: float):
        self._progress = max(0.0, min(1.0, p))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        ym, rm = QFontMetricsF(self._yasb_font), QFontMetricsF(self._reborn_font)
        ascent = max(ym.ascent(), rm.ascent())
        by = (self.height() + ascent - max(ym.descent(), rm.descent())) / 2.0

        center_x = (self.width() - self._yw) / 2.0
        end_x = (self.width() - (self._yw + self._gap + self._rw)) / 2.0
        reborn_start = center_x + self._yw - self._rw

        if self._progress >= 1.0:
            yx = round(end_x)
            rx, rop = round(end_x + self._yw + self._gap), 1.0
        else:
            yx = center_x + (end_x - center_x) * self._progress
            rp = max(0.0, (self._progress - 0.08) / 0.92) if self._progress > 0.08 else 0.0
            rx = reborn_start + (end_x + self._yw + self._gap - reborn_start) * rp
            cl = yx + self._yw + self._gap
            vis = max(0.0, min(self._rw, rx + self._rw - cl))
            rop = min(1.0, vis / self._rw) if self._rw else 0.0

        painter.setPen(self._color)
        painter.setFont(self._yasb_font)
        painter.drawText(QPointF(yx, by), "YASB")

        if rop <= 0.0:
            return
        cl = yx + self._yw + self._gap
        painter.save()
        painter.setFont(self._reborn_font)
        painter.setOpacity(rop)
        painter.setClipRect(QRectF(cl, 0, max(0.0, self.width() - cl), float(self.height())))
        painter.drawText(QPointF(rx, by), "Reborn")
        painter.restore()


class ThemeSplashScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_delay, self._duration, self._end_hold = SPINNER_CYCLE_MS, 400, 1000
        self._anim_active = False

        self.title_widget = AnimatedSplashTitle(self)
        self.spinner = Spinner(size=32, color=_text_color(), pen_width=2, parent=self)

        # Error state widget
        self._error_widget = QWidget(self)
        _ev_layout = QVBoxLayout(self._error_widget)
        _ev_layout.setContentsMargins(0, 0, 0, 0)
        _ev_layout.setSpacing(12)
        _ev_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _err_icon = QLabel()
        _err_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _err_icon.setText("\u26a0")
        _err_icon.setStyleSheet("color: #e87a7a; font-size: 40px; background: transparent;")
        _ev_layout.addWidget(_err_icon)
        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setFont(_ui_font(13))
        self._error_label.setStyleSheet(f"color: {_text_color()}; background: transparent;")
        _ev_layout.addWidget(self._error_label)
        self._error_widget.hide()

        self._delay = QTimer(self, singleShot=True)
        self._delay.timeout.connect(self._start_animation)
        self._frame = QTimer(self)
        self._frame.timeout.connect(self._tick)
        self._frame.start(8)
        self._elapsed = QElapsedTimer()
        self._do_layout()
        self._delay.start(self._start_delay)

    def minimum_display_ms(self) -> int:
        return self._start_delay + self._duration + self._end_hold

    def _start_animation(self):
        self._anim_active = True
        self._elapsed.restart()
        self.title_widget.reset_animation()

    def show_message(self, text: str):
        self._delay.stop()
        self._anim_active = False
        self.title_widget.hide()
        self.spinner.hide()
        self._error_label.setText(text)
        self._error_widget.adjustSize()
        self._error_widget.show()
        self._do_layout()

    def _tick(self):
        if not self._anim_active:
            return
        p = min(1.0, self._elapsed.elapsed() / self._duration)
        self.title_widget.set_progress(p)
        if p >= 1.0:
            self._anim_active = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._do_layout()

    def _do_layout(self):
        if self._error_widget.isVisible():
            self._error_widget.adjustSize()
            ew = self._error_widget
            ew.move((self.width() - ew.width()) // 2, (self.height() - ew.height()) // 2)
            return
        ch = self.title_widget.height() + self.spinner.height() + 8
        ty = (self.height() - ch) // 2
        self.title_widget.move((self.width() - self.title_widget.width()) // 2, ty)
        self.spinner.move(
            (self.width() - self.spinner.width()) // 2,
            ty + self.title_widget.height() + 8,
        )


class RemoteImageTextBrowser(QTextBrowser):
    """QTextBrowser that asynchronously fetches remote images."""

    content_ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().documentLayout().documentSizeChanged.connect(
            lambda s: self.setFixedHeight(int(s.height()) + 20)
        )
        self._images: dict[str, QPixmap] = {}
        self._loading: set[str] = set()
        self._replies: dict[str, QNetworkReply] = {}
        self._rev = 0
        self._ready_emitted = False
        self._html_source = ""

    def _maybe_ready(self, rev: int):
        if rev == self._rev and not self._ready_emitted and not self._loading:
            self._ready_emitted = True
            self.content_ready.emit()

    def loadResource(self, rtype, url):
        if rtype == QTextDocument.ResourceType.ImageResource:
            s = url.toString()
            if s in self._images:
                px = self._images[s]
                vw = self.viewport().width()
                if vw > 0 and px.width() > vw:
                    return px.scaledToWidth(vw, Qt.TransformationMode.SmoothTransformation)
                return px
            if url.scheme() in ("http", "https") and s not in self._loading:
                self._loading.add(s)
                rev = self._rev
                reply = self._net.get(_network_request(s, referer="https://github.com"))
                reply.finished.connect(lambda u=s, rv=rev, r=reply: self._on_fetched(rv, u, r))
                self._replies[s] = reply
            return None
        return super().loadResource(rtype, url)

    def _on_fetched(self, rev: int, url: str, reply: QNetworkReply):
        self._replies.pop(url, None)
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        data = bytes(reply.readAll()) if ok else b""
        reply.deleteLater()
        if rev != self._rev:
            return
        self._loading.discard(url)
        px = QPixmap()
        if not (data and px.loadFromData(data)):
            self._maybe_ready(rev)
            return
        self._images[url] = px
        if self._html_source:
            vbar = self.verticalScrollBar()
            pos = vbar.value()
            super().setHtml(self._html_source)
            QTimer.singleShot(30, lambda: vbar.setValue(pos))
        self._maybe_ready(rev)

    def clear_cache(self):
        self._rev += 1
        self._images.clear()
        self._loading.clear()
        self._ready_emitted = False

    def setMarkdown(self, text: str):
        html = _md_to_html(_preprocess_readme(text))
        self._rev += 1
        self._ready_emitted = False
        self._loading.clear()
        self._images.clear()
        self._html_source = html
        super().setHtml(html)
        QTimer.singleShot(0, lambda r=self._rev: self._maybe_ready(r))

    def shutdown(self):
        self._loading.clear()
        for r in list(self._replies.values()):
            r.abort()
            r.deleteLater()
        self._replies.clear()


class MagnifierOverlay(QWidget):
    RADIUS = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.RADIUS * 2, self.RADIUS * 2)
        self.zoomed_pixmap = None

    def paintEvent(self, event):
        if not self.zoomed_pixmap:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r2 = QRectF(0, 0, self.RADIUS * 2, self.RADIUS * 2)
        path = QPainterPath()
        path.addEllipse(r2)
        painter.setClipPath(path)
        painter.drawPixmap(r2.toRect(), self.zoomed_pixmap)
        painter.setClipping(False)
        for color, width, adj in [(QColor(255, 255, 255, 120), 2, 1), (QColor(0, 0, 0, 80), 1, 2)]:
            pen = QPen(color)
            pen.setWidth(width)
            painter.setPen(pen)
            painter.drawEllipse(r2.adjusted(adj, adj, -adj, -adj))


class MagnifierLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._original_pixmap = None
        self._zoom = 4.0
        self._overlay = MagnifierOverlay()
        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def hasHeightForWidth(self):
        return self._original_pixmap is not None

    def heightForWidth(self, w):
        if self._original_pixmap and self._original_pixmap.width() > 0:
            ow, oh = self._original_pixmap.width(), self._original_pixmap.height()
            return int(min(w, ow) * oh / ow)
        return 0

    def set_pixmap(self, pixmap):
        self._original_pixmap = pixmap
        if not pixmap or pixmap.isNull():
            self._original_pixmap = None
        self.updateGeometry()
        self.update()

    def _draw_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) of the drawn image area."""
        if not self._original_pixmap:
            return 0, 0, 0, 0
        ow, oh = self._original_pixmap.width(), self._original_pixmap.height()
        w = min(ow, self.width())
        h = int(w * oh / ow)
        x = (self.width() - w) // 2
        return x, 0, w, h

    def paintEvent(self, event):
        if not self._original_pixmap or self.width() <= 0:
            return
        x, y, w, h = self._draw_rect()
        if w <= 0 or h <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(x, y, w, h, self._original_pixmap)
        painter.end()

    def mouseMoveEvent(self, event):
        try:
            if not self._original_pixmap or self._original_pixmap.isNull():
                return
            pos = event.pos()
            dx, dy, dw, dh = self._draw_rect()
            if dw <= 0 or dh <= 0:
                return
            ix, iy = pos.x() - dx, pos.y() - dy

            if ix < 0 or iy < 0 or ix > dw or iy > dh:
                self._overlay.hide()
                return

            ts = self._original_pixmap.width() / dw
            cx, cy = ix * ts, iy * ts
            sz = int(((MagnifierOverlay.RADIUS * 2) / self._zoom) * ts)
            if sz <= 0:
                return

            rx, ry = int(cx - sz / 2), int(cy - sz / 2)
            chunk = self._original_pixmap.copy(QRect(rx, ry, sz, sz))
            padded = QPixmap(sz, sz)
            padded.setDevicePixelRatio(self._original_pixmap.devicePixelRatio())
            padded.fill(Qt.GlobalColor.transparent)
            p = QPainter(padded)
            p.drawPixmap(abs(rx) if rx < 0 else 0, abs(ry) if ry < 0 else 0, chunk)
            p.end()

            self._overlay.zoomed_pixmap = padded.scaled(
                self._overlay.width(),
                self._overlay.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            gp = self.mapToGlobal(pos)
            self._overlay.move(
                int(gp.x() - MagnifierOverlay.RADIUS),
                int(gp.y() - MagnifierOverlay.RADIUS),
            )
            if not self._overlay.isVisible():
                self._overlay.show()
            self._overlay.update()
        except Exception:
            traceback.print_exc()

    def leaveEvent(self, event):
        self._overlay.hide()
        super().leaveEvent(event)


class ThemeSidebarItemWidget(QWidget):
    def __init__(
        self,
        name: str,
        palette: ThemePalette,
        selected_background: str,
        disabled: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._disabled = disabled
        self._default_text_color = palette.disabled_text if disabled else palette.text
        self._selected_text_color = _button_tokens("secondary")["text"]
        self._selected_background = selected_background
        self._disabled_selected_background = palette.disabled_selected_background

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)
        self.card = QWidget()
        self.card.setObjectName("themeSidebarCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self.card)
        row.setContentsMargins(11, 8, 8, 8)
        row.setSpacing(6)
        outer.addWidget(self.card)

        self.name_lbl = QLabel(name)
        self.name_lbl.setFont(_ui_font(10, QFont.Weight.DemiBold))
        row.addWidget(self.name_lbl, 1)

        if disabled:
            badge = QLabel("disabled")
            badge.setFont(_ui_font(8))
            badge.setStyleSheet(
                f"color: {palette.disabled_badge_text}; background: {palette.disabled_badge_background};"
                " border-radius: 4px; padding: 1px 5px;"
            )
            row.addWidget(badge, 0)

        self.set_selected(False)

    def set_selected(self, selected: bool):
        if self._disabled:
            background = self._disabled_selected_background if selected else "transparent"
            self.card.setStyleSheet(f"QWidget#themeSidebarCard {{ background: {background}; border-radius: 4px; }}")
            self.name_lbl.setStyleSheet(f"color: {self._default_text_color}; background: transparent;")
            return
        text_color = self._selected_text_color if selected else self._default_text_color
        background = self._selected_background if selected else "transparent"
        self.card.setStyleSheet(f"QWidget#themeSidebarCard {{ background: {background}; border-radius: 4px; }}")
        self.name_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")


class ThemeDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_data: dict | None = None
        self._palette = _build_palette()
        self._net = QNetworkAccessManager(self)
        self._image_reply: QNetworkReply | None = None
        self._readme_reply: QNetworkReply | None = None
        self._image_data = b""
        self._readme_text = ""
        self._pending_requests = 0
        self._build_ui()

    def _build_ui(self) -> None:
        palette = self._palette
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        self._build_header(root, palette)

        self._stack = QWidget()
        self._stack.setStyleSheet(f"background: {palette.content_background}; border-bottom-left-radius: 12px;")
        self._stack_layout = QStackedLayout(self._stack)
        self._stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self._loading_widget = QWidget()
        self._loading_widget.setStyleSheet("background: transparent;")
        loading_layout = QVBoxLayout(self._loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(Spinner(size=32, color=palette.text, pen_width=2, parent=self._loading_widget))
        self._stack_layout.addWidget(self._loading_widget)
        self._loading_widget.hide()

        self._build_readme(self._stack_layout, palette)
        root.addWidget(self._stack, stretch=1)

        self._build_footer(root, palette)

    def _build_header(self, root: QVBoxLayout, palette: ThemePalette) -> None:
        self.header_section = QFrame()
        self.header_section.setObjectName("detailHeader")
        self.header_section.setStyleSheet(
            f"QFrame#detailHeader {{ background: {palette.content_background}; border-top-left-radius: 12px; }}"
        )
        header_layout = QVBoxLayout(self.header_section)
        header_layout.setContentsMargins(20, 16, 20, 14)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.name_label = QLabel()
        self.name_label.setFont(_ui_font(18, QFont.Weight.Bold))
        self.name_label.setWordWrap(False)
        self.name_label.setStyleSheet(f"color: {palette.text}; background: transparent;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        title_row.addWidget(self.name_label, 0)

        self.author_label = QLabel()
        self.author_label.setFont(_ui_font(8, QFont.Weight.DemiBold))
        self.author_label.setOpenExternalLinks(True)
        self.author_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.author_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.author_label.setStyleSheet(
            f"color: {README_LINK_COLOR}; background: rgba(88,166,255,0.18); border-radius: 8px;"
            " padding: 0px 4px; margin-top: 4px; min-height: 16px; max-height: 16px;"
        )
        title_row.addWidget(self.author_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.report_btn = QPushButton("Report")
        self.report_btn.setFont(_ui_font(8, QFont.Weight.DemiBold))
        self.report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.report_btn.setFlat(True)
        self.report_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.report_btn.setStyleSheet(_report_button_style())
        self.report_btn.clicked.connect(self._on_report)
        title_row.addWidget(self.report_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        title_row.addStretch()
        header_layout.addLayout(title_row)

        self.desc_label = QLabel()
        self.desc_label.setFont(_ui_font(10, QFont.Weight.DemiBold))
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(f"color: {palette.muted_text}; background: transparent;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(self.desc_label)
        self._build_info_bar(header_layout, palette)

        root.addWidget(self.header_section)

    @staticmethod
    def _info_icon(size: int = 16, color: str = "#4cc2ff", text_color: str = "#000000") -> QPixmap:
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, size - 1, size - 1)
        p.setPen(QColor(text_color))
        f = QFont("Segoe UI", int(size * 0.55), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRect(0, -1, size, size), Qt.AlignmentFlag.AlignCenter, "i")
        p.end()
        return pix

    def _build_info_bar(self, root: QVBoxLayout, palette: ThemePalette) -> None:
        self._info_bar = QFrame()
        self._info_bar.setObjectName("detailInfoBar")
        self._info_bar.setStyleSheet(
            f"QFrame#detailInfoBar {{ background: {palette.content_background}; border-radius: 6px; }}"
        )
        bar_layout = QHBoxLayout(self._info_bar)
        bar_layout.setContentsMargins(12, 9, 12, 9)
        bar_layout.setSpacing(10)

        icon_label = QLabel()
        primary_tokens = _button_tokens("primary")
        icon_label.setPixmap(self._info_icon(16, primary_tokens["bg"], primary_tokens["text"]))
        icon_label.setFixedSize(16, 16)
        icon_label.setStyleSheet("background: transparent;")
        bar_layout.addWidget(icon_label, 0)

        message_label = QLabel("This theme is temporarily disabled until the author fixes the problem.")
        message_label.setFont(_ui_font(9, QFont.Weight.DemiBold))
        message_label.setWordWrap(True)
        message_label.setStyleSheet("background: transparent;")
        bar_layout.addWidget(message_label, 1)

        self._info_bar_container = QWidget()
        self._info_bar_container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(self._info_bar_container)
        container_layout.setContentsMargins(0, 6, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._info_bar)
        root.addWidget(self._info_bar_container)
        self._info_bar_container.hide()

    def _build_readme(self, stack: QStackedLayout, palette: ThemePalette) -> None:
        self.readme_scroll = QScrollArea()
        self.readme_scroll.setWidgetResizable(True)
        self.readme_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.readme_scroll.setStyleSheet(_readme_scroll_style())

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 0, 0, 14)
        content_layout.setSpacing(10)
        self.readme_scroll.setWidget(container)

        self.image_label = MagnifierLabel()
        content_layout.addWidget(self.image_label, stretch=0)

        widget_style, document_style = _readme_browser_styles(
            palette.text,
            palette.selection_background,
            palette.code_background,
        )
        self.readme_browser = RemoteImageTextBrowser()
        self.readme_browser.setOpenLinks(True)
        self.readme_browser.setOpenExternalLinks(True)
        self.readme_browser.setFont(_ui_font(10))
        self.readme_browser.document().setDocumentMargin(32)
        self.readme_browser.content_ready.connect(self._on_readme_ready)
        self.readme_browser.setStyleSheet(widget_style)
        self.readme_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.readme_browser.document().setDefaultStyleSheet(document_style)

        content_layout.addWidget(self.readme_browser, stretch=1)
        content_layout.addStretch()
        stack.addWidget(self.readme_scroll)
        self.readme_scroll.hide()

        self._readme_smooth_scroll = SmoothScrollFilter(self.readme_scroll.verticalScrollBar(), self)
        for widget in (
            self.readme_scroll.viewport(),
            container,
            self.readme_browser,
            self.readme_browser.viewport(),
            self.image_label,
        ):
            widget.installEventFilter(self._readme_smooth_scroll)

    def _build_footer(self, root: QVBoxLayout, palette: ThemePalette) -> None:
        self.footer = QFrame()
        self.footer.setObjectName("detailFooter")
        self.footer.setStyleSheet(f"QFrame#detailFooter {{ background-color: {palette.footer_background}; }}")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(24, 10, 24, 10)
        footer_layout.setSpacing(10)

        footer_layout.addStretch()
        self.download_btn = _make_btn("Download", "secondary", 120, self._on_download)
        self.install_btn = _make_btn("Install", "primary", 120, self._on_install)
        footer_layout.addWidget(self.download_btn)
        footer_layout.addWidget(self.install_btn)
        root.addWidget(self.footer)
        self.footer.hide()

    def load_theme(self, data: dict) -> None:
        self.theme_data = data
        self._cancel_requests()
        self._image_data = b""
        self._readme_text = ""
        self._pending_requests = 0

        self._apply_theme_metadata(data)

        disabled = bool(data.get("disabled", False))
        self.install_btn.setEnabled(not disabled)
        self._info_bar_container.setVisible(disabled)
        self._reset_content_view()

        theme_id = data.get("id", "")
        image_url = data.get("image")
        readme_url = data.get("readme")
        if image_url:
            self._pending_requests += 1
            self._image_reply = self._net.get(_network_request(image_url))
            self._image_reply.finished.connect(
                lambda current_theme_id=theme_id, reply=self._image_reply: self._on_image_reply(current_theme_id, reply)
            )
        if readme_url:
            self._pending_requests += 1
            self._readme_reply = self._net.get(_network_request(readme_url))
            self._readme_reply.finished.connect(
                lambda current_theme_id=theme_id, reply=self._readme_reply: self._on_readme_reply(
                    current_theme_id, reply
                )
            )

        if self._pending_requests == 0:
            self._show_content()

    def _apply_theme_metadata(self, data: dict) -> None:
        self.name_label.setText(data.get("name", ""))
        author = html_escape(data.get("author", ""))
        homepage = data.get("homepage") or f"https://github.com/{author}"
        self.author_label.setText(
            f'by <a style="color:{README_LINK_COLOR};text-decoration:none" href="{html_escape(homepage)}">{author}</a>'
        )
        self.desc_label.setText(data.get("description", ""))

    def _reset_content_view(self) -> None:
        self.image_label.set_pixmap(QPixmap())
        self.readme_browser.clear_cache()
        self.readme_browser.clear()
        self.readme_scroll.hide()
        self._loading_widget.show()
        self.footer.show()

    def _finish_reply(
        self,
        reply_attr: str,
        theme_id: str,
        reply: QNetworkReply,
        *,
        decode: bool = False,
    ) -> bytes | str | None:
        if getattr(self, reply_attr) is reply:
            setattr(self, reply_attr, None)
        raw = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else b""
        reply.deleteLater()
        if not self.theme_data or theme_id != self.theme_data.get("id"):
            return None
        if decode:
            return raw.decode("utf-8", errors="replace")
        return raw

    def _on_image_reply(self, theme_id: str, reply: QNetworkReply | None) -> None:
        if reply is None:
            return
        data = self._finish_reply("_image_reply", theme_id, reply)
        if data is None:
            return
        self._image_data = data
        self._pending_requests -= 1
        if self._pending_requests <= 0:
            self._show_content()

    def _on_readme_reply(self, theme_id: str, reply: QNetworkReply | None) -> None:
        if reply is None:
            return
        text = self._finish_reply("_readme_reply", theme_id, reply, decode=True)
        if text is None:
            return
        self._readme_text = text
        self._pending_requests -= 1
        if self._pending_requests <= 0:
            self._show_content()

    def _show_content(self) -> None:
        if not self.theme_data:
            return
        if self._image_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(self._image_data):
                primary_screen = QApplication.primaryScreen()
                if primary_screen is not None:
                    pixmap.setDevicePixelRatio(primary_screen.devicePixelRatio())
                self.image_label.set_pixmap(pixmap)

        self.readme_scroll.setGraphicsEffect(None)
        if self._readme_text.strip():
            opacity = QGraphicsOpacityEffect(self.readme_scroll)
            opacity.setOpacity(0.0)
            self.readme_scroll.setGraphicsEffect(opacity)
        self.readme_scroll.show()

        self.readme_browser.clear_cache()
        self.readme_browser.clear()
        if self._readme_text.strip():
            self.readme_browser.setMarkdown(self._readme_text)
        else:
            self._reveal()

    def _on_readme_ready(self) -> None:
        self._reveal()

    def _reveal(self) -> None:
        self._loading_widget.hide()
        self.readme_scroll.setGraphicsEffect(None)

    def _cancel_requests(self) -> None:
        for attr in ("_image_reply", "_readme_reply"):
            reply = getattr(self, attr, None)
            if reply is not None:
                reply.abort()
                reply.deleteLater()
                setattr(self, attr, None)

    def shutdown(self) -> None:
        self._cancel_requests()
        self.readme_browser.shutdown()

    def _on_report(self) -> None:
        if not self.theme_data:
            return
        name = self.theme_data.get("name", "Unknown")
        tid = self.theme_data["id"]
        author = self.theme_data.get("author", "Unknown")
        try:
            yasbc_ver = subprocess.run(
                ["yasbc", "-v"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=3,
            ).stdout.strip()
        except Exception:
            yasbc_ver = "Unknown"
        win_ver = f"Windows {platform.release()} ({platform.version()})"
        body = (
            f"**Theme:** {name}\n"
            f"**ID:** {tid}\n"
            f"**Author:** {author}\n\n"
            f"**YASB Version:**\n"
            f"```\n{yasbc_ver}\n```\n"
            f"**Windows Version:** {win_ver}\n\n"
            f"**Describe the issue:**\n"
            f"<!-- Please describe the problem with this theme -->"
        )
        params = urlencode({"title": f"[Theme issue] {name}", "body": body, "labels": "bug"})
        QDesktopServices.openUrl(QUrl(f"https://github.com/amnweb/yasb-themes/issues/new?{params}"))

    def _on_download(self) -> None:
        if self.theme_data:
            QDesktopServices.openUrl(
                QUrl(f"https://github.com/amnweb/yasb-themes/tree/main/themes/{self.theme_data['id']}")
            )

    def _on_install(self) -> None:
        if not self.theme_data:
            return
        dialog = self._build_install_dialog(self._palette)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._do_install()

    def _build_install_dialog(self, palette: ThemePalette) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle(" ")
        if not is_windows_10():
            dialog.setWindowFlags(
                Qt.WindowType.Dialog
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.CustomizeWindowHint
                | Qt.WindowType.MSWindowsFixedSizeDialogHint
            )
        else:
            dialog.setWindowFlags(
                Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.MSWindowsFixedSizeDialogHint
            )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog_background = "#2B2B2B" if palette.dark else "#F5F5F5"
        footer_background = "#202020" if palette.dark else "#E5E5E5"
        dialog.setStyleSheet(f"QDialog {{ background: {dialog_background}; }}")
        dialog.setModal(True)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("dlgContent")
        content.setStyleSheet(f"QWidget#dlgContent {{ background: {dialog_background}; }}")
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 0, 24, 34)
        body.setSpacing(0)

        title = QLabel("Install Theme")
        title.setFont(_ui_font(14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {palette.text}; background: transparent;")
        body.addWidget(title)
        body.addSpacing(8)

        desc = QLabel(
            f"Are you sure you want to install <b>{html_escape(self.theme_data['name'])}</b>?<br>"
            "This will overwrite your current config and styles files.<br>"
            "Note: Some themes require additional fonts."
        )
        desc.setFont(_ui_font(10))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {palette.muted_text}; background: transparent;")
        body.addWidget(desc)
        root.addWidget(content)

        footer = QWidget()
        footer.setObjectName("dlgFooter")
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"QWidget#dlgFooter {{ background: {footer_background}; }}")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        fl.addStretch()
        cancel_btn = _make_btn("Cancel", "secondary", slot=dialog.reject)
        cancel_btn.setFixedSize(120, 28)
        install_btn = _make_btn("Install", "primary", slot=dialog.accept)
        install_btn.setFixedSize(120, 28)
        fl.addWidget(cancel_btn)
        fl.addWidget(install_btn)
        fl.addStretch()
        root.addWidget(footer)

        dialog.setFixedSize(400, root.minimumSize().height())
        try:
            if not is_windows_10():
                hwnd = int(dialog.winId())
                no_backdrop = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 38, ctypes.byref(no_backdrop), ctypes.sizeof(no_backdrop)
                )
                r, g, b_ch = (0x2B, 0x2B, 0x2B) if palette.dark else (0xF5, 0xF5, 0xF5)
                colorref = ctypes.c_int((b_ch << 16) | (g << 8) | r)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))
        except Exception:
            pass
        return dialog

    def _do_install(self) -> None:
        try:
            _run_yasbc("stop")
            tid = self.theme_data["id"]
            base_urls = [url.format(theme_id=tid) for url in DEFAULT_THEME_INSTALL_URLS]
            home = DEFAULT_CONFIG_DIRECTORY
            config_path, styles_path = os.path.join(home, "config.yaml"), os.path.join(home, "styles.css")
            os.makedirs(home, exist_ok=True)
            ctx = ssl.create_default_context(cafile=certifi.where())
            last_err = None
            for base in base_urls:
                try:
                    for fname, dest in [("styles.css", styles_path), ("config.yaml", config_path)]:
                        with urllib.request.urlopen(f"{base}/{fname}", context=ctx) as r:
                            with open(dest, "wb") as f:
                                f.write(r.read())
                    _run_yasbc("start")
                    return
                except Exception as exc:
                    last_err = exc
            raise last_err or RuntimeError("Failed to download theme files")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to install theme: {exc}")


class ThemeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YASB Themes")
        self.setWindowIcon(_app_icon())
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(600, min(int(screen.height() * 0.78), 1000))
        w = max(900, min(int(screen.width() * 0.78), int(h * 1.6), 1600))
        self.setGeometry((screen.width() - w) // 2 + screen.x(), (screen.height() - h) // 2 + screen.y(), w, h)
        self.setMinimumSize(900, 600)
        self._palette = _build_palette()
        self.theme_items: list[dict] = []
        self.themes: dict = {}
        self._net = QNetworkAccessManager(self)
        self._theme_reply: QNetworkReply | None = None
        self._load_error: str | None = None
        self._themes_loaded = False
        self._minimum_splash_elapsed = False
        self._theme_urls = list(DEFAULT_THEME_INDEX_URLS)
        self._init_ui()

    def _init_ui(self) -> None:
        palette = self._palette
        if is_mica_supported():
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            EnableMica(int(self.winId()), BackdropType.MICA)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_header(root, palette)
        self.splash_screen = ThemeSplashScreen()
        root.addWidget(self.splash_screen, stretch=1)
        self._build_body(root, palette)
        self._start_loading()

    def _build_header(self, root: QVBoxLayout, palette: ThemePalette) -> None:
        self.header = QFrame()
        self.header.setObjectName("headerBar")
        self.header.setFixedHeight(HEADER_HEIGHT)
        self.header.setStyleSheet(f"QFrame#headerBar {{ background-color: {palette.header_background}; }}")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 0, 24, 0)
        header_layout.setSpacing(10)

        title = QLabel("<span style='font-weight:bold'>YASB</span> Themes")
        title.setFont(_ui_font(14))
        title.setStyleSheet(f"color: {palette.text};")
        header_layout.addWidget(title)
        header_layout.addStretch()

        info = QLabel("Backup your config before installing a theme.")
        info.setFont(_ui_font(9))
        info.setStyleSheet(f"color: {palette.text};")
        info_opacity = QGraphicsOpacityEffect()
        info_opacity.setOpacity(0.75)
        info.setGraphicsEffect(info_opacity)
        header_layout.addWidget(info)

        self.backup_button = _make_btn("Backup", "secondary", slot=self._backup_config)
        header_layout.addWidget(self.backup_button)
        self.restore_button = _make_btn("Restore", "secondary", slot=self._restore_config)
        header_layout.addWidget(self.restore_button)

        root.addWidget(self.header)
        self.header.hide()

    def _build_body(self, root: QVBoxLayout, palette: ThemePalette) -> None:
        self.body_widget = QWidget()
        body_layout = QHBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(self.body_widget)
        self.body_widget.hide()
        body_layout.addWidget(self._build_sidebar(palette))
        self.detail_panel = ThemeDetailPanel()
        body_layout.addWidget(self.detail_panel, stretch=1)

    def _build_sidebar(self, palette: ThemePalette) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"QWidget#sidebar {{ background-color: {palette.sidebar_background}; }}")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 0, 16, 8)
        search_layout.setSpacing(0)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search themes...")
        self.search_box.setFont(_ui_font(10))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet(
            _search_box_style(palette.text, palette.search_background, palette.search_focus_background)
        )
        self.search_box.textChanged.connect(self._filter_sidebar)
        search_layout.addWidget(self.search_box)
        sidebar_layout.addWidget(search_container)

        self.theme_list = QListWidget()
        self.theme_list.setStyleSheet(_sidebar_list_style(palette.text, palette.scrollbar_handle))
        self.theme_list.setFrameShape(QFrame.Shape.NoFrame)
        self.theme_list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.theme_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.theme_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.theme_list.currentItemChanged.connect(self._on_theme_selected)
        sidebar_layout.addWidget(self.theme_list, stretch=1)

        accent = _button_tokens("primary")["bg"]
        self._pill = QFrame(self.theme_list.viewport())
        self._pill.setFixedSize(PILL_WIDTH, PILL_HEIGHT)
        self._pill.setStyleSheet(f"background: {accent}; border-radius: 1px;")
        self._pill.hide()
        self._pill.raise_()
        self._pill_anim = QPropertyAnimation(self._pill, b"geometry")
        self._pill_anim.setDuration(PILL_ANIMATION_MS)
        self._pill_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.theme_list.verticalScrollBar().valueChanged.connect(self._sync_pill)

        self._sidebar_smooth_scroll = SmoothScrollFilter(self.theme_list.verticalScrollBar(), self)
        self.theme_list.installEventFilter(self._sidebar_smooth_scroll)
        self.theme_list.viewport().installEventFilter(self._sidebar_smooth_scroll)

        self.count_label = QLabel()
        self.count_label.setFont(_ui_font(9))
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.count_label.setStyleSheet(f"padding: 6px 6px 6px 14px; color: {palette.count_text};")
        sidebar_layout.addWidget(self.count_label)
        return sidebar

    def _start_loading(self) -> None:
        self._request_theme_index(0)
        self._splash_timer = QTimer(self, singleShot=True)
        self._splash_timer.timeout.connect(self._on_splash_elapsed)
        self._splash_timer.start(self.splash_screen.minimum_display_ms())

    def _on_splash_elapsed(self) -> None:
        self._minimum_splash_elapsed = True
        self._check_ready()

    def _request_theme_index(self, index: int) -> None:
        if index >= len(self._theme_urls):
            self._on_load_error("Failed to load themes.")
            return
        reply = self._net.get(_network_request(self._theme_urls[index]))
        reply.finished.connect(
            lambda current_index=index, current_reply=reply: self._on_theme_reply(current_index, current_reply)
        )
        self._theme_reply = reply

    def _on_theme_reply(self, index: int, reply: QNetworkReply) -> None:
        if self._theme_reply is reply:
            self._theme_reply = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                self.themes = json.loads(bytes(reply.readAll()).decode("utf-8"))
                self._themes_loaded = True
                reply.deleteLater()
                self._check_ready()
                return
            except Exception as exc:
                err = f"Invalid theme index response: {exc}"
        else:
            err = reply.errorString()
        reply.deleteLater()
        if index + 1 < len(self._theme_urls):
            self._request_theme_index(index + 1)
        else:
            self._on_load_error(err)

    def _on_load_error(self, message: str) -> None:
        self._themes_loaded = True
        self.themes = {}
        self.theme_items = []
        self._load_error = message
        self._check_ready()

    def _check_ready(self) -> None:
        if not (self._themes_loaded and self._minimum_splash_elapsed):
            return
        if self._load_error is not None:
            self.splash_screen.show_message(f"Failed to load themes.\n{self._load_error}")
            return
        opacity = QGraphicsOpacityEffect()
        self.splash_screen.setGraphicsEffect(opacity)
        animation = QPropertyAnimation(opacity, b"opacity")
        animation.setDuration(DETAIL_FADE_MS)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(self._show_body)
        self._fade = animation
        animation.start()

    def _show_body(self) -> None:
        self.splash_screen.hide()
        self.header.show()
        self.theme_items = [{**theme, "id": theme_id} for theme_id, theme in self.themes.items()]
        self._rebuild_list(self.theme_items)
        if self.theme_list.count():
            self.theme_list.setCurrentRow(0)
        self.body_widget.show()

    def _rebuild_list(self, items: list[dict]) -> None:
        self._pill.hide()
        self.theme_list.clear()
        for theme in items:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, theme)
            item.setSizeHint(QSize(0, LIST_ITEM_HEIGHT))
            self.theme_list.addItem(item)
            self.theme_list.setItemWidget(
                item,
                ThemeSidebarItemWidget(
                    theme.get("name", ""),
                    self._palette,
                    self._palette.content_background,
                    disabled=bool(theme.get("disabled", False)),
                ),
            )
        total = len(self.theme_items)
        shown = self.theme_list.count()
        self.count_label.setText(f"{shown} of {total} themes" if shown < total else f"{total} themes")

    def _refresh_selection(self) -> None:
        current_item = self.theme_list.currentItem()
        for index in range(self.theme_list.count()):
            item = self.theme_list.item(index)
            widget = self.theme_list.itemWidget(item)
            if isinstance(widget, ThemeSidebarItemWidget):
                widget.set_selected(item is current_item)

    def _move_pill(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self._pill.hide()
            return
        rect = self.theme_list.visualItemRect(item)
        target = QRect(PILL_MARGIN, rect.y() + (rect.height() - PILL_HEIGHT) // 2, PILL_WIDTH, PILL_HEIGHT)
        if not self._pill.isVisible():
            self._pill.setGeometry(target)
            self._pill.show()
            self._pill.raise_()
            return
        self._pill_anim.stop()
        self._pill_anim.setStartValue(self._pill.geometry())
        self._pill_anim.setEndValue(target)
        self._pill_anim.start()

    def _sync_pill(self) -> None:
        current_item = self.theme_list.currentItem()
        if current_item is None or not self._pill.isVisible():
            return
        self._pill_anim.stop()
        rect = self.theme_list.visualItemRect(current_item)
        self._pill.setGeometry(
            QRect(PILL_MARGIN, rect.y() + (rect.height() - PILL_HEIGHT) // 2, PILL_WIDTH, PILL_HEIGHT)
        )

    def _filter_sidebar(self, text: str) -> None:
        query = text.strip().lower()
        items = (
            self.theme_items
            if not query
            else [
                theme
                for theme in self.theme_items
                if query in theme.get("name", "").lower() or query in theme.get("author", "").lower()
            ]
        )
        self._rebuild_list(items)
        if self.theme_list.count():
            self.theme_list.setCurrentRow(0)

    def _on_theme_selected(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        self._refresh_selection()
        self._move_pill(current)
        if current is not None and (data := current.data(Qt.ItemDataRole.UserRole)):
            self.detail_panel.load_theme(data)

    @staticmethod
    def _config_paths() -> tuple[str, str, str, str]:
        home = DEFAULT_CONFIG_DIRECTORY
        return (
            os.path.join(home, "config.yaml"),
            os.path.join(home, "styles.css"),
            os.path.join(home, "config.yaml.backup"),
            os.path.join(home, "styles.css.backup"),
        )

    def _backup_config(self):
        cfg, sty, bcfg, bsty = self._config_paths()
        try:
            if os.path.exists(cfg):
                shutil.copy2(cfg, bcfg)
            if os.path.exists(sty):
                shutil.copy2(sty, bsty)
            self.backup_button.setText("Backup complete!")
            apply_button_style(self.backup_button, "primary")
            QTimer.singleShot(
                2000,
                lambda: (
                    self.backup_button.setText("Backup"),
                    apply_button_style(self.backup_button, "secondary"),
                ),
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Backup failed: {e}")

    def _restore_config(self):
        self.restore_button.setText("Restoring\u2026")
        QApplication.processEvents()
        cfg, sty, bcfg, bsty = self._config_paths()
        try:
            if not os.path.exists(bcfg) or not os.path.exists(bsty):
                self.restore_button.setText("Restore")
                QMessageBox.warning(self, "Error", "Restore failed: backup files missing.")
                return
            _run_yasbc("stop")
            shutil.copy2(bcfg, cfg)
            shutil.copy2(bsty, sty)
            self.restore_button.setText("Restore complete!")
            _run_yasbc("start")
            QTimer.singleShot(2000, lambda: self.restore_button.setText("Restore"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Restore failed: {e}")

    def closeEvent(self, event):
        self._splash_timer.stop()
        if self._theme_reply is not None:
            self._theme_reply.abort()
            self._theme_reply.deleteLater()
            self._theme_reply = None
        self.detail_panel.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ThemeViewer()
    viewer.show()
    sys.exit(app.exec())

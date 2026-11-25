"""Markdown for MarkdownView, and the GitHub Markdown it is given."""

import re

from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
    QTextImageFormat,
    QTextLength,
    QTextListFormat,
    QTextTableFormat,
)
from PyQt6.QtQuick import QQuickTextDocument

from core.utils.shell_utils import shell_open

_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_AUTOLINK = re.compile(r"<(https?://[^>]+)>")
# A tag starts with a letter, / or ! right after its <, so "x < 5" is text
_HTML_TAG = re.compile(r"<[A-Za-z/!][^>]*>")
# Fenced and inline code, whose < and > are code
_MD_CODE = re.compile(r"^(`{3,}|~{3,}).*?(?:^\1[ \t]*$|\Z)|``.+?``|`[^`\n]+`", re.MULTILINE | re.DOTALL)

# GFM alert blocks: > [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION]
_GFM_ALERT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", re.IGNORECASE)

# GitHub changelog preprocessing
_IMG_TAG = re.compile(r"<img\s[^>]*/?>", re.IGNORECASE)
_COMMIT_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/commit/([0-9a-fA-F]{7,40})(?=[^0-9a-fA-F]|$)")
_COMPARE_URL = re.compile(r"(?<![<\[(])(https://github\.com/[^/\s]+/[^/\s]+/compare/[^\s<>()]+)")
_PULL_URL = re.compile(r"(?<![\[(])https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")
_PLAIN_HASH = re.compile(r"\b([0-9a-fA-F]{7,40})(?=\s*$)", re.MULTILINE)

# Points: 18, 18 and 16 px
_HEADING_SIZES = {1: 13.5, 2: 13.5, 3: 12}
# Each alert's icon, icon colour and box colour
_ALERTS = {
    "note": (chr(0xE946), "accent", "infoFill"),
    "important": (chr(0xE946), "accent", "infoFill"),
    "tip": (chr(0xE930), "success", "successFill"),
    "warning": (chr(0xE7BA), "caution", "cautionFill"),
    "caution": (chr(0xE783), "critical", "criticalFill"),
}
# Marks an alert's box and the paragraphs around it
_ALERT_BOX = QTextFormat.Property.UserProperty.value
_BULLETS = (QTextListFormat.Style.ListDisc, QTextListFormat.Style.ListCircle, QTextListFormat.Style.ListSquare)


def strip_images_and_html(text: str) -> str:
    """Markdown without images or HTML tags, so nothing loads from the network."""

    def strip(part: str) -> str:
        part = _MD_IMG.sub("", part)
        return _HTML_TAG.sub(lambda tag: tag[0] if _MD_AUTOLINK.fullmatch(tag[0]) else "", part)

    kept: list[str] = []
    end = 0
    for code in _MD_CODE.finditer(text):
        kept += [strip(text[end : code.start()]), code[0]]
        end = code.end()
    kept.append(strip(text[end:]))
    return "".join(kept).strip()


def convert_img_tags(text: str) -> str:
    """Convert HTML ``<img>`` tags to markdown ``![alt](url)`` syntax."""

    def _to_md(m: re.Match[str]) -> str:
        tag = m.group(0)
        src_m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag)
        if not src_m:
            return tag
        alt_m = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', tag)
        return f"![{alt_m.group(1) if alt_m else ''}]({src_m.group(1)})"

    return _IMG_TAG.sub(_to_md, text)


def strip_commit_links(changelog: str, repo_url: str = "") -> str:
    """Convert raw GitHub commit/PR/compare URLs in *changelog* to markdown links.

    If *repo_url* is given (e.g. ``https://github.com/amnweb/yasb``), bare
    commit hashes at the end of a line are also converted.
    """
    if not changelog:
        return changelog
    text = _COMMIT_URL.sub(lambda m: f"[{m.group(1)[:7]}]({m.group(0)})", changelog)
    text = _PULL_URL.sub(lambda m: f"[#{m.group(1)}]({m.group(0)})", text)
    text = _COMPARE_URL.sub(lambda m: f"<{m.group(1)}>", text)
    if repo_url:
        text = _PLAIN_HASH.sub(lambda m: f"[{m.group(1)[:7]}]({repo_url}/commit/{m.group(1)})", text)
    return text


def _alert_boxes(document: QTextDocument, colors: dict[str, QColor]) -> None:
    """Turns each GitHub alert, a quote that starts with its marker, into a box."""
    alerts: list[tuple[int, int, str]] = []
    block = document.begin()
    while block.isValid():
        marker = block.text().partition(" ")[0]
        alert = (
            _GFM_ALERT.match(marker) if block.blockFormat().intProperty(QTextFormat.Property.BlockQuoteLevel) else None
        )
        if alert is not None:
            alerts.append((block.position(), len(marker), alert[1].lower()))
        block = block.next()
    cursor = QTextCursor(document)
    # Its own change: Qt finds the new tables only once it ends
    cursor.beginEditBlock()
    for position, marker, kind in reversed(alerts):
        glyph, color, fill = _ALERTS[kind]
        end = position + document.findBlock(position).length() - 1
        cursor.setPosition(min(position + marker + 1, end))
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        message = cursor.selection()
        cursor.setPosition(position)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        # A table needs a paragraph on each side
        empty = QTextBlockFormat()
        empty.setLineHeight(0, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        empty.setProperty(_ALERT_BOX, True)
        cursor.setBlockFormat(empty)
        box = QTextTableFormat()
        box.setBorder(1)
        box.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        box.setBorderBrush(colors["stroke"])
        box.setBackground(colors[fill])
        box.setCellPadding(12)
        box.setCellSpacing(0)
        box.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        box.setProperty(_ALERT_BOX, True)
        table = cursor.insertTable(1, 1, box)
        if table is None:
            continue
        after = table.lastCursorPosition()
        after.movePosition(QTextCursor.MoveOperation.NextBlock)
        gap = QTextBlockFormat(empty)
        gap.setBottomMargin(8)
        after.setBlockFormat(gap)
        inside = table.cellAt(0, 0).firstCursorPosition()
        inside.setBlockFormat(QTextBlockFormat())
        icon = QTextCharFormat()
        icon.setFontFamilies(["Segoe Fluent Icons"])
        icon.setForeground(colors[color])
        inside.insertText(glyph + "  ", icon)
        title = QTextCharFormat()
        title.setFontWeight(QFont.Weight.DemiBold)
        inside.insertText(kind.capitalize() + "  ", title)
        inside.insertFragment(message)
    cursor.endEditBlock()


def style_document(document: QTextDocument, colors: dict[str, QColor]) -> None:
    _alert_boxes(document, colors)
    document.setIndentWidth(20)
    cursor = QTextCursor(document)
    # One change, laid out once, instead of one per format
    cursor.beginEditBlock()
    consolas = QTextCharFormat()
    consolas.setFontFamilies(["Consolas"])

    def merge(begin: int, end: int, char: QTextCharFormat) -> None:
        cursor.setPosition(begin)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(char)

    block = document.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        fence = block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence)
        quote = block.blockFormat().intProperty(QTextFormat.Property.BlockQuoteLevel)
        end = block.position() + block.length() - 1
        if quote:
            muted = QTextCharFormat()
            muted.setForeground(colors["quote"])
            merge(block.position(), end, muted)
        cursor.setPosition(block.position())
        if cursor.currentTable() is None and not block.blockFormat().boolProperty(_ALERT_BOX):
            spacing = QTextBlockFormat()
            spacing.setTopMargin(24 if level and block != document.begin() else 0)
            spacing.setBottomMargin(8)
            if quote:
                spacing.setLeftMargin(20 * quote)
            if fence:
                spacing.setNonBreakableLines(False)
            cursor.mergeBlockFormat(spacing)
        if level:
            heading = QTextCharFormat()
            if level in _HEADING_SIZES:
                heading.setFontPointSize(_HEADING_SIZES[level])
            heading.setFontWeight(QFont.Weight.DemiBold)
            merge(block.position(), end, heading)
        if fence:
            merge(block.position(), end, consolas)
        else:
            code: list[tuple[int, int]] = []
            fragments = block.begin()
            while not fragments.atEnd():
                fragment = fragments.fragment()
                if fragment.charFormat().fontFixedPitch():
                    code.append((fragment.position(), fragment.position() + fragment.length()))
                fragments += 1
            for begin, stop in code:
                merge(begin, stop, consolas)
        bullets = block.textList()
        if bullets is not None and bullets.format().style() in _BULLETS:
            # By depth, not by the character written
            listing = bullets.format()
            listing.setStyle(_BULLETS[(listing.indent() - 1) % len(_BULLETS)])
            bullets.setFormat(listing)
        block = block.next()
    root = document.rootFrame()
    for frame in root.childFrames() if root is not None else []:
        table = frame.firstCursorPosition().currentTable()
        if table is not None and not table.format().boolProperty(_ALERT_BOX):
            lines = table.format()
            lines.setBorder(1)
            lines.setBorderBrush(colors["line"])
            lines.setBorderCollapse(True)
            lines.setCellPadding(6)
            lines.setCellSpacing(0)
            table.setFormat(lines)
    cursor.endEditBlock()


def fit_images(document: QTextDocument, width: float) -> None:
    """Shrinks the loaded images wider than width to it."""
    cursor = QTextCursor(document)
    cursor.beginEditBlock()
    block = document.begin()
    while block.isValid():
        images: list[tuple[int, int, QTextImageFormat]] = []
        fragments = block.begin()
        while not fragments.atEnd():
            fragment = fragments.fragment()
            if fragment.charFormat().isImageFormat():
                images.append((fragment.position(), fragment.length(), fragment.charFormat().toImageFormat()))
            fragments += 1
        for position, length, image in images:
            loaded = document.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(image.name()))
            if not isinstance(loaded, QImage) or loaded.isNull():
                continue
            scale = min(1.0, width / loaded.width()) if width > 0 else 1.0
            size = round(loaded.width() * scale), round(loaded.height() * scale)
            if (round(image.width()), round(image.height())) == size:
                continue
            fit = QTextImageFormat()
            fit.setWidth(size[0])
            fit.setHeight(size[1])
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(fit)
        block = block.next()
    cursor.endEditBlock()


class Markdown(QObject):
    @pyqtSlot(QObject, str, "QVariantMap")
    def show(self, holder: QObject, markdown: str, colors: dict[str, QColor]) -> None:
        document = holder.textDocument() if isinstance(holder, QQuickTextDocument) else None
        if document is not None:
            document.setMarkdown(markdown)
            style_document(document, colors)

    @pyqtSlot(QObject, float)
    def fitImages(self, holder: QObject, width: float) -> None:
        document = holder.textDocument() if isinstance(holder, QQuickTextDocument) else None
        if document is not None:
            fit_images(document, width)

    @pyqtSlot(str)
    def open(self, url: str) -> None:
        # The text can come from anyone, and a file: or other link would run what it names
        if QUrl(url).scheme().lower() in ("http", "https", "mailto"):
            shell_open(url)

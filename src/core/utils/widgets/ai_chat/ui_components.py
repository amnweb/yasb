import re
from enum import StrEnum
from typing import Any

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QContextMenuEvent, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy, QTextBrowser, QTextEdit, QWidget

from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.widgets.ai_chat.constants import CODE_MONO_FONT
from core.utils.widgets.ai_chat.syntax_highlight import simple_syntax_highlight


def _escape_html(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_chat_text(text: str) -> str:
    """
    Format chat text to HTML with basic Markdown.
    """
    if not text:
        return text

    def repl(match):
        label, url = match.group(1), match.group(2)
        label_stripped = label.strip()
        if label_stripped.startswith("[") and label_stripped.endswith("]"):
            label_stripped = label_stripped[1:-1]
        if label_stripped == url or re.match(r"https?://", label_stripped):
            return url
        return f"{label_stripped} {url}"

    text = re.sub(r"\[([^\]]+)]\((https?://[^)]+)\)", repl, text)

    # Extract code blocks BEFORE escaping HTML (syntax highlighter handles its own escaping)
    code_blocks = []
    code_block_placeholder = "\x00CODE_BLOCK_{}\x00"

    def extract_code_block(match):
        lang = match.group(1) or ""
        code = match.group(2)
        highlighted_code = simple_syntax_highlight(code, lang)
        block_html = (
            f'<table width="100%" cellpadding="10" style="background-color:rgba(0,0,0,0.2);'
            f'border-radius:6px;"><tr><td>'
            f'<pre style="white-space:pre-wrap;word-wrap:break-word;margin:0;'
            f'font-family:{CODE_MONO_FONT};">{highlighted_code}</pre>'
            f"</td></tr></table>"
        )
        code_blocks.append(block_html)
        return code_block_placeholder.format(len(code_blocks) - 1)

    text = re.sub(r"```([a-zA-Z0-9]*)[ \t]*\r?\n([\s\S]*?)```", extract_code_block, text)

    # Extract inline code BEFORE escaping HTML
    inline_codes = []
    inline_code_placeholder = "\x00INLINE_CODE_{}\x00"

    def extract_inline_code(match):
        code = match.group(1)
        escaped_code = _escape_html(code)
        code_html = (
            f'<code style="background-color:rgba(0,0,0,0.2);font-family:{CODE_MONO_FONT};"> {escaped_code} </code>'
        )
        inline_codes.append(code_html)
        return inline_code_placeholder.format(len(inline_codes) - 1)

    text = re.sub(r"`([^`\n]+)`", extract_inline_code, text)

    # Now escape HTML for the rest of the text
    text = _escape_html(text)

    # Convert **bold** to <b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    # Convert *italic* to <i>, but not bullet points
    text = re.sub(r"(?:(?<=\s)|^)\*(?!\s)([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text, flags=re.MULTILINE)

    def replace_url(match):
        url = match.group(1)
        href = "http://" + url if url.startswith("www.") else url
        display_url = url.rstrip(".,;:!?)")
        href = href.rstrip(".,;:!?)")
        return f'<a href="{href}" style="color:#4A9EFF;">{display_url}</a>'

    text = re.sub(r'((?:https?://|ftp://|www\.)[^\s<>"&]+)(?=\s|$|&(?:amp|lt|gt);)', replace_url, text)

    # Convert newlines to <br> for proper display
    text = text.replace("\n", "<br>")

    # Restore code blocks and inline codes
    for i, block in enumerate(code_blocks):
        text = text.replace(code_block_placeholder.format(i), block)
    for i, code in enumerate(inline_codes):
        text = text.replace(inline_code_placeholder.format(i), code)

    return text


class ContextMenuMixin:
    """Mixin class to provide shared context menu functionality for chat widgets"""

    def _init_context_menu(self, is_input_widget=False):
        """Initialize context menu setup."""
        self._parent_widget = None
        self._is_input_widget = is_input_widget
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._handle_context_menu)

    def set_parent_widget(self, parent_widget):
        """Set the parent widget that contains the context menu handler"""
        self._parent_widget = parent_widget

    def _handle_context_menu(self, pos):
        """Handle custom context menu request"""
        if self._parent_widget and hasattr(self._parent_widget, "_context_menu"):
            self._parent_widget._context_menu.show_context_menu(self, pos, is_input=self._is_input_widget)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events to show context menu on right click"""
        if event.button() == Qt.MouseButton.RightButton:
            if self._parent_widget and hasattr(self._parent_widget, "_context_menu"):
                self._parent_widget._context_menu.show_context_menu(self, event.pos(), is_input=self._is_input_widget)
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Override context menu event to show our custom menu"""
        if self._parent_widget and hasattr(self._parent_widget, "_context_menu"):
            local_pos = self.mapFromGlobal(event.globalPos())
            self._parent_widget._context_menu.show_context_menu(self, local_pos, is_input=self._is_input_widget)
            event.accept()
        else:
            super().contextMenuEvent(event)


class AiChatPopup(PopupWidget):
    """Custom popup widget for AI chat with floating and deactivate handling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_floating = False
        self._block_deactivate = False
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

    def set_block_deactivate(self, enabled: bool):
        self._block_deactivate = enabled

    def set_floating(self, floating: bool):
        self._is_floating = floating

        if floating:
            self.setProperty("class", "ai-chat-popup floating")
        else:
            self.setProperty("class", "ai-chat-popup")

        refresh_widget_style(self, *self.findChildren(QWidget))

    def eventFilter(self, obj, event):
        if self._is_floating or self._block_deactivate:
            return False
        return super().eventFilter(obj, event)

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate:
            if self._is_floating or self._block_deactivate:
                event.accept()
                return True
            self.hide_animated()
            return True
        return super().event(event)


class ChatInputEdit(ContextMenuMixin, QTextEdit):
    """Custom text edit for chat input with enter key handling and signal for sending messages"""

    send_message = pyqtSignal()
    text_changed = pyqtSignal()
    focus_changed = pyqtSignal(bool)  # Emits True on focus in, False on focus out

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_streaming = False
        self.setProperty("class", "chat-input")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self._init_context_menu(is_input_widget=True)
        self.textChanged.connect(self.text_changed.emit)
        self.document().contentsChanged.connect(self.updateGeometry)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def set_streaming(self, value: bool):
        self._is_streaming = value

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            if not self._is_streaming:
                self.send_message.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        # Let parent handle attachments/images pasted from clipboard, fallback to text paste
        parent = getattr(self, "_parent_widget", None)
        if parent and hasattr(parent, "_attachment_manager"):
            try:
                if parent._attachment_manager.handle_paste_mime(source):
                    return
            except Exception:
                pass
        self.insertPlainText(source.text())

    def sizeHint(self):
        """Return size hint based on document content height"""
        doc = self.document()
        doc_height = int(doc.size().height())
        return QSize(super().sizeHint().width(), doc_height)

    def minimumSizeHint(self):
        """Return minimum size hint based on document content height"""
        return self.sizeHint()


class ChatMessageBrowser(ContextMenuMixin, QTextBrowser):
    """Custom text browser for chat messages"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.document().setDocumentMargin(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.setUndoRedoEnabled(False)
        self.document().setMaximumBlockCount(0)
        self.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self._init_context_menu(is_input_widget=False)
        # Connect document size changes to update geometry
        self.document().contentsChanged.connect(self.updateGeometry)

    def setText(self, text):
        """Override setText to handle formatting and store original HTML"""
        if text:
            processed_text = format_chat_text(text)
            self.setHtml(processed_text)
        else:
            self.clear()
        self.updateGeometry()

    def set_streaming_text(self, text: str):
        """Set plain text without formatting for streaming."""
        self.setPlainText(text)
        self.updateGeometry()

    def sizeHint(self):
        """Return size hint based on document content height"""
        doc = self.document()
        doc_height = int(doc.size().height()) + 2
        return QSize(super().sizeHint().width(), doc_height)

    def minimumSizeHint(self):
        """Return minimum size hint based on document content height"""
        return self.sizeHint()

    def resizeEvent(self, event):
        """Handle resize to update geometry when width changes"""
        super().resizeEvent(event)
        self.updateGeometry()

    def selectedText(self):
        """Return selected text for compatibility with QLabel API"""
        return self.textCursor().selectedText()


class Corner(StrEnum):
    """Enum for notification dot position corners."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class NotificationLabel(QLabel):
    """Draws a QLabel with a dot on any of the four corners."""

    def __init__(
        self,
        *args: Any,
        color: str = "red",
        corner: Corner = Corner.BOTTOM_LEFT,
        margin: list[int] = [1, 1],
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._show_dot = False
        self._color = color
        self._corner = corner
        self._margin = margin

    def show_dot(self, enabled: bool):
        self._show_dot = enabled
        self.update()

    def set_corner(self, corner: str | Corner):
        """Set the corner where the dot should appear."""
        self._corner = corner
        self.update()

    def set_color(self, color: str):
        """Set the color of the notification dot."""
        self._color = color
        self.update()

    def paintEvent(self, a0: QPaintEvent | None):
        super().paintEvent(a0)
        if self._show_dot:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(self._color))
            painter.setPen(Qt.PenStyle.NoPen)

            radius = 6
            margin_x = self._margin[0]
            margin_y = self._margin[1]

            # Calculate position based on the specified corner
            x = y = 0
            if self._corner == Corner.TOP_LEFT:
                x = margin_x
                y = margin_y
            elif self._corner == Corner.TOP_RIGHT:
                x = self.width() - radius - margin_x
                y = margin_y
            elif self._corner == Corner.BOTTOM_LEFT:
                x = margin_x
                y = self.height() - radius - margin_y
            elif self._corner == Corner.BOTTOM_RIGHT:
                x = self.width() - radius - margin_x
                y = self.height() - radius - margin_y

            painter.drawEllipse(QPoint(x + radius // 2, y + radius // 2), radius // 2, radius // 2)

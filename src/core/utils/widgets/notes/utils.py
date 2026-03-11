import re
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QEvent, QMimeData, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QSizePolicy, QTextEdit, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style

if TYPE_CHECKING:
    from core.widgets.yasb.notes import NotesWidget


class FloatingWindowController:
    def __init__(self, widget: NotesWidget) -> None:
        self._widget: NotesWidget = widget

    def toggle_floating(self) -> None:
        if not self._widget.is_menu_valid() or self._widget.menu is None:
            return

        if not self._widget.is_floating:
            self._widget.original_position = self._widget.menu.pos()
            self._widget.is_floating = True
            self._widget.menu.set_floating(True)
            self._widget.adjust_menu_geometry()
            screen = self._widget.get_target_screen()
            if screen:
                screen_geometry = screen.availableGeometry()
                popup_size = self._widget.menu.size()
                center_x = screen_geometry.x() + (screen_geometry.width() - popup_size.width()) // 2
                center_y = screen_geometry.y() + (screen_geometry.height() - popup_size.height()) // 2
                self._widget.menu.move(center_x, center_y)

            self._widget.float_btn.setText(self._widget.icons["float_off"])
            set_tooltip(self._widget.float_btn, "Dock window")
            self._widget.close_btn.setVisible(True)
        else:
            self._widget.is_floating = False
            self._widget.menu.set_floating(False)
            self._widget.adjust_menu_geometry()

            self._widget.float_btn.setText(self._widget.icons["float_on"])
            set_tooltip(self._widget.float_btn, "Float window")
            self._widget.close_btn.setVisible(False)

    def header_mouse_press(self, event: QMouseEvent | None) -> None:
        if not event:
            return
        if self._widget.is_floating and event.button() == Qt.MouseButton.LeftButton and self._widget.menu:
            self._widget.drag_position = event.globalPosition().toPoint() - self._widget.menu.frameGeometry().topLeft()
            event.accept()

    def header_mouse_move(self, event: QMouseEvent | None) -> None:
        if not event:
            return
        if self._widget.is_floating and self._widget.drag_position is not None and self._widget.menu:
            self._widget.menu.move(event.globalPosition().toPoint() - self._widget.drag_position)
            event.accept()

    def header_mouse_release(self, event: QMouseEvent | None) -> None:
        if not event:
            return
        if self._widget.is_floating:
            self._widget.drag_position = None
            event.accept()


class NotesPopup(PopupWidget):
    """Custom popup widget for Notes with floating and deactivate handling"""

    is_floating: bool
    _block_deactivate: bool
    _pos_args: tuple[str, str, int, int] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.is_floating = False
        self._block_deactivate = False
        self._pos_args = None
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

    def set_block_deactivate(self, enabled: bool) -> None:
        self._block_deactivate = enabled

    def set_floating(self, floating: bool) -> None:
        self.is_floating = floating

        if floating:
            self.setProperty("class", "notes-menu floating")
        else:
            self.setProperty("class", "notes-menu")

        refresh_widget_style(self, *self.findChildren(QWidget))

    def setPosition(
        self, alignment: str = "left", direction: str = "down", offset_left: int = 0, offset_top: int = 0
    ) -> None:
        # Store args for when we might stop floating or for resize events
        self._pos_args = (alignment, direction, offset_left, offset_top)

        # If floating, don't actually move the window to the docked position
        if self.is_floating:
            return

        super().setPosition(alignment, direction, offset_left, offset_top)

    def eventFilter(self, obj: Any, event: Any) -> bool:
        if self.is_floating or self._block_deactivate:
            return False
        if obj is None or event is None:
            return False
        return bool(super().eventFilter(obj, event))  # type: ignore

    def event(self, a0: Any) -> bool:
        if a0 and a0.type() == QEvent.Type.WindowDeactivate:
            if self.is_floating or self._block_deactivate:
                a0.accept()
                return True
            self.hide_animated()
            return True
        return bool(super().event(a0))  # type: ignore


class ElidedLabel(QLabel):
    """A QLabel that automatically elides its text if it doesn't fit the width."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, a0: str | None) -> None:
        self._full_text = a0 or ""
        self._update_elided_text()

    def text(self) -> str:
        return self._full_text

    def resizeEvent(self, a0: Any) -> None:
        super().resizeEvent(a0)
        self._update_elided_text()

    def minimumSizeHint(self) -> Any:
        from PyQt6.QtCore import QSize

        metrics = self.fontMetrics()
        return QSize(10, metrics.height())

    def sizeHint(self) -> Any:
        from PyQt6.QtCore import QSize

        metrics = self.fontMetrics()
        # Cap the natural size hint so the popup doesn't expand infinitely for huge titles
        return QSize(min(250, metrics.horizontalAdvance(self._full_text)), metrics.height())

    def _update_elided_text(self) -> None:
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        if elided != super().text():
            super().setText(elided)


class NoteTextEdit(QTextEdit):
    """
    Custom QTextEdit widget for note input that overrides keyPressEvent.
    Captures Enter/Return key presses to trigger note addition in the parent widget,
    while allowing multiline input using Shift+Enter.
    """

    def __init__(self, notes_widget: NotesWidget) -> None:
        super().__init__()
        self._notes_widget = notes_widget
        self._force_rich_paste: bool = False

        self.copy_btn = QPushButton(self._notes_widget.config.icons.copy_icon, self)
        self.copy_btn.setProperty("class", "input-copy-button")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        set_tooltip(self.copy_btn, "Copy to clipboard")

        self.textChanged.connect(self._update_copy_btn_position)

    def _copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.toPlainText())

    def _update_copy_btn_position(self) -> None:
        margin = 4
        btn_size = self.copy_btn.sizeHint()

        # Calculate the right offset. If the vertical scrollbar is visible,
        # we need to shift the button to the left by the scrollbar's width.
        vbar = self.verticalScrollBar()
        vbar_width = vbar.width() if vbar and vbar.isVisible() else 0

        self.copy_btn.setGeometry(
            self.width() - btn_size.width() - margin - vbar_width,
            margin,
            btn_size.width(),
            btn_size.height(),
        )

    def resizeEvent(self, a0: Any) -> None:
        super().resizeEvent(a0)
        self._update_copy_btn_position()

    def insertFromMimeData(self, source: QMimeData | None) -> None:
        if source is None:
            return

        # Check if we should enforce plain text paste
        should_paste_plain = self._notes_widget.config.paste_plain_text
        if self._force_rich_paste:
            should_paste_plain = False

        if should_paste_plain:
            self.insertPlainText(source.text())
            return

        if source.hasHtml():
            html = source.html()
            # Strip background color from inline styles
            html = re.sub(r'background-color\s*:\s*[^;">\']+;?', "", html, flags=re.IGNORECASE)
            html = re.sub(r'background\s*:\s*[^;">\']+;?', "", html, flags=re.IGNORECASE)
            # Strip bgcolor attributes
            html = re.sub(r'bgcolor\s*=\s*["\'][^"\']+["\']', "", html, flags=re.IGNORECASE)

            new_source = QMimeData()
            new_source.setHtml(html)
            if source.hasText():
                new_source.setText(source.text())
            super().insertFromMimeData(new_source)
        else:
            super().insertFromMimeData(source)

    def _get_indent_string(self) -> str:
        cursor = self.textCursor()
        block = cursor.block()
        text = block.text()
        if text.startswith("\t"):
            return "\t"
        elif text.startswith(" ") or text.startswith("\xa0"):
            return "    "

        # Check previous lines
        prev_block = block.previous()
        while prev_block.isValid():
            prev_text = prev_block.text()
            if prev_text.startswith("\t"):
                return "\t"
            elif prev_text.startswith(" ") or prev_text.startswith("\xa0"):
                return "    "
            prev_block = prev_block.previous()

        return "    "

    def _handle_tab(self) -> None:
        cursor = self.textCursor()
        indent_str = self._get_indent_string()

        if not cursor.hasSelection():
            cursor.insertText(indent_str)
            return

        doc = self.document()
        if not doc:
            return

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        cursor.beginEditBlock()

        start_block_obj = doc.findBlock(start_pos)
        end_block_obj = doc.findBlock(end_pos)

        if start_pos != end_pos and end_pos == end_block_obj.position():
            end_block_obj = end_block_obj.previous()

        cur_block = start_block_obj
        while cur_block.isValid() and cur_block.blockNumber() <= end_block_obj.blockNumber():
            block_cursor = QTextCursor(cur_block)
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.insertText(indent_str)
            cur_block = cur_block.next()

        cursor.endEditBlock()

    def _handle_backtab(self) -> None:
        cursor = self.textCursor()
        doc = self.document()

        if not doc:
            return

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        if not cursor.hasSelection():
            start_pos = cursor.position()
            end_pos = cursor.position()

        cursor.beginEditBlock()

        start_block_obj = doc.findBlock(start_pos)
        end_block_obj = doc.findBlock(end_pos)

        if start_pos != end_pos and end_pos == end_block_obj.position():
            end_block_obj = end_block_obj.previous()

        cur_block = start_block_obj
        while cur_block.isValid() and cur_block.blockNumber() <= end_block_obj.blockNumber():
            block_cursor = QTextCursor(cur_block)
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            text = block_cursor.selectedText()

            if text.startswith("\t"):
                block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                block_cursor.removeSelectedText()
            else:
                spaces_to_remove = 0
                for i in range(min(4, len(text))):
                    if text[i] == " " or text[i] == "\xa0":
                        spaces_to_remove += 1
                    else:
                        break
                if spaces_to_remove > 0:
                    block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    block_cursor.movePosition(
                        QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, spaces_to_remove
                    )
                    block_cursor.removeSelectedText()

            cur_block = cur_block.next()

        cursor.endEditBlock()

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is None:
            return

        if (
            e.key() == Qt.Key.Key_V
            and (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
            and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            if self._notes_widget.config.paste_plain_text:
                # Force rich text
                self._force_rich_paste = True
                self.paste()
                self._force_rich_paste = False
            else:
                # Force plain text
                clipboard = QApplication.clipboard()
                if clipboard:
                    self.setCurrentCharFormat(QTextCharFormat())
                    self.insertPlainText(clipboard.text())
            e.accept()
            return

        # Normal Paste (Ctrl+V)
        if e.key() == Qt.Key.Key_V and (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            # insertFromMimeData will handle the logic based on config
            super().keyPressEvent(e)
            return

        if e.key() == Qt.Key.Key_Tab:
            self._handle_tab()
            e.accept()
            return

        if e.key() == Qt.Key.Key_Backtab:
            self._handle_backtab()
            e.accept()
            return

        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._notes_widget.config.enter_to_add_note != bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._notes_widget.add_note_from_input()
                e.accept()
                return

        super().keyPressEvent(e)

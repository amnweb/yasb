from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QMenu

from core.utils.win32.utilities import apply_qmenu_style


class ContextMenuService:
    def __init__(self, owner):
        self._owner = owner

    def show_context_menu(self, widget, pos, is_input=False):
        context_menu = QMenu(widget)
        context_menu.setProperty("class", "context-menu")

        if is_input:
            text_edit = widget

            select_all_action = context_menu.addAction("Select All")
            select_all_action.triggered.connect(lambda: text_edit.selectAll())
            select_all_action.setEnabled(bool(text_edit.toPlainText()))

            selected_text = text_edit.textCursor().selectedText()
            if selected_text:
                copy_action = context_menu.addAction("Copy")
                copy_action.triggered.connect(lambda: QApplication.clipboard().setText(selected_text))

                cut_action = context_menu.addAction("Cut")
                cut_action.triggered.connect(
                    lambda: (
                        QApplication.clipboard().setText(selected_text),
                        text_edit.textCursor().removeSelectedText(),
                    )
                )

            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text:
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: text_edit.insertPlainText(clipboard_text))

            if text_edit.toPlainText():
                context_menu.addSeparator()
                clear_action = context_menu.addAction("Clear")
                clear_action.triggered.connect(lambda: text_edit.clear())

        else:
            label = widget
            selected_text = label.selectedText()

            if selected_text:
                copy_selected_action = context_menu.addAction("Copy")

                def copy_selected():
                    try:
                        self.simulate_shortcut(label, Qt.Key.Key_C)
                    except Exception:
                        QApplication.clipboard().setText(selected_text)

                copy_selected_action.triggered.connect(copy_selected)

            select_all_action = context_menu.addAction("Select All")

            def select_all():
                try:
                    self.simulate_shortcut(label, Qt.Key.Key_A)
                except Exception:
                    pass

            select_all_action.triggered.connect(select_all)
        apply_qmenu_style(context_menu)

        global_pos = widget.mapToGlobal(pos)
        if is_input:
            menu_height = context_menu.sizeHint().height()
            global_pos.setY(global_pos.y() - menu_height)

        if is_input:
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            try:
                context_menu.exec(global_pos)
            finally:
                QApplication.restoreOverrideCursor()
        else:
            context_menu.exec(global_pos)

    def simulate_shortcut(self, widget, key):
        press_event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.ControlModifier)
        release_event = QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.ControlModifier)
        QApplication.sendEvent(widget, press_event)
        QApplication.sendEvent(widget, release_event)

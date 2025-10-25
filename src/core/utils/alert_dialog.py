import os
import sys
import traceback

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QPushButton, QSizePolicy, QTextEdit

from core.ui.style import apply_button_style
from settings import SCRIPT_PATH


class AlertDialog(QMessageBox):
    def __init__(
        self,
        title: str,
        message: str,
        informative_message: str = None,
        additional_details: str = None,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
        show_quit: bool = False,
        show_ok: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowCloseButtonHint)
        self.setIcon(icon)
        self.setText(message)
        self.icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        if informative_message:
            self.setInformativeText(informative_message)

        if additional_details:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setDetailedText(additional_details)

        self.ok_button = self.addButton("Ok", QMessageBox.ButtonRole.AcceptRole) if show_ok else None
        self.quit_button = self.addButton("Quit", QMessageBox.ButtonRole.DestructiveRole) if show_quit else None
        self.setSizeGripEnabled(False)

        self.setMinimumHeight(0)
        self.setMaximumHeight(260)
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.adjustSize()

    def showEvent(self, event):
        self._style_dialog_buttons()
        text_edit = self.findChild(QTextEdit)
        if text_edit:
            text_edit.setStyleSheet("background-color: rgba(0,0,0,0.2); border: none;")
            text_edit.setMinimumHeight(60)
            text_edit.setMaximumHeight(150)
            text_edit.setMinimumWidth(420)
            text_edit.setMaximumWidth(520)
            text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        super().showEvent(event)

    def event(self, e):
        result = QMessageBox.event(self, e)
        self.setMinimumHeight(0)
        self.setMaximumHeight(260)
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        text_edit = self.findChild(QTextEdit)
        if text_edit:
            text_edit.setMinimumHeight(60)
            text_edit.setMaximumHeight(150)
            text_edit.setMinimumWidth(420)
            text_edit.setMaximumWidth(520)
            text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        return result

    def _style_dialog_buttons(self):
        for button in self.findChildren(QPushButton):
            apply_button_style(button, "secondary")


_persistent_dialogs = []


def _remove_dialog(dialog):
    try:
        _persistent_dialogs.remove(dialog)
    except ValueError:
        pass


def raise_info_alert(
    title: str,
    msg: str,
    informative_msg: str,
    additional_details: str = None,
    rich_text: bool = False,
    exit_on_close: bool = False,
    parent=None,
):
    alert = AlertDialog(
        icon=QMessageBox.Icon.Information,
        title=title,
        message=msg,
        informative_message=informative_msg,
        additional_details=additional_details,
        parent=parent,
    )
    if rich_text:
        alert.setTextFormat(Qt.TextFormat.RichText)

    alert.finished.connect(lambda _: _remove_dialog(alert))
    if exit_on_close:
        alert.finished.connect(lambda _: sys.exit())

    _persistent_dialogs.append(alert)
    QTimer.singleShot(100, alert.show)


def raise_error_alert(
    title: str,
    msg: str,
    informative_msg: str,
    additional_details: str = None,
    rich_text: bool = False,
    exit_on_close: bool = True,
    parent=None,
):
    alert = AlertDialog(
        icon=QMessageBox.Icon.Critical,
        title=title,
        message=msg,
        informative_message=informative_msg,
        additional_details=additional_details if additional_details else traceback.format_exc(),
        show_quit=True,
        parent=parent,
    )
    if rich_text:
        alert.setTextFormat(Qt.TextFormat.RichText)

    alert.finished.connect(lambda _: _remove_dialog(alert))
    if exit_on_close:
        alert.finished.connect(lambda _: sys.exit())

    _persistent_dialogs.append(alert)
    QTimer.singleShot(100, alert.show)

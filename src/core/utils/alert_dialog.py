import sys
import traceback
from settings import APP_NAME
from PyQt6.QtWidgets import QMessageBox, QTextEdit, QSizePolicy
from PyQt6.QtCore import Qt


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
    ):
        super().__init__()
        self.setWindowTitle(title)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.setIcon(icon)
        self.setText(message)

        if informative_message:
            self.setInformativeText(informative_message)

        if additional_details:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setDetailedText(additional_details)

        self.setFixedSize(500, 500)
        self.setStyleSheet('QTextEdit QLabel {min-height: 300px;}')
        self.ok_button = self.addButton('Ok', QMessageBox.ButtonRole.AcceptRole) if show_ok else None
        self.quit_button = self.addButton('Quit', QMessageBox.ButtonRole.DestructiveRole) if show_quit else None
        self.setSizeGripEnabled(True)

    def event(self, e):
        result = QMessageBox.event(self, e)

        self.setMinimumHeight(0)
        self.setMaximumHeight(800)
        self.setMinimumWidth(0)
        self.setMaximumWidth(800)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        text_edit = self.findChild(QTextEdit)

        if text_edit:
            text_edit.setMinimumHeight(0)
            text_edit.setMaximumHeight(800)
            text_edit.setMinimumWidth(0)
            text_edit.setMaximumWidth(800)
            text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        return result

    def show(self) -> None:
        self.exec()

        if self.clickedButton() == self.quit_button:
            sys.exit()


def raise_error_alert(
        title: str,
        msg: str,
        informative_msg: str,
        additional_details: str = None,
        rich_text: bool = False,
        exit_on_close: bool = True
):
    alert = AlertDialog(
        icon=QMessageBox.Icon.Critical,
        title=f"{APP_NAME}: {title}",
        message=msg,
        informative_message=informative_msg,
        additional_details=additional_details if additional_details else traceback.format_exc(),
        show_quit=True
    )

    if rich_text:
        alert.setTextFormat(Qt.TextFormat.RichText)

    alert.show()

    if exit_on_close:
        sys.exit()


def raise_info_alert(
        title: str,
        msg: str,
        informative_msg: str,
        additional_details: str = None,
        rich_text: bool = False,
        exit_on_close: bool = False
):
    alert = AlertDialog(
        icon=QMessageBox.Icon.Information,
        title=f"{APP_NAME}: {title}",
        message=msg,
        informative_message=informative_msg,
        additional_details=additional_details
    )

    if rich_text:
        alert.setTextFormat(Qt.TextFormat.RichText)

    alert.show()

    if exit_on_close:
        sys.exit()

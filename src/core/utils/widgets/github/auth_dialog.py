import os
import threading
from typing import Callable

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from winmica import BackdropType, EnableMica, is_mica_supported

from core.ui.style import apply_button_style
from core.utils.widgets.github import auth as github_auth
from settings import SCRIPT_PATH


class GitHubAuthDialog(QDialog):
    auth_completed = pyqtSignal(str)
    _device_code_received = pyqtSignal(dict)
    _device_error = pyqtSignal(str)
    _auth_success = pyqtSignal(str)
    _auth_error = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        name: str = "notifications",
        save_fn: Callable[[str], None] | None = None,
    ):
        super().__init__(parent)
        self._name = name
        self._save_fn = save_fn
        self._stop = False
        self._user_code: str = ""

        self._primary_buttons: list[QPushButton] = []
        self._secondary_buttons: list[QPushButton] = []

        self._build_window()
        self._build_ui()
        self._apply_palette()

        self._device_code_received.connect(self._on_device_code_received)
        self._device_error.connect(self._on_device_error)
        self._auth_success.connect(self._finish_success)
        self._auth_error.connect(self._finish_error)

        QTimer.singleShot(100, self._start_device_flow)

    def _build_window(self) -> None:
        self.setWindowTitle("GitHub Authorization - YASB")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(420, 260)

        if is_mica_supported():
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            hwnd = int(self.winId())
            EnableMica(hwnd, BackdropType.MICA)

        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(6)

        # Title
        self._title_label = QLabel("Sign in to GitHub")
        title_font = self._title_label.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        layout.addWidget(self._title_label)

        # Instructions
        self._instructions = QLabel("Requesting authorization code...")
        self._instructions.setWordWrap(True)
        self._instructions_effect = QGraphicsOpacityEffect()
        self._instructions_effect.setOpacity(0.7)
        self._instructions.setGraphicsEffect(self._instructions_effect)
        layout.addWidget(self._instructions)

        # Code display frame
        self._code_frame = QFrame()
        self._code_frame.setFixedHeight(56)
        code_layout = QHBoxLayout(self._code_frame)
        code_layout.setContentsMargins(16, 0, 8, 0)
        code_layout.setSpacing(8)

        self._code_label = QLabel("\u2013" * 10)
        code_font = QFont()
        code_font.setStyleHint(QFont.StyleHint.Monospace)
        code_font.setPointSize(16)
        code_font.setBold(True)
        code_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        self._code_label.setFont(code_font)
        self._code_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        code_layout.addWidget(self._code_label, 1)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setFixedSize(80, 30)
        self._copy_btn.setEnabled(False)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_code)
        self._secondary_buttons.append(self._copy_btn)
        code_layout.addWidget(self._copy_btn)

        layout.addSpacing(4)
        layout.addWidget(self._code_frame)

        # Status
        self._status_label = QLabel("Connecting to GitHub...")
        self._status_effect = QGraphicsOpacityEffect()
        self._status_effect.setOpacity(0.5)
        self._status_label.setGraphicsEffect(self._status_effect)
        status_font = self._status_label.font()
        status_font.setPointSize(status_font.pointSize() - 1)
        self._status_label.setFont(status_font)
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Separator
        self._separator = QFrame()
        self._separator.setFixedHeight(1)
        layout.addWidget(self._separator)
        layout.addSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._open_btn = QPushButton("Open Browser")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._open_browser)
        self._primary_buttons.append(self._open_btn)
        btn_row.addWidget(self._open_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        self._secondary_buttons.append(cancel_btn)
        self._cancel_btn = cancel_btn
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _apply_palette(self) -> None:
        palette = self.palette()
        text_color = palette.color(QPalette.ColorRole.WindowText)

        for btn in self._primary_buttons:
            apply_button_style(btn, "primary")
        for btn in self._secondary_buttons:
            apply_button_style(btn, "secondary")

        # Code frame
        border = QColor(text_color)
        border.setAlphaF(0.12)
        bg = QColor(text_color)
        bg.setAlphaF(0.04)
        self._code_frame.setStyleSheet(
            f"QFrame {{ border-radius: 6px; border: 1px solid {border.name(QColor.NameFormat.HexArgb)};"
            f" background-color: {bg.name(QColor.NameFormat.HexArgb)}; }}"
        )
        self._code_label.setStyleSheet("background: transparent; border: none;")

        sep_color = QColor(text_color)
        sep_color.setAlphaF(0.08)
        self._separator.setStyleSheet(f"background-color: {sep_color.name(QColor.NameFormat.HexArgb)};")

    def _start_device_flow(self):
        def _request():
            try:
                data = github_auth.request_device_code(self._name)
                if "error" in data:
                    msg = data.get("error_description", data["error"])
                    self._device_error.emit(msg)
                else:
                    self._device_code_received.emit(data)
            except Exception as exc:
                self._device_error.emit(str(exc))

        threading.Thread(target=_request, daemon=True).start()

    def _on_device_code_received(self, data: dict):
        self._user_code = data.get("user_code", "")
        device_code = data.get("device_code", "")
        interval = int(data.get("interval", 5))

        self._code_label.setText(self._user_code)
        self._copy_btn.setEnabled(True)
        self._apply_palette()
        self._status_label.setText("Waiting for authorization...")
        self._instructions.setText("Your browser has been opened. Enter the code below at github.com/login/device:")

        QDesktopServices.openUrl(QUrl("https://github.com/login/device"))

        threading.Thread(
            target=github_auth.poll_for_token,
            args=(device_code, interval, self._auth_success.emit, self._auth_error.emit, lambda: self._stop),
            kwargs={"save_fn": self._save_fn, "name": self._name},
            daemon=True,
        ).start()

    def _on_device_error(self, message: str):
        self._show_result_page(message)

    def _show_result_page(self, message: str):
        self._title_label.hide()
        self._instructions.hide()
        self._code_frame.hide()
        self._status_label.hide()
        self._separator.hide()
        self._open_btn.hide()

        self._result_label = QLabel(message)
        self._result_label.setWordWrap(True)
        font = self._result_label.font()
        font.setPointSize(font.pointSize() + 4)
        self._result_label.setFont(font)
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().insertWidget(0, self._result_label, 1)
        self._cancel_btn.setText("Close")

    def _finish_success(self, token: str):
        self._show_result_page("Authorization successful!")
        self.auth_completed.emit(token)
        QTimer.singleShot(1800, self.accept)

    def _finish_error(self, message: str):
        self._show_result_page(message)

    def _copy_code(self):
        if self._user_code:
            QApplication.clipboard().setText(self._user_code)
            self._copy_btn.setText("Copied")
            QTimer.singleShot(1000, lambda: self._copy_btn.setText("Copy"))

    def _open_browser(self):
        QDesktopServices.openUrl(QUrl("https://github.com/login/device"))

    def showEvent(self, event) -> None:
        self._apply_palette()
        super().showEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_palette()
        return super().event(event)

    def closeEvent(self, event):
        self._stop = True
        super().closeEvent(event)

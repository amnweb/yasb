"""Auth dialog for the Google Calendar widget.

Mirrors the shape of `services/github/auth_dialog.py` but drives Google's
installed-app flow (browser + localhost redirect) instead of device flow.
"""

from __future__ import annotations

import os
import subprocess
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
)

from core.ui.components.button import Button
from core.ui.components.loader import Spinner
from core.ui.components.text_block import TextBlock
from core.ui.views.view_base import ViewBase
from core.utils.system import app_data_path
from core.widgets.services.google_calendar import auth as gcal_auth


class GoogleCalendarAuthDialog(ViewBase, QDialog):
    auth_completed = pyqtSignal()
    _auth_success = pyqtSignal()
    _auth_error = pyqtSignal(str)

    # state ∈ {"missing", "ready", "running", "done"}
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False
        self._state = "missing"
        self._flow_thread: threading.Thread | None = None

        self._build_window()
        self._build_ui()

        self._auth_success.connect(self._finish_success)
        self._auth_error.connect(self._finish_error)

        QTimer.singleShot(0, self._render_initial_state)

    def _build_window(self) -> None:
        self.setWindowTitle("Google Calendar Authorization - YASB")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(440, 240)
        self.build_view()
        self.build_app_icon()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(8)

        self._title_label = TextBlock("Sign in to Google Calendar", variant="subtitle", parent=self)
        layout.addWidget(self._title_label)

        self._instructions = TextBlock("", variant="caption", parent=self)
        self._instructions.setWordWrap(True)
        layout.addWidget(self._instructions)

        spinner_row = QHBoxLayout()
        spinner_row.setContentsMargins(0, 4, 0, 0)
        self._spinner = Spinner(size=24, parent=self)
        self._spinner.hide()
        spinner_row.addWidget(self._spinner)
        spinner_row.addStretch()
        layout.addLayout(spinner_row)

        layout.addStretch()

        self._separator = QFrame()
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet("background-color: rgba(255,255,255,0.08);")
        layout.addWidget(self._separator)
        layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._secondary_btn = Button("Open Folder", font_size=12, font_weight="demibold", parent=self)
        self._secondary_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(self._secondary_btn)

        self._primary_btn = Button("Sign In", variant="accent", font_size=12, font_weight="demibold", parent=self)
        self._primary_btn.clicked.connect(self._on_primary_clicked)
        btn_row.addWidget(self._primary_btn)

        self._cancel_btn = Button("Cancel", font_size=12, font_weight="demibold", parent=self)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)

    def _render_initial_state(self) -> None:
        if not gcal_auth.credentials_path().exists():
            self._render_missing()
        else:
            self._render_ready()

    def _render_missing(self) -> None:
        self._state = "missing"
        self._instructions.setText(
            "OAuth client secrets file not found. Place your credentials JSON "
            f"from Google Cloud Console at:\n{gcal_auth.credentials_path()}"
        )
        self._spinner.hide()
        self._primary_btn.setText("Recheck")
        self._primary_btn.setEnabled(True)
        self._secondary_btn.show()

    def _render_ready(self) -> None:
        self._state = "ready"
        self._instructions.setText(
            "Your browser will open. Sign in to your Google account and authorise YASB. "
            "This window will close automatically when complete."
        )
        self._spinner.hide()
        self._primary_btn.setText("Sign In")
        self._primary_btn.setEnabled(True)
        self._secondary_btn.hide()

    def _render_running(self) -> None:
        self._state = "running"
        self._instructions.setText("Waiting for sign-in in your browser…")
        self._spinner.show()
        self._primary_btn.setEnabled(False)
        self._secondary_btn.hide()

    def _on_primary_clicked(self) -> None:
        if self._state == "missing":
            self._render_initial_state()
        elif self._state == "ready":
            self._start_flow()

    def _open_folder(self) -> None:
        folder = app_data_path()
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]  # Windows-only
        except Exception:
            subprocess.Popen(["explorer", str(folder)])

    def _start_flow(self) -> None:
        self._render_running()

        def _run() -> None:
            try:
                gcal_auth.run_install_flow()
                if not self._stop:
                    self._auth_success.emit()
            except Exception as exc:
                if not self._stop:
                    self._auth_error.emit(str(exc))

        self._flow_thread = threading.Thread(target=_run, daemon=True)
        self._flow_thread.start()

    def _finish_success(self) -> None:
        self._state = "done"
        self._show_result_page("Signed in successfully.")
        self.auth_completed.emit()
        QTimer.singleShot(1200, self.accept)

    def _finish_error(self, message: str) -> None:
        self._state = "done"
        self._show_result_page(f"Sign-in failed:\n{message}")

    def _show_result_page(self, message: str) -> None:
        self._title_label.hide()
        self._instructions.setText(message)
        self._spinner.hide()
        self._primary_btn.hide()
        self._secondary_btn.hide()
        self._cancel_btn.setText("Close")

    def closeEvent(self, event):
        self._stop = True
        super().closeEvent(event)

"""Update dialog for checking, downloading, and installing application updates."""

import json
import logging
import os
import re
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import certifi
from PyQt6.QtCore import QEvent, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)
from winmica import BackdropType, EnableMica, is_mica_supported

from core.ui.style import apply_button_style
from core.utils.controller import exit_application
from core.utils.utilities import is_process_running, is_valid_qobject
from settings import APP_NAME, SCRIPT_PATH

GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/amnweb/yasb/releases/latest"
USER_AGENT_HEADER = {"User-Agent": f"{APP_NAME} Updater"}

_COMMIT_URL_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/commit/([0-9a-fA-F]{7,40})(?=[^0-9a-fA-F]|$)")
_COMPARE_URL_PATTERN = re.compile(r"(?<![<\[(])(https://github\.com/[^/\s]+/[^/\s]+/compare/[^\s<>()]+)")
_PULL_URL_PATTERN = re.compile(r"(?<![\[(])https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")

_DOWNLOAD_READY_TEXT = "Download and Install"
_DOWNLOADING_TEXT = "Downloading..."

_CLOSE_BUTTON_TEXT = "Close"
_CANCEL_BUTTON_TEXT = "Cancel"


def _strip_commit_links(changelog: str) -> str:
    if not changelog:
        return changelog
    transformed = _COMMIT_URL_PATTERN.sub(lambda match: f"[[link]]({match.group(0)})", changelog)
    transformed = _PULL_URL_PATTERN.sub(
        lambda match: f"[#{match.group(1)}]({match.group(0)})",
        transformed,
    )
    return _COMPARE_URL_PATTERN.sub(lambda match: f"<{match.group(1)}>", transformed)


@dataclass(slots=True)
class ReleaseInfo:
    version: str
    changelog: str
    download_url: str
    asset_name: str
    asset_size: Optional[int]


def _normalize_version_segments(version: str) -> list[int]:
    """Return a list of numeric segments found within the version string."""
    segments = [int(part) for part in re.findall(r"\d+", version)]
    if not segments:
        return [0]
    return segments


def is_newer_version(latest: str, current: str) -> bool:
    latest_segments = _normalize_version_segments(latest)
    current_segments = _normalize_version_segments(current)
    max_length = max(len(latest_segments), len(current_segments))
    latest_segments.extend([0] * (max_length - len(latest_segments)))
    current_segments.extend([0] * (max_length - len(current_segments)))
    return latest_segments > current_segments


class ReleaseFetcher(QThread):
    update_available = pyqtSignal(object)
    up_to_date = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self._current_version = current_version

    def run(self):
        try:
            request = urllib.request.Request(GITHUB_LATEST_RELEASE_URL, headers=USER_AGENT_HEADER)
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(request, context=context, timeout=15) as response:
                data = response.read()
            release_info = json.loads(data)
            latest_version = release_info.get("tag_name", "").lstrip("vV")
            if not latest_version:
                raise ValueError("Latest release tag is missing.")

            if not is_newer_version(latest_version, self._current_version):
                self.up_to_date.emit(f"You already have the latest version ({self._current_version}).")
                return

            assets = release_info.get("assets", [])
            msi_asset = next((asset for asset in assets if asset.get("name", "").lower().endswith(".msi")), None)
            if not msi_asset:
                raise ValueError("Latest release does not include a Windows installer (MSI).")

            info = ReleaseInfo(
                version=latest_version,
                changelog=release_info.get("body", ""),
                download_url=msi_asset.get("browser_download_url"),
                asset_name=msi_asset.get("name", f"yasb-{latest_version}.msi"),
                asset_size=msi_asset.get("size"),
            )
            self.update_available.emit(info)
        except urllib.error.HTTPError as http_error:
            logging.error("GitHub responded with HTTP error during update check: %s", http_error)
            self.error.emit("GitHub returned an error while checking for updates.")
        except urllib.error.URLError as url_error:
            logging.warning("Network error during update check: %s", url_error)
            self.error.emit("Couldn't reach GitHub. Check your internet connection and try again.")
        except Exception as exc:
            logging.error("Unexpected error while checking for updates")
            self.error.emit(str(exc))


class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, download_url: str, output_path: Path, expected_size: Optional[int] = None, parent=None):
        super().__init__(parent)
        self._download_url = download_url
        self._output_path = output_path
        self._expected_size = expected_size

    def run(self):
        try:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(self._download_url, headers=USER_AGENT_HEADER)
            bytes_read = 0
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(request, context=context, timeout=30) as response:
                total_size = self._expected_size or response.headers.get("Content-Length")
                if isinstance(total_size, str) and total_size.isdigit():
                    total_size = int(total_size)
                elif not isinstance(total_size, int):
                    total_size = None
                if total_size is None:
                    self.progress.emit(-1)
                chunk_size = 8192
                with open(self._output_path, "wb") as file_handle:
                    while True:
                        if self.isInterruptionRequested():
                            raise InterruptedError("Download cancelled")
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file_handle.write(chunk)
                        bytes_read += len(chunk)
                        if total_size:
                            percent = int(bytes_read * 100 / total_size)
                            self.progress.emit(min(percent, 100))
            if bytes_read == 0:
                raise IOError("No data received from server.")
            if total_size and bytes_read < total_size:
                raise IOError("Download incomplete; connection lost.")
            self.progress.emit(100)
            self.finished.emit(self._output_path)
        except InterruptedError:
            if self._output_path.exists():
                try:
                    self._output_path.unlink()
                except Exception:
                    pass
            self.error.emit("Download cancelled.")
        except urllib.error.URLError as url_error:
            logging.warning("Network error while downloading update: %s", url_error)
            if self._output_path.exists():
                try:
                    self._output_path.unlink()
                except Exception:
                    pass
            self.error.emit("Couldn't reach GitHub. Check your internet connection and try again.")
        except Exception as exc:
            if isinstance(exc, IOError):
                logging.warning("Download did not finish: %s", exc)
            else:
                logging.error("Failed to download update from %s", self._download_url)
            if self._output_path.exists():
                try:
                    self._output_path.unlink()
                except Exception:
                    pass
            self.error.emit(str(exc))


class UpdateDialog(QDialog):
    def __init__(
        self,
        parent=None,
        on_install_started: Optional[Callable[[], None]] = None,
        release_info: Optional[ReleaseInfo] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(800, 600)
        if is_mica_supported():
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            hwnd = int(self.winId())
            EnableMica(hwnd, BackdropType.MICA)
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._on_install_started = on_install_started
        self._download_worker: Optional[DownloadWorker] = None
        self._available_release: Optional[ReleaseInfo] = None
        self._cancel_requested = False

        self._build_ui()
        self._apply_button_styles()
        if release_info is not None:
            QTimer.singleShot(0, lambda: self.set_release_info(release_info))
        self.open()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.changelog_view = QTextBrowser(self)
        self.changelog_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        changelog_font = self.changelog_view.font()
        changelog_font.setPointSize(max(changelog_font.pointSize(), 10))
        self.changelog_view.setFont(changelog_font)
        self.changelog_view.setStyleSheet("QTextBrowser { background-color: rgba(0,0,0,0); border: none; }")
        self.changelog_view.document().setDefaultStyleSheet(
            """
            body, p, li {
                font-size: 10pt;
            }
            ul, ol {
                margin-left: 0px;
                padding-left: 0px;
            }
            li {
                margin-left: 0px;
                padding-left: 0px;
            }
            li > p {
                margin-left: 0px;
                padding-left: 0px;
            }
            """
        )
        self.changelog_view.document().setIndentWidth(20)
        self.changelog_view.setOpenExternalLinks(True)
        self.changelog_view.setMinimumHeight(260)
        self.changelog_view.setContentsMargins(6, 6, 6, 6)
        self.changelog_view.clear()
        layout.addWidget(self.changelog_view)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("", self)
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("color: #a0d8ff; font-size: 11px;")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        button_row.addWidget(self.status_label)
        button_row.addStretch(1)

        self.download_button = QPushButton(_DOWNLOAD_READY_TEXT, self)
        self.download_button.setVisible(True)
        self.download_button.setEnabled(False)
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.clicked.connect(self._start_download)
        button_row.addWidget(self.download_button)

        self.close_button = QPushButton(_CLOSE_BUTTON_TEXT, self)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self._on_close_button_clicked)
        button_row.addWidget(self.close_button)

        layout.addLayout(button_row)

    def _apply_button_styles(self) -> None:
        if not hasattr(self, "download_button") or not hasattr(self, "close_button"):
            return
        apply_button_style(self.download_button, "primary")
        apply_button_style(self.close_button, "secondary")

    def _set_status(self, text: str = "", *, error: bool = False) -> None:
        if text:
            self.status_label.setStyleSheet("font-size: 11px;")
            self.status_label.setText(text)
            self.status_label.setVisible(True)
        else:
            self.status_label.clear()
            self.status_label.setVisible(False)

    def _set_idle_state(self, *, enabled: bool, status: str = "", error: bool = False) -> None:
        self.download_button.setEnabled(enabled)
        self.download_button.setText(_DOWNLOAD_READY_TEXT)
        self.download_button.setDefault(enabled)
        self.download_button.setVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_close_button_state(is_cancel=False)
        self.close_button.setEnabled(True)
        self._set_status(status, error=error)
        self._cancel_requested = False

    def set_release_info(self, release_info: ReleaseInfo) -> None:
        self._available_release = release_info
        self.setWindowTitle(f"Update Available - {release_info.version}")
        # self.changelog_label.setText(f"Latest changes - {release_info.version}")
        changelog = release_info.changelog.strip() or "_No changelog provided._"
        self.changelog_view.setMarkdown(_strip_commit_links(changelog))
        self._apply_heading_spacing()
        self._set_idle_state(enabled=True)
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def _start_download(self) -> None:
        if not self._available_release:
            return
        updates_directory = Path(tempfile.gettempdir()) / "yasb-updates"
        output_path = updates_directory / self._available_release.asset_name

        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass

        self._cancel_requested = False
        self.download_button.setEnabled(False)
        self.download_button.setText(_DOWNLOADING_TEXT)
        self.download_button.setDefault(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_status("Downloading update...")
        self._set_close_button_state(is_cancel=True)
        self.close_button.setEnabled(True)

        self._download_worker = DownloadWorker(
            self._available_release.download_url,
            output_path,
            expected_size=self._available_release.asset_size,
            parent=self,
        )
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.finished.connect(self._download_worker.deleteLater)
        self._download_worker.start()

    def _on_close_button_clicked(self) -> None:
        worker = self._active_download_worker()
        if worker:
            self.close_button.setEnabled(False)
            self._set_status("Cancelling download.")
            self._cancel_active_download()
            self.close_button.setEnabled(True)
            return
        self.close()

    def _on_download_progress(self, value: int) -> None:
        self.progress_bar.setVisible(True)
        if value < 0:
            self.progress_bar.setRange(0, 0)
        else:
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(max(value, 0), 100))

    def _on_download_finished(self, path: Path) -> None:
        self._download_worker = None
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        expected_size = self._available_release.asset_size if self._available_release else None
        try:
            actual_size = path.stat().st_size
        except FileNotFoundError:
            actual_size = 0
        if actual_size <= 0 or (expected_size and actual_size < expected_size):
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
            self._set_idle_state(
                enabled=self._available_release is not None,
                status="Download failed: installer file is incomplete. Please try again.",
                error=True,
            )
            return
        self.download_button.setText("Launching installer...")
        self.download_button.setEnabled(False)
        self._set_close_button_state(is_cancel=False)
        self._set_status("Download complete. Launching installer...")
        self._cancel_requested = False
        QTimer.singleShot(0, lambda: self._launch_installer(path))

    def _launch_installer(self, path: Path) -> None:
        if self._on_install_started:
            self._on_install_started()
        self.close()

        install_command = f'msiexec /i "{os.path.abspath(path)}" /passive /norestart'
        run_after_command = "yasbc start"
        combined_command = f"{install_command} && {run_after_command}"
        subprocess.Popen(combined_command, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        exit_application("Exiting Application to start installer...")
        for proc in ["yasb.exe", "yasbc.exe", "yasb_themes.exe"]:
            if is_process_running(proc):
                subprocess.run(["taskkill", "/f", "/im", proc], creationflags=subprocess.CREATE_NO_WINDOW)

    def _on_download_error(self, message: str) -> None:
        self._download_worker = None
        self.close_button.setEnabled(True)
        normalized_message = (message or "").strip().lower()
        was_cancelled = self._cancel_requested or normalized_message == "download cancelled."
        details = message.splitlines()[0] if message else "Unknown error"
        status_message = "Download cancelled." if was_cancelled else f"Download failed: {details}"
        self._set_idle_state(
            enabled=self._available_release is not None,
            status=status_message,
            error=not was_cancelled,
        )
        self._cancel_requested = False

    def _cancel_active_download(self, wait_timeout: int = 5000) -> None:
        worker = self._active_download_worker()
        if not worker:
            return

        self._cancel_requested = True
        try:
            worker.requestInterruption()
            worker.wait(wait_timeout)
        except RuntimeError:
            pass

    def _active_download_worker(self) -> Optional[DownloadWorker]:
        worker = self._download_worker
        if not is_valid_qobject(worker):
            return None
        return worker

    def closeEvent(self, event) -> None:
        self._cancel_active_download()
        super().closeEvent(event)

    def _set_close_button_state(self, *, is_cancel: bool) -> None:
        self.close_button.setText(_CANCEL_BUTTON_TEXT if is_cancel else _CLOSE_BUTTON_TEXT)

    def showEvent(self, event) -> None:
        self._apply_button_styles()
        super().showEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_button_styles()
            self.changelog_view.style().unpolish(self.changelog_view)
            self.changelog_view.style().polish(self.changelog_view)
        return super().event(event)

    def present(self) -> None:
        if not self.isVisible():
            self.open()
        self.raise_()
        self.activateWindow()

    def _apply_heading_spacing(self) -> None:
        document = self.changelog_view.document()
        cursor = QTextCursor(document)
        block = document.begin()
        while block.isValid():
            fmt = block.blockFormat()
            if fmt.headingLevel() > 0:
                fmt.setTopMargin(18)
                fmt.setBottomMargin(12)
                cursor.setPosition(block.position())
                cursor.setBlockFormat(fmt)
            block = block.next()

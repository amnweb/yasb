import logging
import os
import ssl
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import certifi
from PyQt6.QtCore import QObject, pyqtBoundSignal, pyqtSignal, pyqtSlot
from PyQt6.QtQml import QQmlEngine

from core.app.controller import exit_application
from core.app.update.service import ReleaseInfo, get_update_service
from core.app.windows.qml_window import show_window
from core.utils.markdown import convert_img_tags, strip_commit_links
from core.utils.process import is_process_running
from core.utils.qml import qml_property
from settings import APP_NAME, GITHUB_URL

USER_AGENT_HEADER = {"User-Agent": f"{APP_NAME} Updater"}


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def download_installer(
    url: str, path: Path, expected_size: int | None, cancelled: threading.Event, progress: Callable[[int], None]
) -> None:
    """Downloads to path, reporting percent done or -1 when the size is unknown, and removes it on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = urllib.request.Request(url, headers=USER_AGENT_HEADER)
        with urllib.request.urlopen(request, context=_ssl_context(), timeout=30) as response, open(path, "wb") as file:
            length = response.headers.get("Content-Length")
            total = expected_size or (int(length) if length and length.isdigit() else None)
            if total is None:
                progress(-1)
            received, percent = 0, -1
            while chunk := response.read(65536):
                if cancelled.is_set():
                    raise InterruptedError("Download cancelled")
                file.write(chunk)
                received += len(chunk)
                if total and received * 100 // total != percent:
                    percent = min(received * 100 // total, 100)
                    progress(percent)
        if received == 0:
            raise OSError("No data received from server.")
        if total and received < total:
            raise OSError("Download incomplete, connection lost.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def launch_installer(path: Path) -> None:
    install = f'msiexec /i "{os.path.abspath(path)}" /passive /norestart'
    subprocess.Popen(f"{install} && yasbc start", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    exit_application("Exiting Application to start installer...")
    for process in ["yasb.exe", "yasbc.exe"]:
        if is_process_running(process):
            subprocess.run(["taskkill", "/f", "/im", process], creationflags=subprocess.CREATE_NO_WINDOW)


class Updater(QObject):
    changelogChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    _prepared = pyqtSignal(str)
    _progressed = pyqtSignal(int)
    _downloaded = pyqtSignal(str, str)

    def __init__(self, release: ReleaseInfo, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._release = release
        self._changelog = ""
        self._loading = False
        self._state = "ready"
        self._progress = 0
        self._status = ""
        self._cancelled = threading.Event()
        self._prepared.connect(self._show_changelog)
        self._progressed.connect(self._show_progress)
        self._downloaded.connect(self._install)

    @qml_property(str, constant=True)
    def heading(self) -> str:
        release = self._release
        if get_update_service().current_channel == "preview":
            version = f"New Preview Build ({release.version.removeprefix('preview-')})"
        else:
            version = f"Version {release.version}"
        return f"{version} - {release.architecture}" if release.architecture else version

    # Markdown, with its HTML images as Markdown ones and its commit, pull request and compare links shortened;
    # empty until loadChangelog has prepared it
    @qml_property(str, notify=changelogChanged)
    def changelog(self) -> str:
        return self._changelog

    @pyqtSlot()
    def loadChangelog(self) -> None:
        if self._loading:
            return
        self._loading = True
        changelog = self._release.changelog

        def prepare() -> None:
            text = changelog.strip() or "_No changelog provided._"
            try:
                text = strip_commit_links(convert_img_tags(text), repo_url=GITHUB_URL)
            except Exception:
                logging.exception("Could not prepare the changelog, so it shows as written")
            try:
                self._prepared.emit(text)
            except RuntimeError:
                # The window was closed first
                pass

        threading.Thread(target=prepare, daemon=True, name="Changelog").start()

    def _show_changelog(self, changelog: str) -> None:
        self._changelog = changelog
        self.changelogChanged.emit()

    # ready, downloading or installing
    @qml_property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    # Percent done, -1 while the size is unknown
    @qml_property(int, notify=stateChanged)
    def progress(self) -> int:
        return self._progress

    @qml_property(str, notify=stateChanged)
    def status(self) -> str:
        return self._status

    def _set(self, state: str, status: str, progress: int = 0) -> None:
        self._state, self._status, self._progress = state, status, progress
        self.stateChanged.emit()

    @pyqtSlot()
    def download(self) -> None:
        if self._state != "ready":
            return
        self._cancelled = threading.Event()
        cancelled = self._cancelled
        release = self._release
        path = Path(tempfile.gettempdir()) / "yasb-updates" / release.asset_name
        self._set("downloading", "Downloading update...")

        def send(signal: pyqtBoundSignal, *args: object) -> None:
            try:
                signal.emit(*args)
            except RuntimeError:
                # The window was closed during the download
                pass

        def run() -> None:
            error = ""
            try:
                download_installer(
                    release.download_url,
                    path,
                    release.asset_size,
                    cancelled,
                    lambda percent: send(self._progressed, percent),
                )
            except InterruptedError:
                error = "Download cancelled."
            except urllib.error.URLError as e:
                logging.warning("Network error while downloading update: %s", e)
                error = "Download failed: Couldn't reach GitHub. Check your internet connection and try again."
            except Exception as e:
                logging.warning("Download did not finish: %s", e)
                error = f"Download failed: {str(e).splitlines()[0] if str(e) else type(e).__name__}"
            send(self._downloaded, str(path), error)

        threading.Thread(target=run, daemon=True, name="UpdateDownload").start()

    @pyqtSlot()
    def cancel(self) -> None:
        if self._state == "downloading":
            self._cancelled.set()
            self._set("downloading", "Cancelling download.", self._progress)

    def _show_progress(self, percent: int) -> None:
        if self._state == "downloading" and not self._cancelled.is_set():
            self._set("downloading", self._status, percent)

    def _install(self, path: str, error: str) -> None:
        if error:
            self._set("ready", error)
            return
        self._set("installing", "Download complete. Launching installer...", 100)
        launch_installer(Path(path))


def show_update(engine: QQmlEngine, release: ReleaseInfo) -> None:
    show_window(engine, "UpdateWindow", {"updater": Updater(release)})

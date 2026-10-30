import threading

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtQml import QQmlEngine

from core.utils.qml import qml_property
from core.utils.qml_window import show_window
from core.utils.shell_utils import shell_open
from core.utils.system import get_architecture
from core.utils.update_service import ReleaseInfo, get_update_service
from settings import (
    BUILD_VERSION,
    DEFAULT_CONFIG_DIRECTORY,
    GITHUB_URL,
    RELEASE_CHANNEL,
    SCRIPT_PATH,
    WEBSITE_DOCS_URL,
    WEBSITE_URL,
)


def release_notes_url() -> str:
    if RELEASE_CHANNEL.startswith("pr-"):
        number = RELEASE_CHANNEL.split("-", 1)[1].split("-", 1)[0]
        return f"{GITHUB_URL}/pull/{number}" if number.isdigit() else GITHUB_URL
    if RELEASE_CHANNEL.startswith("preview-"):
        return f"{GITHUB_URL}/releases/tag/preview"
    return f"{GITHUB_URL}/releases/tag/v{BUILD_VERSION}"


class About(QObject):
    stateChanged = pyqtSignal()
    updateRequested = pyqtSignal(object)
    _checked = pyqtSignal(object, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._release: ReleaseInfo | None = None
        self._state = "idle" if get_update_service().is_update_supported() else "unsupported"
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(lambda: self._set_state("idle"))
        self._checked.connect(self._receive)

    def show(self, engine: QQmlEngine) -> None:
        show_window(engine, "AboutWindow", {"about": self})

    @qml_property(str, constant=True)
    def version(self) -> str:
        architecture = get_architecture()
        return f"Version {BUILD_VERSION}{f' {architecture}' if architecture else ''} ({RELEASE_CHANNEL})"

    @qml_property(str, constant=True)
    def releaseUrl(self) -> str:
        return release_notes_url()

    @qml_property(str, constant=True)
    def releaseLabel(self) -> str:
        return "PR details" if RELEASE_CHANNEL.startswith("pr-") else "Release notes"

    @qml_property(str, constant=True)
    def githubUrl(self) -> str:
        return GITHUB_URL

    @qml_property(str, constant=True)
    def siteUrl(self) -> str:
        return WEBSITE_URL

    @qml_property(str, constant=True)
    def docSiteUrl(self) -> str:
        return WEBSITE_DOCS_URL

    @qml_property(str, constant=True)
    def iconUrl(self) -> str:
        return QUrl.fromLocalFile(f"{SCRIPT_PATH}/assets/images/app_icon.png").toString()

    @qml_property(str, constant=True)
    def unsupportedReason(self) -> str:
        if RELEASE_CHANNEL.startswith("pr-"):
            return "Automatic updates are disabled for PR builds."
        return "Install YASB to enable automatic updates."

    # idle, checking, available, latest, failed or unsupported
    @qml_property(str, notify=stateChanged)
    def updateState(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        self._state = state
        self.stateChanged.emit()

    @pyqtSlot(str)
    def open(self, url: str) -> None:
        shell_open(url)

    @pyqtSlot()
    def openConfig(self) -> None:
        shell_open(DEFAULT_CONFIG_DIRECTORY)

    @pyqtSlot()
    def checkForUpdates(self) -> None:
        if self._state == "available" and self._release is not None:
            self.updateRequested.emit(self._release)
            return
        if self._state in ("checking", "unsupported"):
            return
        self._reset_timer.stop()
        self._set_state("checking")

        def check() -> None:
            release, failed = None, False
            try:
                release = get_update_service().check_for_updates(timeout=15)
            except Exception:
                # check_for_updates logs why
                failed = True
            self._checked.emit(release, failed)

        threading.Thread(target=check, daemon=True, name="AboutUpdateCheck").start()

    def _receive(self, release: ReleaseInfo | None, failed: bool) -> None:
        self._release = release
        if failed:
            self._set_state("failed")
            self._reset_timer.start(3200)
        elif release is None:
            self._set_state("latest")
            self._reset_timer.start(2400)
        else:
            self._set_state("available")

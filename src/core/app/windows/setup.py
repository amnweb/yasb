"""The welcome window, shown when config.yaml is missing or from 2.x."""

import logging
from functools import cache
from typing import Any

from pydantic import ValidationError
from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtQml import QQmlEngine, qmlRegisterUncreatableType

from core.app.controller import exit_application, reload_application
from core.app.update.service import get_update_service
from core.app.windows.qml_window import show_window
from core.cloud.constants import BASE_URL as CLOUD_URL
from core.config import ConfigError
from core.qml_types import QML_URI, QML_VERSION
from core.setup import (
    ICON_FONT_URL,
    THEME_NAME,
    SetupChoices,
    SetupReason,
    build_config,
    config_folder,
    icon_font_installed,
    write_setup,
)
from core.utils.qml import qml_property
from core.utils.shell_utils import shell_open
from core.utils.validation_errors import format_pydantic_errors_to_yaml
from core.utils.win32.autostart import AUTOSTART_FILE, disable_autostart, enable_autostart
from core.utils.win32.composition import host_backdrop_supported
from core.widget_files import builtin_manifests
from settings import APP_ICON, APP_NAME, WEBSITE_DOCS_URL


@cache
def register_setup_type() -> None:
    """Registers Setup for QML, apart from the other types so a normal start never loads it."""
    major, minor = QML_VERSION
    qmlRegisterUncreatableType(Setup, QML_URI, major, minor, "Setup is created by YASB", "Setup")


class Setup(QObject):
    """The welcome window's backend. Finish writes the config and emits finished; closing before that exits YASB."""

    finished = pyqtSignal()

    def __init__(self, reason: SetupReason, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._reason = reason
        self._icon_font_missing = not icon_font_installed()
        self._done = False

    def show(self, engine: QQmlEngine) -> bool:
        """Opens the window; False if it could not."""
        register_setup_type()
        window = show_window(engine, "SetupWindow", {"setup": self}, module="Setup")
        if window is None:
            return False
        window.setIcon(QIcon(APP_ICON))
        window.visibleChanged.connect(self._window_shown)
        logging.info("Showing the setup (%s config)", self._reason)
        return True

    def _window_shown(self, visible: bool) -> None:
        if not visible and not self._done:
            exit_application("Exiting Application, the setup was closed before it finished...")

    @qml_property(bool, constant=True)
    def upgrade(self) -> bool:
        return self._reason == "upgrade"

    @qml_property(str, constant=True)
    def configFolder(self) -> str:
        return str(config_folder())

    @qml_property(bool, constant=True)
    def iconFontMissing(self) -> bool:
        return self._icon_font_missing

    @qml_property(bool, constant=True)
    def backdropSupported(self) -> bool:
        return host_backdrop_supported()

    @qml_property(bool, constant=True)
    def canAutostart(self) -> bool:
        return AUTOSTART_FILE is not None

    @qml_property(bool, constant=True)
    def canCheckForUpdates(self) -> bool:
        return get_update_service().is_update_supported()

    @qml_property(str, constant=True)
    def iconUrl(self) -> str:
        return QUrl.fromLocalFile(APP_ICON).toString()

    @qml_property(str, constant=True)
    def docsUrl(self) -> str:
        return WEBSITE_DOCS_URL

    @qml_property(str, constant=True)
    def cloudUrl(self) -> str:
        return CLOUD_URL

    @qml_property(str, constant=True)
    def iconFontUrl(self) -> str:
        return ICON_FONT_URL

    @qml_property(str, constant=True)
    def themeName(self) -> str:
        return THEME_NAME

    @qml_property("QVariantMap", constant=True)
    def manifests(self) -> dict[str, Any]:
        return builtin_manifests()

    @pyqtSlot("QVariantMap", result="QString")
    def finish(self, choices: dict[str, Any]) -> str:
        """Writes the setup's files; returns the error, or "" once done."""
        if self._done:
            return ""
        try:
            picked = SetupChoices.model_validate(choices)
            write_setup(build_config(picked), picked)
        except ValidationError as e:
            logging.error("The setup got choices it cannot use:\n%s", format_pydantic_errors_to_yaml(e))
            return "The choices could not be used. The log has the details."
        except ConfigError as e:
            logging.error("%s\n%s", e, e.details)
            return f"{e} The log has the details."
        except OSError as e:
            logging.error("The setup could not write the config: %s", e)
            return f"The config could not be saved: {e.strerror or e}"
        # Off also removes an entry an earlier install made
        if AUTOSTART_FILE is not None:
            if picked.autostart:
                enable_autostart(APP_NAME, AUTOSTART_FILE)
            else:
                disable_autostart(APP_NAME)
        self._done = True
        self.finished.emit()
        return ""

    @pyqtSlot(str)
    def open(self, url: str) -> None:
        shell_open(url)

    @pyqtSlot()
    def restart(self) -> None:
        self._done = True
        reload_application("Restarting YASB to look for the icon font again...")

    @pyqtSlot()
    def quit(self) -> None:
        self._done = True
        exit_application("Exiting Application from the setup...")

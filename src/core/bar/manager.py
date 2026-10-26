import logging
import os
from contextlib import suppress
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QScreen
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core import widget_files
from core.bar.hotkeys import WidgetHotkeys
from core.bar.revisions import Revisions, path_key
from core.bar.window import BAR_QML, BarWindow, is_dark_scheme
from core.config import get_config
from core.qml_types import register_qml_types
from core.utils.controller import reload_application
from core.utils.global_state import GlobalState
from core.utils.icons.image_provider import ICON_PROVIDER, IconImageProvider
from core.validation.config import YasbConfig
from settings import SCRIPT_PATH

QML_IMPORT_PATH = os.path.join(SCRIPT_PATH, "core", "qml")
QML_RELOAD_DELAY_MS = 200


class BarManager(QObject):
    config_modified = pyqtSignal()
    qml_changed = pyqtSignal(str)

    def __init__(self, config: YasbConfig):
        super().__init__()
        self.config = config
        self.bars: list[BarWindow] = []
        self.revisions = Revisions()
        register_qml_types()
        self.engine = QQmlEngine(self)
        self.engine.addImportPath(QML_IMPORT_PATH)
        self.engine.addImageProvider(ICON_PROVIDER, IconImageProvider())
        self.hotkeys = WidgetHotkeys(self)

        self._changed_qml: set[str] = set()
        self._qml_timer = QTimer(self)
        self._qml_timer.setSingleShot(True)
        self._qml_timer.setInterval(QML_RELOAD_DELAY_MS)
        self._qml_timer.timeout.connect(self._reload_changed_qml)
        self.qml_changed.connect(self._on_qml_changed)

        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            raise RuntimeError("BarManager requires a running QGuiApplication")
        self._app = app
        self._app.aboutToQuit.connect(self.close_bars)
        self._app.screenAdded.connect(self.on_screens_update)
        self._app.screenRemoved.connect(self.on_screens_update)
        self.config_modified.connect(self.on_config_modified)

        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)
        GlobalState.set_dark(is_dark_scheme())

    def _disconnect_reload_signals(self) -> None:
        with suppress(TypeError):
            self._app.screenAdded.disconnect(self.on_screens_update)
            self._app.screenRemoved.disconnect(self.on_screens_update)
            self.config_modified.disconnect(self.on_config_modified)

    @pyqtSlot()
    def on_config_modified(self) -> None:
        try:
            config = get_config(show_error_dialog=True)
        except Exception as e:
            logging.error("Error loading config: %s", e)
            return
        if config is None or config == self.config:
            return
        unchanged = config.model_dump(exclude={"watch"}) == self.config.model_dump(exclude={"watch"})
        self.config = config
        if unchanged:
            logging.info("Configuration updated (no reload required).")
            return
        self._disconnect_reload_signals()
        reload_application("Reloading Application because of config change.")

    @pyqtSlot(QScreen)
    def on_screens_update(self, _screen: QScreen) -> None:
        logging.info("Screens updated. Re-initialising all bars.")
        self._disconnect_reload_signals()
        reload_application("Reloading Application because of screen update.")

    @pyqtSlot(str)
    def _on_qml_changed(self, path: str) -> None:
        self._changed_qml.add(path)
        self._qml_timer.start()

    def _compile_errors(self, path: Path) -> list[str]:
        component = QQmlComponent(self.engine, self.revisions.next_url(path))
        return [error.toString() for error in component.errors()] if component.isError() else []

    def _reload_changed_qml(self) -> None:
        paths = [Path(path) for path in self._changed_qml]
        self._changed_qml.clear()
        changed: set[str] = set()
        for path in paths:
            if not path.is_file():
                self.revisions.bump(path)
            elif errors := self._compile_errors(path):
                logging.error("%s has errors, bars keep the current version:\n%s", path, "\n".join(errors))
                continue
            else:
                self.revisions.accept(path)
            changed.add(path_key(path))
        reloaded = False
        for bar in self.bars:
            if bar.uses(changed) or bar.widget_files_changed():
                bar.reload_qml()
                reloaded = True
        if reloaded:
            self.hotkeys.restart(self.bars)

    def qml_folders(self) -> set[Path]:
        return {bar.bar_file.parent for bar in self.bars if bar.bar_file != BAR_QML}

    def _on_color_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        dark = scheme == Qt.ColorScheme.Dark
        GlobalState.set_dark(dark)
        for bar in self.bars:
            bar.apply_backdrop(dark)

    def _find_screen(self, name: str) -> QScreen | None:
        primary = QGuiApplication.primaryScreen()
        wanted = primary.name() if name == "primary" and primary is not None else name
        screen = next((screen for screen in QGuiApplication.screens() if screen.name() == wanted), None)
        if screen is None:
            logging.warning("Screen '%s' from config not found among connected screens.", wanted)
        return screen

    def initialize_bars(self) -> None:
        bars = {name: bar for name, bar in self.config.bars.items() if bar.enabled}
        screens = QGuiApplication.screens()
        explicit = {
            name: [screen for screen_name in bar.screens if (screen := self._find_screen(screen_name)) is not None]
            for name, bar in bars.items()
            if bar.screens not in (["*"], ["**"])
        }
        assigned = {screen.name() for targets in explicit.values() for screen in targets}

        for name, bar in bars.items():
            if bar.screens == ["*"]:
                targets = [screen for screen in screens if screen.name() not in assigned]
            elif bar.screens == ["**"]:
                targets = screens
            else:
                targets = explicit[name]
            for screen in targets:
                self.bars.append(BarWindow(self.engine, name, screen, bar, self.revisions))

        widget_files.report_undefined_widgets(self.config)
        self.hotkeys.restart(self.bars)

    def close_bars(self) -> None:
        self.hotkeys.stop()
        for bar in self.bars:
            bar.close()
        self.bars.clear()

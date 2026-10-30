import logging
from contextlib import suppress
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QScreen
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core import widget_files
from core.bar.hotkeys import WidgetHotkeys
from core.bar.revisions import Revisions, path_key
from core.bar.window import BAR_QML, BarWindow
from core.config import get_config
from core.utils.alert_dialog import show_alert
from core.utils.controller import reload_application
from core.validation.config import YasbConfig

QML_RELOAD_DELAY_MS = 200


class BarManager(QObject):
    config_modified = pyqtSignal()
    qml_changed = pyqtSignal(str)

    def __init__(self, config: YasbConfig, engine: QQmlEngine):
        super().__init__()
        self.config = config
        self.bars: list[BarWindow] = []
        self.revisions = Revisions()
        self.engine = engine
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
        self._app.aboutToQuit.connect(self.shutdown)
        self._app.screenAdded.connect(self.on_screens_update)
        self._app.screenRemoved.connect(self.on_screens_update)
        self.config_modified.connect(self.on_config_modified)

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

    def _compile_errors(self, url: QUrl) -> list[str]:
        component = QQmlComponent(self.engine, url)
        return [error.toString() for error in component.errors()] if component.isError() else []

    def _reload_changed_qml(self) -> None:
        paths = [Path(path) for path in self._changed_qml]
        self._changed_qml.clear()
        changed: set[str] = set()
        failed: list[str] = []
        for path in paths:
            if not path.is_file():
                self.revisions.bump(path)
            elif errors := self._compile_errors(self.revisions.next_url(path)):
                logging.error("%s has errors, bars keep the current version: %s", path, "; ".join(errors))
                failed.extend(errors)
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
        if failed:
            show_alert(
                title="A QML file has errors",
                message="The bars keep the version they show now. Fix the file and save it again.",
                details="\n".join(failed),
            )

    def _report_widget_errors(self) -> None:
        paths = {
            file.path
            for bar in self.bars
            for files in widget_files.bar_widget_files(bar.config).values()
            for file in files
        }
        errors = [error for path in sorted(paths) for error in self._compile_errors(self.revisions.url(path))]
        if errors:
            details = "\n".join(errors)
            logging.error("Some widgets have errors and were left out of the bars:\n%s", details)
            show_alert(
                title="Some widgets could not load",
                message="Their QML files have errors, so the bars show them without these widgets.",
                details=details,
            )

    def qml_folders(self) -> set[Path]:
        return {bar.bar_file.parent for bar in self.bars if bar.bar_file != BAR_QML}

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
        self._report_widget_errors()
        self.hotkeys.restart(self.bars)

    @pyqtSlot()
    def shutdown(self) -> None:
        self._qml_timer.stop()
        self.close_bars()

    def close_bars(self) -> None:
        self.hotkeys.stop()
        for bar in self.bars:
            bar.close()
        self.bars.clear()
        # The bars' QML items must be deleted while their engine still exists
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

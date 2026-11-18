"""Start's apps, read once for every widget that shows apps and read again whenever apps change."""

import logging
from typing import ClassVar

from PyQt6.QtCore import QCoreApplication, QObject, QThread, pyqtSignal

from core.services.apps.reader import ControlPanelItem, Shortcut, StartApp, read_start_apps
from core.services.apps.watcher import AppChanges


class _Reader(QThread):
    read = pyqtSignal(object)

    def run(self) -> None:
        self.read.emit(read_start_apps())


class StartApps(QObject):
    """What Start lists, as last read: apps (All apps, A to Z), shortcuts (the Start menus' shortcut files) and
    control_panel (its items). Each widget picks what it shows; changed comes after a read that found a change."""

    changed = pyqtSignal()

    _instance: ClassVar[StartApps | None] = None

    @classmethod
    def instance(cls) -> StartApps:
        """The one StartApps, read on first use and stopped as YASB quits."""
        if cls._instance is None:
            cls._instance = cls()
            app = QCoreApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(cls._instance.stop)
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self.apps: list[StartApp] = []
        self.shortcuts: list[Shortcut] = []
        self.control_panel: list[ControlPanelItem] = []
        self.loaded = False
        self._reader: _Reader | None = None
        self._read_again = False
        self._changes = AppChanges(self)
        self._changes.changed.connect(self._on_apps_changed)
        self._read()

    def stop(self) -> None:
        self._changes.stop()
        if self._reader is not None:
            self._reader.wait()

    def _on_apps_changed(self) -> None:
        logging.info("Apps were installed, removed or updated, rebuild.")
        self._read()

    def _read(self) -> None:
        if self._reader is not None:
            self._read_again = True
            return
        reader = _Reader()
        reader.read.connect(self._store)
        reader.finished.connect(self._finished)
        self._reader = reader
        reader.start()

    def _store(self, read: tuple[list[StartApp], list[Shortcut], list[ControlPanelItem]]) -> None:
        if self.loaded and read == (self.apps, self.shortcuts, self.control_panel):
            return
        self.apps, self.shortcuts, self.control_panel = read
        self.loaded = True
        self.changed.emit()

    def _finished(self) -> None:
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.deleteLater()
        if self._read_again:
            self._read_again = False
            self._read()

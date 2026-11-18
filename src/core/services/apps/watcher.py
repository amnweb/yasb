"""Says when apps were installed, removed or updated."""

import logging
import os
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QFileSystemWatcher, QObject, QThread, QTimer, pyqtSignal
from winrt.windows.applicationmodel import PackageCatalog

# Where installers put the shortcuts of desktop apps: the user's own and every user's
START_MENU_FOLDERS = (
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs",
    r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs",
)
# An install changes many files; changed waits this long after the last one
SETTLE_MS = 5000


class _FolderCollector(QThread):
    """Lists the Start menu folders and every folder inside them."""

    collected = pyqtSignal(list)

    def run(self) -> None:
        folders: list[str] = []
        for folder in START_MENU_FOLDERS:
            root = os.path.expandvars(folder)
            if os.path.isdir(root):
                folders.append(root)
                for parent, children, _ in os.walk(root):
                    folders.extend(os.path.join(parent, child) for child in children)
        self.collected.emit(folders)


class AppChanges(QObject):
    """Emits changed after a shortcut is added or removed in a Start menu folder, or a Store package of this user
    finishes installing, uninstalling or updating."""

    changed = pyqtSignal()
    # Package events come on a Windows thread; this signal brings them to this object's thread
    _package_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_folder_changed)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._settled)
        self._package_changed.connect(self._settle.start)
        self._collector: _FolderCollector | None = None
        self._collect_again = False
        self._collect()
        self._catalog: Any = None
        self._handlers: list[tuple[Callable[[Any], None], Any]] = []
        try:
            catalog = PackageCatalog.open_for_current_user()
            self._handlers = [
                (catalog.remove_package_installing, catalog.add_package_installing(self._on_package)),
                (catalog.remove_package_uninstalling, catalog.add_package_uninstalling(self._on_package)),
                (catalog.remove_package_updating, catalog.add_package_updating(self._on_package)),
            ]
            self._catalog = catalog
        except Exception as e:
            logging.warning("Could not watch for app package changes: %s", e)

    def stop(self) -> None:
        self._settle.stop()
        for remove, token in self._handlers:
            try:
                remove(token)
            except Exception as e:
                logging.debug("Could not stop watching app packages: %s", e)
        self._handlers.clear()
        self._catalog = None
        if self._collector is not None:
            self._collector.wait()

    def _on_package(self, _catalog: Any, args: Any) -> None:
        if args.is_complete:
            self._package_changed.emit()

    def _on_folder_changed(self, _folder: str) -> None:
        self._settle.start()

    def _settled(self) -> None:
        self.changed.emit()
        # A folder made by the install is watched from now on
        self._collect()

    def _collect(self) -> None:
        if self._collector is not None:
            self._collect_again = True
            return
        collector = _FolderCollector()
        collector.collected.connect(self._watch)
        collector.finished.connect(self._collected)
        self._collector = collector
        collector.start()

    def _watch(self, folders: list[str]) -> None:
        new = sorted(set(folders) - set(self._watcher.directories()))
        if new:
            self._watcher.addPaths(new)

    def _collected(self) -> None:
        collector, self._collector = self._collector, None
        if collector is not None:
            collector.deleteLater()
        if self._collect_again:
            self._collect_again = False
            self._collect()

import hashlib
import logging
import os
from pathlib import Path
from typing import override

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    PatternMatchingEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from core.bar.manager import BarManager
from core.bar.revisions import path_key
from core.config import get_config_dir, get_config_path
from settings import DEFAULT_CONFIG_FILENAME


class FileModifiedEventHandler(PatternMatchingEventHandler):
    def __init__(self, bar_manager: BarManager):
        super().__init__(patterns=[DEFAULT_CONFIG_FILENAME, "*.qml"], ignore_directories=True, case_sensitive=False)
        self.bar_manager = bar_manager
        self._config_key = path_key(get_config_path())
        self._last_config_hash = self._file_hash(get_config_path())
        self._qml_hashes: dict[str, str | None] = {}

    def _file_hash(self, path: str) -> str | None:
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def _changed(self, path: str) -> None:
        if not self.bar_manager.config.watch:
            return
        key = path_key(path)
        if key == self._config_key:
            new_hash = self._file_hash(path)
            if new_hash and new_hash != self._last_config_hash:
                self._last_config_hash = new_hash
                self.bar_manager.config_modified.emit()
                logging.debug("Config file modified: %s", path)
        elif path.lower().endswith(".qml"):
            new_hash = self._file_hash(path)
            if key in self._qml_hashes and self._qml_hashes[key] == new_hash:
                return
            self._qml_hashes[key] = new_hash
            self.bar_manager.qml_changed.emit(path)
            logging.debug("QML file changed: %s", path)

    @override
    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self._changed(os.fsdecode(event.src_path))

    @override
    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self._changed(os.fsdecode(event.src_path))

    @override
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        self._changed(os.fsdecode(event.src_path))

    @override
    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        self._changed(os.fsdecode(event.src_path))
        self._changed(os.fsdecode(event.dest_path))


def create_observer(bar_manager: BarManager) -> BaseObserver:
    observer = Observer()
    handler = FileModifiedEventHandler(bar_manager)
    config_dir = Path(get_config_dir())
    observer.schedule(handler, path=str(config_dir), recursive=True)
    watched = [config_dir]
    for folder in sorted(bar_manager.qml_folders()):
        if folder.is_dir() and not any(folder.is_relative_to(parent) for parent in watched):
            observer.schedule(handler, path=str(folder), recursive=False)
            watched.append(folder)
    logging.info("Watching for changes: %s", ", ".join(str(folder) for folder in watched))
    return observer

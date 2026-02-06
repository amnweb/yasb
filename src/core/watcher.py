import hashlib
import logging
import os
from os.path import basename

from watchdog.events import FileModifiedEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

from core.bar_manager import BarManager
from core.config import get_config_dir, get_stylesheet_path
from core.utils.css_processor import CSSProcessor
from settings import DEFAULT_CONFIG_FILENAME, DEFAULT_STYLES_FILENAME


class FileModifiedEventHandler(PatternMatchingEventHandler):
    styles_file = DEFAULT_STYLES_FILENAME
    config_file = DEFAULT_CONFIG_FILENAME

    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self.bar_manager = bar_manager
        self._patterns = [self.styles_file, self.config_file]
        self._ignore_patterns = []
        self._ignore_directories = True
        self._case_sensitive = False
        self._last_styles_hash = None
        self._last_config_hash = None
        self._stylesheet_path = self._normalize_path(get_stylesheet_path())
        self._imported_stylesheets = set()
        self._imported_hashes = {}
        self._observer = None
        self._watched_dirs = set()
        self._refresh_imported_stylesheets()

    def _normalize_path(self, path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def _refresh_imported_stylesheets(self) -> None:
        try:
            processor = CSSProcessor(self._stylesheet_path)
            processor.process()
            self._imported_stylesheets = {self._normalize_path(path) for path in processor.imported_files}
            if self._stylesheet_path:
                self._imported_stylesheets.add(self._stylesheet_path)
            self._patterns = [self.styles_file, self.config_file, *self._imported_stylesheets]
            self._ensure_watch_paths()
        except Exception:
            logging.exception("Failed to refresh imported stylesheets list")

    def set_observer(self, observer) -> None:
        self._observer = observer
        self._ensure_watch_paths()

    def _ensure_watch_paths(self) -> None:
        if not self._observer:
            return
        paths = {get_config_dir()}
        for css_path in self._imported_stylesheets:
            if css_path:
                paths.add(os.path.dirname(css_path))
        for path in {self._normalize_path(path) for path in paths}:
            if path and path not in self._watched_dirs and os.path.isdir(path):
                self._observer.schedule(self, path=path, recursive=False)
                self._watched_dirs.add(path)
                logging.info(f"Watching directory: {path}")

    def _file_hash(self, path):
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def on_modified(self, event: FileModifiedEvent):
        modified_file = basename(event.src_path)
        normalized_path = self._normalize_path(event.src_path)

        if modified_file == self.styles_file and self.bar_manager.config.watch_stylesheet:
            new_hash = self._file_hash(event.src_path)
            if new_hash and new_hash != self._last_styles_hash:
                self._last_styles_hash = new_hash
                self._refresh_imported_stylesheets()
                self.bar_manager.styles_modified.emit()
                logging.debug(f"Stylesheet modified: {event.src_path}")
        elif modified_file == self.config_file and self.bar_manager.config.watch_config:
            new_hash = self._file_hash(event.src_path)
            if new_hash and new_hash != self._last_config_hash:
                self._last_config_hash = new_hash
                self.bar_manager.config_modified.emit()
                logging.debug(f"Config file modified: {event.src_path}")
        elif normalized_path in self._imported_stylesheets and self.bar_manager.config.watch_stylesheet:
            new_hash = self._file_hash(event.src_path)
            if new_hash and self._imported_hashes.get(normalized_path) != new_hash:
                self._imported_hashes[normalized_path] = new_hash
                self._refresh_imported_stylesheets()
                self.bar_manager.styles_modified.emit()
                logging.debug(f"Imported stylesheet modified: {event.src_path}")


def create_observer(bar_manager: BarManager):
    event_handler = FileModifiedEventHandler(bar_manager)
    observer = Observer()
    event_handler.set_observer(observer)
    logging.info("Created file watcher")
    return observer

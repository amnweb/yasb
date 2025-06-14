import hashlib
import logging
from os.path import basename

from watchdog.events import FileModifiedEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

from core.bar_manager import BarManager
from core.config import get_config_dir
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

    def _file_hash(self, path):
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def on_modified(self, event: FileModifiedEvent):
        modified_file = basename(event.src_path)

        if modified_file == self.styles_file and self.bar_manager.config["watch_stylesheet"]:
            new_hash = self._file_hash(event.src_path)
            if new_hash and new_hash != self._last_styles_hash:
                self._last_styles_hash = new_hash
                self.bar_manager.styles_modified.emit()
        elif modified_file == self.config_file and self.bar_manager.config["watch_config"]:
            new_hash = self._file_hash(event.src_path)
            if new_hash and new_hash != self._last_config_hash:
                self._last_config_hash = new_hash
                self.bar_manager.config_modified.emit()


def create_observer(bar_manager: BarManager):
    event_handler = FileModifiedEventHandler(bar_manager)
    config_path = get_config_dir()
    observer = Observer()
    observer.schedule(event_handler, path=config_path, recursive=False)
    logging.info(f"Created file watcher for path {config_path}")
    return observer

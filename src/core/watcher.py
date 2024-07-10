import logging
from os.path import basename
from core.config import get_config_dir
from settings import DEFAULT_STYLES_FILENAME, DEFAULT_CONFIG_FILENAME
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileModifiedEvent
from core.bar_manager import BarManager


class FileModifiedEventHandler(PatternMatchingEventHandler):
    styles_file = DEFAULT_STYLES_FILENAME
    config_file = DEFAULT_CONFIG_FILENAME

    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self.bar_manager = bar_manager
        self._patterns = [
            self.styles_file,
            self.config_file
        ]
        self._ignore_patterns = []
        self._ignore_directories = True
        self._case_sensitive = False

    def on_modified(self, event: FileModifiedEvent):
        modified_file = basename(event.src_path)

        if modified_file == self.styles_file and self.bar_manager.config['watch_stylesheet']:
            self.bar_manager.styles_modified.emit()
        elif modified_file == self.config_file and self.bar_manager.config['watch_config']:
            self.bar_manager.config_modified.emit()


def create_observer(bar_manager: BarManager):
    event_handler = FileModifiedEventHandler(bar_manager)
    config_path = get_config_dir()
    observer = Observer()
    observer.schedule(event_handler, path=config_path, recursive=False)
    logging.info(f"Created file watcher for path {config_path}")
    return observer

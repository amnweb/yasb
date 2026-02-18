import logging
import os
from queue import Empty, SimpleQueue
from threading import Event

from PyQt6.QtCore import QThread, pyqtSignal

from core.utils.widgets.quick_launch.base_provider import ProviderResult


class StartMenuWatcherThread(QThread):
    """Collects Start Menu and UWP package directories for file system watching."""

    dirs_ready = pyqtSignal(list)

    def run(self):
        start_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        uwp_packages = os.path.expandvars(r"%LOCALAPPDATA%\Packages")
        if os.path.isdir(uwp_packages):
            start_dirs.append(uwp_packages)

        dirs = []
        for d in start_dirs:
            if os.path.isdir(d):
                dirs.append(d)
                if "Packages" not in d:
                    for root, subdirs, _ in os.walk(d):
                        dirs.extend(os.path.join(root, sd) for sd in subdirs)
        self.dirs_ready.emit(dirs)


class QueryWorker(QThread):
    """Persistent single-thread query executor.

    A single thread stays alive for the lifetime of the service.
    New queries are submitted via `submit()` which cancels any
    in-progress work and queues the new query. The thread drains
    the queue to only process the latest query, avoiding wasted work.
    """

    finished = pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self._queue: SimpleQueue[tuple[str, str, int, list] | None] = SimpleQueue()
        self._cancel = Event()

    def submit(self, query_id: str, text: str, max_results: int, providers: list):
        self._cancel.set()
        self._queue.put((query_id, text, max_results, providers))

    def shutdown(self):
        self._cancel.set()
        self._queue.put(None)

    def run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            # Drain to latest - skip stale queries
            while not self._queue.empty():
                try:
                    newer = self._queue.get_nowait()
                    if newer is None:
                        return
                    item = newer
                except Empty:
                    break

            query_id, text, max_results, providers = item
            self._cancel.clear()
            self._run_query(query_id, text.lstrip(), max_results, providers)

    def _run_query(self, query_id: str, text: str, max_results: int, providers: list):
        all_results: list[ProviderResult] = []
        try:
            # Prefixed providers get exclusive handling (require prefix + space)
            for provider in providers:
                if self._cancel.is_set():
                    return
                if provider.prefix and text.startswith(provider.prefix + " "):
                    results = provider.get_results(text, cancel_event=self._cancel)[:max_results]
                    if not self._cancel.is_set():
                        self.finished.emit(query_id, results)
                    return

            # Non-prefixed providers contribute to combined results
            for provider in providers:
                if self._cancel.is_set():
                    return
                if provider.prefix:
                    continue
                if provider.match(text):
                    all_results.extend(provider.get_results(text, cancel_event=self._cancel))

            if not self._cancel.is_set():
                self.finished.emit(query_id, all_results[:max_results])
        except Exception as e:
            logging.debug(f"Query worker error: {e}")
            if not self._cancel.is_set():
                self.finished.emit(query_id, [])

"""Update check service."""

import logging
import threading

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from core.utils.widgets.update_check import scoop as scoop_mgr
from core.utils.widgets.update_check import windows_update as wu_mgr
from core.utils.widgets.update_check import winget as winget_mgr

# Map source name.
# Each module must expose check_updates() and upgrade_packages().
_SOURCE_MODULES = {
    "winget": winget_mgr,
    "scoop": scoop_mgr,
    "windows": wu_mgr,
}


class _UpdateWorker(QThread):
    """Background worker that checks one source for updates."""

    finished = pyqtSignal(str, dict)  # (source, result_dict)

    def __init__(self, source: str, exclude_list: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.source = source
        self.exclude_list = exclude_list or []

    def run(self):
        try:
            module = _SOURCE_MODULES.get(self.source)
            if module is None:
                logging.error("Unknown update source: %s", self.source)
                self.finished.emit(self.source, {"count": 0, "names": [], "ids": []})
                return

            updates = module.check_updates()

            # Build display names
            if self.source == "winget":
                names = [f"{u['name']}: {u['version']} -> {u['available']}" for u in updates]
            elif self.source == "scoop":
                names = [f"{u['name']}: {u['version']} -> {u['available']}" for u in updates]
            elif self.source == "windows":
                names = [u["name"] for u in updates]

            # Apply exclude filter
            ids = [u["id"] for u in updates]
            if self.exclude_list:
                valid_excludes = [x.lower() for x in self.exclude_list if x and x.strip()]
                filtered_names = []
                filtered_ids = []
                for update, name, uid in zip(updates, names, ids):
                    if not any(
                        ex in update.get("id", "").lower() or ex in update.get("name", "").lower()
                        for ex in valid_excludes
                    ):
                        filtered_names.append(name)
                        filtered_ids.append(uid)
                names = filtered_names
                ids = filtered_ids

            self.finished.emit(
                self.source,
                {
                    "count": len(names),
                    "names": names,
                    "ids": ids,
                },
            )

        except Exception as e:
            logging.error("Error in %s update worker: %s", self.source, e)
            self.finished.emit(self.source, {"count": 0, "names": [], "ids": []})


class UpdateCheckService(QObject):
    """Singleton service shared by all update_check widgets."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        super().__init__()

        self._widgets: list = []
        self._workers: dict[str, _UpdateWorker] = {}
        self._timers: dict[str, QTimer] = {}
        self._results: dict[str, dict] = {}
        self._lock = threading.Lock()

        logging.info("UpdateCheckService initialized...")

    def register_widget(self, widget):
        """Register a widget and start polling for its enabled sources."""
        if widget not in self._widgets:
            self._widgets.append(widget)

        # Start polling for each source the widget has enabled
        self._ensure_source_polling(widget)

        # Push any cached results immediately so late-registering widgets
        # don't have to wait for the next poll cycle.
        for source, result in self._results.items():
            self._push_to_widget(widget, source, result)

    def unregister_widget(self, widget):
        """Remove a widget. Stops polling when no widgets remain."""
        if widget in self._widgets:
            self._widgets.remove(widget)
        if not self._widgets:
            self._stop_all()

    def _ensure_source_polling(self, widget):
        """Start timers for sources that don't have one yet."""
        config = widget.config

        sources = []
        if hasattr(config, "winget_update") and config.winget_update.enabled:
            sources.append(("winget", config.winget_update.interval, config.winget_update.exclude))
        if hasattr(config, "scoop_update") and config.scoop_update.enabled:
            sources.append(("scoop", config.scoop_update.interval, config.scoop_update.exclude))
        if hasattr(config, "windows_update") and config.windows_update.enabled:
            sources.append(("windows", config.windows_update.interval, config.windows_update.exclude))

        for source, interval_min, exclude in sources:
            if source not in self._timers:
                self._start_polling(source, interval_min, exclude)

    def _start_polling(self, source: str, interval_min: int, exclude: list[str]):
        """Create a timer for a source."""
        interval_ms = interval_min * 60 * 1000

        timer = QTimer(self)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.timeout.connect(lambda s=source, e=exclude: self._run_check(s, e))
        self._timers[source] = timer

        # Initial check after short delay (stagger to avoid all at once)
        delay = {"winget": 10_000, "scoop": 15_000, "windows": 20_000}.get(source, 10_000)
        QTimer.singleShot(delay, lambda s=source, e=exclude, t=timer, i=interval_ms: self._initial_check(s, e, t, i))

    def _initial_check(self, source: str, exclude: list[str], timer: QTimer, interval_ms: int):
        """Run the first check and then start the repeating timer."""
        self._run_check(source, exclude)
        timer.start(interval_ms)

    def _run_check(self, source: str, exclude: list[str]):
        """Launch a worker for the given source."""
        # Don't stack workers for same source
        if source in self._workers and self._workers[source].isRunning():
            return

        worker = _UpdateWorker(source, exclude)
        worker.finished.connect(self._on_worker_finished)
        self._workers[source] = worker
        worker.start()

    def _on_worker_finished(self, source: str, result: dict):
        """Handle worker results - cache and push to all widgets."""
        self._results[source] = result

        for widget in self._widgets[:]:
            self._push_to_widget(widget, source, result)

        # Clean up finished worker
        if source in self._workers:
            worker = self._workers.pop(source)
            worker.deleteLater()

    @staticmethod
    def _push_to_widget(widget, source: str, result: dict):
        """Call the widget's update method for a specific source."""
        try:
            widget.on_update(source, result)
        except Exception:
            logging.exception("Error pushing %s update to widget", source)

    def handle_left_click(self, source: str):
        """Upgrade packages for the given source."""
        result = self._results.get(source, {})
        ids = result.get("ids", [])

        module = _SOURCE_MODULES.get(source)
        if module:
            module.upgrade_packages(ids)

        # Hide after click
        self._results.pop(source, None)
        for widget in self._widgets[:]:
            self._push_to_widget(widget, source, {"count": 0, "names": [], "ids": []})

    def handle_right_click(self, source: str):
        """Force re-check for a source."""
        # Hide first
        self._results.pop(source, None)
        for widget in self._widgets[:]:
            self._push_to_widget(widget, source, {"count": 0, "names": [], "ids": []})

        # Gather exclude list from all widgets
        exclude: list[str] = []
        for widget in self._widgets[:]:
            cfg = getattr(widget.config, f"{source}_update", None)
            if cfg:
                exclude.extend(cfg.exclude)

        self._run_check(source, exclude)

    def _stop_all(self):
        """Stop all timers and workers."""
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()

        for worker in self._workers.values():
            if worker.isRunning():
                worker.quit()
        self._workers.clear()

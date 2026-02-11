import json
import logging
import os
import tempfile
import time

from PyQt6.QtCore import QFileSystemWatcher, QObject, QThread, QTimer, pyqtSignal

from core.utils.utilities import app_data_path
from core.utils.widgets.launchpad.app_loader import AppListLoader
from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.icon_resolver import IconResolverWorker
from core.utils.widgets.quick_launch.providers.apps import AppsProvider
from core.utils.widgets.quick_launch.providers.bookmarks import BookmarksProvider
from core.utils.widgets.quick_launch.providers.calculator import CalculatorProvider
from core.utils.widgets.quick_launch.providers.color_converter import ColorConverterProvider
from core.utils.widgets.quick_launch.providers.currency import CurrencyProvider
from core.utils.widgets.quick_launch.providers.emoji import EmojiProvider
from core.utils.widgets.quick_launch.providers.file_search import FileSearchProvider
from core.utils.widgets.quick_launch.providers.kill_process import KillProcessProvider
from core.utils.widgets.quick_launch.providers.settings import SettingsProvider
from core.utils.widgets.quick_launch.providers.system_commands import SystemCommandsProvider
from core.utils.widgets.quick_launch.providers.unit_converter import UnitConverterProvider
from core.utils.widgets.quick_launch.providers.web_search import WebSearchProvider

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "apps": AppsProvider,
    "bookmarks": BookmarksProvider,
    "calculator": CalculatorProvider,
    "color_converter": ColorConverterProvider,
    "currency": CurrencyProvider,
    "emoji": EmojiProvider,
    "file_search": FileSearchProvider,
    "kill_process": KillProcessProvider,
    "settings": SettingsProvider,
    "system_commands": SystemCommandsProvider,
    "unit_converter": UnitConverterProvider,
    "web_search": WebSearchProvider,
}


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
    """Runs provider queries off the main thread."""

    finished = pyqtSignal(str, list)

    def __init__(self, query_id: str, text: str, max_results: int, providers: list):
        super().__init__()
        self._query_id = query_id
        self._text = text
        self._max_results = max_results
        self._providers = providers
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        text_stripped = self._text.strip()
        all_results: list[ProviderResult] = []
        try:
            for provider in self._providers:
                if self._cancelled:
                    return
                if provider.prefix and text_stripped.startswith(provider.prefix):
                    results = provider.get_results(text_stripped)[: self._max_results]
                    if not self._cancelled:
                        self.finished.emit(self._query_id, results)
                    return

            for provider in self._providers:
                if self._cancelled:
                    return
                if provider.prefix:
                    continue
                if provider.match(text_stripped):
                    results = provider.get_results(text_stripped)
                    all_results.extend(results)

            if not self._cancelled:
                self.finished.emit(self._query_id, all_results[: self._max_results])
        except Exception as e:
            logging.debug(f"Query worker error: {e}")
            if not self._cancelled:
                self.finished.emit(self._query_id, [])


class QuickLaunchService(QObject):
    """Singleton service shared across all QuickLaunchWidget instances.

    Manages app loading, icon resolution, file system watching,
    recent launches and provider orchestration.
    """

    request_refresh = pyqtSignal()
    icon_ready = pyqtSignal(str, str)
    query_finished = pyqtSignal(str, list)

    _instance: "QuickLaunchService | None" = None

    @classmethod
    def instance(cls) -> "QuickLaunchService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._apps: list[tuple[str, str, object]] = []
        self._apps_loaded = False
        self._icon_paths: dict[str, str] = {}
        self._icon_worker: IconResolverWorker | None = None
        self._app_loader: AppListLoader | None = None
        self._icons_dir = os.path.join(tempfile.gettempdir(), "yasb_quick_launch_icons")
        os.makedirs(self._icons_dir, exist_ok=True)
        self._recent_file = str(app_data_path("quick_launch_recent.json"))
        self._launch_history: dict[str, dict] = self._load_history()
        self._providers: list[BaseProvider] = []
        self._providers_config: dict = {}
        self._query_worker: QueryWorker | None = None
        self._query_counter = 0
        self._setup_fs_watcher()
        self._start_app_loading()

    # Properties

    @property
    def providers(self) -> list[BaseProvider]:
        return self._providers

    @property
    def apps(self) -> list[tuple[str, str, object]]:
        return self._apps

    @property
    def apps_loaded(self) -> bool:
        return self._apps_loaded

    @property
    def icon_paths(self) -> dict[str, str]:
        return self._icon_paths

    @property
    def launch_history(self) -> dict[str, dict]:
        return self._launch_history

    # Providers

    def configure_providers(self, providers_config: dict, max_results: int = 50):
        if self._providers and self._providers_config == providers_config:
            return
        self._providers_config = providers_config
        self._providers.clear()
        for name, cls in PROVIDER_REGISTRY.items():
            provider_cfg = providers_config.get(name, {})
            if not provider_cfg.get("enabled", True):
                continue
            provider_cfg["_max_results"] = max_results
            provider = cls(config=provider_cfg)
            provider.request_refresh = self.request_refresh.emit
            self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

    # Query

    def query(self, text: str, max_results: int = 50) -> list[ProviderResult]:
        if not self._providers:
            return []
        text_stripped = text.strip()
        all_results: list[ProviderResult] = []
        for provider in self._providers:
            if provider.prefix and text_stripped.startswith(provider.prefix):
                return provider.get_results(text_stripped)[:max_results]
        for provider in self._providers:
            if provider.prefix:
                continue
            if provider.match(text_stripped):
                results = provider.get_results(text_stripped)
                all_results.extend(results)
        return all_results[:max_results]

    def async_query(self, text: str, max_results: int = 50) -> str:
        if self._query_worker and self._query_worker.isRunning():
            self._query_worker.cancel()
            self._query_worker.finished.disconnect()
            self._query_worker = None
        self._query_counter += 1
        query_id = str(self._query_counter)
        self._query_worker = QueryWorker(query_id, text, max_results, list(self._providers))
        self._query_worker.finished.connect(self._on_query_finished)
        self._query_worker.start()
        return query_id

    def _on_query_finished(self, query_id: str, results: list):
        self.query_finished.emit(query_id, results)

    def execute_result(self, result: ProviderResult) -> bool:
        for provider in self._providers:
            if provider.name == result.provider:
                return provider.execute(result)
        return False

    # App loading

    def _start_app_loading(self):
        self._app_loader = AppListLoader()
        self._app_loader.apps_loaded.connect(self._on_apps_loaded)
        self._app_loader.start()

    def _on_apps_loaded(self, apps: list):
        self._apps = apps
        self._apps_loaded = True
        self._start_icon_resolution()
        self.request_refresh.emit()

    # Icon resolution

    def _start_icon_resolution(self):
        if self._icon_worker and self._icon_worker.isRunning():
            self._icon_worker.icon_ready.disconnect(self._on_icon_ready)
            self._icon_worker.stop()
            self._icon_worker.wait()
        self._icon_worker = IconResolverWorker(self._apps, self._icons_dir)
        self._icon_worker.icon_ready.connect(self._on_icon_ready)
        self._icon_worker.start()

    def _on_icon_ready(self, app_key: str, icon_path: str):
        self._icon_paths[app_key] = icon_path
        self.icon_ready.emit(app_key, icon_path)

    # File system watcher

    def _setup_fs_watcher(self):
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(lambda _: self._fs_debounce.start())
        self._fs_debounce = QTimer(self)
        self._fs_debounce.setSingleShot(True)
        self._fs_debounce.setInterval(2000)
        self._fs_debounce.timeout.connect(self._on_fs_change_debounced)
        self._watcher_thread = StartMenuWatcherThread()
        self._watcher_thread.dirs_ready.connect(lambda dirs: self._fs_watcher.addPaths(dirs) if dirs else None)
        self._watcher_thread.start()

    def _on_fs_change_debounced(self):
        logging.info("Quick Launch: rebuilding app list after install/uninstall detected")
        AppListLoader.clear_cache()
        self._start_app_loading()

    # Frecency / launch history

    def _load_history(self) -> dict[str, dict]:
        try:
            if os.path.isfile(self._recent_file):
                with open(self._recent_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    history = {}
                    for r in reversed(data):
                        key = r.get("key", "")
                        if key:
                            history[key] = {
                                "name": r.get("name", ""),
                                "path": r.get("path", ""),
                                "count": 1,
                                "last_used": r.get("timestamp", time.time()),
                            }
                    return history
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self._recent_file), exist_ok=True)
            with open(self._recent_file, "w", encoding="utf-8") as f:
                json.dump(self._launch_history, f, indent=2)
        except Exception:
            pass

    def record_recent(self, name: str, path: str):
        key = f"{name}::{path}"
        now = time.time()
        if key in self._launch_history:
            self._launch_history[key]["count"] += 1
            self._launch_history[key]["last_used"] = now
        else:
            self._launch_history[key] = {
                "name": name,
                "path": path,
                "count": 1,
                "last_used": now,
            }
        self._save_history()

    def get_frecency_score(self, app_key: str) -> float:
        entry = self._launch_history.get(app_key)
        if not entry:
            return 0.0
        count = entry.get("count", 0)
        last_used = entry.get("last_used", 0)
        hours_ago = (time.time() - last_used) / 3600
        if hours_ago < 4:
            recency = 1.0
        elif hours_ago < 24:
            recency = 0.8
        elif hours_ago < 168:
            recency = 0.6
        else:
            recency = 0.4
        return count * recency

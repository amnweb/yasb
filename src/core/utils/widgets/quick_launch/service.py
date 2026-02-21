import logging
import os
import tempfile

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

from core.utils.widgets.launchpad.app_loader import AppListLoader
from core.utils.widgets.quick_launch.base_provider import BaseProvider
from core.utils.widgets.quick_launch.icon_resolver import IconResolverWorker
from core.utils.widgets.quick_launch.providers import (
    AppsProvider,
    BookmarksProvider,
    CalculatorProvider,
    ClipboardHistoryProvider,
    ColorProvider,
    CurrencyProvider,
    DevToolsProvider,
    EmojiProvider,
    FileSearchProvider,
    HackerNewsProvider,
    IpInfoProvider,
    KillProcessProvider,
    PortViewerProvider,
    SettingsProvider,
    SnippetsProvider,
    SystemCommandsProvider,
    UnitConverterProvider,
    VSCodeProvider,
    WebSearchProvider,
    WindowSwitcherProvider,
    WorldClockProvider,
)
from core.utils.widgets.quick_launch.workers import QueryWorker, StartMenuWatcherThread

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "apps": AppsProvider,
    "bookmarks": BookmarksProvider,
    "calculator": CalculatorProvider,
    "clipboard_history": ClipboardHistoryProvider,
    "color": ColorProvider,
    "currency": CurrencyProvider,
    "dev_tools": DevToolsProvider,
    "emoji": EmojiProvider,
    "file_search": FileSearchProvider,
    "hacker_news": HackerNewsProvider,
    "ip_info": IpInfoProvider,
    "kill_process": KillProcessProvider,
    "port_viewer": PortViewerProvider,
    "settings": SettingsProvider,
    "snippets": SnippetsProvider,
    "system_commands": SystemCommandsProvider,
    "unit_converter": UnitConverterProvider,
    "web_search": WebSearchProvider,
    "window_switcher": WindowSwitcherProvider,
    "world_clock": WorldClockProvider,
    "vscode": VSCodeProvider,
}


class QuickLaunchService(QObject):
    """Quick Launch service."""

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
        self._providers: list[BaseProvider] = []
        self._providers_config: dict = {}
        self._show_icons: bool = True

        self._app_loader: AppListLoader | None = None
        self._icon_worker: IconResolverWorker | None = None
        self._query_worker = QueryWorker()
        self._query_worker.finished.connect(self._on_query_finished)
        self._query_worker.start()
        self._query_counter = 0

        self._icons_dir = os.path.join(tempfile.gettempdir(), "yasb_quick_launch_icons")
        os.makedirs(self._icons_dir, exist_ok=True)

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

    def configure_providers(self, providers_config: dict, max_results: int = 50, show_icons: bool = True):
        if self._providers and self._providers_config == providers_config:
            return
        self._providers_config = providers_config
        self._show_icons = show_icons
        self._providers.clear()
        apps_enabled = False
        for name, cls in PROVIDER_REGISTRY.items():
            provider_cfg = providers_config.get(name, {})
            if not provider_cfg.get("enabled", True):
                continue
            if name == "apps":
                apps_enabled = True
            provider_cfg["_max_results"] = max_results
            provider = cls(config=provider_cfg)
            provider.request_refresh = self.request_refresh.emit
            self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

        if apps_enabled:
            if not self._apps_loaded and not self._app_loader:
                self._setup_fs_watcher()
                self._start_app_loading()

    def async_query(self, text: str, max_results: int = 50) -> str:
        """Submit an async query. Returns a query_id to match results."""
        self._query_counter += 1
        query_id = str(self._query_counter)
        self._query_worker.submit(query_id, text, max_results, list(self._providers))
        return query_id

    def _on_query_finished(self, query_id: str, results: list):
        self.query_finished.emit(query_id, results)

    def _start_app_loading(self):
        if self._app_loader:
            self._app_loader.apps_loaded.disconnect(self._on_apps_loaded)
        self._app_loader = AppListLoader()
        self._app_loader.apps_loaded.connect(self._on_apps_loaded)
        self._app_loader.start()

    def _on_apps_loaded(self, apps: list):
        self._apps = apps
        self._apps_loaded = True
        if self._show_icons:
            self._start_icon_resolution()
        self._start_description_resolution()
        self.request_refresh.emit()

    def _start_description_resolution(self):
        for provider in self._providers:
            if isinstance(provider, AppsProvider):
                if provider.config.get("show_description", False):
                    provider.start_description_resolution(self._apps)
                break

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

    def _setup_fs_watcher(self):
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(lambda _: self._fs_debounce.start())
        self._fs_debounce = QTimer(self)
        self._fs_debounce.setSingleShot(True)
        self._fs_debounce.setInterval(5000)
        self._fs_debounce.timeout.connect(self._on_fs_change)
        self._watcher_thread = StartMenuWatcherThread()
        self._watcher_thread.dirs_ready.connect(lambda dirs: self._fs_watcher.addPaths(dirs) if dirs else None)
        self._watcher_thread.start()

    def _on_fs_change(self):
        logging.info("Quick Launch rebuilding app list after install/uninstall detected")
        AppListLoader.clear_cache()
        self._start_app_loading()

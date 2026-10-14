import logging
from typing import Any

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.icons.service import IconService
from core.utils.win32.app_loader import AppEntry, AppListLoader, app_icon_source
from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.providers import (
    AppsProvider,
    BinanceProvider,
    BookmarksProvider,
    CalculatorProvider,
    ClipboardHistoryProvider,
    ColorProvider,
    CurrencyProvider,
    DevToolsProvider,
    EmojiProvider,
    FileSearchProvider,
    GithubNotificationsProvider,
    HackerNewsProvider,
    IpInfoProvider,
    KillProcessProvider,
    PortViewerProvider,
    SettingsProvider,
    SnippetsProvider,
    SshProvider,
    SystemCommandsProvider,
    UnitConverterProvider,
    VSCodeProvider,
    WebSearchProvider,
    WindowsTerminalProvider,
    WindowSwitcherProvider,
    WorldClockProvider,
    WslProvider,
)
from core.widgets.services.quick_launch.workers import QueryWorker, StartMenuWatcherThread

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "apps": AppsProvider,
    "bookmarks": BookmarksProvider,
    "calculator": CalculatorProvider,
    "clipboard_history": ClipboardHistoryProvider,
    "color": ColorProvider,
    "binance": BinanceProvider,
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
    "ssh": SshProvider,
    "system_commands": SystemCommandsProvider,
    "unit_converter": UnitConverterProvider,
    "web_search": WebSearchProvider,
    "window_switcher": WindowSwitcherProvider,
    "windows_terminal": WindowsTerminalProvider,
    "world_clock": WorldClockProvider,
    "vscode": VSCodeProvider,
    "github_notifications": GithubNotificationsProvider,
    "wsl": WslProvider,
}


class QuickLaunchService(QObject):
    """Quick Launch service."""

    request_refresh = pyqtSignal()
    query_finished = pyqtSignal(str, list)

    _instance: QuickLaunchService | None = None

    @classmethod
    def instance(cls) -> QuickLaunchService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()

        self._apps: list[AppEntry] = []
        self._apps_loaded = False
        self._providers: list[BaseProvider] = []
        self._providers_config: dict[str, Any] = {}
        self._show_icons: bool = True

        self._app_loader: AppListLoader | None = None
        self._query_worker = QueryWorker()
        self._query_worker.finished.connect(self._on_query_finished)
        self._query_worker.start()
        self._query_counter = 0

        app_inst = QApplication.instance()
        if app_inst:
            app_inst.aboutToQuit.connect(self._stop_workers)

    def _stop_workers(self):
        self._query_worker.shutdown()
        self._query_worker.wait(2000)

    @property
    def providers(self) -> list[BaseProvider]:
        return self._providers

    @property
    def apps(self) -> list[AppEntry]:
        return self._apps

    @property
    def apps_loaded(self) -> bool:
        return self._apps_loaded

    def configure_providers(
        self, providers_config: dict[str, Any], max_results: int = 50, show_icons: bool = True, icon_size: int = 32
    ):
        self._icon_size = icon_size
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

    def _on_query_finished(self, query_id: str, results: list[ProviderResult]):
        self.query_finished.emit(query_id, results)

    def _start_app_loading(self):
        if self._app_loader:
            self._app_loader.apps_loaded.disconnect(self._on_apps_loaded)
        self._app_loader = AppListLoader()
        self._app_loader.apps_loaded.connect(self._on_apps_loaded)
        self._app_loader.start()

    def _on_apps_loaded(self, apps: list[AppEntry]):
        self._apps = apps
        self._apps_loaded = True
        if self._show_icons:
            self._preload_icons()
        self._start_description_resolution()
        self.request_refresh.emit()

    def _start_description_resolution(self):
        for provider in self._providers:
            if isinstance(provider, AppsProvider):
                if provider.config.get("show_description", False):
                    provider.start_description_resolution(self._apps)
                break

    def _preload_icons(self):
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        IconService.instance().preload((app_icon_source(path) for _, path, _ in self._apps), self._icon_size, dpr)

    def _setup_fs_watcher(self):
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._on_directory_changed)
        self._fs_debounce = QTimer(self)
        self._fs_debounce.setSingleShot(True)
        self._fs_debounce.setInterval(5000)
        self._fs_debounce.timeout.connect(self._on_fs_change)
        self._watcher_thread = StartMenuWatcherThread()
        self._watcher_thread.dirs_ready.connect(self._on_watch_dirs_ready)
        self._watcher_thread.start()

    def _on_directory_changed(self, path: str) -> None:
        self._fs_debounce.start()

    def _on_watch_dirs_ready(self, dirs: list[str]) -> None:
        if dirs:
            self._fs_watcher.addPaths(dirs)

    def _on_fs_change(self):
        logging.info("Quick Launch rebuilding app list after install/uninstall detected")
        AppListLoader.clear_cache()
        self._start_app_loading()

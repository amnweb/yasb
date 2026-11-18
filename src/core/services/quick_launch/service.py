import re
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from core.services.apps.service import StartApps
from core.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.services.quick_launch.providers import (
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
from core.services.quick_launch.workers import QueryWorker
from core.utils.icons.service import IconService
from core.utils.win32.app_loader import AppEntry, app_icon_source

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

        self._watching_apps = False
        self._query_worker = QueryWorker()
        self._query_worker.finished.connect(self._on_query_finished)
        self._query_worker.start()
        self._query_counter = 0

        app_inst = QGuiApplication.instance()
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
            provider_cfg = dict(providers_config.get(name, {}))
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
            if not self._watching_apps:
                self._watching_apps = True
                start = StartApps.instance()
                start.changed.connect(self._update_apps)
                if start.loaded:
                    self._update_apps()
            elif self._apps_loaded:
                self._start_description_resolution()

    def async_query(self, text: str, max_results: int = 50) -> str:
        """Submit an async query. Returns a query_id to match results."""
        self._query_counter += 1
        query_id = str(self._query_counter)
        self._query_worker.submit(query_id, text, max_results, list(self._providers))
        return query_id

    def _on_query_finished(self, query_id: str, results: list[ProviderResult]):
        self.query_finished.emit(query_id, results)

    def _update_apps(self):
        self._on_apps_loaded(_quick_launch_apps(StartApps.instance()))

    def _on_apps_loaded(self, apps: list[AppEntry]):
        if self._apps_loaded and apps == self._apps:
            return
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
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        IconService.instance().preload((app_icon_source(path) for _, path, _ in self._apps), self._icon_size, dpr)


# Names that aren't apps: any containing one of the first, or one of the second as a whole word
_SKIPPED_NAMES = ("readme", "documentation", "license", "setup", "administrative tools")
_SKIPPED_WORDS = re.compile(r"\b(uninstall|installer|help)\b")


def _quick_launch_apps(start: StartApps) -> list[AppEntry]:
    """The Start menu shortcuts, then the All apps entries and Control Panel items whose names are not among them."""
    apps: list[AppEntry] = []
    seen: set[str] = set()

    def skipped(name: str) -> bool:
        lower = name.lower()
        return any(word in lower for word in _SKIPPED_NAMES) or _SKIPPED_WORDS.search(lower) is not None

    def first(name: str) -> bool:
        # "LiveCaptions" from a shortcut and "Live captions" from All apps are one app
        lower = name.lower()
        if lower in seen or lower.replace(" ", "") in seen:
            return False
        seen.update((lower, lower.replace(" ", "")))
        return True

    for shortcut in start.shortcuts:
        if not skipped(shortcut.name) and first(shortcut.name):
            apps.append((shortcut.name, shortcut.path, None))
    for app in start.apps:
        if app.name and app.id and not skipped(app.name) and first(app.name):
            apps.append((app.name, f"UWP::{app.id}", None))
    for item in start.control_panel:
        if first(item.name):
            apps.append((item.name, f"CPL::{item.clsid}::{item.canonical}", item.description))
    return apps

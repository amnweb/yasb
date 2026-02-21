from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class QuickLaunchPopupConfig(CustomBaseModel):
    width: int = 720
    height: int = 480
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    dark_mode: bool = True
    screen: Literal["primary", "focus", "cursor"] = "focus"


class QuickLaunchCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_quick_launch"
    on_middle: str = "do_nothing"
    on_right: str = "do_nothing"


class AppsProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "*"
    priority: int = 0
    show_recent: bool = True
    max_recent: int = 10
    show_description: bool = True


class CalculatorProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "="
    priority: int = 0


class WebSearchProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "?"
    priority: int = 0
    engine: str = "google"


class SystemCommandsProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = ">"
    priority: int = 0


class SettingsProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "@"
    priority: int = 0


class KillProcessProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "!"
    priority: int = 0


class FileSearchProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "/"
    priority: int = 0
    backend: Literal["auto", "everything", "index", "disk"] = "auto"
    show_path: bool = True


class CurrencyProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "$"
    priority: int = 0


class BookmarksProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "*"
    priority: int = 0
    browser: str = "all"
    profile: str = "Default"


class UnitConverterProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "~"
    priority: int = 0


class EmojiProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = ":"
    priority: int = 0


class SnippetsProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = ";"
    priority: int = 0
    type_delay: int = 200


class ColorProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "c:"
    priority: int = 0


class ClipboardHistoryProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "cb"
    priority: int = 0
    max_items: int = 30


class PortViewerProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "pv"
    priority: int = 0
    tcp_listening_only: bool = True
    include_established: bool = False


class WorldClockProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "tz"
    priority: int = 0


class HackerNewsProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "hn"
    priority: int = 0
    cache_ttl: int = 300
    max_items: int = 30


class DevToolsProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "dev"
    priority: int = 0


class IpInfoProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "ip"
    priority: int = 0


class VSCodeProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "vsc"
    priority: int = 0


class WindowSwitcherProviderConfig(CustomBaseModel):
    enabled: bool = False
    prefix: str = "win"
    priority: int = 0


class QuickLaunchProvidersConfig(CustomBaseModel):
    apps: AppsProviderConfig = AppsProviderConfig()
    bookmarks: BookmarksProviderConfig = BookmarksProviderConfig()
    calculator: CalculatorProviderConfig = CalculatorProviderConfig()
    clipboard_history: ClipboardHistoryProviderConfig = ClipboardHistoryProviderConfig()
    currency: CurrencyProviderConfig = CurrencyProviderConfig()
    web_search: WebSearchProviderConfig = WebSearchProviderConfig()
    system_commands: SystemCommandsProviderConfig = SystemCommandsProviderConfig()
    settings: SettingsProviderConfig = SettingsProviderConfig()
    kill_process: KillProcessProviderConfig = KillProcessProviderConfig()
    file_search: FileSearchProviderConfig = FileSearchProviderConfig()
    unit_converter: UnitConverterProviderConfig = UnitConverterProviderConfig()
    emoji: EmojiProviderConfig = EmojiProviderConfig()
    snippets: SnippetsProviderConfig = SnippetsProviderConfig()
    color: ColorProviderConfig = ColorProviderConfig()
    port_viewer: PortViewerProviderConfig = PortViewerProviderConfig()
    world_clock: WorldClockProviderConfig = WorldClockProviderConfig()
    hacker_news: HackerNewsProviderConfig = HackerNewsProviderConfig()
    dev_tools: DevToolsProviderConfig = DevToolsProviderConfig()
    ip_info: IpInfoProviderConfig = IpInfoProviderConfig()
    vscode: VSCodeProviderConfig = VSCodeProviderConfig()
    window_switcher: WindowSwitcherProviderConfig = WindowSwitcherProviderConfig()


class QuickLaunchConfig(CustomBaseModel):
    label: str = "\uf002"
    search_placeholder: str = "Search applications..."
    max_results: int = Field(default=50, ge=1, le=500)
    show_icons: bool = True
    icon_size: int = 32
    home_page: bool = False
    compact_mode: bool = False
    providers: QuickLaunchProvidersConfig = QuickLaunchProvidersConfig()
    popup: QuickLaunchPopupConfig = QuickLaunchPopupConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: QuickLaunchCallbacksConfig = QuickLaunchCallbacksConfig()

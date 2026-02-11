from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class QuickLaunchPopupConfig(CustomBaseModel):
    width: int = 640
    height: int = 480
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    dark_mode: bool = False


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
    show_path: bool = False


class CalculatorProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "="
    priority: int = 0


class WebSearchProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "?"
    priority: int = 0
    engine: str = "google"


class SystemCommandsProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = ">"
    priority: int = 0


class SettingsProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "@"
    priority: int = 0


class KillProcessProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "!"
    priority: int = 0


class FileSearchProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "/"
    priority: int = 0
    backend: str = "auto"


class CurrencyProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "$"
    priority: int = 0


class BookmarksProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "*"
    priority: int = 0
    browser: str = "all"
    profile: str = "Default"


class UnitConverterProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "~"
    priority: int = 0


class EmojiProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = ":"
    priority: int = 0


class ColorConverterProviderConfig(CustomBaseModel):
    enabled: bool = True
    prefix: str = "c:"
    priority: int = 0


class QuickLaunchProvidersConfig(CustomBaseModel):
    apps: AppsProviderConfig = AppsProviderConfig()
    bookmarks: BookmarksProviderConfig = BookmarksProviderConfig()
    calculator: CalculatorProviderConfig = CalculatorProviderConfig()
    currency: CurrencyProviderConfig = CurrencyProviderConfig()
    web_search: WebSearchProviderConfig = WebSearchProviderConfig()
    system_commands: SystemCommandsProviderConfig = SystemCommandsProviderConfig()
    settings: SettingsProviderConfig = SettingsProviderConfig()
    kill_process: KillProcessProviderConfig = KillProcessProviderConfig()
    file_search: FileSearchProviderConfig = FileSearchProviderConfig()
    unit_converter: UnitConverterProviderConfig = UnitConverterProviderConfig()
    emoji: EmojiProviderConfig = EmojiProviderConfig()
    color_converter: ColorConverterProviderConfig = ColorConverterProviderConfig()


class QuickLaunchConfig(CustomBaseModel):
    label: str = "\uf002"
    search_placeholder: str = "Search applications..."
    max_results: int = 50
    show_icons: bool = True
    icon_size: int = 32
    providers: QuickLaunchProvidersConfig = QuickLaunchProvidersConfig()
    popup: QuickLaunchPopupConfig = QuickLaunchPopupConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: QuickLaunchCallbacksConfig = QuickLaunchCallbacksConfig()

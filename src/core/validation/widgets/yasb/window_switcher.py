from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel, KeybindingConfig


class WindowSwitcherPopupConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    dark_mode: bool = True


class WindowSwitcherCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_window_switcher"


class WindowSwitcherConfig(CustomBaseModel):
    label: str = "\uf2d2"
    label_alt: str = ""
    icon_size: int = 48
    max_visible_apps: int = 5
    show_title: bool = True
    popup: WindowSwitcherPopupConfig = WindowSwitcherPopupConfig()
    callbacks: WindowSwitcherCallbacksConfig = WindowSwitcherCallbacksConfig()
    keybindings: list[KeybindingConfig] = []

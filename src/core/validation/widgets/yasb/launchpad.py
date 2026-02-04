from typing import Literal

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class WindowConfig(CustomBaseModel):
    fullscreen: bool = False
    width: int = 800
    height: int = 600
    overlay_block: bool = True


class WindowAnimationConfig(CustomBaseModel):
    fade_in_duration: int = 400
    fade_out_duration: int = 400


class WindowStyleConfig(CustomBaseModel):
    enable_blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "sharp"] = "normal"
    border_color: str = "system"


class AnimationConfig(CustomBaseModel):
    enabled: bool = True
    type: str = "fadeInOut"
    duration: int = 200


class ShortcutsConfig(CustomBaseModel):
    add_app: str = "Ctrl+N"
    edit_app: str = "F2"
    show_context_menu: str = "Shift+F10"
    delete_app: str = "Delete"


class LaunchpadCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_launchpad"
    on_right: str = "do_nothing"
    on_middle: str = "do_nothing"


class LaunchpadConfig(CustomBaseModel):
    label: str = "\udb85\udcde"
    search_placeholder: str = "Search applications..."
    app_icon_size: int = 64
    group_apps: bool = False
    window: WindowConfig = WindowConfig()
    window_animation: WindowAnimationConfig = WindowAnimationConfig()
    window_style: WindowStyleConfig = WindowStyleConfig()
    animation: AnimationConfig = AnimationConfig()
    shortcuts: ShortcutsConfig = ShortcutsConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    app_title_shadow: ShadowConfig = ShadowConfig()
    app_icon_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: LaunchpadCallbacksConfig = LaunchpadCallbacksConfig()

from typing import Literal

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class IconsConfig(CustomBaseModel):
    start: str = "\uead3"
    stop: str = "\uead7"
    reload: str = "\uead2"


class KomorebiMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class KomorebiControlCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"


class KomorebiControlWidgetConfig(CustomBaseModel):
    label: str = "\udb80\uddd9"
    icons: IconsConfig = IconsConfig()
    run_ahk: bool = False
    run_whkd: bool = False
    run_masir: bool = False
    config_path: str | None = None
    show_version: bool = True
    komorebi_menu: KomorebiMenuConfig = KomorebiMenuConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: KomorebiControlCallbacksConfig = KomorebiControlCallbacksConfig()

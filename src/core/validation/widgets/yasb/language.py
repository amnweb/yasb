from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class LanguageMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "system"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    layout_icon: str = "\uf11c"
    show_layout_icon: bool = True


class LanguageCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class LanguageConfig(CustomBaseModel):
    label: str = "{lang[language_code]}-{lang[country_code]}"
    label_alt: str = "{lang[full_name]}"
    update_interval: int = Field(default=5, ge=1, le=3600)
    class_name: str = ""
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    language_menu: LanguageMenuConfig = LanguageMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: LanguageCallbacksConfig = LanguageCallbacksConfig()

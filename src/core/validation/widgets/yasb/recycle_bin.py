from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class RecycleBinIconsConfig(CustomBaseModel):
    bin_empty: str = "\udb82\ude7a"
    bin_filled: str = "\udb82\ude79"


class RecycleBinCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"
    on_right: str = "open_bin"


class RecycleBinConfig(CustomBaseModel):
    label: str = "{icon} {items_count} {items_size}"
    label_alt: str = "{icon} {items_count} {items_size}"
    class_name: str = ""
    icons: RecycleBinIconsConfig = RecycleBinIconsConfig()
    tooltip: bool = True
    show_confirmation: bool = False
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: RecycleBinCallbacksConfig = RecycleBinCallbacksConfig()

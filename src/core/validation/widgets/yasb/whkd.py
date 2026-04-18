from core.validation.widgets.base_model import (
    AnimationConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class WhkdSpecialKeyConfig(CustomBaseModel):
    key: str
    key_replace: str


class WhkdConfig(CustomBaseModel):
    label: str = "\uf11c"
    animation: AnimationConfig = AnimationConfig()
    special_keys: list[WhkdSpecialKeyConfig] = []
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []

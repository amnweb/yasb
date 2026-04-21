from core.validation.widgets.base_model import (
    CustomBaseModel,
    KeybindingConfig,
)


class WhkdSpecialKeyConfig(CustomBaseModel):
    key: str
    key_replace: str


class WhkdConfig(CustomBaseModel):
    label: str = "\uf11c"
    special_keys: list[WhkdSpecialKeyConfig] = []
    keybindings: list[KeybindingConfig] = []

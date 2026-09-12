from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class LockKeysStateLabelsConfig(CustomBaseModel):
    caps_lock_on: str = "CAPS"
    caps_lock_off: str = ""
    num_lock_on: str = "NUM"
    num_lock_off: str = ""


class LockKeysCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class LockKeysConfig(CustomBaseModel):
    label: str = "{caps_lock} {num_lock}"
    label_alt: str = "Caps: {caps_lock} Num: {num_lock}"
    update_interval: int = Field(default=200, ge=50, le=5000)
    class_name: str = ""
    state_labels: LockKeysStateLabelsConfig = LockKeysStateLabelsConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: LockKeysCallbacksConfig = LockKeysCallbacksConfig()

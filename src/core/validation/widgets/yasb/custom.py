from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class ExecOptionsConfig(CustomBaseModel):
    run_cmd: str | None = None
    run_once: bool = False
    run_interval: int = Field(default=120000, ge=0)
    return_format: Literal["string", "json"] = "json"
    hide_empty: bool = False
    use_shell: bool = True
    encoding: str | None = None


class CustomCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class CustomConfig(CustomBaseModel):
    class_name: str
    label: str
    label_alt: str = ""
    label_placeholder: str = "Loading..."
    label_max_length: int | None = Field(default=None, ge=1)
    tooltip: bool = False
    tooltip_label: str | None = None
    exec_options: ExecOptionsConfig = ExecOptionsConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CustomCallbacksConfig = CustomCallbacksConfig()

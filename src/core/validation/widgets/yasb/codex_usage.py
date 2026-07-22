from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class CodexUsageCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_right: str = "toggle_label"


class CodexUsageMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class CodexUsageConfig(CustomBaseModel):
    label: str = "Codex {five_hour}%"
    label_alt: str = "Codex {weekly}%"
    update_interval: int = Field(default=60, ge=30, le=3600)
    cache_ttl: int = Field(default=120, ge=0, le=3600)
    tooltip: bool = True
    callbacks: CodexUsageCallbacksConfig = CodexUsageCallbacksConfig()
    menu: CodexUsageMenuConfig = CodexUsageMenuConfig()
    keybindings: list[KeybindingConfig] = []

from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel, KeybindingConfig


class CodexUsageCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "refresh"
    on_right: str = "toggle_label"


class CodexUsageMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_overview: bool = True
    show_models: bool = True
    show_activity: bool = True
    show_resets: bool = True
    show_details: bool = True
    refresh_icon: str = "\ue72c"
    previous_page_icon: str = "\ue76b"
    next_page_icon: str = "\ue76c"


class CodexUsageProgressBarConfig(CustomBaseModel):
    enabled: bool = True
    progress_type: Literal["circular", "linear_horizontal", "linear_vertical"] = "linear_horizontal"
    size: int = Field(default=36, ge=1, le=200)
    thickness: int = Field(default=6, ge=1, le=100)
    radius: int = Field(default=3, ge=0, le=100)
    color: str | list[str] = "#4caf50"
    background_color: str = "#3c3c3c"
    position: Literal["left", "right"] = "left"
    animation: bool = True


class CodexUsageConfig(CustomBaseModel):
    label: str = "Codex {primary_remaining}%"
    label_alt: str = "Codex {secondary_window} {secondary_remaining}%"
    codex_path: str = "codex"
    update_interval: int = Field(default=60, ge=30, le=3600)
    cache_ttl: int = Field(default=120, ge=0, le=3600)
    timeout: float = Field(default=15.0, ge=1.0, le=60.0)
    tooltip: bool = True
    show_token_usage: bool = True
    stale_icon: str = "⚠"
    progress_bar: CodexUsageProgressBarConfig = CodexUsageProgressBarConfig()
    callbacks: CodexUsageCallbacksConfig = CodexUsageCallbacksConfig()
    menu: CodexUsageMenuConfig = CodexUsageMenuConfig()
    keybindings: list[KeybindingConfig] = []

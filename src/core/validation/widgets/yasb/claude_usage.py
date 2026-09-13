from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class ClaudeUsageCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_right: str = "toggle_label"
    on_middle: str = "do_nothing"


class ClaudeUsageMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    pin_icon: str = "\ue718"
    unpin_icon: str = "\ue77a"


class ClaudeTokenHistoryConfig(CustomBaseModel):
    enabled: bool = False
    default_period: Literal["session", "today", "week", "month", "year"] = "today"
    show_graph: bool = False
    show_graph_grid: bool = False
    show_models: bool = False
    week_starts_on: Literal["monday", "sunday"] = "monday"
    # Cache-read tokens dominate the totals for heavy users; set false for "new work only".
    count_cache_read: bool = True
    scan_interval: int = Field(default=120, ge=30, le=3600)


class ClaudeStatusConfig(CustomBaseModel):
    enabled: bool = False
    show_in_menu: bool = True
    icon: str = "●"  # coloured via .status.<level> CSS classes
    poll_interval: int = Field(default=300, ge=60, le=3600)


class ClaudeUsageProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    progress_type: Literal["circular", "linear_horizontal", "linear_vertical"] = "circular"
    size: int = Field(default=36, ge=1, le=200)
    thickness: int = Field(default=6, ge=1, le=100)
    radius: int = Field(default=3, ge=0, le=100)
    color: str | list[str] = "#4caf50"
    background_color: str = "#3c3c3c"
    position: Literal["left", "right"] = "left"
    animation: bool = True


class ClaudeUsageConfig(CustomBaseModel):
    label: str = "Claude {five_hour}%"
    label_alt: str = "Claude {seven_day}%"
    update_interval: int = Field(default=60, ge=30, le=3600)
    cache_ttl: int = Field(default=120, ge=0, le=3600)
    token_history: ClaudeTokenHistoryConfig = ClaudeTokenHistoryConfig()
    status: ClaudeStatusConfig = ClaudeStatusConfig()
    # Popup reset line per window: "relative" -> "Resets in 4h 11m", "absolute" -> "Resets on Sat @ 6:00 AM".
    five_hour_reset_format: Literal["relative", "absolute"] = "relative"
    seven_day_reset_format: Literal["relative", "absolute"] = "absolute"
    reset_show_date: bool = True
    # Whether {five_hour_value}/{seven_day_value} (and the progress bar) report the share
    # of the window consumed or the share still available. Flipped at runtime by the
    # "toggle_usage_mode" callback. The explicit {*_used}/{*_remaining} placeholders ignore it.
    usage_mode: Literal["used", "remaining"] = "used"
    mode_label_used: str = "used"
    mode_label_remaining: str = "left"
    tooltip: bool = True
    # Tracks whichever window the bar label is currently showing (5h, or 7d after toggle_label).
    progress_bar: ClaudeUsageProgressBarConfig = ClaudeUsageProgressBarConfig()
    callbacks: ClaudeUsageCallbacksConfig = ClaudeUsageCallbacksConfig()
    menu: ClaudeUsageMenuConfig = ClaudeUsageMenuConfig()
    keybindings: list[KeybindingConfig] = []

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


class ClaudeUsageMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class ClaudeTokenHistoryConfig(CustomBaseModel):
    # Reads Claude Code's local session transcripts (~/.claude/projects/**/*.jsonl) to
    # show Session / Today / Week / Month / Year token totals in the popup menu.
    enabled: bool = False
    default_period: Literal["session", "today", "week", "month", "year"] = "today"
    show_graph: bool = False
    show_graph_grid: bool = False
    week_starts_on: Literal["monday", "sunday"] = "monday"
    # Whether cache-read tokens count toward the totals (they dominate for heavy users).
    count_cache_read: bool = True
    scan_interval: int = Field(default=120, ge=30, le=3600)


class ClaudeStatusConfig(CustomBaseModel):
    # Polls the public Claude status page; drives the {status} dot colour
    # (green/yellow/orange/red) and an optional status line in the popup header.
    enabled: bool = False
    show_in_menu: bool = True
    icon: str = "●"  # ● — coloured via .status.<level> CSS classes
    poll_interval: int = Field(default=300, ge=60, le=3600)


class ClaudeUsageConfig(CustomBaseModel):
    label: str = "Claude {five_hour}%"
    label_alt: str = "Claude {seven_day}%"
    update_interval: int = Field(default=60, ge=30, le=3600)
    cache_ttl: int = Field(default=120, ge=0, le=3600)
    token_history: ClaudeTokenHistoryConfig = ClaudeTokenHistoryConfig()
    status: ClaudeStatusConfig = ClaudeStatusConfig()
    # How each window's popup reset line is phrased, per window:
    #   "relative" -> "Resets in 4h 11m" / "Resets in 6d 21h" (countdown)
    #   "absolute" -> "Resets on Sat @ 6:00 AM" (local weekday + time)
    # The near-term 5-hour window defaults to a countdown; the multi-day 7-day window to a date.
    five_hour_reset_format: Literal["relative", "absolute"] = "relative"
    seven_day_reset_format: Literal["relative", "absolute"] = "absolute"
    # Include the month/day in the "absolute" reset line ("Resets on Sat, Jun 13 @ 6:00 AM"),
    # disambiguating windows that reset on the same weekday. No effect on "relative".
    reset_show_date: bool = True
    # Colour the {five_hour}/{seven_day} percentage on the bar by usage level, using the same
    # low/medium/high thresholds as the popup progress bars. Wrap the percent in its own span
    # (e.g. "<span class='percent'>{five_hour}%</span>") so only the number is coloured.
    colorize_percent: bool = False
    tooltip: bool = True
    callbacks: ClaudeUsageCallbacksConfig = ClaudeUsageCallbacksConfig()
    menu: ClaudeUsageMenuConfig = ClaudeUsageMenuConfig()
    keybindings: list[KeybindingConfig] = []

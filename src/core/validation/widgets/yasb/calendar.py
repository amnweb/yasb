from enum import StrEnum

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class Corner(StrEnum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class CalendarIconsConfig(CustomBaseModel):
    meet: str = ""
    zoom: str = ""
    teams: str = ""
    other: str = ""
    none: str = ""
    calendar: str = ""


class CalendarMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    event_count: int = Field(default=5, ge=1, le=20)


class CalendarNotificationDotConfig(CustomBaseModel):
    enabled: bool = True
    corner: Corner = Corner.BOTTOM_LEFT
    color: str = "red"
    margin: list[int] = [1, 1]
    threshold_minutes: int = Field(default=10, ge=0, le=240)


class CalendarCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "join_meeting"
    on_right: str = "toggle_label"


class CalendarConfig(CustomBaseModel):
    label: str = "{icon} {title} {countdown}"
    label_alt: str = "{icon} {title} at {start_time}"
    class_name: str = ""
    update_interval: int = Field(default=60, ge=15, le=3600)
    tick_interval: int = Field(default=1000, ge=250, le=60000)
    calendar_ids: list[str] = Field(default_factory=lambda: ["primary"])
    look_ahead_minutes: int = Field(default=0, ge=0, le=10080)
    grace_period_minutes: int = Field(default=5, ge=0, le=120)
    skip_all_day: bool = True
    max_title_length: int = Field(default=30, ge=5, le=200)
    hide_when_empty: bool = True
    empty_label: str = "No upcoming events"
    auth_label: str = "Calendar: sign in"
    tooltip: bool = True
    tooltip_event_count: int = Field(default=1, ge=1, le=20)
    icons: CalendarIconsConfig = CalendarIconsConfig()
    menu: CalendarMenuConfig = CalendarMenuConfig()
    notification_dot: CalendarNotificationDotConfig = CalendarNotificationDotConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CalendarCallbacksConfig = CalendarCallbacksConfig()

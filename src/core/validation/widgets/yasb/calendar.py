from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class CalendarIconsConfig(CustomBaseModel):
    meet: str = ""
    zoom: str = ""
    teams: str = ""
    other: str = ""
    none: str = ""
    calendar: str = ""


class CalendarCallbacksConfig(CallbacksConfig):
    on_left: str = "join_meeting"
    on_middle: str = "open_event"
    on_right: str = "toggle_label"


class CalendarConfig(CustomBaseModel):
    label: str = "{icon} {title} {countdown}"
    label_alt: str = "{icon} {title} at {start_time}"
    class_name: str = ""
    update_interval: int = Field(default=60, ge=15, le=3600)
    tick_interval: int = Field(default=1000, ge=250, le=60000)
    calendar_ids: list[str] = Field(default_factory=lambda: ["primary"])
    credentials_path: str = "~/.config/yasb/calendar/credentials.json"
    token_path: str = "~/.config/yasb/calendar/token.json"
    look_ahead_minutes: int = Field(default=0, ge=0, le=10080)
    grace_period_minutes: int = Field(default=5, ge=0, le=120)
    skip_all_day: bool = True
    max_title_length: int = Field(default=30, ge=5, le=200)
    tooltip_event_count: int = Field(default=3, ge=1, le=10)
    hide_when_empty: bool = True
    empty_label: str = "No upcoming events"
    auth_label: str = "Calendar: setup needed"
    setup_url: str = "https://github.com/amnweb/yasb/blob/main/docs/widgets/calendar.md"
    tooltip: bool = True
    icons: CalendarIconsConfig = CalendarIconsConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CalendarCallbacksConfig = CalendarCallbacksConfig()

import re
from typing import Any

from pydantic import Field, RootModel

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class ClockCalendarConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    distance: int = 6  # deprecated
    offset_top: int = 6
    offset_left: int = 0
    country_code: str | None = None
    subdivision: str | None = None
    show_holidays: bool = False
    holiday_color: str = "#FF6464"
    show_week_numbers: bool = False
    show_years: bool = False
    extended: bool = False


class ClockAlarmIconsConfig(CustomBaseModel):
    enabled: str = "\uf0f3"
    disabled: str = "\uf0a2"
    snooze: str = "\uf1f6"


class ClockIcons(RootModel[dict[str, str]]):
    root: dict[str, str] = {}

    def model_post_init(self, __context: Any):
        for key in self.root:
            if not re.match(r"^clock_\d{2}$", key):
                raise ValueError(f"Invalid icon key '{key}'. Must match 'clock_XX' where XX is two digits.")


class ClockCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_calendar"
    on_middle: str = "next_timezone"
    on_right: str = "toggle_label"


class ClockConfig(CustomBaseModel):
    label: str = "\uf017 {%H:%M:%S}"
    label_alt: str = "\uf017 {%d-%m-%y %H:%M:%S}"
    class_name: str = ""
    update_interval: int = Field(default=1000, ge=0, le=60000)
    locale: str = ""
    tooltip: bool = True
    timezones: list[str] = []
    icons: dict[str, str] = {}
    alarm_icons: ClockAlarmIconsConfig = ClockAlarmIconsConfig()
    calendar: ClockCalendarConfig = ClockCalendarConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ClockCallbacksConfig = ClockCallbacksConfig()

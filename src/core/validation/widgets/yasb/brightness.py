from datetime import time
from typing import Annotated

from pydantic import Field, WithJsonSchema

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class BrightnessMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    distance: int = 6  # deprecated
    offset_top: int = 6
    offset_left: int = 0


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=18, ge=8, le=64)
    thickness: int = Field(default=3, ge=1, le=10)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: str = "left"
    animation: bool = True


class BrightnessCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class BrightnessConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "Brightness {percent}%"
    tooltip: bool = True
    scroll_step: int = Field(default=1, ge=1, le=100)
    brightness_icons: list[str] = [
        "\udb80\udcde",  # Icon for 0-25% brightness
        "\udb80\udcdd",  # Icon for 26-50% brightness
        "\udb80\udcdf",  # Icon for 51-75% brightness
        "\udb80\udce0",  # Icon for 76-100% brightness
    ]
    brightness_toggle_level: list[int] = []
    brightness_menu: BrightnessMenuConfig = BrightnessMenuConfig()
    hide_unsupported: bool = True  # deprecated
    auto_light: bool = False
    auto_light_icon: str = "\udb80\udce1"
    auto_light_night_level: int = 50
    auto_light_night_start_time: Annotated[time, WithJsonSchema({"type": "string"})] = time(20, 0)
    auto_light_night_end_time: Annotated[time, WithJsonSchema({"type": "string"})] = time(6, 30)
    auto_light_day_level: int = 100
    container_padding: PaddingConfig = PaddingConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: BrightnessCallbacksConfig = BrightnessCallbacksConfig()

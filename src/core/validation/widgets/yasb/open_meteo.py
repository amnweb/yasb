from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class OpenMeteoIconsConfig(CustomBaseModel):
    sunnyDay: str = "\ue30d"
    clearNight: str = "\ue32b"
    cloudyDay: str = "\ue312"
    cloudyNight: str = "\ue311"
    drizzleDay: str = "\udb81\ude7e"
    drizzleNight: str = "\udb81\ude7e"
    rainyDay: str = "\udb81\ude7e"
    rainyNight: str = "\udb81\ude7e"
    snowyDay: str = "\udb81\udd98"
    snowyNight: str = "\udb81\udd98"
    foggyDay: str = "\ue303"
    foggyNight: str = "\ue346"
    thunderstormDay: str = "\ue30f"
    thunderstormNight: str = "\ue338"
    default: str = "\uebaa"


class OpenMeteoCardButtonsConfig(CustomBaseModel):
    enabled: bool = False
    default_view: Literal["temperature", "rain", "snow"] = "temperature"
    snow_icon: str = "\udb81\udd98"
    rain_icon: str = "\udb81\udd96"
    temperature_icon: str = "\udb81\udd99"


class OpenMeteoCardGradientConfig(CustomBaseModel):
    enabled: bool = False
    top_color: str = "#8EAEE8"
    bottom_color: str = "#2A3E68"


class OpenMeteoCardAnimationConfig(CustomBaseModel):
    enabled: bool = False
    snow_overrides_rain: bool = True
    temp_line_animation_style: Literal["rain", "snow", "both", "none"] = "both"
    rain_effect_intensity: float = Field(default=1.0, ge=0.01, le=10.0)
    snow_effect_intensity: float = Field(default=1.0, ge=0.01, le=10.0)
    scale_with_chance: bool = True


class OpenMeteoCardConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    icon_size: int = 64
    show_hourly_forecast: bool = False
    time_format: Literal["12h", "24h"] = "24h"
    hourly_point_spacing: int = 76
    hourly_icon_size: int = Field(default=32, ge=8, le=64)
    icon_smoothing: bool = True
    temp_line_width: int = Field(default=2, ge=0, le=10)
    current_line_color: str = "#8EAEE8"
    current_line_width: int = Field(default=1, ge=0, le=10)
    current_line_style: Literal["solid", "dash", "dot", "dashDot", "dashDotDot"] = "dot"
    hourly_gradient: OpenMeteoCardGradientConfig = OpenMeteoCardGradientConfig()
    hourly_forecast_buttons: OpenMeteoCardButtonsConfig = OpenMeteoCardButtonsConfig()
    weather_animation: OpenMeteoCardAnimationConfig = OpenMeteoCardAnimationConfig()


class OpenMeteoWidgetConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{temp}"
    class_name: str = ""
    update_interval: int = Field(default=3600, ge=60, le=36000000)
    hide_decimal: bool = False
    units: Literal["metric", "imperial"] = "metric"
    tooltip: bool = True
    icons: OpenMeteoIconsConfig = OpenMeteoIconsConfig()
    weather_card: OpenMeteoCardConfig = OpenMeteoCardConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksConfig = CallbacksConfig()

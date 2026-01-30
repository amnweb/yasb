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


class WeatherIconsConfig(CustomBaseModel):
    sunnyDay: str = "\ue30d"
    clearNight: str = "\ue32b"
    cloudyDay: str = "\ue312"
    cloudyNight: str = "\ue311"
    rainyDay: str = "\udb81\ude7e"
    rainyNight: str = "\udb81\ude7e"
    snowyDay: str = "\udb81\udd98"
    snowyNight: str = "\udb81\udd98"
    blizzardDay: str = "\uebaa"
    blizzardNight: str = "\uebaa"
    foggyDay: str = "\ue303"
    foggyNight: str = "\ue346"
    thunderstormDay: str = "\ue30f"
    thunderstormNight: str = "\ue338"
    default: str = "\uebaa"


class WeatherCardButtonsConfig(CustomBaseModel):
    enabled: bool = False
    default_view: Literal["temperature", "rain", "snow"] = "temperature"
    snow_icon: str = "\udb81\udd98"
    rain_icon: str = "\udb81\udd96"
    temperature_icon: str = "\udb81\udd99"


class WeatherCardGradientConfig(CustomBaseModel):
    enabled: bool = False
    top_color: str = "#8EAEE8"
    bottom_color: str = "#2A3E68"


class WeatherCardAnimationConfig(CustomBaseModel):
    enabled: bool = False
    snow_overrides_rain: bool = True
    temp_line_animation_style: Literal["rain", "snow", "both", "none"] = "both"
    rain_effect_intensity: float = Field(default=1.0, ge=0.01, le=10.0)
    snow_effect_intensity: float = Field(default=1.0, ge=0.01, le=10.0)
    scale_with_chance: bool = True
    enable_debug: bool = False


class WeatherCardConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    distance: int = 6  # deprecated
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
    hourly_gradient: WeatherCardGradientConfig = WeatherCardGradientConfig()
    hourly_forecast_buttons: WeatherCardButtonsConfig = WeatherCardButtonsConfig()
    weather_animation: WeatherCardAnimationConfig = WeatherCardAnimationConfig()


class WeatherWidgetConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{temp}"
    class_name: str = ""
    update_interval: int = Field(default=3600, ge=60, le=36000000)
    hide_decimal: bool = False
    location: str = "0"
    api_key: str = "0"
    units: Literal["metric", "imperial"] = "metric"
    show_alerts: bool = False
    tooltip: bool = True
    icons: WeatherIconsConfig = WeatherIconsConfig()
    weather_card: WeatherCardConfig = WeatherCardConfig()
    # Note: reusing AnimationConfig from base_model which matches the structure
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksConfig = CallbacksConfig()

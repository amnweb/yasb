from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class ChargingOptionsConfig(CustomBaseModel):
    icon_format: str = "{charging_icon} {icon}"
    blink_charging_icon: bool = True
    blink_interval: int = Field(default=500, ge=100, le=5000)


class StatusThresholdsConfig(CustomBaseModel):
    critical: int = Field(default=10, ge=0, le=100)
    low: int = Field(default=25, ge=0, le=100)
    medium: int = Field(default=75, ge=0, le=100)
    high: int = Field(default=95, ge=0, le=100)
    full: int = Field(default=100, ge=0, le=100)


class StatusIconsConfig(CustomBaseModel):
    icon_charging: str = "\uf0e7"
    icon_critical: str = "\uf244"
    icon_low: str = "\uf243"
    icon_medium: str = "\uf242"
    icon_high: str = "\uf241"
    icon_full: str = "\uf240"


class CallbacksBatteryConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class BatteryConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{percent}% | remaining: {time_remaining}"
    class_name: str = ""
    update_interval: int = Field(default=5000, ge=0, le=60000)
    time_remaining_natural: bool = False
    hide_unsupported: bool = True
    charging_options: ChargingOptionsConfig = ChargingOptionsConfig()
    status_thresholds: StatusThresholdsConfig = StatusThresholdsConfig()
    status_icons: StatusIconsConfig = StatusIconsConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksBatteryConfig = CallbacksBatteryConfig()

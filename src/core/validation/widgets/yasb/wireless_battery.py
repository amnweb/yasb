from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class WirelessBatteryIconsConfig(CustomBaseModel):
    mouse: str = "\ue962"
    keyboard: str = "\ue765"
    headset: str = "\ue7f6"
    gamepad: str = "\ue7fc"
    phone: str = "\ue8ea"
    microphone: str = "\ue720"
    default: str = "\ue702"
    charging: str = "\ue945"
    disconnected: str = "\ue711"


class WirelessBatteryThresholdsConfig(CustomBaseModel):
    critical: int = Field(default=15, ge=0, le=100)
    low: int = Field(default=30, ge=0, le=100)


class CallbacksWirelessBatteryConfig(CallbacksConfig):
    on_left: str = "refresh"
    on_right: str = "do_nothing"


class WirelessBatteryConfig(CustomBaseModel):
    executable: str = "BatteryHub.exe"
    label: str = "<span>{icon}</span> {percent}%"
    label_charging: str | None = None
    label_unknown: str = "<span>{icon}</span> --"
    label_disconnected: str = "<span>{icon}</span> \u00d7"
    class_name: str = ""
    update_interval: int = Field(default=60000, ge=5000, le=3600000)
    devices: list[str] = []
    kinds: list[str] = []
    show_disconnected: bool = False
    hide_when_empty: bool = True
    sort_by: Literal["name", "kind", "percent"] = "kind"
    icons: WirelessBatteryIconsConfig = WirelessBatteryIconsConfig()
    thresholds: WirelessBatteryThresholdsConfig = WirelessBatteryThresholdsConfig()
    tooltip: bool = True
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksWirelessBatteryConfig = CallbacksWirelessBatteryConfig()

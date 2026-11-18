from typing import Literal

from pydantic import Field, model_validator

from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel, KeybindingConfig


class SensorThresholds(CustomBaseModel):
    warning: float = Field(ge=-100, le=200)
    critical: float = Field(ge=-100, le=200)

    @model_validator(mode="after")
    def ordered(self) -> SensorThresholds:
        if self.warning >= self.critical:
            raise ValueError("warning must be lower than critical")
        return self


class TemperatureMenuConfig(CustomBaseModel):
    enabled: bool = True
    blur: bool = False
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: Literal["left", "center", "right"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    width: int = Field(default=400, ge=360, le=800)
    show_graph: bool = True
    show_graph_grid: bool = False
    pin_icon: str = "\ue718"
    unpin_icon: str = "\ue77a"


class TemperatureCallbacks(CallbacksConfig):
    on_left: str = "toggle_menu"


class TemperatureConfig(CustomBaseModel):
    label: str = "<span>\ue9ca</span>"
    label_alt: str = "<span>\ue9ca</span>"
    class_name: str = ""
    libre_host: str = "127.0.0.1"
    libre_port: int = Field(default=8085, ge=1, le=65535)
    update_interval: int = Field(default=1000, ge=1000, le=60000)
    history_seconds: int = Field(default=120, ge=30, le=3600)
    hardware_labels: dict[str, str] = Field(default_factory=dict)
    thresholds: dict[str, SensorThresholds] = Field(default_factory=dict)
    menu: TemperatureMenuConfig = TemperatureMenuConfig()
    callbacks: TemperatureCallbacks = TemperatureCallbacks()
    keybindings: list[KeybindingConfig] = []

from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class PowerPlanMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "system"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0


class PowerPlanCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "toggle_label"


class PowerPlanConfig(CustomBaseModel):
    label: str = "\uf0e7 {active_plan}"
    label_alt: str = "\uf0e7 Power Plan"
    class_name: str = ""
    update_interval: int = Field(default=5000, ge=0)
    menu: PowerPlanMenuConfig = PowerPlanMenuConfig()
    container_padding: PaddingConfig = PaddingConfig()
    callbacks: PowerPlanCallbacksConfig = PowerPlanCallbacksConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []

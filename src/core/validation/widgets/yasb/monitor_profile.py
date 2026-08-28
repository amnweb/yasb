from typing import Literal

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class MonitorProfileMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "system"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    monitors_section: bool = True


class MonitorProfileCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "toggle_label"


class MonitorProfileConfig(CustomBaseModel):
    label: str = "\uf3e2 {active_profile}"
    label_alt: str = "\uf3e2 Monitor Profile"
    class_name: str = ""
    menu: MonitorProfileMenuConfig = MonitorProfileMenuConfig()
    callbacks: MonitorProfileCallbacksConfig = MonitorProfileCallbacksConfig()
    keybindings: list[KeybindingConfig] = []

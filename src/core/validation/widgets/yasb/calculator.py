from typing import Literal

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class CalculatorMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: Literal["left", "center", "right"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    width: int = 230


class CallbacksCalculatorConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_right: str = "toggle_label"


class CalculatorConfig(CustomBaseModel):
    label: str = "<span>\uf5ec</span>"
    label_alt: str = "Calc"
    class_name: str = ""
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksCalculatorConfig = CallbacksCalculatorConfig()
    menu: CalculatorMenuConfig = CalculatorMenuConfig()

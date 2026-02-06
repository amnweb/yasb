from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CustomBaseModel,
)


class ButtonLabelsConfig(CustomBaseModel):
    minimize: str = "\uea71"
    maximize: str = "\uea71"
    restore: str = "\uea71"
    close: str = "\uea71"


class WindowControlsConfig(CustomBaseModel):
    class_name: str = ""
    show_app_name: bool = False
    maximized_only: bool = True
    buttons: list[Literal["minimize", "maximize", "close"]] = ["minimize", "maximize", "close"]
    button_labels: ButtonLabelsConfig = ButtonLabelsConfig()
    monitor_exclusive: bool = True
    animation_duration: int = Field(default=120, ge=0, le=2000)

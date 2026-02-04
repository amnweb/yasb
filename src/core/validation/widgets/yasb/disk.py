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


class DiskThresholdsConfig(CustomBaseModel):
    low: int = Field(default=25, ge=0, le=100)
    medium: int = Field(default=50, ge=0, le=100)
    high: int = Field(default=90, ge=0, le=100)


class GroupLabelConfig(CustomBaseModel):
    volume_labels: list[str] = ["C"]
    show_label_name: bool = True
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
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
    position: Literal["left", "right"] = "left"
    animation: bool = True


class CallbacksDiskConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class DiskConfig(CustomBaseModel):
    label: str = "{volume_label} {space[used][percent]}"
    label_alt: str = "{volume_label} {space[used][gb]} / {space[total][gb]}"
    class_name: str = ""
    volume_label: str = "C"
    update_interval: int = Field(default=60, ge=0, le=3600)
    decimal_display: int = Field(default=1, ge=0, le=3)
    disk_thresholds: DiskThresholdsConfig = DiskThresholdsConfig()
    group_label: GroupLabelConfig = GroupLabelConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksDiskConfig = CallbacksDiskConfig()

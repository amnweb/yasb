from typing import Literal

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class SpeedThresholdConfig(CustomBaseModel):
    min_upload: int = 1000
    min_download: int = 1000


class MenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "system"
    alignment: str = "left"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_interface_name: bool = True
    show_internet_info: bool = True


class TrafficCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"
    on_middle: str = "do_nothing"
    on_right: str = "do_nothing"


class TrafficWidgetConfig(CustomBaseModel):
    label: str = "\ueb01 \ueab4 {download_speed} | \ueab7 {upload_speed}"
    label_alt: str = "\ueb01 \ueab4 {upload_speed} | \ueab7 {download_speed}"
    class_name: str = ""
    interface: str = "auto"
    update_interval: int = 1000
    hide_if_offline: bool = False
    max_label_length: int = 0
    max_label_length_align: Literal["left", "center", "right"] = "left"
    speed_unit: Literal["bits", "bytes"] = "bits"
    hide_decimal: bool = False
    speed_threshold: SpeedThresholdConfig = SpeedThresholdConfig()
    menu: MenuConfig = MenuConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: TrafficCallbacksConfig = TrafficCallbacksConfig()

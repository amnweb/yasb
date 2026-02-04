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


class IconsConfig(CustomBaseModel):
    normal: str = "\uf130"
    muted: str = "\uf131"


class MicMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "system"
    alignment: str = "right"
    direction: str = "down"
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


class CallbacksMicrophoneConfig(CallbacksConfig):
    on_left: str = "toggle_mic_menu"
    on_middle: str = "toggle_label"
    on_right: str = "toggle_mute"


class MicrophoneConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{icon} {level}%"
    class_name: str = ""
    mute_text: str = "mute"
    tooltip: bool = True
    scroll_step: int = Field(default=2, ge=1, le=100)
    icons: IconsConfig = IconsConfig()
    mic_menu: MicMenuConfig = MicMenuConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksMicrophoneConfig = CallbacksMicrophoneConfig()

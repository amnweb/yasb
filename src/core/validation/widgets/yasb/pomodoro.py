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
    work: str = "\uf252"
    break_: str = Field(default="\uf253", alias="break")
    paused: str = "\uf254"


class MenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    circle_background_color: str = "#09ffffff"
    circle_work_progress_color: str = "#a6e3a1"
    circle_break_progress_color: str = "#89b4fa"
    circle_thickness: int = 8
    circle_size: int = 160


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=18, ge=8, le=64)
    thickness: int = Field(default=3, ge=1, le=10)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: Literal["left", "right"] = "left"
    animation: bool = True


class CallbacksPomodoroConfig(CallbacksConfig):
    on_left: str = "toggle_timer"
    on_middle: str = "reset_timer"
    on_right: str = "toggle_label"


class PomodoroConfig(CustomBaseModel):
    label: str = "\uf252 {remaining}"
    label_alt: str = "{session}/{total_sessions} - {remaining}"
    class_name: str = ""
    work_duration: int = Field(default=25, ge=1)
    break_duration: int = Field(default=5, ge=1)
    long_break_duration: int = Field(default=15, ge=1)
    long_break_interval: int = Field(default=4, ge=1)
    auto_start_breaks: bool = True
    auto_start_work: bool = True
    sound_notification: bool = True
    show_notification: bool = True
    session_target: int = Field(default=0, ge=0)
    hide_on_break: bool = False
    icons: IconsConfig = IconsConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksPomodoroConfig = CallbacksPomodoroConfig()
    menu: MenuConfig = MenuConfig()

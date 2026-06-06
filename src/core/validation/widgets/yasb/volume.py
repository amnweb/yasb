from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class AppIconsConfig(CustomBaseModel):
    toggle_down: str = "\uf078"
    toggle_up: str = "\uf077"


class AudioMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_apps: bool = False
    show_app_labels: bool = False
    show_app_icons: bool = True
    show_apps_expanded: bool = False
    app_icons: AppIconsConfig = AppIconsConfig()


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    progress_type: Literal["circular", "linear_horizontal", "linear_vertical"] = "circular"
    size: int = Field(default=18, ge=1, le=200)
    thickness: int = Field(default=3, ge=1, le=100)
    radius: int = Field(default=0, ge=0, le=100)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: str = "left"
    animation: bool = True


class VolumeCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_volume_menu"
    on_right: str = "toggle_mute"


class VolumeConfig(CustomBaseModel):
    label: str = "{icon} {level}"
    label_alt: str = "{icon} {level}"
    class_name: str = ""
    mute_text: str = "mute"
    tooltip: bool = True
    scroll_step: int = Field(default=2, ge=1, le=100)
    slider_beep: bool = True
    # Support both list and dict for backward compatibility.
    icons: list[str] | dict[str, str] = {
        "muted": "\ueee8",  # Icon for muted
        "10": "\uf026",  # Icon for 0-10% volume
        "30": "\uf027",  # Icon for 11-30% volume
        "60": "\uf027",  # Icon for 31-60% volume
        "100": "\uf028",  # Icon for 61-100% volume
    }
    audio_menu: AudioMenuConfig = AudioMenuConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: VolumeCallbacksConfig = VolumeCallbacksConfig()

from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class MediaMenuIconsConfig(CustomBaseModel):
    play: str = "\ue768"
    pause: str = "\ue769"
    prev_track: str = "\ue892"
    next_track: str = "\ue893"
    shuffle: str = "\ue8b1"
    repeat: str = "\ue8ee"
    repeat_one: str = "\ue8ed"
    volume: str = "\ue767"
    mute: str = "\ue994"


class MediaMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    artwork_background: bool = True
    artwork_blur_radius: int = Field(default=24, ge=0, le=64)
    artwork_dim: float = Field(default=0.85, ge=0.0, le=1.0)
    image_size: int = Field(default=160, ge=32, le=400)
    thumbnail_corner_radius: int = Field(default=12, ge=0, le=200)
    icons: MediaMenuIconsConfig = MediaMenuIconsConfig()


class MediaLiteCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_media_menu"


class MediaLiteWidgetConfig(CustomBaseModel):
    class_name: str = ""
    show_thumbnail: bool = True
    show_title: bool = True
    show_artist: bool = True
    scrolling_label: bool = False
    image_size: int = Field(default=28, ge=12, le=128)
    thumbnail_corner_radius: int = Field(default=6, ge=0, le=100)
    max_label_size: int = Field(default=20, ge=0, le=200)
    tooltip: bool = True
    media_menu: MediaMenuConfig = MediaMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: MediaLiteCallbacksConfig = MediaLiteCallbacksConfig()

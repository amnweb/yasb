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
    prev_track: str = "\uf048"
    next_track: str = "\uf051"
    play: str = "\uf04b"
    pause: str = "\uf04c"


class MediaMenuIconsConfig(CustomBaseModel):
    play: str = "\ue768"
    pause: str = "\ue769"
    prev_track: str = "\ue892"
    next_track: str = "\ue893"
    mute: str = "\ue994"
    unmute: str = "\ue74f"


class MediaMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    thumbnail_size: int = 100
    thumbnail_corner_radius: int = 8
    max_title_size: int = 150
    max_artist_size: int = 40
    show_source: bool = True
    show_volume_slider: bool = False


class ScrollingLabelConfig(CustomBaseModel):
    enabled: bool = False
    update_interval_ms: int = 33
    style: Literal["left", "right", "bounce", "bounce-ease"] = "left"
    always_scroll: bool = False
    separator: str = " "
    label_padding: int = 0
    ease_slope: int = 20
    ease_pos: float = 0.8
    ease_min: float = 0.5


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    alignment: Literal["top", "bottom", "center"] = "bottom"


class MaxFieldSizeConfig(CustomBaseModel):
    label: int = Field(default=15, ge=0, le=200)
    label_alt: int = Field(default=30, ge=0, le=200)
    truncate_whole_label: bool = True


class MediaWidgetConfig(CustomBaseModel):
    label: str = "{title}"
    label_alt: str = "{artist} - {title}"
    separator: str = " - "
    class_name: str = ""
    hide_empty: bool = False
    animation: AnimationConfig = AnimationConfig()
    icons: IconsConfig = IconsConfig()
    media_menu: MediaMenuConfig = MediaMenuConfig()
    media_menu_icons: MediaMenuIconsConfig = MediaMenuIconsConfig()
    container_padding: PaddingConfig = PaddingConfig()
    scrolling_label: ScrollingLabelConfig = ScrollingLabelConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    max_field_size: MaxFieldSizeConfig = MaxFieldSizeConfig()
    show_thumbnail: bool = True
    controls_only: bool = False
    controls_left: bool = True
    controls_hide: bool = False
    thumbnail_alpha: int = Field(default=50, ge=0, le=255)
    thumbnail_padding: int = Field(default=8, ge=0, le=200)
    thumbnail_corner_radius: int = Field(default=0, ge=0, le=100)
    symmetric_corner_radius: bool = False
    thumbnail_edge_fade: bool = False
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksConfig = CallbacksConfig()

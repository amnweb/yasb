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


class GalleryConfig(CustomBaseModel):
    enabled: bool = False
    blur: bool = True
    image_width: int = Field(default=100, ge=32, le=640)
    image_per_page: int = Field(default=5, ge=1, le=64)
    gallery_columns: int = Field(default=0, ge=0, le=64)
    horizontal_position: Literal["left", "center", "right"] = "center"
    vertical_position: Literal["top", "center", "bottom"] = "center"
    position_offset: int | list[int] = Field(default=0, ge=-2000, le=2000)
    respect_work_area: bool = True
    image_corner_radius: int = Field(default=0, ge=0, le=50)
    show_buttons: bool = True
    orientation: Literal["landscape", "portrait"] = "landscape"
    image_spacing: int = Field(default=5, ge=0, le=100)
    lazy_load: bool = True
    lazy_load_fadein: int = Field(default=200, ge=0, le=1000)
    lazy_load_delay: int = Field(default=0, ge=0, le=1000)  # Deprecated
    enable_cache: bool = False  # Deprecated


class CallbacksWallpapersConfig(CallbacksConfig):
    on_left: str = "toggle_gallery"
    on_middle: str = "do_nothing"
    on_right: str = "change_wallpaper"


class WallpapersConfig(CustomBaseModel):
    label: str = "{icon}"
    update_interval: int = Field(default=60, ge=60, le=86400)
    change_automatically: bool = False
    image_path: str | list[str]
    tooltip: bool = True
    run_after: list[str] = []
    gallery: GalleryConfig = GalleryConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksWallpapersConfig = CallbacksWallpapersConfig()

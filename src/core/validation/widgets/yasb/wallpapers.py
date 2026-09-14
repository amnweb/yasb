from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class EngineConfig(CustomBaseModel):
    enabled: bool = False
    animation: Literal["circle", "slide_top", "diamond", "split"] = "circle"


class GalleryConfig(CustomBaseModel):
    type: Literal["default", "magnified", "strip", "slide"] = "default"
    image_width: int = Field(default=100, ge=32, le=640)
    orientation: Literal["landscape", "portrait"] = "landscape"
    image_corner_radius: int = Field(default=0, ge=0, le=50)
    accent_color: str = "auto"


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
    engine: EngineConfig = EngineConfig()
    gallery: GalleryConfig = GalleryConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksWallpapersConfig = CallbacksWallpapersConfig()

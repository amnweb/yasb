from typing import Literal

from pydantic import Field

from core.validation.base_model import CustomBaseModel


class EngineConfig(CustomBaseModel):
    enabled: bool = False
    animation: Literal["circle", "slide_top", "diamond", "split"] = "circle"


class GalleryConfig(CustomBaseModel):
    type: Literal["default", "magnified", "strip", "slide"] = "default"
    image_width: int = Field(default=100, ge=32, le=640)
    orientation: Literal["landscape", "portrait"] = "landscape"
    image_corner_radius: int = Field(default=0, ge=0, le=50)
    accent_color: str = "auto"

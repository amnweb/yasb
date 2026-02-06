from typing import Literal

from pydantic import Field, field_validator

from core.validation.widgets.base_model import CustomBaseModel


class BarAlignment(CustomBaseModel):
    position: Literal["top", "bottom"] = "top"
    center: bool = False  # deprecated
    align: Literal["left", "center", "right"] = "center"


class BarBlurEffect(CustomBaseModel):
    enabled: bool = False
    dark_mode: bool = False
    acrylic: bool = False
    round_corners: bool = False
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"


class BarAnimation(CustomBaseModel):
    enabled: bool = True
    duration: int = Field(default=500, ge=0)
    type: Literal["slide", "fade"] = "slide"


class BarWindowFlags(CustomBaseModel):
    always_on_top: bool = False
    windows_app_bar: bool = False
    hide_on_fullscreen: bool = False
    hide_on_maximized: bool = False
    auto_hide: bool = False


class BarDimensions(CustomBaseModel):
    width: str | int = "100%"
    height: int = Field(default=30, ge=0)

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: str | int) -> str | int:
        if isinstance(v, int):
            if v < 0:
                raise ValueError("Width must be non-negative")
            return v
        if v == "auto":
            return v
        if v.endswith("%") and v[:-1].isdigit():
            return v
        raise ValueError("Width must be an integer, 'auto', or a percentage string (e.g. '100%')")


class BarPadding(CustomBaseModel):
    top: int = 0
    left: int = 0
    bottom: int = 0
    right: int = 0


class BarWidgets(CustomBaseModel):
    left: list[str] = []
    center: list[str] = []
    right: list[str] = []


class BarLayout(CustomBaseModel):
    alignment: Literal["left", "center", "right"] = "left"
    stretch: bool = True


class BarLayouts(CustomBaseModel):
    left: BarLayout = BarLayout(alignment="left")
    center: BarLayout = BarLayout(alignment="center")
    right: BarLayout = BarLayout(alignment="right")


class BarConfig(CustomBaseModel):
    enabled: bool = True
    screens: list[str] = ["*"]
    class_name: str = "yasb-bar"
    context_menu: bool = True
    alignment: BarAlignment = BarAlignment()
    blur_effect: BarBlurEffect = BarBlurEffect()
    animation: BarAnimation = BarAnimation()
    window_flags: BarWindowFlags = BarWindowFlags()
    dimensions: BarDimensions = BarDimensions()
    padding: BarPadding = BarPadding()
    widgets: BarWidgets = BarWidgets()
    layouts: BarLayouts = BarLayouts()

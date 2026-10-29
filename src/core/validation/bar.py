from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from core.validation.base_model import CustomBaseModel

NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"

type WidgetName = Annotated[str, StringConstraints(pattern=NAME_PATTERN)]
type SlotName = Annotated[str, StringConstraints(pattern=NAME_PATTERN)]


class BarMargin(CustomBaseModel):
    top: int = 0
    left: int = 0
    bottom: int = 0
    right: int = 0


class BarAnimation(CustomBaseModel):
    type: Literal["none", "slide", "fade"] = "slide"
    duration: int = Field(default=500, ge=0)


class BarConfig(CustomBaseModel):
    enabled: bool = True
    file: str | None = Field(default=None, min_length=1)
    screens: list[str] = ["*"]
    edge: Literal["top", "bottom", "left", "right"] = "top"
    align: Literal["left", "center", "right", "top", "bottom"] = "center"
    length: str | int = "100%"
    thickness: int = Field(default=30, ge=0)
    margin: BarMargin = BarMargin()
    reserve_space: bool = False
    always_on_top: bool = False
    hide_on_fullscreen: bool = False
    auto_hide: Literal["never", "always", "maximized"] = "never"
    backdrop: bool = False
    animation: BarAnimation = BarAnimation()
    widgets: dict[SlotName, list[WidgetName]] = {}

    @property
    def vertical(self) -> bool:
        return self.edge in ("left", "right")

    @field_validator("length")
    @classmethod
    def validate_length(cls, v: str | int) -> str | int:
        if isinstance(v, int):
            if v < 0:
                raise ValueError("Length must be non-negative")
            return v
        if v == "auto":
            return v
        if v.endswith("%") and v[:-1].isdigit():
            return v
        raise ValueError("Length must be an integer, 'auto', or a percentage string (e.g. '100%')")

    @model_validator(mode="after")
    def validate_align(self) -> Self:
        allowed = ("top", "center", "bottom") if self.vertical else ("left", "center", "right")
        if self.align not in allowed:
            raise ValueError(f"Align must be {', '.join(allowed)} on a bar at the {self.edge} edge")
        return self

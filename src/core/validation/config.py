from typing import Self

from pydantic import Field, model_validator

from core.validation.bar import BarConfig
from core.validation.base_model import CustomBaseModel


class YasbConfig(CustomBaseModel):
    watch: bool = True
    debug: bool = False
    update_check: bool = True
    theme: str | None = Field(default=None, min_length=1)
    bars: dict[str, BarConfig] = {"yasb-bar": BarConfig()}

    @model_validator(mode="after")
    def apply_theme(self) -> Self:
        for bar in self.bars.values():
            bar.theme = bar.theme or self.theme
        return self

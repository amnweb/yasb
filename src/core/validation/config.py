from typing import Self

from pydantic import Field, model_validator

from core.validation.bar import BarConfig
from core.validation.base_model import CustomBaseModel


class KomorebiConfig(CustomBaseModel):
    start_command: str | None = None
    stop_command: str | None = None
    reload_command: str | None = None


class GlazeWMConfig(CustomBaseModel):
    start_command: str | None = None
    stop_command: str | None = None
    reload_command: str | None = None


class YasbConfig(CustomBaseModel):
    watch: bool = True
    debug: bool = False
    update_check: bool = True
    show_systray: bool = True
    komorebi: KomorebiConfig = KomorebiConfig()
    glazewm: GlazeWMConfig = GlazeWMConfig()
    theme: str | None = Field(default=None, min_length=1)
    bars: dict[str, BarConfig] = {"yasb-bar": BarConfig()}

    @model_validator(mode="after")
    def apply_theme(self) -> Self:
        for bar in self.bars.values():
            bar.theme = bar.theme or self.theme
        return self

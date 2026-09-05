from typing import Literal

from pydantic import Field, field_validator, model_validator

from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel, KeybindingConfig

DEFAULT_COLORS = ["#74c7ec", "#89b4fa", "#cba6f7"]


class BarsStyleConfig(CustomBaseModel):
    count: int = Field(default=24, ge=4, le=128)
    width: int = Field(default=2, ge=1, le=32)
    gap: int = Field(default=4, ge=0, le=32)


class WavesStyleConfig(CustomBaseModel):
    width: int = Field(default=80, ge=16, le=512)


class DotsStyleConfig(CustomBaseModel):
    count: int = Field(default=24, ge=4, le=128)
    size: int = Field(default=2, ge=1, le=32)
    gap: int = Field(default=4, ge=0, le=32)


class AudioVisualizerConfig(CustomBaseModel):
    class_name: str = ""
    style: Literal["bars", "waves", "dots"] = "bars"
    height: int = Field(default=14, ge=4, le=64)
    smoothness: int = Field(default=55, ge=0, le=100)
    sensitivity: int = Field(default=50, ge=0, le=100)
    auto_gain: bool = True
    framerate: int = Field(default=60, ge=1, le=120)
    freq_min: int = Field(default=50, ge=20, le=24000)
    freq_max: int = Field(default=12000, ge=20, le=24000)
    hide_idle: bool = False
    hide_idle_after: int = Field(default=2000, ge=100, le=60000)
    channels: Literal["stereo", "mono"] = "mono"
    mono_option: Literal["average", "left", "right"] = "average"
    reverse: bool = False
    gradient: bool = True
    mirror: bool = False
    colors: list = Field(default=DEFAULT_COLORS)
    edge_fade: int | list[int] = 0
    bars: BarsStyleConfig = Field(default_factory=BarsStyleConfig)
    waves: WavesStyleConfig = Field(default_factory=WavesStyleConfig)
    dots: DotsStyleConfig = Field(default_factory=DotsStyleConfig)
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksConfig = CallbacksConfig()

    @field_validator("colors")
    @classmethod
    def _validate_colors(cls, value: list[str]) -> list[str]:
        cleaned = [c.strip() for c in value if isinstance(c, str) and c.strip()]
        return cleaned or list(DEFAULT_COLORS)

    @field_validator("edge_fade")
    @classmethod
    def _validate_edge_fade(cls, value: int | list[int]) -> int | list[int]:
        if isinstance(value, list):
            if len(value) != 2:
                raise ValueError("edge_fade must be a single number, or a [left, right] list of exactly two")
            return [max(0, int(value[0])), max(0, int(value[1]))]
        return max(0, int(value))

    @model_validator(mode="after")
    def _validate_freq_range(self) -> AudioVisualizerConfig:
        if self.freq_min >= self.freq_max:
            raise ValueError("freq_min must be less than freq_max")
        return self

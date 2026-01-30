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


class MemoryThresholdsConfig(CustomBaseModel):
    low: int = Field(default=25, ge=0, le=100)
    medium: int = Field(default=50, ge=0, le=100)
    high: int = Field(default=90, ge=0, le=100)


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=18, ge=8, le=64)
    thickness: int = Field(default=3, ge=1, le=10)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: Literal["left", "right"] = "left"
    animation: bool = True


class CallbacksMemoryConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class MemoryConfig(CustomBaseModel):
    label: str = "\uf4bc {virtual_mem_free}/{virtual_mem_total}"
    label_alt: str = "\uf4bc VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%"
    class_name: str = ""
    update_interval: int = Field(default=5000, ge=1000, le=60000)
    histogram_icons: list[str] = Field(
        default=["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"],
        min_length=9,
        max_length=9,
    )
    hide_decimal: bool = False
    memory_thresholds: MemoryThresholdsConfig = MemoryThresholdsConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksMemoryConfig = CallbacksMemoryConfig()

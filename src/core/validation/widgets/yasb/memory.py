from typing import Literal

from pydantic import Field, model_validator
from PyQt6.QtGui import QColor

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class MemoryThresholdsConfig(CustomBaseModel):
    low: int = Field(default=25, ge=0, le=100)
    medium: int = Field(default=50, ge=0, le=100)
    high: int = Field(default=90, ge=0, le=100)


class MemoryProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    progress_type: Literal["circular", "linear_horizontal", "linear_vertical"] = "circular"
    size: int = Field(default=18, ge=1, le=200)
    thickness: int = Field(default=3, ge=1, le=100)
    radius: int = Field(default=0, ge=0, le=100)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: Literal["left", "right"] = "left"
    animation: bool = True


class CallbacksMemoryConfig(CallbacksConfig):
    on_left: str = "toggle_label"
    on_right: str = "do_nothing"


class MemoryGraphColorsConfig(CustomBaseModel):
    enabled: bool = False
    warning_threshold: float = Field(default=70, ge=0, le=100)
    critical_threshold: float = Field(default=90, ge=0, le=100)
    normal: str = "#53ce87"
    warning: str = "#e6bc50"
    critical: str = "#f06464"

    @model_validator(mode="after")
    def check_bands(self) -> MemoryGraphColorsConfig:
        if self.warning_threshold >= self.critical_threshold:
            raise ValueError("warning_threshold must be lower than critical_threshold")
        if any(not QColor(color).isValid() for color in (self.normal, self.warning, self.critical)):
            raise ValueError("Graph colors must be valid Qt color names or hex colors")
        return self


class MemoryMenuConfig(CustomBaseModel):
    enabled: bool = False
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: Literal["left", "center", "right"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    graph_history_size: int = Field(default=60, ge=10, le=180)
    show_graph: bool = True
    show_graph_grid: bool = False
    show_graph_fill: bool = True
    show_hardware_details: bool = False
    show_swap_total: bool = False
    highlight_usage: bool = False
    show_usage_bar: bool = False
    graph_colors: MemoryGraphColorsConfig = MemoryGraphColorsConfig()
    pin_icon: str = "\ue718"
    unpin_icon: str = "\ue77a"


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
    progress_bar: MemoryProgressBarConfig = MemoryProgressBarConfig()
    menu: MemoryMenuConfig = MemoryMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksMemoryConfig = CallbacksMemoryConfig()

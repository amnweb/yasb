from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class CpuThresholdsConfig(CustomBaseModel):
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


class CallbacksCpuConfig(CallbacksConfig):
    on_left: str = "toggle_label"
    on_right: str = "do_nothing"


class CpuMenuConfig(CustomBaseModel):
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
    pin_icon: str = "\ue718"
    unpin_icon: str = "\ue77a"


class CpuConfig(CustomBaseModel):
    label: str = "\uf200 {info[histograms][cpu_percent]}"
    label_alt: str = "\uf200 CPU: {info[percent][total]}% | freq: {info[freq][current]:.2f} Mhz"
    class_name: str = ""
    update_interval: int = Field(default=1000, ge=1000, le=60000)
    histogram_icons: list[str] = Field(
        default=[
            "\u2581",
            "\u2581",
            "\u2582",
            "\u2583",
            "\u2584",
            "\u2585",
            "\u2586",
            "\u2587",
            "\u2588",
        ],
        min_length=9,
        max_length=9,
    )
    histogram_num_columns: int = Field(default=10, ge=0, le=128)
    hide_decimal: bool = False
    cpu_thresholds: CpuThresholdsConfig = CpuThresholdsConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksCpuConfig = CallbacksCpuConfig()
    menu: CpuMenuConfig = CpuMenuConfig()

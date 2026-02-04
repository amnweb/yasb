from typing import Literal

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
)


class CavaCallbacksConfig(CallbacksConfig):
    on_right: str = "reload_cava"


class CavaConfig(CustomBaseModel):
    class_name: str = ""
    bar_height: int = 20
    min_bar_height: int = 1
    bars_number: int = 10
    output_bit_format: str = "16bit"
    orientation: Literal["top", "bottom"] = "bottom"
    bar_spacing: int = 1
    bar_width: int = 3
    sleep_timer: int = 0
    sensitivity: int = 100
    lower_cutoff_freq: int = 50
    higher_cutoff_freq: int = 10000
    framerate: int = 60
    noise_reduction: float = 0.77
    channels: str = "stereo"
    mono_option: str = "average"
    reverse: int = 0
    waveform: int = 0
    foreground: str = "#ffffff"
    gradient: int = 1
    gradient_color_1: str | None = None
    gradient_color_2: str | None = None
    gradient_color_3: str | None = None
    monstercat: int = 0
    waves: int = 0
    hide_empty: bool = False
    bar_type: Literal["bars", "bars_mirrored", "waves", "waves_mirrored"] = "bars"
    edge_fade: int | list[int] = 0
    container_padding: PaddingConfig = PaddingConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CavaCallbacksConfig = CavaCallbacksConfig()

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
)


class LyricsPopupConfig(CustomBaseModel):
    width: int = Field(default=420, ge=200, le=1200)
    height: int = Field(default=520, ge=200, le=1000)
    alignment: Literal["left", "center", "right"] = "center"
    direction: Literal["up", "down"] = "down"
    offset_left: int = 0
    offset_top: int = Field(default=6, ge=0)
    font_scale: float = Field(default=1.0, ge=0.5, le=3.0)
    romanize: bool = True
    background_style: Literal["ambient", "blur", "gradient", "inherit", "black"] = "ambient"
    progress_style: Literal["line", "wave"] = "line"  # wave: thicker bar with a moving album-coloured wave


class LyricsVisualizerOptions(CustomBaseModel):
    """Look and behaviour of the instrumental-break visualizer (bars, waves, ...).

    The beat effects (beat_jump, sparkles) do not depend on any of these.
    """

    bars_number: int | None = Field(default=None, ge=4, le=32)  # None: 10 bars / 14 wave points
    bar_width: float = Field(default=3.0, ge=1.0, le=20.0)
    bar_spacing: float = Field(default=2.0, ge=0.0, le=30.0)
    bar_radius: float = Field(default=1.5, ge=0.0, le=10.0)
    bar_height: int | None = Field(default=None, ge=4, le=100)  # None: follows the font height
    min_bar_height: int | None = Field(default=None, ge=1, le=50)  # None: follows the font height
    # bars / waves / notes / dots only. Top flips bars and waves. Mirrored styles and "none" stay centred.
    vertical_alignment: Literal["top", "middle", "bottom"] = "middle"
    layout: Literal["linear", "mirrored"] = "linear"  # mirrored: bass in the centre, symmetrical stereo layout
    reverse: bool = False
    noise_reduction: int = Field(default=65, ge=0, le=100)  # higher = smoother, slower fall-off
    monstercat: float = Field(default=1.0, ge=0.0, le=5.0)  # 0 = off; higher = more neighbour spread
    sensitivity: int = Field(default=100, ge=10, le=200)  # trim on top of auto gain
    lower_cutoff_freq: int = Field(default=50, ge=20, le=1000)
    higher_cutoff_freq: int = Field(default=10000, ge=1000, le=20000)
    framerate: int = Field(default=60, ge=15, le=120)

    @model_validator(mode="after")
    def _validate_options(self) -> LyricsVisualizerOptions:
        if self.lower_cutoff_freq >= self.higher_cutoff_freq:
            raise ValueError("lower_cutoff_freq must be less than higher_cutoff_freq")
        if self.bar_height is not None and self.min_bar_height is not None and self.min_bar_height >= self.bar_height:
            raise ValueError("min_bar_height must be less than bar_height")
        return self


class LyricsCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_popup"
    on_right: str = "toggle_menu"


class LyricsWidgetConfig(CustomBaseModel):
    class_name: str = ""
    max_width: int | None = Field(default=None, ge=10)
    fixed_width: int | None = Field(default=None, ge=40, le=1200)
    line_transition: Literal["none", "slide_up", "scale", "wipe"] = "slide_up"
    font_scale: float = Field(default=1.0, ge=0.5, le=3.0)
    visualizer: Literal["bars", "bars_mirrored", "waves", "waves_mirrored", "notes", "dots", "none"] | bool | None = (
        None
    )
    visualizer_options: LyricsVisualizerOptions = LyricsVisualizerOptions()
    sparkles: bool | Literal["on", "off"] = True
    apply_accent_to: Literal["effects", "all", "nothing"] = "effects"
    accent: Literal["album_art", "yasb"] = "album_art"
    beat_jump: bool | Literal["on", "off"] = True
    romanize_replace: bool = False
    hide_when_paused: bool | int | float = False
    hide_when_no_lyrics: bool = False
    popup: LyricsPopupConfig = LyricsPopupConfig()
    callbacks: LyricsCallbacksConfig = LyricsCallbacksConfig()

from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class GifPlayerCallbacksConfig(CallbacksConfig):
    on_left: str = "do_nothing"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_popup"


class GifPlayerPopupConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "None"
    alignment: Literal["left", "center", "right"] = "center"
    direction: Literal["down", "up"] = "down"
    icons_per_row: int = Field(default=4, ge=1, le=12, description="Number of columns in the GIF picker grid")
    offset_top: int = Field(default=6, description="Top offset in pixels")
    offset_left: int = Field(default=0, description="Left offset in pixels")


class GifPlayerConfig(CustomBaseModel):
    id: str = Field(
        default="",
        description="Unique identifier to synchronize state across multiple bar instances",
    )
    gif_folder: str = Field(
        default="",
        description="Path to folder containing .gif files for quick switching via the popup grid",
    )
    gif_path: str = Field(
        default="",
        description="Path to default/initial .gif file",
    )
    folder_icon: str = Field(
        default="",
        description="Path to custom folder icon for the 'Open Folder' tile in the popup",
    )
    icon_size: int = Field(
        default=22,
        ge=8,
        le=128,
        description="Height in pixels for the GIF animation on the bar",
    )
    icons_per_row: int = Field(
        default=4,
        ge=1,
        le=12,
        description="Fallback columns in the popup grid if not specified in popup config",
    )
    speed_percent: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Animation playback speed percentage (100 = 1x, 200 = 2x, 50 = 0.5x)",
    )
    tooltip: bool = Field(
        default=True,
        description="Whether to show tooltip when hovering over the GIF",
    )
    tooltip_text: str = Field(
        default="{name}",
        description="Custom tooltip template format string ({name}, {width}, {height})",
    )
    class_name: str = Field(
        default="gif-widget",
        description="CSS class name for styling the widget",
    )
    popup: GifPlayerPopupConfig = Field(default_factory=GifPlayerPopupConfig)
    callbacks: GifPlayerCallbacksConfig = Field(default_factory=GifPlayerCallbacksConfig)
    keybindings: list[KeybindingConfig] = Field(default_factory=list)


# Backward compatibility alias
GifWidgetConfig = GifPlayerConfig

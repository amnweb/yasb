from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class SalahTimesMenuConfig(CustomBaseModel):
    """Appearance of the click-through popup (location chooser + editor)."""

    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0


class SalahTimesWidgetConfig(CustomBaseModel):
    label: str = "<span></span> {compact}"
    label_alt: str = "{list_inline}"
    label_placeholder: str = "Loading salah times..."
    class_name: str = "salah-times-widget"
    # How often the label refreshes (seconds). Salah times only change slowly,
    # but the countdown ("time left") is recomputed each tick.
    update_interval: int = Field(default=10, ge=1, le=3600)
    time_format: Literal["12h", "24h"] = "12h"
    show_sunnah_times: bool = True
    tooltip: bool = True
    # Optional path override for the persisted locations/state file. When empty
    # the widget stores data in %LOCALAPPDATA%/YASB/salah_times.json.
    data_file: str = ""
    menu: SalahTimesMenuConfig = SalahTimesMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksConfig = CallbacksConfig(on_left="toggle_menu", on_right="toggle_label")

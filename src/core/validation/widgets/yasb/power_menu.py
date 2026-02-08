from typing import Literal

from pydantic import Field

from core.validation.utilities import PreserveOrderMixin
from core.validation.widgets.base_model import (
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class PowerMenuButtonsConfig(PreserveOrderMixin, CustomBaseModel):
    lock: list[str] | None = None
    signout: list[str] | None = None
    sleep: list[str] | None = None
    restart: list[str]
    shutdown: list[str]
    cancel: list[str]
    hibernate: list[str] | None = None
    force_shutdown: list[str] | None = None
    force_restart: list[str] | None = None


class PowerMenuPopupConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class PowerMenuConfig(CustomBaseModel):
    label: str = "power"
    uptime: bool = True
    show_user: bool = False
    blur: bool = False
    blur_background: bool = True
    animation_duration: int = Field(default=200, ge=0, le=2000)
    button_row: int = Field(default=3, ge=1, le=6)
    menu_style: Literal["fullscreen", "popup"] = "fullscreen"
    popup: PowerMenuPopupConfig = PowerMenuPopupConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    buttons: PowerMenuButtonsConfig

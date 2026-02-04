from pydantic import Field

from core.validation.widgets.base_model import (
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class PowerMenuButtonsConfig(CustomBaseModel):
    lock: list[str] | None = None
    signout: list[str] | None = None
    sleep: list[str] | None = None
    restart: list[str]
    shutdown: list[str]
    cancel: list[str]
    hibernate: list[str] | None = None
    force_shutdown: list[str] | None = None
    force_restart: list[str] | None = None


class PowerMenuConfig(CustomBaseModel):
    label: str = "power"
    uptime: bool = True
    blur: bool = False
    blur_background: bool = True
    animation_duration: int = Field(default=200, ge=0, le=2000)
    button_row: int = Field(default=3, ge=1, le=5)
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    buttons: PowerMenuButtonsConfig

import logging

from pydantic import Field, field_validator

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)

logger = logging.getLogger("deprecation")


class ServerEntryConfig(CustomBaseModel):
    name: str
    url: str


class DesktopNotificationsConfig(CustomBaseModel):
    ssl: bool = False
    offline: bool = False


class MenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class IconsConfig(CustomBaseModel):
    online: str = "\uf444"
    offline: str = "\uf4c3"
    warning: str = "\uf4c3"
    reload: str = "\udb81\udc50"


class ServerMonitorCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class ServerMonitorConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{online}/{offline} of {total} servers"
    update_interval: int = Field(default=300, ge=10, le=36000)
    tooltip: bool = True
    servers: list[ServerEntryConfig] = []
    ssl_check: bool = True
    ssl_verify: bool = True
    ssl_warning: int = Field(default=30, ge=1, le=365)

    @field_validator("servers", mode="before")
    @classmethod
    def _migrate_servers(cls, v: list) -> list:
        # TODO: Remove this migration code in a future major release after users migrate to the new format.
        if not isinstance(v, list) or not v:
            return v
        if isinstance(v[0], str):
            logger.warning(
                "ServerMonitorConfig: 'servers' format has changed."
                " Use list of {name: ..., url: ...} instead of plain strings."
            )
            return [{"name": s, "url": s} for s in v if s]
        return v

    desktop_notifications: DesktopNotificationsConfig = DesktopNotificationsConfig()
    timeout: int = Field(default=5, ge=1, le=30)
    menu: MenuConfig = MenuConfig()
    icons: IconsConfig = IconsConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ServerMonitorCallbacksConfig = ServerMonitorCallbacksConfig()

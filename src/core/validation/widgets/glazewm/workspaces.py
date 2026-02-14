from core.validation.widgets.base_model import CustomBaseModel, PaddingConfig, ShadowConfig


class AppIconsConfig(CustomBaseModel):
    enabled_populated: bool = False
    enabled_active: bool = False
    enabled_focused: bool | None = None
    size: int = 16
    max_icons: int = 0
    hide_label: bool = False
    hide_duplicates: bool = False
    hide_floating: bool = False


class GlazewmWorkspacesConfig(CustomBaseModel):
    offline_label: str = "GlazeWM Offline"
    populated_label: str | None = None
    empty_label: str | None = None
    active_populated_label: str | None = None
    active_empty_label: str | None = None
    focused_populated_label: str | None = None
    focused_empty_label: str | None = None
    hide_empty_workspaces: bool = True  # deprecated
    hide_if_offline: bool = False
    monitor_exclusive: bool = True
    glazewm_server_uri: str = "ws://localhost:6123"
    enable_scroll_switching: bool = True
    reverse_scroll_direction: bool = False
    container_shadow: ShadowConfig = ShadowConfig()
    btn_shadow: ShadowConfig = ShadowConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_padding: PaddingConfig = PaddingConfig()
    app_icons: AppIconsConfig = AppIconsConfig()
    animation: bool = False

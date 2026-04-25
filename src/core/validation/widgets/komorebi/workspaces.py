from core.validation.widgets.base_model import CustomBaseModel


class ToggleWorkspaceLayerConfig(CustomBaseModel):
    enabled: bool = False
    tiling_label: str = "Tiling"
    floating_label: str = "Floating"


class AppIconsConfig(CustomBaseModel):
    enabled_populated: bool = False
    enabled_active: bool = False
    size: int = 16
    max_icons: int = 0
    hide_label: bool = False
    hide_duplicates: bool = False
    hide_floating: bool = False


class KomorebiWorkspacesConfig(CustomBaseModel):
    label_offline: str = "Komorebi Offline"
    label_workspace_btn: str = "{index}"
    label_workspace_active_btn: str = "{index}"
    label_workspace_populated_btn: str = "{index}"
    label_default_name: str = ""
    label_float_override: str = "Override Active"
    toggle_workspace_layer: ToggleWorkspaceLayerConfig = ToggleWorkspaceLayerConfig()
    hide_if_offline: bool = False
    label_zero_index: bool = False
    hide_empty_workspaces: bool = False
    app_icons: AppIconsConfig = AppIconsConfig()
    enable_scroll_switching: bool = False
    reverse_scroll_direction: bool = False

from core.validation.widgets.base_model import CustomBaseModel, PaddingConfig, ShadowConfig


class ShellwrightWorkspacesConfig(CustomBaseModel):
    label_offline: str = "SW"
    label_workspace_btn: str = ""
    label_workspace_active_btn: str = ""
    label_workspace_populated_btn: str = ""
    # 0-based index of the monitor this bar lives on.
    # -1 (default) = auto-detect from Qt screen API.
    # Override only if auto-detection gives the wrong monitor.
    monitor_index: int = -1
    # Optional remapping when Qt screen order != shellwright monitor order.
    # Index = Qt screen index, value = shellwright monitor index.
    # Example: [2, 0, 1] means Qt screen 0 → shellwright mon 2, etc.
    # Empty list (default) = use Qt screen index directly.
    monitor_index_remap: list[int] = []
    hide_if_offline: bool = False
    hide_empty_workspaces: bool = False
    show_layout: bool = False
    label_layout: str = "[{layout}]"
    container_padding: PaddingConfig = PaddingConfig()
    btn_shadow: ShadowConfig = ShadowConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()

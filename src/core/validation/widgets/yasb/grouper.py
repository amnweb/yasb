from core.validation.widgets.base_model import (
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class GrouperCollapseOptions(CustomBaseModel):
    enabled: bool = False
    exclude_widgets: list[str] = []
    expanded_label: str = "\uf054"
    collapsed_label: str = "\uf053"
    label_position: str = "right"


class GrouperWidgetConfig(CustomBaseModel):
    class_name: str = "grouper"
    widgets: list[str] = []
    hide_empty: bool = False
    container_padding: PaddingConfig = PaddingConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    collapse_options: GrouperCollapseOptions = GrouperCollapseOptions()
    keybindings: list[KeybindingConfig] = []

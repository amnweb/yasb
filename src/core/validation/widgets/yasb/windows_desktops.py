from core.validation.widgets.base_model import (
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class WindowsDesktopsConfig(CustomBaseModel):
    label_workspace_btn: str = "{index}"
    label_workspace_active_btn: str = "{index}"
    switch_workspace_animation: bool = True
    animation: bool = False
    btn_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    container_padding: PaddingConfig = PaddingConfig()
    keybindings: list[KeybindingConfig] = []

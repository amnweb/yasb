from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class WindowsDesktopsCallbacksConfig(CallbacksConfig):
    on_left: str = "activate_workspace"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_context_menu"


class WindowsDesktopsConfig(CustomBaseModel):
    label_workspace_btn: str = "{index}"
    label_workspace_active_btn: str = "{index}"
    callbacks: WindowsDesktopsCallbacksConfig = WindowsDesktopsCallbacksConfig()
    keybindings: list[KeybindingConfig] = []

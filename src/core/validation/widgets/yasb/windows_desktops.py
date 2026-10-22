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
    label_workspace_populated_btn: str | None = None
    enable_scroll_switching: bool = False
    reverse_scroll_direction: bool = False
    callbacks: WindowsDesktopsCallbacksConfig = WindowsDesktopsCallbacksConfig()
    keybindings: list[KeybindingConfig] = []

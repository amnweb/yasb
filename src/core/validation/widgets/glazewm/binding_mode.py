from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class GlazewmBindingModeCallbacksConfig(CallbacksConfig):
    on_left: str = "next_binding_mode"
    on_middle: str = "toggle_label"
    on_right: str = "disable_binding_mode"


class GlazewmBindingModeConfig(CustomBaseModel):
    label: str = "<span>{icon}</span> {binding_mode}"
    label_alt: str = "<span>{icon}</span> Current mode: {binding_mode}"
    glazewm_server_uri: str = "ws://localhost:6123"
    hide_if_no_active: bool = True
    label_if_no_active: str = "No binding mode active"
    default_icon: str = "\uf071"
    icons: dict[str, str] = {
        "none": "",
        "resize": "\uf071",
        "pause": "\uf28c",
    }
    binding_modes_to_cycle_through: list[str] = [
        "none",
        "resize",
        "pause",
    ]
    container_shadow: ShadowConfig = ShadowConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: GlazewmBindingModeCallbacksConfig = GlazewmBindingModeCallbacksConfig()

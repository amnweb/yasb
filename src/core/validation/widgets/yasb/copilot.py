from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class CopilotIconsConfig(CustomBaseModel):
    copilot: str = "\uf4b8"
    error: str = "\uf4b9"


class CopilotThresholdsConfig(CustomBaseModel):
    warning: int = 75
    critical: int = 90


class CopilotMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    chart: bool = True


class CopilotCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_popup"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class CopilotConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{used}/{allowance}"
    token: str = ""
    plan: str = "pro"
    tooltip: bool = True
    update_interval: int = 3600
    icons: CopilotIconsConfig = CopilotIconsConfig()
    thresholds: CopilotThresholdsConfig = CopilotThresholdsConfig()
    menu: CopilotMenuConfig = CopilotMenuConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CopilotCallbacksConfig = CopilotCallbacksConfig()

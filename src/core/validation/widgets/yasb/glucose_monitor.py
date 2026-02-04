from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class DirectionIconsConfig(CustomBaseModel):
    double_up: str = "\u2b06\ufe0f\u2b06\ufe0f"
    single_up: str = "\u2b06\ufe0f"
    forty_five_up: str = "\u2197\ufe0f"
    flat: str = "\u27a1\ufe0f"
    forty_five_down: str = "\u2198\ufe0f"
    single_down: str = "\u2b07\ufe0f"
    double_down: str = "\u2b07\ufe0f\u2b07\ufe0f"


class SgvRangeConfig(CustomBaseModel):
    min: float = 4.0
    max: float = 9.0


class CallbacksGlucoseMonitorConfig(CallbacksConfig):
    on_left: str = "open_cgm"
    on_middle: str = "do_nothing"
    on_right: str = "do_nothing"


class GlucoseMonitorConfig(CustomBaseModel):
    label: str = "<span>\U0001fa78<span><span class='sgv'>{sgv}</span><span>{direction}</span>"
    error_label: str = "<span>\U0001fa78</span>{error_message}"
    tooltip: str = "({sgv_delta}) {delta_time_in_minutes} min"
    host: str = ""
    secret: str = ""
    secret_env_name: str = ""
    direction_icons: DirectionIconsConfig = DirectionIconsConfig()
    sgv_measurement_units: str = "mmol/l"
    callbacks: CallbacksGlucoseMonitorConfig = CallbacksGlucoseMonitorConfig()
    notify_on_error: bool = True
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    sgv_range: SgvRangeConfig = SgvRangeConfig()
    keybindings: list[KeybindingConfig] = []

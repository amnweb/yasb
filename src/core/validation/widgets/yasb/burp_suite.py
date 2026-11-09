from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class BurpSuiteIconsConfig(CustomBaseModel):
    offline: str = "\U000f099c"  # nf-md-shield_off_outline
    running: str = "\U000f0499"  # nf-md-shield_outline
    ready: str = "\U000f0565"  # nf-md-shield_check


class BurpSuiteStatusTextConfig(CustomBaseModel):
    offline: str = "Offline"
    running: str = "Running"
    ready: str = "REST Ready"


class BurpSuiteRestApiConfig(CustomBaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=1337, ge=1, le=65535)


class BurpSuiteCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"
    on_right: str = "do_nothing"


class BurpSuiteConfig(CustomBaseModel):
    label: str = "<span>{icon}</span> {status}"
    label_alt: str = "<span>{icon}</span> Burp {edition}"
    update_interval: int = Field(default=5, ge=1, le=3600)
    rest_api: BurpSuiteRestApiConfig = BurpSuiteRestApiConfig()
    icons: BurpSuiteIconsConfig = BurpSuiteIconsConfig()
    status_text: BurpSuiteStatusTextConfig = BurpSuiteStatusTextConfig()
    hide_when_offline: bool = False
    tooltip: bool = True
    callbacks: BurpSuiteCallbacksConfig = BurpSuiteCallbacksConfig()
    keybindings: list[KeybindingConfig] = []

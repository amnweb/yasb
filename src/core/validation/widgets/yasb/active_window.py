from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class RewriteConfig(CustomBaseModel):
    pattern: str
    replacement: str
    case: Literal["lower", "upper", "title", "capitalize"] | None = None


class IgnoreWindowConfig(CustomBaseModel):
    classes: list[str] = []
    processes: list[str] = []
    titles: list[str] = []


class ActiveWindowCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class ActiveWindowConfig(CustomBaseModel):
    label: str = "{win[title]}"
    label_alt: str = "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]"
    class_name: str = ""
    label_no_window: str | None = None
    label_icon: bool = True
    label_icon_size: int = 16
    max_length: int | None = Field(default=None, gt=0)
    max_length_ellipsis: str = "..."
    monitor_exclusive: bool = True
    rewrite: list[RewriteConfig] = []
    animation: AnimationConfig = AnimationConfig()
    ignore_window: IgnoreWindowConfig = IgnoreWindowConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ActiveWindowCallbacksConfig = ActiveWindowCallbacksConfig()

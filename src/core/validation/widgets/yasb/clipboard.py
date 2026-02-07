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


class ClipboardMenuConfig(CustomBaseModel):
    """Configuration for the clipboard popup menu."""

    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "System"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    max_item_length: int = Field(default=50, ge=10, le=200)


class ClipboardIconsConfig(CustomBaseModel):
    """Configuration for clipboard widget icons."""

    clipboard: str = "\udb80\udd4d"
    clear: str = "\uf1f8"
    search_clear: str = "\uf00d"


class ClipboardCallbacksConfig(CallbacksConfig):
    """Callbacks configuration with clipboard-specific defaults."""

    on_left: str = "toggle_menu"
    on_right: str = "toggle_label"


class ClipboardConfig(CustomBaseModel):
    """Main configuration model for the Clipboard widget."""

    label: str = "<span>\udb80\udd4d</span> {clipboard}"
    label_alt: str = "{clipboard}"
    class_name: str = ""
    max_length: int = Field(default=30, ge=5, le=100)
    max_history: int = Field(default=50, ge=10, le=500)
    menu: ClipboardMenuConfig = ClipboardMenuConfig()
    icons: ClipboardIconsConfig = ClipboardIconsConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ClipboardCallbacksConfig = ClipboardCallbacksConfig()

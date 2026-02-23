from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
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
    tooltip_enabled: bool = True
    tooltip_delay: int = Field(default=400, ge=0, le=2000)
    tooltip_position: Literal["top", "bottom"] = "bottom"
    show_image_thumbnail: bool = True
    image_replacement_text: str = "[Image]"
    show_image_list_info: bool = True
    image_info_position: Literal["right", "left"] = "right"


class ClipboardIconsConfig(CustomBaseModel):
    """Configuration for clipboard widget icons."""

    clear_icon: str = "\uf1f8"
    delete_icon: str = "\uf1f8"


class ClipboardCallbacksConfig(CallbacksConfig):
    """Callbacks configuration with clipboard-specific defaults."""

    on_left: str = "toggle_menu"
    on_right: str = "toggle_label"


class ClipboardConfig(CustomBaseModel):
    """Main configuration model for the Clipboard widget."""

    label: str = "<span>\udb80\udd4d</span>"
    label_alt: str = "CLIPBOARD"
    class_name: str = ""
    copied_feedback: str = "\uf00c"
    max_history: int = Field(default=50, ge=10, le=500)
    menu: ClipboardMenuConfig = ClipboardMenuConfig()
    icons: ClipboardIconsConfig = ClipboardIconsConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ClipboardCallbacksConfig = ClipboardCallbacksConfig()

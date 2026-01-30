from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class ChatConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "system"
    alignment: Literal["left", "right", "center"] = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0


class IconsConfig(CustomBaseModel):
    send: str = "\uf1d8"
    stop: str = "\uf04d"
    clear: str = "\uf1f8"
    assistant: str = "\udb81\ude74"
    attach: str = "\uf0c6"
    float_on: str = "\udb84\udcac"
    float_off: str = "\udb84\udca9"
    close: str = "\uf00d"
    copy_icon: str = Field(default="\uebcc", alias="copy")
    copy_check: str = "\uf00c"


class NotificationDotConfig(CustomBaseModel):
    enabled: bool = True
    corner: Literal["top_left", "top_right", "bottom_left", "bottom_right"] = "bottom_left"
    color: str = "red"
    margin: list[int] = [1, 1]


class AiChatCallbacksConfig(CustomBaseModel):
    on_left: Literal["toggle_chat", "do_nothing"] = "toggle_chat"
    on_middle: Literal["toggle_chat", "do_nothing"] = "do_nothing"
    on_right: Literal["toggle_chat", "do_nothing"] = "do_nothing"


class ModelConfig(CustomBaseModel):
    name: str
    label: str
    default: bool = False
    max_tokens: int = 0
    temperature: float = 0.7
    top_p: float = 0.95
    max_image_size: int = Field(default=0, ge=0)
    max_attachment_size: int = Field(default=256, ge=0)
    instructions: str | None = None


class ProviderConfig(CustomBaseModel):
    provider: str
    provider_type: Literal["openai", "copilot"] = "openai"
    api_endpoint: str | None = None
    credential: str | None = None
    models: list[ModelConfig] = []
    copilot_cli_url: str | None = None


class AiChatConfig(CustomBaseModel):
    label: str = "AI Chat"
    chat: ChatConfig = ChatConfig()
    icons: IconsConfig = IconsConfig()
    notification_dot: NotificationDotConfig = NotificationDotConfig()
    start_floating: bool = True
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    callbacks: AiChatCallbacksConfig = AiChatCallbacksConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    providers: list[ProviderConfig]

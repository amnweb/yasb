from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class WifiMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    wifi_icons_secured: list[str] = [
        "\ue670",
        "\ue671",
        "\ue672",
        "\ue673",
    ]
    wifi_icons_unsecured: list[str] = [
        "\uec3c",
        "\uec3d",
        "\uec3e",
        "\uec3f",
    ]


class WifiCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class WifiConfig(CustomBaseModel):
    label: str = "{wifi_icon}"
    label_alt: str = "{wifi_icon} {wifi_name}"
    update_interval: int = Field(default=1000, ge=0, le=60000)
    class_name: str = ""
    wifi_icons: list[str] = [
        "\udb82\udd2e",
        "\udb82\udd1f",
        "\udb82\udd22",
        "\udb82\udd25",
        "\udb82\udd28",
    ]
    ethernet_label: str = "{wifi_icon}"
    ethernet_label_alt: str = "{wifi_icon} {ip_addr}"
    ethernet_icon: str = "\ueba9"
    get_exact_wifi_strength: bool = False
    hide_if_ethernet: bool = False
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: WifiCallbacksConfig = WifiCallbacksConfig()
    menu_config: WifiMenuConfig = WifiMenuConfig()

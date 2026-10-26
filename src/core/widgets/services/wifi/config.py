from core.validation.base_model import CustomBaseModel


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
        "",
        "",
        "",
        "",
    ]
    wifi_icons_unsecured: list[str] = [
        "",
        "",
        "",
        "",
    ]

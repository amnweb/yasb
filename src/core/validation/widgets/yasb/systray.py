from pydantic import Field

from core.validation.widgets.base_model import CustomBaseModel, PaddingConfig, ShadowConfig


class SystrayPopupConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class SystrayWidgetConfig(CustomBaseModel):
    class_name: str = "systray"
    label_collapsed: str = "▼"
    label_expanded: str = "▶"
    label_position: str = "left"
    icon_size: int = Field(default=16, ge=8, le=64)
    pin_click_modifier: str = "alt"
    show_unpinned: bool = True
    show_unpinned_button: bool = True
    show_in_popup: bool = False
    icons_per_row: int = Field(default=5, ge=1, le=12)
    popup: SystrayPopupConfig = SystrayPopupConfig()
    show_battery: bool = False
    show_volume: bool = False
    show_network: bool = False
    tooltip: bool = True
    container_padding: PaddingConfig = PaddingConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    unpinned_shadow: ShadowConfig = ShadowConfig()
    pinned_shadow: ShadowConfig = ShadowConfig()
    unpinned_vis_btn_shadow: ShadowConfig = ShadowConfig()
    btn_shadow: ShadowConfig = ShadowConfig()

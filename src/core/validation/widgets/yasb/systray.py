from pydantic import Field

from core.validation.widgets.base_model import CustomBaseModel, PaddingConfig, ShadowConfig


class SystrayWidgetConfig(CustomBaseModel):
    class_name: str = "systray"
    label_collapsed: str = "▼"
    label_expanded: str = "▶"
    label_position: str = "left"
    icon_size: int = Field(default=16, ge=8, le=64)
    pin_click_modifier: str = "alt"
    show_unpinned: bool = True
    show_unpinned_button: bool = True
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

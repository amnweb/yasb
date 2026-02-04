from core.validation.widgets.base_model import (
    AnimationConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class ActiveLayoutIconsConfig(CustomBaseModel):
    bsp: str = "[\\]"
    columns: str = "[||]"
    rows: str = "[==]"
    grid: str = "[G]"
    scrolling: str = "[SC]"
    vertical_stack: str = "[V]="
    horizontal_stack: str = "[H]="
    ultrawide_vertical_stack: str = "||="
    right_main_vertical_stack: str = "=||"
    monocle: str = "[M]"
    maximized: str = "[X]"
    maximised: str = "[X]"  # deprecated, use "maximized" instead
    floating: str = "><>"
    paused: str = "[P]"
    tiling: str = "[T]"


class ActiveLayoutMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "left"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_layout_icons: bool = True


class ActiveLayoutCallbacksConfig(CustomBaseModel):
    on_left: str = "next_layout"
    on_middle: str = "toggle_monocle"
    on_right: str = "prev_layout"


class ActiveLayoutConfig(CustomBaseModel):
    hide_if_offline: bool = False
    label: str = "{icon}"
    layouts: list[str] = [
        "bsp",
        "columns",
        "rows",
        "grid",
        "scrolling",
        "vertical_stack",
        "horizontal_stack",
        "ultrawide_vertical_stack",
        "right_main_vertical_stack",
        "monocle",
        "maximized",
        "floating",
        "paused",
        "tiling",
    ]
    layout_icons: ActiveLayoutIconsConfig = ActiveLayoutIconsConfig()
    layout_menu: ActiveLayoutMenuConfig = ActiveLayoutMenuConfig()
    container_padding: PaddingConfig = PaddingConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: ActiveLayoutCallbacksConfig = ActiveLayoutCallbacksConfig()

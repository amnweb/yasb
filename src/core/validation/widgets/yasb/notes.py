from pydantic import ConfigDict, Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class MenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    max_title_size: int = 150
    show_date_time: bool = True


class IconsConfig(CustomBaseModel):
    model_config = ConfigDict(populate_by_name=True)

    note: str = "\udb82\udd0c"
    delete: str = "\ueab8"
    copy_icon: str = Field(default="\uebcc", alias="copy")


class NotesCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class NotesConfig(CustomBaseModel):
    label: str = "<span>\udb82\udd0c</span> {count}"
    label_alt: str = "{count} notes"
    class_name: str = ""
    data_path: str = ""
    container_padding: PaddingConfig = PaddingConfig()
    animation: AnimationConfig = AnimationConfig()
    menu: MenuConfig = MenuConfig()
    icons: IconsConfig = IconsConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: NotesCallbacksConfig = NotesCallbacksConfig()

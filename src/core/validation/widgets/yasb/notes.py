from pydantic import ConfigDict, Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class NotesMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_date_time: bool = True


class NotesIconsConfig(CustomBaseModel):
    model_config = ConfigDict(populate_by_name=True)
    note: str = "\ue70b"
    delete: str = "\ue74d"
    copy_icon: str = Field(default="\ue8c8", alias="copy")
    float_on: str = "\ue922"
    float_off: str = "\ue923"
    close: str = "\ue8bb"


class NotesCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class NotesConfig(CustomBaseModel):
    label: str = "<span>\udb82\udd0c</span> {count}"
    label_alt: str = "{count} notes"
    class_name: str = ""
    data_path: str = ""
    start_floating: bool = False
    paste_plain_text: bool = False
    enter_to_add_note: bool = True
    menu: NotesMenuConfig = NotesMenuConfig()
    icons: NotesIconsConfig = NotesIconsConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: NotesCallbacksConfig = NotesCallbacksConfig()

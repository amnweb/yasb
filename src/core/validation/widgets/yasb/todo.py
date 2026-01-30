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


class CategoryConfig(CustomBaseModel):
    label: str


class IconsConfig(CustomBaseModel):
    add: str = "New Task"
    edit: str = "Edit"
    delete: str = "Delete"
    date: str = "\ue641"
    category: str = "\uf412"
    checked: str = "\udb80\udd34"
    unchecked: str = "\udb80\udd30"
    sort: str = "\ueab4"
    no_tasks: str = "\uf4a0"


class MenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: Literal["normal", "small"] = "normal"
    border_color: str = "system"
    alignment: str = "left"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class CallbacksTodoConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class TodoConfig(CustomBaseModel):
    label: str = "\uf4a0 {count}/{completed}"
    label_alt: str = "\uf4a0 Tasks: {count}"
    data_path: str = ""
    container_padding: PaddingConfig = PaddingConfig()
    animation: AnimationConfig = AnimationConfig()
    menu: MenuConfig = MenuConfig()
    icons: IconsConfig = IconsConfig()
    categories: dict[str, CategoryConfig] = Field(
        default={
            "default": CategoryConfig(label="General"),
            "urgent": CategoryConfig(label="Urgent"),
            "important": CategoryConfig(label="Important"),
            "soon": CategoryConfig(label="Complete soon"),
            "today": CategoryConfig(label="End of day"),
        }
    )
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksTodoConfig = CallbacksTodoConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()

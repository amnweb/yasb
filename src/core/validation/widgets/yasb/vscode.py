from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class VSCodeMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    distance: int = 6  # deprecated
    offset_top: int = 6
    offset_left: int = 0


class CallbacksVSCodeConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class VSCodeConfig(CustomBaseModel):
    label: str = "<span>\udb82\ude1e</span>"
    label_alt: str = "<span>\udb82\ude1e</span> recents"
    menu_title: str = "<span style='font-weight:bold'>VScode</span> recents"
    folder_icon: str = "\uf114"
    file_icon: str = "\uf016"
    hide_folder_icon: bool = False
    hide_file_icon: bool = False
    truncate_to_root_dir: bool = False
    max_number_of_folders: int = Field(default=30, ge=0)
    max_number_of_files: int = Field(default=30, ge=0)
    max_field_size: int = Field(default=100, ge=1)
    state_storage_path: str = ""
    modified_date_format: str = "Date modified: %Y-%m-%d %H:%M"
    cli_command: str = "code"
    menu: VSCodeMenuConfig = VSCodeMenuConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksVSCodeConfig = CallbacksVSCodeConfig()

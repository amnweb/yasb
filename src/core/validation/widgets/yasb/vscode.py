from typing import Any

from pydantic import Field, model_validator

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class VSCodeMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class CallbacksVSCodeConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class VSCodeIconsConfig(CustomBaseModel):
    folder: str = "\uf114"
    file: str = "\uf016"
    remote: str = ""


class VSCodeConfig(CustomBaseModel):
    label: str = "<span>\udb82\ude1e</span>"
    label_alt: str = "<span>\udb82\ude1e</span> recents"
    menu_title: str = "<span style='font-weight:bold'>VS code</span> recents"
    icons: VSCodeIconsConfig = VSCodeIconsConfig()
    truncate_to_root_dir: bool = False
    max_number_of_folders: int = Field(default=30, ge=0)
    max_number_of_files: int = Field(default=30, ge=0)
    state_storage_path: str = ""
    modified_date_format: str = "Date modified: %Y-%m-%d %H:%M"
    cli_command: str = "code"
    menu: VSCodeMenuConfig = VSCodeMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksVSCodeConfig = CallbacksVSCodeConfig()

    @model_validator(mode="before")
    @classmethod
    def migrate_old_icon_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        icons_data = data.setdefault("icons", {})
        if not isinstance(icons_data, dict):
            icons_data = {}
            data["icons"] = icons_data

        if "folder_icon" in data:
            icons_data.setdefault("folder", data["folder_icon"])
        if "file_icon" in data:
            icons_data.setdefault("file", data["file_icon"])
        if data.get("hide_folder_icon") is True:
            icons_data["folder"] = ""
        if data.get("hide_file_icon") is True:
            icons_data["file"] = ""

        return data

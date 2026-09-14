from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import CustomBaseModel


class LeopardWMAppIconsConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=16, ge=8, le=64)
    max_icons: int = Field(default=0, ge=0, le=100)
    hide_label: bool = False
    hide_duplicates: bool = False
    hide_floating: bool = False
    monochrome: bool = False
    mode: Literal["native", "glyph"] = "native"
    glyphs: dict[str, str] = {}
    fallback_icon: str = "\ue8a5"


class LeopardWMWorkspacesConfig(CustomBaseModel):
    lwm_path: str = "lwm.exe"
    monitor: str | None = None
    monitor_exclusive: bool = True
    label_workspace_btn: str = "{index}"
    label_workspace_active_btn: str = "{index}"
    label_workspace_populated_btn: str = "{index}"
    label_offline: str = "LeopardWM Offline"
    show_inactive_workspaces: bool = True
    hide_empty_workspaces: bool = False
    hide_if_offline: bool = False
    enable_scroll_switching: bool = True
    reverse_scroll_direction: bool = False
    app_icons: LeopardWMAppIconsConfig = LeopardWMAppIconsConfig()

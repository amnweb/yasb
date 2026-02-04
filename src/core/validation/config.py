from typing import Any

from core.validation.bar import BarConfig
from core.validation.widgets.base_model import CustomBaseModel


class KomorebiConfig(CustomBaseModel):
    start_command: str | None = "komorebic start --whkd"
    stop_command: str | None = "komorebic stop --whkd"
    reload_command: str | None = "komorebic reload-configuration"


class GlazeWMConfig(CustomBaseModel):
    start_command: str | None = "glazewm.exe start"
    stop_command: str | None = "glazewm.exe command wm-exit"
    reload_command: str | None = "glazewm.exe command wm-exit && glazewm.exe start"


class YasbConfig(CustomBaseModel):
    watch_config: bool = True
    watch_stylesheet: bool = True
    debug: bool = False
    # env_file is deprecated and will be removed in the future
    # Use load .env file from the config folder instead
    env_file: str | None = None
    update_check: bool = True
    show_systray: bool = True
    komorebi: KomorebiConfig = KomorebiConfig()
    glazewm: GlazeWMConfig = GlazeWMConfig()
    bars: dict[str, BarConfig] = {"yasb-bar": BarConfig()}
    widgets: dict[str, str | dict[str, Any]] = {}

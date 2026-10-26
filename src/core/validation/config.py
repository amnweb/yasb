from core.validation.bar import BarConfig
from core.validation.base_model import CustomBaseModel


class KomorebiConfig(CustomBaseModel):
    start_command: str | None = None
    stop_command: str | None = None
    reload_command: str | None = None


class GlazeWMConfig(CustomBaseModel):
    start_command: str | None = None
    stop_command: str | None = None
    reload_command: str | None = None


class YasbConfig(CustomBaseModel):
    watch: bool = True
    debug: bool = False
    update_check: bool = True
    show_systray: bool = True
    komorebi: KomorebiConfig = KomorebiConfig()
    glazewm: GlazeWMConfig = GlazeWMConfig()
    bars: dict[str, BarConfig] = {"yasb-bar": BarConfig()}

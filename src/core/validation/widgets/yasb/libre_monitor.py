from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class LibreMenuSensorConfig(CustomBaseModel):
    id: str
    name: str | None = None


class LibreMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    header_label: str = "YASB HW Monitor"
    precision: int = 2
    columns: int = 1
    sensors: list[LibreMenuSensorConfig] = []


class LibreMonitorCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class LibreMonitorConfig(CustomBaseModel):
    class_name: str = "libre-monitor-widget"
    label: str = "<span>\udb82\udcae </span> {info[value]}{info[unit]}"
    label_alt: str = "<span>\uf437 </span>{info[histogram]} {info[value]} ({info[min]}/{info[max]}) {info[unit]}"
    update_interval: int = Field(default=1000, ge=0, le=60000)
    sensor_id: str = "/amdcpu/0/load/0"
    histogram_icons: list[str] = Field(
        default_factory=lambda: [
            r"\u2581",
            r"\u2581",
            r"\u2582",
            r"\u2583",
            r"\u2584",
            r"\u2585",
            r"\u2586",
            r"\u2587",
            r"\u2588",
        ],
        min_length=9,
        max_length=9,
    )
    histogram_num_columns: int = Field(default=10, ge=0, le=128)
    precision: int = Field(default=2, ge=0, le=30)
    history_size: int = Field(default=60, ge=0, le=50000)
    histogram_fixed_min: float | None = Field(default=None, ge=-10000.0, le=10000.0)
    histogram_fixed_max: float | None = Field(default=None, ge=-10000.0, le=10000.0)
    sensor_id_error_label: str = "N/A"
    connection_error_label: str = "Connection error..."
    auth_error_label: str = "Auth Failed..."
    server_host: str = "localhost"
    server_port: int = Field(default=8085, ge=0, le=65535)
    server_username: str = ""
    server_password: str = ""
    callbacks: LibreMonitorCallbacksConfig = LibreMonitorCallbacksConfig()
    libre_menu: LibreMenuConfig = LibreMenuConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    container_padding: PaddingConfig = PaddingConfig()
    animation: AnimationConfig = AnimationConfig()
    keybindings: list[KeybindingConfig] = []

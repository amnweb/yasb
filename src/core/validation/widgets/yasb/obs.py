from core.validation.widgets.base_model import CustomBaseModel, KeybindingConfig, PaddingConfig


class ObsIconsConfig(CustomBaseModel):
    recording: str = "\ueba7"
    stopped: str = "\ueba7"
    paused: str = "\ueba7"
    virtual_cam_on: str = "\udb81\udda0"
    virtual_cam_off: str = "\udb81\udda0"
    studio_mode_on: str = "\udb84\uddd8"
    studio_mode_off: str = "\udb84\uddd8"
    streaming: str = "\udb82\udd02"
    streaming_stopped: str = "\udb82\udd02"


class ObsConnectionConfig(CustomBaseModel):
    host: str = "localhost"
    port: int = 4455
    password: str = ""


class ObsConfig(CustomBaseModel):
    icons: ObsIconsConfig = ObsIconsConfig()
    connection: ObsConnectionConfig = ObsConnectionConfig()
    hide_when_not_recording: bool = False
    blinking_icon: bool = True
    show_record_time: bool = False
    show_virtual_cam: bool = False
    show_studio_mode: bool = False
    show_stream: bool = False
    show_stream_time: bool = False
    show_scene_name: bool = False
    show_stream_stats: bool = False
    tooltip: bool = True
    container_padding: PaddingConfig = PaddingConfig()
    keybindings: list[KeybindingConfig] = []

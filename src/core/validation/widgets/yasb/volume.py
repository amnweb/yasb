from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class AppIconsConfig(CustomBaseModel):
    toggle_down: str = "\uf078"
    toggle_up: str = "\uf077"


class AudioMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    distance: int = 6  # deprecated
    offset_top: int = 6
    offset_left: int = 0
    show_apps: bool = False
    show_app_labels: bool = False
    show_app_icons: bool = True
    show_apps_expanded: bool = False
    app_icons: AppIconsConfig = AppIconsConfig()


class ProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=18, ge=8, le=64)
    thickness: int = Field(default=3, ge=1, le=10)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: str = "left"
    animation: bool = True


class VolumeCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_volume_menu"
    on_right: str = "toggle_mute"


class VolumeConfig(CustomBaseModel):
    label: str = "{volume[percent]}%"
    label_alt: str = "{volume[percent]}%"
    class_name: str = ""
    mute_text: str = "mute"
    tooltip: bool = True
    scroll_step: int = Field(default=2, ge=1, le=100)
    slider_beep: bool = True
    volume_icons: list[str] = [
        "\ueee8",  # Icon for muted
        "\uf026",  # Icon for 0-10% volume
        "\uf027",  # Icon for 11-30% volume
        "\uf027",  # Icon for 31-60% volume
        "\uf028",  # Icon for 61-100% volume
    ]
    audio_menu: AudioMenuConfig = AudioMenuConfig()
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    progress_bar: ProgressBarConfig = ProgressBarConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: VolumeCallbacksConfig = VolumeCallbacksConfig()

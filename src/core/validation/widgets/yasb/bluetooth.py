from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class BluetoothIconsConfig(CustomBaseModel):
    bluetooth_on: str = "\udb80\udcaf"
    bluetooth_off: str = "\udb80\udcb2"
    bluetooth_connected: str = "\udb80\udcb1"


class BluetoothDeviceAliasConfig(CustomBaseModel):
    name: str
    alias: str


class BluetoothCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"


class BluetoothConfig(CustomBaseModel):
    label: str = "\udb80\udcb1"
    label_alt: str = "\uf293"
    class_name: str = ""
    label_no_device: str = "No devices connected"
    label_device_separator: str = ", "
    max_length: int | None = None
    max_length_ellipsis: str = "..."
    tooltip: bool = True
    icons: BluetoothIconsConfig = BluetoothIconsConfig()
    device_aliases: list[BluetoothDeviceAliasConfig] = []
    animation: AnimationConfig = AnimationConfig()
    container_padding: PaddingConfig = PaddingConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: BluetoothCallbacksConfig = BluetoothCallbacksConfig()

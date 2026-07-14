from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class BluetoothIconsConfig(CustomBaseModel):
    bluetooth_on: str = "\ue702"
    bluetooth_off: str = "\ue702"
    bluetooth_connected: str = "\ue702"


class BluetoothBatteryIconsConfig(CustomBaseModel):
    empty: str = "\ueba0"
    low: str = "\ueba2"
    medium: str = "\ueba5"
    high: str = "\ueba8"
    full: str = "\uebaa"


class BluetoothDeviceIconsConfig(CustomBaseModel):
    headphones: str = "\ue7f6"
    headset: str = "\ue95b"
    speaker: str = "\ue7f5"
    phone: str = "\ue8ea"
    tablet: str = "\ue70a"
    laptop: str = "\ue7f8"
    computer: str = "\ue950"
    keyboard: str = "\ue765"
    mouse: str = "\ue962"
    controller: str = "\ue7fc"
    watch: str = "\ue918"
    camera: str = "\ue722"
    generic: str = "\ue702"
    battery: BluetoothBatteryIconsConfig = BluetoothBatteryIconsConfig()
    refresh: str = "\ue72c"


class BluetoothDeviceAliasConfig(CustomBaseModel):
    name: str
    alias: str


class BluetoothLabelsConfig(CustomBaseModel):
    title: str = "Bluetooth"
    your_devices: str = "Your devices"
    new_devices: str = "New devices"
    not_connected: str = "Not connected"
    connected: str = "Connected"
    more_settings: str = "More Bluetooth settings"
    connect: str = "Connect"
    disconnect: str = "Disconnect"
    connecting: str = "Connecting"
    disconnecting: str = "Disconnecting"
    pair: str = "Pair"
    manage: str = "Manage"
    power_on: str = "On"
    power_off: str = "Off"


class BluetoothMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    labels: BluetoothLabelsConfig = BluetoothLabelsConfig()
    device_icons: BluetoothDeviceIconsConfig = BluetoothDeviceIconsConfig()


class BluetoothCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"


class BluetoothConfig(CustomBaseModel):
    label: str = "\ue702"
    label_alt: str = "\ue702"
    class_name: str = ""
    label_no_device: str = "No devices connected"
    label_device_separator: str = ", "
    max_length: int | None = None
    max_length_ellipsis: str = "..."
    tooltip: bool = True
    icons: BluetoothIconsConfig = BluetoothIconsConfig()
    device_aliases: list[BluetoothDeviceAliasConfig] = []
    keybindings: list[KeybindingConfig] = []
    callbacks: BluetoothCallbacksConfig = BluetoothCallbacksConfig()
    menu_config: BluetoothMenuConfig = BluetoothMenuConfig()

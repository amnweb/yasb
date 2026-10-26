from core.validation.base_model import CustomBaseModel


class BluetoothBatteryIconsConfig(CustomBaseModel):
    empty: str = ""
    low: str = ""
    medium: str = ""
    high: str = ""
    full: str = ""


class BluetoothDeviceIconsConfig(CustomBaseModel):
    headphones: str = ""
    headset: str = ""
    speaker: str = ""
    phone: str = ""
    tablet: str = ""
    laptop: str = ""
    computer: str = ""
    keyboard: str = ""
    mouse: str = ""
    controller: str = ""
    watch: str = ""
    camera: str = ""
    generic: str = ""
    battery: BluetoothBatteryIconsConfig = BluetoothBatteryIconsConfig()
    scan: str = ""


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

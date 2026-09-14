import ctypes
import uuid
from ctypes import wintypes
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

from winrt.windows.devices.bluetooth import (
    BluetoothLEAppearanceCategories,
    BluetoothLEAppearanceSubcategories,
    BluetoothMinorClass,
)

# BluetoothAdapter interface (BluetoothAdapter.get_device_selector())
BT_ADAPTER_IFACE = "{92383b0e-f90e-4ac9-8d44-8c2d0d0ebda2}"

LE_PHONE = int(BluetoothLEAppearanceCategories.phone)
LE_COMPUTER = int(BluetoothLEAppearanceCategories.computer)
LE_WATCH = int(BluetoothLEAppearanceCategories.watch)
LE_HID = int(BluetoothLEAppearanceCategories.human_interface_device)
LE_HID_KEYBOARD = int(BluetoothLEAppearanceSubcategories.keyboard)
LE_HID_MOUSE = int(BluetoothLEAppearanceSubcategories.mouse)
LE_HID_JOYSTICK = int(BluetoothLEAppearanceSubcategories.joystick)
LE_HID_GAMEPAD = int(BluetoothLEAppearanceSubcategories.gamepad)
COD_COMPUTER_LAPTOP = int(BluetoothMinorClass.COMPUTER_LAPTOP)
COD_COMPUTER_TABLET = int(BluetoothMinorClass.COMPUTER_TABLET)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

    @classmethod
    def from_string(cls, guid_str: str) -> GUID:
        u = uuid.UUID(guid_str)
        g = cls()
        g.Data1 = u.time_low
        g.Data2 = u.time_mid
        g.Data3 = u.time_hi_version
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", ctypes.c_ulonglong),
        ("ulClassofDevice", wintypes.ULONG),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", SYSTEMTIME),
        ("stLastUsed", SYSTEMTIME),
        ("szName", ctypes.c_wchar * 248),
    ]


class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE),
    ]


class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD)]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.ULONG)]


class DeviceType(StrEnum):
    HEADPHONES = "headphones"
    HEADSET = "headset"
    SPEAKER = "speaker"
    PHONE = "phone"
    TABLET = "tablet"
    LAPTOP = "laptop"
    COMPUTER = "computer"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    CONTROLLER = "controller"
    WATCH = "watch"
    CAMERA = "camera"
    GENERIC = "generic"


class ScanResultStatus(StrEnum):
    SUCCESS = "Success"
    RADIO_OFF = "Radio Off"
    API_UNAVAILABLE = "API Unavailable"
    ERROR = "Error"


class BluetoothMajorClass(IntEnum):
    COMPUTER = 1
    PHONE = 2
    AUDIO_VIDEO = 4
    PERIPHERAL = 5
    IMAGING = 6
    WEARABLE = 7
    TOY = 8


@dataclass
class DeviceInfo:
    name: str
    address: str
    address_int: int = 0
    connected: bool = False
    paired: bool = False
    remembered: bool = False
    device_id: str = ""
    major_class: int = 0
    device_type: DeviceType = DeviceType.GENERIC
    icon: str = ""
    status_text: str = "Not connected"
    battery: int | None = None
    is_le: bool = False
    profiles: list[str] = field(default_factory=list)

    @property
    def supports_connect(self) -> bool:
        """Classic audio devices we can oneshot connect/disconnect."""
        if self.is_le:
            return False
        return self.device_type in (
            DeviceType.HEADPHONES,
            DeviceType.HEADSET,
            DeviceType.SPEAKER,
        )


@dataclass
class BluetoothStatus:
    radio_on: bool = False
    devices: list[DeviceInfo] = field(default_factory=list)

    @property
    def connected_devices(self) -> list[DeviceInfo]:
        return [d for d in self.devices if d.connected and (d.paired or d.remembered)]


def format_address(address: int) -> str:
    return ":".join(f"{(address >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))


def parse_class_of_device(cod: int) -> tuple[int, int]:
    return (cod >> 8) & 0x1F, (cod >> 2) & 0x3F


def device_type_from_cod(major: int, minor: int) -> DeviceType:
    if major == BluetoothMajorClass.AUDIO_VIDEO:
        if minor in (1, 2):
            return DeviceType.HEADSET
        if minor in (6, 7):
            return DeviceType.HEADPHONES
        return DeviceType.SPEAKER
    if major == BluetoothMajorClass.PHONE:
        return DeviceType.PHONE
    if major == BluetoothMajorClass.COMPUTER:
        if minor == COD_COMPUTER_TABLET:
            return DeviceType.TABLET
        if minor == COD_COMPUTER_LAPTOP:
            return DeviceType.LAPTOP
        return DeviceType.COMPUTER
    if major == BluetoothMajorClass.PERIPHERAL:
        peripheral_type = (minor >> 4) & 0x3
        if peripheral_type == 1:
            return DeviceType.KEYBOARD
        if peripheral_type == 2:
            return DeviceType.MOUSE
        if (minor & 0x0F) in (2, 3, 4, 5):
            return DeviceType.CONTROLLER
        return DeviceType.GENERIC
    if major == BluetoothMajorClass.WEARABLE:
        return DeviceType.WATCH
    if major == BluetoothMajorClass.IMAGING:
        if minor & 0x08:
            return DeviceType.CAMERA
        return DeviceType.GENERIC
    if major == BluetoothMajorClass.TOY and (minor & 0x0F) in (1, 2, 5):
        return DeviceType.CONTROLLER
    return DeviceType.GENERIC


def device_type_from_le_appearance(category: int, subcategory: int) -> DeviceType:
    if category == LE_HID:
        if subcategory == LE_HID_KEYBOARD:
            return DeviceType.KEYBOARD
        if subcategory == LE_HID_MOUSE:
            return DeviceType.MOUSE
        if subcategory in (LE_HID_JOYSTICK, LE_HID_GAMEPAD):
            return DeviceType.CONTROLLER
        return DeviceType.GENERIC
    if category == LE_PHONE:
        return DeviceType.PHONE
    if category == LE_COMPUTER:
        return DeviceType.COMPUTER
    if category == LE_WATCH:
        return DeviceType.WATCH
    return DeviceType.GENERIC


def profiles_from_cod(major: int, connected: bool) -> list[str]:
    if not connected:
        return []
    if major == BluetoothMajorClass.AUDIO_VIDEO:
        return ["mic", "audio"]
    if major == BluetoothMajorClass.PERIPHERAL:
        return ["input"]
    return []


def prefer_device(candidate: DeviceInfo, existing: DeviceInfo) -> bool:
    cand_known = candidate.paired or candidate.remembered
    exist_known = existing.paired or existing.remembered
    if cand_known != exist_known:
        return cand_known
    if candidate.connected != existing.connected:
        return candidate.connected
    return False

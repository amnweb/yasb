"""Wrappers for BluetoothAPIs.dll (the API bthprops.cpl forwards to)"""

from ctypes import POINTER, WinDLL
from ctypes.wintypes import BOOL, HANDLE

from core.utils.win32.structs import BLUETOOTH_DEVICE_INFO, BLUETOOTH_DEVICE_SEARCH_PARAMS, BLUETOOTH_FIND_RADIO_PARAMS
from core.utils.win32.typecheck import CArgObject


class BluetoothApis:
    """Raises OSError when BluetoothAPIs.dll is missing, as on a Windows build without the Bluetooth stack."""

    def __init__(self) -> None:
        self._dll = WinDLL("BluetoothAPIs", use_last_error=True)
        self._dll.BluetoothFindFirstRadio.argtypes = [POINTER(BLUETOOTH_FIND_RADIO_PARAMS), POINTER(HANDLE)]
        self._dll.BluetoothFindFirstRadio.restype = HANDLE
        self._dll.BluetoothFindNextRadio.argtypes = [HANDLE, POINTER(HANDLE)]
        self._dll.BluetoothFindNextRadio.restype = BOOL
        self._dll.BluetoothFindRadioClose.argtypes = [HANDLE]
        self._dll.BluetoothFindRadioClose.restype = BOOL
        self._dll.BluetoothFindFirstDevice.argtypes = [
            POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
            POINTER(BLUETOOTH_DEVICE_INFO),
        ]
        self._dll.BluetoothFindFirstDevice.restype = HANDLE
        self._dll.BluetoothFindNextDevice.argtypes = [HANDLE, POINTER(BLUETOOTH_DEVICE_INFO)]
        self._dll.BluetoothFindNextDevice.restype = BOOL
        self._dll.BluetoothFindDeviceClose.argtypes = [HANDLE]
        self._dll.BluetoothFindDeviceClose.restype = BOOL

    def BluetoothFindFirstRadio(self, pbtfrp: CArgObject, phRadio: CArgObject) -> int | None:
        return self._dll.BluetoothFindFirstRadio(pbtfrp, phRadio)

    def BluetoothFindNextRadio(self, hFind: int, phRadio: CArgObject) -> bool:
        return bool(self._dll.BluetoothFindNextRadio(hFind, phRadio))

    def BluetoothFindRadioClose(self, hFind: int) -> bool:
        return bool(self._dll.BluetoothFindRadioClose(hFind))

    def BluetoothFindFirstDevice(self, pbtsp: CArgObject, pbtdi: CArgObject) -> int | None:
        return self._dll.BluetoothFindFirstDevice(pbtsp, pbtdi)

    def BluetoothFindNextDevice(self, hFind: int, pbtdi: CArgObject) -> bool:
        return bool(self._dll.BluetoothFindNextDevice(hFind, pbtdi))

    def BluetoothFindDeviceClose(self, hFind: int) -> bool:
        return bool(self._dll.BluetoothFindDeviceClose(hFind))

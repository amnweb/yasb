import asyncio
import ctypes
import logging
import os
from ctypes import wintypes
from typing import Any

from winrt.windows.devices.bluetooth import (
    BluetoothAdapter,
    BluetoothConnectionStatus,
    BluetoothDevice,
    BluetoothLEDevice,
)
from winrt.windows.devices.enumeration import DeviceInformation, DeviceWatcherStatus
from winrt.windows.devices.radios import Radio, RadioAccessStatus, RadioKind, RadioState

from core.widgets.services.bluetooth.bluetooth_types import (
    BLUETOOTH_DEVICE_INFO,
    BLUETOOTH_DEVICE_SEARCH_PARAMS,
    BLUETOOTH_FIND_RADIO_PARAMS,
    BLUETOOTH_SERVICE_DISABLE,
    BLUETOOTH_SERVICE_ENABLE,
    BT_ADAPTER_IFACE,
    DEVPROPKEY,
    GUID,
    BluetoothMajorClass,
    DeviceInfo,
    DeviceType,
    connect_service_guids,
    device_type_from_cod,
    device_type_from_le_appearance,
    format_address,
    parse_class_of_device,
    prefer_device,
    profiles_from_cod,
)

logger = logging.getLogger("bluetooth_widget")

_ENRICH_CONCURRENCY = 6

_CM_GETIDLIST_FILTER_PRESENT = 0x00000100
_CR_SUCCESS = 0
_DEVPROP_TYPE_BYTE = 0x00000003
_DEVPROP_TYPE_MASK = 0x00000FFF
_BATTERY_ID_LIST_MAX = 256 * 1024
_BATTERY_PROPKEY = DEVPROPKEY()
_BATTERY_PROPKEY.fmtid = GUID.from_string("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}")
_BATTERY_PROPKEY.pid = 2
_cfgmgr: Any | None = None
_cfgmgr_ready = False


def get_bluetooth_api() -> Any:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    paths = [
        "BluetoothAPIs.dll",
        os.path.join(system_root, "System32", "BluetoothAPIs.dll"),
        os.path.join(system_root, "SysWOW64", "BluetoothAPIs.dll"),
    ]
    last_error: OSError | None = None
    for path in paths:
        try:
            return ctypes.WinDLL(path)
        except OSError as e:
            last_error = e
    raise RuntimeError(f"Failed to load BluetoothAPIs.dll. Error: {last_error}")


class BluetoothNativeApi:
    """Thin wrapper around BluetoothAPIs.dll."""

    def __init__(self) -> None:
        self._api = get_bluetooth_api()
        api = self._api
        api.BluetoothFindFirstRadio.argtypes = [
            ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS),
            ctypes.POINTER(wintypes.HANDLE),
        ]
        api.BluetoothFindFirstRadio.restype = wintypes.HANDLE
        api.BluetoothFindNextRadio.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE)]
        api.BluetoothFindNextRadio.restype = wintypes.BOOL
        api.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]
        api.BluetoothFindRadioClose.restype = wintypes.BOOL
        api.BluetoothFindFirstDevice.argtypes = [
            ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
            ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
        ]
        api.BluetoothFindFirstDevice.restype = wintypes.HANDLE
        api.BluetoothFindNextDevice.argtypes = [wintypes.HANDLE, ctypes.POINTER(BLUETOOTH_DEVICE_INFO)]
        api.BluetoothFindNextDevice.restype = wintypes.BOOL
        api.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
        api.BluetoothFindDeviceClose.restype = wintypes.BOOL
        api.BluetoothSetServiceState.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
            ctypes.POINTER(GUID),
            wintypes.DWORD,
        ]
        api.BluetoothSetServiceState.restype = wintypes.DWORD

    def _iter_radios(self):
        """Yield each radio HANDLE, closed when the caller's loop advances past it."""
        find_params = BLUETOOTH_FIND_RADIO_PARAMS(dwSize=ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS))
        radio_handle = wintypes.HANDLE()
        finder = self._api.BluetoothFindFirstRadio(ctypes.byref(find_params), ctypes.byref(radio_handle))
        if not finder or finder == wintypes.HANDLE(0):
            return
        try:
            while True:
                handle = radio_handle.value
                if not handle:
                    break
                try:
                    yield handle
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
                if not self._api.BluetoothFindNextRadio(finder, ctypes.byref(radio_handle)):
                    break
        finally:
            self._api.BluetoothFindRadioClose(finder)

    def enumerate_devices(self, *, inquiry: bool = False, include_unknown: bool = False) -> list[DeviceInfo]:
        """List devices via BluetoothFindFirstDevice (Address = MAC)."""
        devices: dict[str, DeviceInfo] = {}
        for radio in self._iter_radios():
            search = BLUETOOTH_DEVICE_SEARCH_PARAMS(
                dwSize=ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS),
                fReturnAuthenticated=True,
                fReturnRemembered=True,
                fReturnUnknown=include_unknown or inquiry,
                fReturnConnected=True,
                fIssueInquiry=inquiry,
                cTimeoutMultiplier=2 if inquiry else 1,
                hRadio=radio,
            )
            info = BLUETOOTH_DEVICE_INFO()
            info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
            finder = self._api.BluetoothFindFirstDevice(ctypes.byref(search), ctypes.byref(info))
            if not finder or finder == wintypes.HANDLE(0):
                continue
            try:
                while True:
                    address = format_address(info.Address)
                    major, minor = parse_class_of_device(info.ulClassofDevice)
                    connected = bool(info.fConnected)
                    device = DeviceInfo(
                        name=info.szName or address,
                        address=address,
                        address_int=int(info.Address),
                        connected=connected,
                        paired=bool(info.fAuthenticated),
                        remembered=bool(info.fRemembered),
                        major_class=major,
                        device_type=device_type_from_cod(major, minor),
                        profiles=profiles_from_cod(major, connected),
                    )
                    existing = devices.get(address)
                    if existing is None or prefer_device(device, existing):
                        devices[address] = device
                    if not self._api.BluetoothFindNextDevice(finder, ctypes.byref(info)):
                        break
            finally:
                self._api.BluetoothFindDeviceClose(finder)
        return list(devices.values())

    def set_service_state(self, device: DeviceInfo, enable: bool) -> bool:
        """Enable/disable classic services to connect or disconnect."""
        guids = connect_service_guids(device)
        if not guids:
            return False

        info = BLUETOOTH_DEVICE_INFO()
        info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
        info.Address = device.address_int
        info.szName = device.name[:247]
        flag = BLUETOOTH_SERVICE_ENABLE if enable else BLUETOOTH_SERVICE_DISABLE
        any_ok = False
        for radio in self._iter_radios():
            for guid_str in guids:
                result = self._api.BluetoothSetServiceState(
                    radio,
                    ctypes.byref(info),
                    ctypes.byref(GUID.from_string(guid_str)),
                    flag,
                )
                if result == 0:
                    any_ok = True
        return any_ok


async def radio_is_on() -> bool | None:
    """True = on, False = adapter present but off, None = no adapter / query failed."""
    try:
        found = False
        for radio in await Radio.get_radios_async():
            if radio.kind == RadioKind.BLUETOOTH:
                found = True
                if radio.state == RadioState.ON:
                    return True
        return False if found else None
    except Exception as e:
        logger.debug("Bluetooth radio_is_on failed: %s", e)
        return None


async def set_radio_power(on: bool) -> bool:
    try:
        access = await Radio.request_access_async()
        if access != RadioAccessStatus.ALLOWED:
            logger.warning("Bluetooth radio access denied: %s", access)
            return False
        for radio in await Radio.get_radios_async():
            if radio.kind == RadioKind.BLUETOOTH:
                target = RadioState.ON if on else RadioState.OFF
                return await radio.set_state_async(target) == RadioAccessStatus.ALLOWED
    except Exception as e:
        logger.error("Failed to set Bluetooth radio state: %s", e)
    return False


async def bind_radio(on_changed) -> tuple[Any, Any] | None:
    try:
        for radio in await Radio.get_radios_async():
            if radio.kind == RadioKind.BLUETOOTH:
                return radio, radio.add_state_changed(on_changed)
    except Exception as e:
        logger.warning("Bluetooth bind_radio failed: %s", e)
    return None


def _is_bluetooth_adapter_id(device_id: str) -> bool:
    # pywinrt has no create_watcher(aqs) filter unfiltered watcher by this GUID.
    return BT_ADAPTER_IFACE in (device_id or "").lower()


def open_adapter_watch(on_changed) -> Any | None:
    """Watch local Bluetooth adapter presence via DeviceWatcher.

    pywinrt only exposes DeviceInformation.create_watcher() with no AQS filter.
    We ignore non-adapter devices and all events until EnumerationCompleted.
    on_changed() is invoked from a WinRT thread bridge to the app loop.
    """
    try:
        _ = BluetoothAdapter.get_device_selector()
        watcher = DeviceInformation.create_watcher()
    except Exception as e:
        logger.warning("Bluetooth open_adapter_watch failed: %s", e)
        return None

    state = {"ready": False, "watcher": watcher, "tokens": [], "handlers": []}

    def _fire(kind: str, _device_id: str) -> None:
        try:
            on_changed(kind)
        except Exception as e:
            logger.debug("Bluetooth adapter watch callback failed: %s", e)

    def on_added(_sender, info) -> None:
        device_id = getattr(info, "id", "") or ""
        if not _is_bluetooth_adapter_id(device_id):
            return
        if not state["ready"]:
            return
        _fire("Added", device_id)

    def on_removed(_sender, update) -> None:
        device_id = getattr(update, "id", "") or ""
        if not _is_bluetooth_adapter_id(device_id):
            return
        if not state["ready"]:
            return
        _fire("Removed", device_id)

    def on_updated(_sender, update) -> None:
        device_id = getattr(update, "id", "") or ""
        if not _is_bluetooth_adapter_id(device_id):
            return
        if not state["ready"]:
            return
        _fire("Updated", device_id)

    def on_enum_completed(_sender, _args) -> None:
        state["ready"] = True

    # Keep handler refs alive on the state object (WinRT only holds weak-ish tokens).
    state["handlers"] = [on_added, on_removed, on_updated, on_enum_completed]
    try:
        state["tokens"] = [
            watcher.add_added(on_added),
            watcher.add_removed(on_removed),
            watcher.add_updated(on_updated),
            watcher.add_enumeration_completed(on_enum_completed),
        ]
        watcher.start()
    except Exception as e:
        logger.warning("Bluetooth adapter watcher start failed: %s", e)
        return None
    return state


def close_adapter_watch(state: Any | None) -> None:
    if not state:
        return
    watcher = state.get("watcher")
    tokens = state.get("tokens") or []
    if watcher is None:
        return
    try:
        removers = (
            watcher.remove_added,
            watcher.remove_removed,
            watcher.remove_updated,
            watcher.remove_enumeration_completed,
        )
        for remove, token in zip(removers, tokens, strict=False):
            try:
                remove(token)
            except Exception:
                pass
        if int(watcher.status) not in (
            int(DeviceWatcherStatus.STOPPED),
            int(DeviceWatcherStatus.ABORTED),
        ):
            watcher.stop()
    except Exception as e:
        logger.debug("Bluetooth close_adapter_watch failed: %s", e)
    finally:
        state["ready"] = False
        state["watcher"] = None
        state["tokens"] = []
        state["handlers"] = []


async def open_device_watch(device: DeviceInfo, on_changed) -> tuple[Any, Any] | None:
    """Open one WinRT device and subscribe ConnectionStatusChanged."""
    if not device.address_int:
        return None
    try:
        if device.is_le:
            le = await BluetoothLEDevice.from_bluetooth_address_async(device.address_int)
            if le is None:
                return None
            return le, le.add_connection_status_changed(on_changed)

        bt = None
        if device.device_id and "BluetoothLE" not in device.device_id:
            bt = await BluetoothDevice.from_id_async(device.device_id)
        if bt is None:
            bt = await BluetoothDevice.from_bluetooth_address_async(device.address_int)
        if bt is None:
            return None
        return bt, bt.add_connection_status_changed(on_changed)
    except Exception as e:
        logger.debug("Bluetooth open_device_watch failed for %s: %s", device.address, e)
        return None


def _get_cfgmgr() -> Any | None:
    """Load cfgmgr32 once and bind CM_* prototypes."""
    global _cfgmgr, _cfgmgr_ready
    if _cfgmgr_ready:
        return _cfgmgr
    _cfgmgr_ready = True
    try:
        cfg = ctypes.WinDLL("cfgmgr32.dll")
    except OSError:
        _cfgmgr = None
        return None

    cfg.CM_Get_Device_ID_List_SizeW.argtypes = [
        ctypes.POINTER(wintypes.ULONG),
        wintypes.LPCWSTR,
        wintypes.ULONG,
    ]
    cfg.CM_Get_Device_ID_List_SizeW.restype = wintypes.DWORD
    cfg.CM_Get_Device_ID_ListW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    cfg.CM_Get_Device_ID_ListW.restype = wintypes.DWORD
    cfg.CM_Locate_DevNodeW.argtypes = [
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPCWSTR,
        wintypes.ULONG,
    ]
    cfg.CM_Locate_DevNodeW.restype = wintypes.DWORD
    cfg.CM_Get_DevNode_PropertyW.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(DEVPROPKEY),
        ctypes.POINTER(wintypes.ULONG),
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    cfg.CM_Get_DevNode_PropertyW.restype = wintypes.DWORD
    _cfgmgr = cfg
    return _cfgmgr


def read_battery(address_int: int) -> int | None:
    """Read DEVPKEY_Bluetooth_BatteryLevel from PnP nodes containing this MAC."""
    cfg = _get_cfgmgr()
    if cfg is None:
        return None

    addr_hex = f"{address_int:012X}"
    for filt in (
        "BTHENUM\\{0000111E-0000-1000-8000-00805F9B34FB}",
        "BTHENUM",
        "BTHLE",
    ):
        length = wintypes.ULONG(0)
        if cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(length), filt, _CM_GETIDLIST_FILTER_PRESENT) != _CR_SUCCESS:
            continue
        if length.value <= 1 or length.value > _BATTERY_ID_LIST_MAX:
            continue
        buf = ctypes.create_unicode_buffer(length.value)
        if cfg.CM_Get_Device_ID_ListW(filt, buf, length, _CM_GETIDLIST_FILTER_PRESENT) != _CR_SUCCESS:
            continue
        blob = ctypes.wstring_at(ctypes.addressof(buf), length.value)
        for device_id in (part for part in blob.split("\x00") if part):
            if addr_hex not in device_id.upper():
                continue
            devinst = wintypes.DWORD(0)
            if cfg.CM_Locate_DevNodeW(ctypes.byref(devinst), device_id, 0) != _CR_SUCCESS:
                continue
            prop_type = wintypes.ULONG(0)
            prop_size = wintypes.ULONG(1)
            value = ctypes.c_ubyte(0)
            status = cfg.CM_Get_DevNode_PropertyW(
                devinst,
                ctypes.byref(_BATTERY_PROPKEY),
                ctypes.byref(prop_type),
                ctypes.byref(value),
                ctypes.byref(prop_size),
                0,
            )
            if status == _CR_SUCCESS and (prop_type.value & _DEVPROP_TYPE_MASK) == _DEVPROP_TYPE_BYTE:
                level = int(value.value)
                if 0 <= level <= 100:
                    return level
    return None


async def enrich_device(device: DeviceInfo) -> DeviceInfo:
    """Fill name/type/connected/battery via await WinRT + PnP battery off-loop."""
    if not device.address_int:
        return device

    if device.is_le:
        try:
            le = await BluetoothLEDevice.from_bluetooth_address_async(device.address_int)
            if le is None:
                device.connected = False
            else:
                device.connected = int(le.connection_status) == int(BluetoothConnectionStatus.CONNECTED)
                device.device_id = le.device_id or device.device_id
                device.name = le.name or device.name
                appearance = le.appearance
                if appearance is not None:
                    category = int(appearance.category)
                    subcategory = int(getattr(appearance, "sub_category", 0) or 0)
                    device.device_type = device_type_from_le_appearance(category, subcategory)
                    if device.device_type in (DeviceType.KEYBOARD, DeviceType.MOUSE, DeviceType.CONTROLLER):
                        device.major_class = int(BluetoothMajorClass.PERIPHERAL)
                device.profiles = profiles_from_cod(device.major_class, device.connected)
        except Exception as e:
            logger.debug("Bluetooth LE enrich failed for %s: %s", device.address, e)
            device.connected = False
    else:
        try:
            bt = await BluetoothDevice.from_bluetooth_address_async(device.address_int)
            if bt is not None:
                device.device_id = bt.device_id or device.device_id
                device.name = bt.name or device.name
                device.connected = int(bt.connection_status) == int(BluetoothConnectionStatus.CONNECTED)
                if bt.class_of_device is not None:
                    major = int(bt.class_of_device.major_class)
                    minor = int(bt.class_of_device.minor_class)
                    device.major_class = major
                    device.device_type = device_type_from_cod(major, minor)
                device.profiles = profiles_from_cod(device.major_class, device.connected)
        except Exception as e:
            logger.debug("Bluetooth classic enrich failed for %s: %s", device.address, e)

    if device.connected:
        loop = asyncio.get_running_loop()
        device.battery = await loop.run_in_executor(None, read_battery, device.address_int)
    else:
        device.battery = None
    return device


async def list_le_devices() -> list[DeviceInfo] | None:
    """BLE devices via FromIdAsync (pywinrt has no AQS FindAll). None = enum failed."""
    found: dict[str, DeviceInfo] = {}
    try:
        for di in await DeviceInformation.find_all_async():
            device_id = di.id or ""
            # Windows uses BTHLEDevice#...; older/odd paths may use BTHLE#DEV_
            upper = device_id.upper()
            if "BTHLEDEVICE#" not in upper and "BTHLE#DEV_" not in upper:
                continue
            try:
                le = await BluetoothLEDevice.from_id_async(device_id)
            except Exception:
                continue
            if le is None:
                continue
            address_int = int(le.bluetooth_address)
            if not address_int:
                continue
            address = format_address(address_int)
            if address in found:
                continue
            found[address] = DeviceInfo(
                name=(le.name or di.name or "").strip() or address,
                address=address,
                address_int=address_int,
                paired=True,
                remembered=True,
                device_id=le.device_id or device_id,
                is_le=True,
            )
    except Exception as e:
        logger.error("LE enumerate failed: %s", e)
        return None

    return list(found.values())


def _list_classic(native: BluetoothNativeApi | None, *, inquiry: bool) -> list[DeviceInfo]:
    """Classic BluetoothAPIs enum only (sync; run via executor)."""
    by_addr: dict[str, DeviceInfo] = {}
    if native is None:
        return []
    for device in native.enumerate_devices(inquiry=False):
        if device.paired or device.remembered:
            by_addr[device.address] = device
    if inquiry:
        for device in native.enumerate_devices(inquiry=True, include_unknown=True):
            if device.address in by_addr or device.paired or device.remembered:
                continue
            by_addr[device.address] = device
    return list(by_addr.values())


async def list_devices(
    native: BluetoothNativeApi | None,
    *,
    inquiry: bool = False,
    le_cache: dict[str, DeviceInfo] | None = None,
    refresh_le: bool = False,
) -> tuple[list[DeviceInfo], dict[str, DeviceInfo]]:
    """Classic paired + BLE-only, then enrich (bounded concurrency). Returns (devices, le_cache)."""
    loop = asyncio.get_running_loop()
    classic = await loop.run_in_executor(None, lambda: _list_classic(native, inquiry=inquiry))
    by_addr: dict[str, DeviceInfo] = {d.address: d for d in classic}

    cache = dict(le_cache) if le_cache else {}
    if refresh_le or not cache:
        refreshed = await list_le_devices()
        if refreshed is not None:
            cache = {d.address: d for d in refreshed}

    for device in cache.values():
        if device.address not in by_addr:
            by_addr[device.address] = device

    sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _enrich(device: DeviceInfo) -> DeviceInfo:
        async with sem:
            return await enrich_device(device)

    enriched = await asyncio.gather(*(_enrich(d) for d in by_addr.values()))
    return list(enriched), cache

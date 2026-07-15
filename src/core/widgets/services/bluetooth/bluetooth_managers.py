import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, pyqtSignal
from winrt.windows.devices.bluetooth import BluetoothConnectionStatus

from core.widgets.services.bluetooth.bluetooth_api import (
    BluetoothNativeApi,
    bind_radio,
    close_adapter_watch,
    enrich_device,
    list_devices,
    open_adapter_watch,
    open_device_watch,
    radio_is_on,
    read_battery,
    set_radio_power,
)
from core.widgets.services.bluetooth.bluetooth_audio import (
    audio_is_connected,
    set_audio_connection,
)
from core.widgets.services.bluetooth.bluetooth_types import (
    BluetoothStatus,
    DeviceInfo,
    ScanResultStatus,
    format_address,
    profiles_from_cod,
)

logger = logging.getLogger("bluetooth_widget")


def _connect_error(action: str, reason: str) -> str:
    if reason == "cancelled":
        return f"{action.capitalize()} cancelled"
    if reason in ("not_audio_device", "no_ks_controls"):
        return f"Failed to {action} device (no audio path; use Windows Settings)"
    if reason == "oneshot_failed":
        return f"Failed to {action} device (audio driver request failed)"
    if reason == "timeout" and action == "connect":
        return "Failed to connect device. Is it powered on and in range?"
    if reason == "timeout":
        return f"Failed to {action} device"
    return f"Failed to {action} device"


class BluetoothManager(QObject):
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(object, object)  # ScanResultStatus, list[DeviceInfo]
    status_updated = pyqtSignal(object)  # BluetoothStatus
    refresh_failed = pyqtSignal(str)
    connection_finished = pyqtSignal(bool, str, object)
    _instance: ClassVar[BluetoothManager | None] = None
    _users: ClassVar[int] = 0

    def __init__(self) -> None:
        super().__init__()
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
            logger.warning("BluetoothManager created without a running asyncio loop")
        self._native: BluetoothNativeApi | None = None
        try:
            self._native = BluetoothNativeApi()
        except RuntimeError:
            self._native = None
        self._pending_scan = False
        self._refresh_pending = False
        self._refresh_le_pending = False
        self._refresh_running = False
        self._scan_running = False
        self._connect_running = False
        self._radio_running = False
        self._started = False
        self._radio_subscribed = False
        self._devices: dict[str, DeviceInfo] = {}
        self._le_cache: dict[str, DeviceInfo] = {}
        self._radio_on = False
        self._radio: Any | None = None
        self._radio_token: Any | None = None
        self._watches: dict[int, tuple[Any, Any]] = {}
        self._adapter_watch: Any | None = None
        self._enum_lock: asyncio.Lock | None = None
        self._connect_cancel = threading.Event()

    @classmethod
    def acquire(cls) -> BluetoothManager:
        if cls._instance is None:
            cls._instance = cls()
        cls._users += 1
        return cls._instance

    def release(self) -> None:
        type(self)._users = max(type(self)._users - 1, 0)
        if type(self)._users > 0:
            return
        self.shutdown()
        type(self)._instance = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is not None and self._loop.is_running():
            return self._loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        return self._loop

    def _ensure_enum_lock(self) -> asyncio.Lock | None:
        loop = self._ensure_loop()
        if loop is None:
            return None
        if self._enum_lock is None:
            self._enum_lock = asyncio.Lock()
        return self._enum_lock

    @property
    def has_pending_scan(self) -> bool:
        return self._pending_scan

    def start(self) -> None:
        if self._started:
            return
        if self._ensure_loop() is None:
            logger.error("BluetoothManager.start() aborted: no asyncio loop")
            return
        self._ensure_enum_lock()
        self._started = True
        self._start_adapter_watch()
        self._refresh_le_pending = True
        self._schedule(self._refresh_async())
        logger.info("BluetoothManager started...")

    def shutdown(self) -> None:
        self._started = False
        self._connect_cancel.set()
        self._refresh_pending = False
        self._refresh_le_pending = False
        self._pending_scan = False
        self._connect_running = False
        self._stop_adapter_watch()
        self._clear_device_watchers()
        self._unsubscribe_radio()
        self._le_cache.clear()
        self._devices.clear()
        logger.info("BluetoothManager stopped...")

    def devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def is_radio_on(self) -> bool:
        return self._radio_on

    def refresh(self) -> None:
        self._refresh_le_pending = True
        self._schedule(self._refresh_async())

    def scan(self) -> None:
        self._schedule(self._scan_async())

    def set_radio(self, on: bool) -> bool:
        if self._connect_running or self._radio_running:
            return False
        self._schedule(self._set_radio_async(on))
        return True

    def connect_device(self, address: str) -> None:
        self._schedule(self._connect_async(address, True))

    def disconnect_device(self, address: str) -> None:
        self._schedule(self._connect_async(address, False))

    def _schedule(self, coro) -> None:
        loop = self._ensure_loop()
        if loop is None:
            return
        try:
            loop.create_task(coro)
        except RuntimeError:
            pass

    def _safe_create_task(self, callback: Callable, *args: Any) -> None:
        if not self._started:
            return
        loop = self._ensure_loop()
        if loop is None:
            return
        try:
            loop.create_task(callback(*args))
        except RuntimeError:
            pass

    def _bridge(self, callback: Callable):
        def wrapper(sender: Any, _args: Any) -> None:
            if not self._started:
                return
            try:
                loop = self._loop
                if loop is None:
                    return
                loop.call_soon_threadsafe(self._safe_create_task, callback, sender)
            except RuntimeError:
                pass

        return wrapper

    def _bridge_plain(self, callback: Callable):
        def wrapper(*args: Any) -> None:
            if not self._started:
                return
            try:
                loop = self._loop
                if loop is None:
                    return
                loop.call_soon_threadsafe(self._safe_create_task, callback, *args)
            except RuntimeError:
                pass

        return wrapper

    def _emit_status(self) -> None:
        self.status_updated.emit(BluetoothStatus(radio_on=self._radio_on, devices=list(self._devices.values())))

    def _set_connected(self, device: DeviceInfo, connected: bool) -> None:
        device.connected = connected
        device.profiles = profiles_from_cod(device.major_class, connected)
        if not connected:
            device.battery = None

    async def _read_battery(self, device: DeviceInfo) -> None:
        if not device.connected or not device.address_int:
            device.battery = None
            return
        loop = asyncio.get_running_loop()
        device.battery = await loop.run_in_executor(None, read_battery, device.address_int)

    def _alive(self) -> bool:
        return self._started

    def _start_adapter_watch(self) -> None:
        if self._adapter_watch is not None:
            return
        self._adapter_watch = open_adapter_watch(self._bridge_plain(self._on_adapter_changed))

    def _stop_adapter_watch(self) -> None:
        close_adapter_watch(self._adapter_watch)
        self._adapter_watch = None

    def _reset_backend(self) -> None:
        """Clear radio and device state after a HW change."""
        self._unsubscribe_radio()
        self._clear_device_watchers()
        self._devices.clear()
        self._le_cache.clear()
        self._radio_on = False

    async def _on_adapter_changed(self, kind: str = "Updated") -> None:
        """Adapter events rebuild; DeviceAdded/Removed refresh the list."""
        if not self._alive():
            return
        if kind.startswith("Device"):
            self._refresh_le_pending = True
            busy = self._connect_running or self._scan_running or self._refresh_running
            if busy:
                self._refresh_pending = True
                return
            await self._refresh_async()
            return
        busy = self._connect_running or self._scan_running or self._refresh_running
        self._reset_backend()
        self._emit_status()
        self._refresh_le_pending = True
        if busy:
            self._refresh_pending = True
            return
        await self._refresh_async()

    async def _refresh_async(self) -> None:
        if not self._alive():
            return
        if self._scan_running or self._refresh_running:
            self._refresh_pending = True
            return
        lock = self._ensure_enum_lock()
        if lock is None:
            return
        self._refresh_running = True
        refresh_le = self._refresh_le_pending or not self._le_cache
        self._refresh_le_pending = False
        try:
            async with lock:
                if not self._alive():
                    return
                radio = await radio_is_on()
                if not self._alive():
                    return

                # WinRT Radio can lag after a dongle swap while devices still enumerate.
                # Only RadioState.OFF is treated as really off.
                if radio is False:
                    self._radio_on = False
                    self._devices.clear()
                    self._le_cache.clear()
                    self._clear_device_watchers()
                    if not self._radio_subscribed:
                        watch = await bind_radio(self._bridge(self._on_radio_state_changed))
                        if not self._alive():
                            return
                        if watch is not None:
                            self._unsubscribe_radio()
                            self._radio, self._radio_token = watch
                            self._radio_subscribed = True
                    self._emit_status()
                    return

                devices, self._le_cache = await list_devices(
                    self._native,
                    inquiry=False,
                    le_cache=self._le_cache,
                    refresh_le=refresh_le,
                )
                if not self._alive():
                    return

                if radio is None and not devices:
                    self._radio_on = False
                    self._devices.clear()
                    self._le_cache.clear()
                    self._clear_device_watchers()
                    self._emit_status()
                    return

                self._radio_on = True
                self._devices = {d.address: d for d in devices if d.address}
                if not self._radio_subscribed:
                    watch = await bind_radio(self._bridge(self._on_radio_state_changed))
                    if not self._alive():
                        return
                    if watch is not None:
                        self._unsubscribe_radio()
                        self._radio, self._radio_token = watch
                        self._radio_subscribed = True
                await self._sync_device_watchers(list(self._devices.values()))
                if not self._alive():
                    return
                self._emit_status()
        except Exception as e:
            logger.error("Bluetooth refresh failed: %s", e)
            if self._alive():
                self._emit_status()
                self.refresh_failed.emit(str(e) or "Bluetooth refresh failed")
        finally:
            self._refresh_running = False
            if self._alive():
                if self._refresh_pending:
                    self._refresh_pending = False
                    self._schedule(self._refresh_async())
                elif self._pending_scan:
                    self._pending_scan = False
                    self._schedule(self._scan_async())

    async def _scan_async(self) -> None:
        if not self._alive():
            return
        if self._scan_running or self._refresh_running:
            self._pending_scan = True
            self.scan_started.emit()
            return
        lock = self._ensure_enum_lock()
        if lock is None:
            return
        self._pending_scan = False
        self._scan_running = True
        self.scan_started.emit()
        try:
            async with lock:
                if not self._alive():
                    return
                radio = await radio_is_on()
                if not self._alive():
                    return
                if self._native is None:
                    self.scan_completed.emit(ScanResultStatus.API_UNAVAILABLE, [])
                    return
                if radio is not True:
                    self._radio_on = False
                    self._devices.clear()
                    self._le_cache.clear()
                    self._clear_device_watchers()
                    self._emit_status()
                    self.scan_completed.emit(ScanResultStatus.RADIO_OFF, [])
                    return
                devices, self._le_cache = await list_devices(
                    self._native,
                    inquiry=True,
                    le_cache=self._le_cache,
                    refresh_le=True,
                )
                if not self._alive():
                    return
                paired = [d for d in devices if d.paired or d.remembered]
                self._radio_on = True
                self._devices = {d.address: d for d in paired if d.address}
                await self._sync_device_watchers(paired)
                if not self._alive():
                    return
                self._emit_status()
                self.scan_completed.emit(ScanResultStatus.SUCCESS, devices)
        except Exception as e:
            logger.error("Bluetooth scan failed: %s", e)
            if self._alive():
                self.scan_completed.emit(ScanResultStatus.ERROR, [])
        finally:
            self._scan_running = False
            if self._alive():
                if self._pending_scan:
                    self._pending_scan = False
                    self._schedule(self._scan_async())
                elif self._refresh_pending:
                    self._refresh_pending = False
                    self._schedule(self._refresh_async())

    async def _set_radio_async(self, on: bool) -> None:
        self._radio_running = True
        try:
            ok = await set_radio_power(on)
            if not self._alive():
                return
            if not ok:
                radio = await radio_is_on()
                if not self._alive():
                    return
                self._radio_on = bool(radio)
                if not self._radio_on:
                    self._devices.clear()
                    self._le_cache.clear()
                    self._clear_device_watchers()
                self._emit_status()
                self.refresh_failed.emit("Unable to change Bluetooth power")
                return
            self._refresh_le_pending = True
            await self._refresh_async()
        finally:
            self._radio_running = False

    async def _connect_async(self, address: str, connect: bool) -> None:
        action = "connect" if connect else "disconnect"
        device = self._devices.get(address)
        if device is None:
            self.connection_finished.emit(False, "Device not found", DeviceInfo(name="", address=address))
            return
        if self._native is None:
            self.connection_finished.emit(False, "Bluetooth API unavailable", device)
            return
        if self._connect_running:
            self.connection_finished.emit(False, "Another connection is in progress", device)
            return
        if device.is_le or not device.supports_connect:
            self.connection_finished.emit(False, "Use Windows Settings to manage this device", device)
            return

        self._connect_running = True
        self._connect_cancel.clear()
        try:
            loop = asyncio.get_running_loop()
            addr = device.address_int or device.address
            name = device.name or ""
            cancel = self._connect_cancel
            audio_before = await loop.run_in_executor(None, audio_is_connected, name)
            error = await loop.run_in_executor(
                None,
                lambda: set_audio_connection(addr, connect=connect, device_name=name, cancel=cancel),
            )
            if not self._alive():
                return
            audio = await loop.run_in_executor(None, audio_is_connected, name)
            if error is None and audio != connect:
                error = "timeout"
            # Idle audio + WinRT still Connected is not a real disconnect.
            if error is None and not connect and audio_before is not True:
                await enrich_device(device)
                if not self._alive():
                    return
                if device.connected:
                    error = "timeout"
            if error is not None:
                self._finish_connect(device, False, _connect_error(action, error))
                return
            if audio is not None:
                self._set_connected(device, audio)
                if device.connected:
                    await self._read_battery(device)
            self._finish_connect(device, True, f"Device {action}ed")
        except Exception as e:
            if self._alive():
                self._finish_connect(device, False, str(e))

    def _finish_connect(self, device: DeviceInfo, success: bool, message: str) -> None:
        self._connect_running = False
        self.connection_finished.emit(success, message, device)
        self._emit_status()
        if self._alive() and self._refresh_pending:
            self._refresh_pending = False
            self._schedule(self._refresh_async())

    async def _on_radio_state_changed(self, _sender: Any) -> None:
        if not self._alive():
            return
        busy = self._connect_running or self._scan_running or self._refresh_running
        self._refresh_le_pending = True
        if busy:
            self._refresh_pending = True
            return
        await self._refresh_async()

    async def _on_device_connection_changed(self, sender: Any) -> None:
        if not self._alive() or self._connect_running:
            return
        try:
            address_int = int(sender.bluetooth_address)
            connected = int(sender.connection_status) == int(BluetoothConnectionStatus.CONNECTED)
        except Exception:
            self._refresh_le_pending = True
            if not (self._scan_running or self._refresh_running):
                await self._refresh_async()
            else:
                self._refresh_pending = True
            return

        device = self._devices.get(format_address(address_int))
        if device is None:
            self._refresh_le_pending = True
            if not (self._scan_running or self._refresh_running):
                await self._refresh_async()
            else:
                self._refresh_pending = True
            return

        if device.connected == connected:
            if connected and device.battery is None:
                await self._read_battery(device)
                if self._alive():
                    self._emit_status()
            return
        self._set_connected(device, connected)
        if connected:
            await self._read_battery(device)
        if self._alive():
            self._emit_status()

    async def _sync_device_watchers(self, devices: list[DeviceInfo]) -> None:
        """Add/remove watchers by MAC - do not tear down unchanged devices."""
        needed = {d.address_int: d for d in devices if d.address_int}
        for address in list(self._watches):
            if address not in needed:
                self._unwatch_device(address)
        on_changed = self._bridge(self._on_device_connection_changed)
        for address, device in needed.items():
            if not self._alive():
                return
            if address in self._watches:
                continue
            watch = await open_device_watch(device, on_changed)
            if watch is not None:
                self._watches[address] = watch

    def _unsubscribe_radio(self) -> None:
        if self._radio is not None and self._radio_token is not None:
            try:
                self._radio.remove_state_changed(self._radio_token)
            except Exception as e:
                logger.debug("Bluetooth radio unsubscribe failed: %s", e)
        self._radio = None
        self._radio_token = None
        self._radio_subscribed = False

    def _unwatch_device(self, address: int) -> None:
        watch = self._watches.pop(address, None)
        if watch is None:
            return
        bt, token = watch
        try:
            bt.remove_connection_status_changed(token)
        except Exception as e:
            logger.debug("Bluetooth device unwatch failed for %s: %s", address, e)
        try:
            close = getattr(bt, "close", None)
            if callable(close):
                close()
        except Exception as e:
            logger.debug("Bluetooth device close failed for %s: %s", address, e)

    def _clear_device_watchers(self) -> None:
        for address in list(self._watches):
            self._unwatch_device(address)

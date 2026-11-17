"""Cached physical DIMM information, queried without blocking the memory sampler."""

import logging
import threading
import time
from typing import NamedTuple

from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_dispatch


class MemoryModule(NamedTuple):
    capacity: int
    configured_speed: int | None
    rated_speed: int | None


class MemoryHardware(NamedTuple):
    modules: tuple[MemoryModule, ...] = ()

    @property
    def installed_bytes(self) -> int | None:
        total = sum(module.capacity for module in self.modules)
        return total if total > 0 else None


def read_hardware() -> MemoryHardware:
    """Read SMBIOS-backed WMI data on the caller's COM-initialized thread."""
    locator = create_dispatch("WbemScripting.SWbemLocator")
    service = locator.ConnectServer(".", r"root\cimv2")
    rows = service.ExecQuery("SELECT Capacity, ConfiguredClockSpeed, Speed FROM Win32_PhysicalMemory", "WQL", 48)
    modules: list[MemoryModule] = []
    for row in rows:
        capacity = int(row.Properties_.Item("Capacity").Value or 0)
        if capacity <= 0:
            continue
        configured = int(row.Properties_.Item("ConfiguredClockSpeed").Value or 0)
        rated = int(row.Properties_.Item("Speed").Value or 0)
        modules.append(MemoryModule(capacity, configured if configured > 0 else None, rated if rated > 0 else None))
    return MemoryHardware(tuple(modules))


class HardwareCache:
    """One daemon query at a time; stalled firmware never stalls the UI or sampler."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = MemoryHardware()
        self._loading = False
        self._retry_at = 0.0

    def snapshot(self) -> MemoryHardware:
        with self._lock:
            if not self._loading and time.monotonic() >= self._retry_at:
                self._loading = True
                threading.Thread(target=self._refresh, name="yasb-memory-hardware", daemon=True).start()
            return self._value

    def _refresh(self) -> None:
        initialized = False
        success = False
        try:
            initialized = CoInitialize() >= 0
            if not initialized:
                raise RuntimeError("COM initialization failed")
            value = read_hardware()
            with self._lock:
                self._value = value
            success = bool(value.modules)
        except Exception as error:
            logging.debug("Memory hardware information unavailable: %s", error)
        finally:
            if initialized:
                CoUninitialize()
            with self._lock:
                self._loading = False
                self._retry_at = time.monotonic() + (300 if success else 60)

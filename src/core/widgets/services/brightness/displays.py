import asyncio
import logging
from dataclasses import dataclass

import win32api
from winrt.windows.devices.display import DisplayMonitor, DisplayMonitorConnectionKind

EDD_GET_DEVICE_INTERFACE_NAME = 1
DISPLAY_DEVICE_ACTIVE = 0x00000001


@dataclass(frozen=True)
class DisplayTarget:
    monitor_name: str
    connection_type: str
    is_internal: bool


def _interface_paths(device: str) -> list[tuple[str, bool]]:
    """Return (interface path, is_active) for each EnumDisplayDevices index."""
    paths: list[tuple[str, bool]] = []
    index = 0
    while index < 16:
        try:
            info = win32api.EnumDisplayDevices(device, index, EDD_GET_DEVICE_INTERFACE_NAME)
        except Exception:
            break
        path = info.DeviceID or ""
        if path:
            active = bool(int(getattr(info, "StateFlags", 0) or 0) & DISPLAY_DEVICE_ACTIVE)
            paths.append((path, active))
        index += 1
    return paths


async def _query_monitor(device_path: str) -> DisplayTarget:
    try:
        monitor = await DisplayMonitor.from_interface_id_async(device_path)
        name = (monitor.display_name or "").strip()
        connector = monitor.physical_connector.name.replace("_", " ").title()
        is_internal = monitor.connection_kind == DisplayMonitorConnectionKind.INTERNAL
        return DisplayTarget(name, connector, is_internal)
    except Exception as ex:
        logging.debug("DisplayMonitor lookup failed: %s", ex)
        return DisplayTarget("", "", False)


async def _query_device(device: str) -> DisplayTarget:
    """Prefer an active INTERNAL panel else first active path"""
    first: DisplayTarget | None = None
    first_active: DisplayTarget | None = None
    for path, active in _interface_paths(device):
        target = await _query_monitor(path)
        if first is None:
            first = target
        if not active:
            continue
        if first_active is None:
            first_active = target
        if target.is_internal:
            return target
    return first_active or first or DisplayTarget("", "", False)


def query_display(device: str) -> DisplayTarget:
    """Resolve metadata."""
    if not device:
        return DisplayTarget("", "", False)
    return asyncio.run(_query_device(device))

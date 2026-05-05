import ctypes as ct
from ctypes import wintypes
from dataclasses import dataclass

from core.utils.win32.bindings.user32 import user32
from core.utils.win32.constants import (
    DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME,
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME,
    DISPLAYCONFIG_MODE_INFO_SIZE,
    DISPLAYCONFIG_OUTPUT_TECHNOLOGY_MAP,
    ERROR_INSUFFICIENT_BUFFER,
    QDC_ONLY_ACTIVE_PATHS,
)
from core.utils.win32.structs import (
    DISPLAYCONFIG_DEVICE_INFO_HEADER,
    DISPLAYCONFIG_PATH_INFO,
    DISPLAYCONFIG_SOURCE_DEVICE_NAME,
    DISPLAYCONFIG_TARGET_DEVICE_NAME,
)


@dataclass(frozen=True)
class DisplayTarget:
    source_name: str
    monitor_name: str
    connection_type: str


user32.GetDisplayConfigBufferSizes.argtypes = [wintypes.UINT, ct.POINTER(wintypes.UINT), ct.POINTER(wintypes.UINT)]
user32.GetDisplayConfigBufferSizes.restype = wintypes.LONG
user32.QueryDisplayConfig.argtypes = [
    wintypes.UINT,
    ct.POINTER(wintypes.UINT),
    ct.POINTER(DISPLAYCONFIG_PATH_INFO),
    ct.POINTER(wintypes.UINT),
    ct.c_void_p,
    ct.c_void_p,
]
user32.QueryDisplayConfig.restype = wintypes.LONG
user32.DisplayConfigGetDeviceInfo.argtypes = [ct.POINTER(DISPLAYCONFIG_DEVICE_INFO_HEADER)]
user32.DisplayConfigGetDeviceInfo.restype = wintypes.LONG


def _clean(value: object) -> str:
    return str(value or "").rstrip("\x00")


def _source_name(path: DISPLAYCONFIG_PATH_INFO) -> str:
    source = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
    source.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    source.header.size = ct.sizeof(source)
    source.header.adapterId = path.sourceInfo.adapterId
    source.header.id = path.sourceInfo.id
    if user32.DisplayConfigGetDeviceInfo(ct.byref(source.header)) == 0:
        return _clean(source.viewGdiDeviceName)
    return ""


def _target_name(path: DISPLAYCONFIG_PATH_INFO) -> DISPLAYCONFIG_TARGET_DEVICE_NAME | None:
    target = DISPLAYCONFIG_TARGET_DEVICE_NAME()
    target.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
    target.header.size = ct.sizeof(target)
    target.header.adapterId = path.targetInfo.adapterId
    target.header.id = path.targetInfo.id
    if user32.DisplayConfigGetDeviceInfo(ct.byref(target.header)) == 0:
        return target
    return None


def get_active_display_targets() -> dict[str, DisplayTarget]:
    """Return active display metadata keyed by GDI source, e.g. '\\\\.\\DISPLAY1'."""
    targets: dict[str, DisplayTarget] = {}
    path_count = wintypes.UINT()
    mode_count = wintypes.UINT()
    result = user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ct.byref(path_count), ct.byref(mode_count))
    if result != 0:
        return targets

    while True:
        paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        modes = (ct.c_byte * (mode_count.value * DISPLAYCONFIG_MODE_INFO_SIZE))()
        result = user32.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS,
            ct.byref(path_count),
            paths,
            ct.byref(mode_count),
            modes,
            None,
        )
        if result != ERROR_INSUFFICIENT_BUFFER:
            break
        path_count = wintypes.UINT(path_count.value + 4)
        mode_count = wintypes.UINT(mode_count.value + 8)

    if result != 0:
        return targets

    for index in range(path_count.value):
        path = paths[index]
        source_name = _source_name(path)
        target = _target_name(path)
        if not source_name or target is None:
            continue
        targets[source_name] = DisplayTarget(
            source_name=source_name,
            monitor_name=_clean(target.monitorFriendlyDeviceName),
            connection_type=DISPLAYCONFIG_OUTPUT_TECHNOLOGY_MAP.get(target.outputTechnology, ""),
        )
    return targets

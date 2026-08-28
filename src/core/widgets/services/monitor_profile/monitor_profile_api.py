import ctypes
import logging
from dataclasses import dataclass

from core.utils.win32.bindings.display_config import (
    DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME,
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME,
    DISPLAYCONFIG_MODE_INFO,
    DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE,
    DISPLAYCONFIG_PATH_ACTIVE,
    DISPLAYCONFIG_PATH_INFO,
    DISPLAYCONFIG_ROTATION_IDENTITY,
    DISPLAYCONFIG_ROTATION_ROTATE90,
    DISPLAYCONFIG_ROTATION_ROTATE180,
    DISPLAYCONFIG_ROTATION_ROTATE270,
    DISPLAYCONFIG_SOURCE_DEVICE_NAME,
    DISPLAYCONFIG_TARGET_DEVICE_NAME,
    LUID,
    QDC_ALL_PATHS,
    QDC_ONLY_ACTIVE_PATHS,
    QDC_VIRTUAL_MODE_AWARE,
    SDC_ALLOW_CHANGES,
    SDC_APPLY,
    SDC_USE_SUPPLIED_DISPLAY_CONFIG,
    SDC_VALIDATE,
    SDC_VIRTUAL_MODE_AWARE,
    user32,
)

logger = logging.getLogger("monitor_profile_service")

_QUERY_FLAGS = QDC_ONLY_ACTIVE_PATHS | QDC_VIRTUAL_MODE_AWARE
# Plain flags (no SDC_ALLOW_CHANGES/SDC_VIRTUAL_MODE_AWARE) are the only combination
# that reliably re-enables a disabled monitor in testing.
_ENABLE_FLAGS = SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_APPLY
_APPLY_FLAGS = SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_APPLY | SDC_ALLOW_CHANGES | SDC_VIRTUAL_MODE_AWARE
_VALIDATE_FLAGS = SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_VALIDATE | SDC_VIRTUAL_MODE_AWARE

_ROTATION_NAMES = {
    DISPLAYCONFIG_ROTATION_IDENTITY: "Landscape",
    DISPLAYCONFIG_ROTATION_ROTATE90: "Portrait",
    DISPLAYCONFIG_ROTATION_ROTATE180: "Landscape (flipped)",
    DISPLAYCONFIG_ROTATION_ROTATE270: "Portrait (flipped)",
}


@dataclass(frozen=True)
class MonitorInfo:
    """Friendly description of one active monitor."""

    device_name: str  # GDI device name, e.g. \\.\DISPLAY1
    friendly_name: str  # EDID name, e.g. "DELL U2723QE"
    resolution: str  # e.g. "2560x1440"
    position: tuple[int, int]  # desktop position of the source surface
    refresh_rate: str  # e.g. "60" or "59.94"
    rotation: str  # human readable rotation
    is_primary: bool


class MonitorProfileError(Exception):
    """Raised when a display configuration cannot be captured or applied."""


def get_monitors() -> list[MonitorInfo]:
    """Return a friendly description of every currently active monitor."""
    paths, modes = _query_active_config()
    monitors: list[MonitorInfo] = []
    for path in paths:
        if not path.flags & DISPLAYCONFIG_PATH_ACTIVE:
            continue
        source_name = _get_source_name(path)
        mode = _find_source_mode(path, modes)
        position = (mode.position.x, mode.position.y) if mode else (0, 0)
        width = mode.width if mode else 0
        height = mode.height if mode else 0
        refresh = path.targetInfo.refreshRate
        refresh_str = f"{refresh.Numerator / refresh.Denominator:g}" if refresh.Denominator else "?"
        monitor = MonitorInfo(
            device_name=source_name,
            friendly_name=_get_target_name(path) or source_name,
            resolution=f"{width}x{height}",
            position=position,
            refresh_rate=refresh_str,
            rotation=_ROTATION_NAMES.get(path.targetInfo.rotation, "Unknown"),
            is_primary=position == (0, 0),
        )
        monitors.append(monitor)
    return monitors


def capture_profile() -> dict:
    """Capture the current display configuration as a JSON-serialisable profile dict."""
    paths, modes = _query_active_config()
    return {
        "paths": [_path_to_dict(p) for p in paths if p.flags & DISPLAYCONFIG_PATH_ACTIVE],
        "modes": [_mode_to_dict(m) for m in modes],
    }


def apply_profile(profile: dict) -> None:
    """Apply a previously captured profile. Raises MonitorProfileError on failure."""
    paths = [_path_from_dict(d) for d in profile.get("paths", [])]
    modes = [_mode_from_dict(d) for d in profile.get("modes", [])]
    result = _set_display_config(paths, modes, _APPLY_FLAGS)
    if result != 0:
        raise MonitorProfileError(f"SetDisplayConfig failed with error code {result}")


def validate_profile(profile: dict) -> bool:
    """Return True when Windows reports the profile as applicable."""
    paths = [_path_from_dict(d) for d in profile.get("paths", [])]
    modes = [_mode_from_dict(d) for d in profile.get("modes", [])]
    return _set_display_config(paths, modes, _VALIDATE_FLAGS) == 0


def set_monitor_enabled(monitor: MonitorInfo, enabled: bool) -> None:
    """Enable or disable a single monitor.

    Disabling applies a config containing only the other active paths.
    Re-enabling queries the CCD database (QDC_DATABASE_CURRENT) and applies
    its stored paths+modes with plain flags, which brings disabled monitors
    back at their last saved mode.
    """
    if enabled:
        paths, modes = _query_database_config()
        result = _set_display_config(paths, modes, _ENABLE_FLAGS)
        if result != 0:
            raise MonitorProfileError(f"Failed to re-enable monitor (error {result})")
        return

    paths, modes = _query_active_config()
    active = [p for p in paths if p.flags & DISPLAYCONFIG_PATH_ACTIVE]
    remaining = []
    for p in active:
        name = _get_source_name(p)
        if name and name != monitor.device_name:
            remaining.append(p)
    if len(remaining) == len(active):
        return  # Monitor not found among active paths
    kept_modes = _modes_for_paths(remaining, modes)
    result = _set_display_config(remaining, kept_modes, _APPLY_FLAGS)
    if result != 0:
        raise MonitorProfileError(f"Failed to disable monitor (error {result})")


def get_inactive_monitors() -> list[str]:
    """Return friendly names of monitors that are connected but currently disabled."""
    flags = QDC_ALL_PATHS | QDC_VIRTUAL_MODE_AWARE
    all_paths: list = []
    for _attempt in range(4):
        path_count = ctypes.c_uint32(0)
        mode_count = ctypes.c_uint32(0)
        if user32.GetDisplayConfigBufferSizes(flags, ctypes.byref(path_count), ctypes.byref(mode_count)) != 0:
            return []
        path_array = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        mode_array = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
        result = user32.QueryDisplayConfig(
            flags,
            ctypes.byref(path_count),
            path_array,
            ctypes.byref(mode_count),
            mode_array,
            None,
        )
        if result == 0:
            all_paths = list(path_array)[: path_count.value]
            break
        if result != 122:  # ERROR_INSUFFICIENT_BUFFER
            return []
    if not all_paths:
        return []

    active_targets = {_get_target_name(p) for p in all_paths if p.flags & DISPLAYCONFIG_PATH_ACTIVE}
    active_targets.discard("")
    names: list[str] = []
    seen: set[str] = set()
    for p in all_paths:
        if p.flags & DISPLAYCONFIG_PATH_ACTIVE or not p.targetInfo.targetAvailable:
            continue
        name = _get_target_name(p)
        if not name or name in seen or name in active_targets:
            continue
        seen.add(name)
        names.append(name)
    return names


# ---------------------------------------------------------------- internals


def _modes_for_paths(paths: list, modes: list) -> list:
    """Return the subset of modes referenced by the given paths."""
    kept = []
    for p in paths:
        for m in modes:
            if (
                m.adapterId.LowPart == p.sourceInfo.adapterId.LowPart
                and m.adapterId.HighPart == p.sourceInfo.adapterId.HighPart
                and (m.id == p.sourceInfo.id or m.id == p.targetInfo.id)
            ):
                if m not in kept:
                    kept.append(m)
    return kept


def _query_database_config() -> tuple[list, list]:
    """Query the CCD persistence database (QDC_DATABASE_CURRENT)."""
    import ctypes

    from core.utils.win32.bindings.display_config import QDC_DATABASE_CURRENT

    path_count = ctypes.c_uint32(0)
    mode_count = ctypes.c_uint32(0)
    if (
        user32.GetDisplayConfigBufferSizes(QDC_DATABASE_CURRENT, ctypes.byref(path_count), ctypes.byref(mode_count))
        != 0
    ):
        raise MonitorProfileError("GetDisplayConfigBufferSizes failed")
    path_array = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
    mode_array = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
    topology = ctypes.c_uint32(0)
    result = user32.QueryDisplayConfig(
        QDC_DATABASE_CURRENT,
        ctypes.byref(path_count),
        path_array,
        ctypes.byref(mode_count),
        mode_array,
        ctypes.byref(topology),
    )
    if result != 0:
        raise MonitorProfileError(f"QueryDisplayConfig failed with error code {result}")
    return list(path_array)[: path_count.value], list(mode_array)[: mode_count.value]


def _query_active_config() -> tuple[list, list]:
    for _attempt in range(4):
        path_count = ctypes.c_uint32(0)
        mode_count = ctypes.c_uint32(0)
        if user32.GetDisplayConfigBufferSizes(_QUERY_FLAGS, ctypes.byref(path_count), ctypes.byref(mode_count)) != 0:
            raise MonitorProfileError("GetDisplayConfigBufferSizes failed")
        path_array = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        mode_array = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
        result = user32.QueryDisplayConfig(
            _QUERY_FLAGS,
            ctypes.byref(path_count),
            path_array,
            ctypes.byref(mode_count),
            mode_array,
            None,
        )
        if result == 0:
            return list(path_array)[: path_count.value], list(mode_array)[: mode_count.value]
        if result != 122:  # ERROR_INSUFFICIENT_BUFFER - retry with new sizes
            raise MonitorProfileError(f"QueryDisplayConfig failed with error code {result}")
    raise MonitorProfileError("QueryDisplayConfig kept reporting an insufficient buffer")


def _set_display_config(paths: list, modes: list, flags: int) -> int:
    path_array = (DISPLAYCONFIG_PATH_INFO * len(paths))(*paths)
    mode_array = (DISPLAYCONFIG_MODE_INFO * len(modes))(*modes)
    return user32.SetDisplayConfig(len(paths), path_array, len(modes), mode_array, flags)


def _get_source_name(path) -> str:
    info = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
    info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    info.header.size = ctypes.sizeof(info)
    info.header.adapterId = path.sourceInfo.adapterId
    info.header.id = path.sourceInfo.id
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info.header)) == 0:
        return info.viewGdiDeviceName.split("\x00")[0] if info.viewGdiDeviceName else ""
    return ""


def _get_target_name(path) -> str:
    info = DISPLAYCONFIG_TARGET_DEVICE_NAME()
    info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
    info.header.size = ctypes.sizeof(info)
    info.header.adapterId = path.targetInfo.adapterId
    info.header.id = path.targetInfo.id
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info.header)) == 0:
        return info.monitorFriendlyDeviceName.split("\x00")[0] if info.monitorFriendlyDeviceName else ""
    return ""


def _find_source_mode(path, modes):
    """Return the DISPLAYCONFIG_SOURCE_MODE for a path, or None.

    Under QDC_VIRTUAL_MODE_AWARE the source modeInfoIdx may be packed or invalid,
    so match on adapter LUID + source id as a fallback.
    """
    idx = path.sourceInfo.modeInfoIdx & 0xFFFF
    if idx != 0xFFFF and 0 <= idx < len(modes):
        mode = modes[idx]
        if mode.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
            return mode.sourceMode
    for mode in modes:
        if (
            mode.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
            and mode.id == path.sourceInfo.id
            and mode.adapterId.LowPart == path.sourceInfo.adapterId.LowPart
            and mode.adapterId.HighPart == path.sourceInfo.adapterId.HighPart
        ):
            return mode.sourceMode
    return None


# ------------------------------------------------- profile (de)serialisation


def _rational_to_dict(r) -> dict:
    return {"num": r.Numerator, "den": r.Denominator}


def _path_to_dict(p: DISPLAYCONFIG_PATH_INFO) -> dict:
    return {
        "source": {
            "adapter_luid": [p.sourceInfo.adapterId.LowPart, p.sourceInfo.adapterId.HighPart],
            "id": p.sourceInfo.id,
            "mode_info_idx": p.sourceInfo.modeInfoIdx,
            "status_flags": p.sourceInfo.statusFlags,
        },
        "target": {
            "adapter_luid": [p.targetInfo.adapterId.LowPart, p.targetInfo.adapterId.HighPart],
            "id": p.targetInfo.id,
            "mode_info_idx": p.targetInfo.modeInfoIdx,
            "output_technology": p.targetInfo.outputTechnology,
            "rotation": p.targetInfo.rotation,
            "scaling": p.targetInfo.scaling,
            "refresh_rate": _rational_to_dict(p.targetInfo.refreshRate),
            "scan_line_ordering": p.targetInfo.scanLineOrdering,
            "status_flags": p.targetInfo.statusFlags,
        },
        "flags": p.flags,
    }


def _mode_to_dict(m: DISPLAYCONFIG_MODE_INFO) -> dict:
    data = {
        "info_type": m.infoType,
        "id": m.id,
        "adapter_luid": [m.adapterId.LowPart, m.adapterId.HighPart],
    }
    if m.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
        data["source_mode"] = {
            "width": m.sourceMode.width,
            "height": m.sourceMode.height,
            "pixel_format": m.sourceMode.pixelFormat,
            "position": [m.sourceMode.position.x, m.sourceMode.position.y],
        }
    else:
        signal = m.targetMode.targetVideoSignalInfo
        data["target_mode"] = {
            "pixel_rate": signal.pixelRate,
            "h_sync_freq": _rational_to_dict(signal.hSyncFreq),
            "v_sync_freq": _rational_to_dict(signal.vSyncFreq),
            "active_size": [signal.activeSize.cx, signal.activeSize.cy],
            "total_size": [signal.totalSize.cx, signal.totalSize.cy],
            "video_standard": signal.videoStandard,
            "scan_line_ordering": signal.scanLineOrdering,
        }
    return data


def _luid_from_pair(pair: list) -> LUID:
    luid = LUID()
    luid.LowPart = int(pair[0]) & 0xFFFFFFFF
    luid.HighPart = int(pair[1]) & 0xFFFFFFFF
    return luid


def _path_from_dict(d: dict) -> DISPLAYCONFIG_PATH_INFO:
    p = DISPLAYCONFIG_PATH_INFO()
    src, tgt = d["source"], d["target"]
    p.sourceInfo.adapterId = _luid_from_pair(src["adapter_luid"])
    p.sourceInfo.id = src["id"]
    p.sourceInfo.modeInfoIdx = src["mode_info_idx"]
    p.sourceInfo.statusFlags = src.get("status_flags", 0)
    p.targetInfo.adapterId = _luid_from_pair(tgt["adapter_luid"])
    p.targetInfo.id = tgt["id"]
    p.targetInfo.modeInfoIdx = tgt["mode_info_idx"]
    p.targetInfo.outputTechnology = tgt["output_technology"]
    p.targetInfo.rotation = tgt["rotation"]
    p.targetInfo.scaling = tgt["scaling"]
    p.targetInfo.refreshRate.Numerator = tgt["refresh_rate"]["num"]
    p.targetInfo.refreshRate.Denominator = tgt["refresh_rate"]["den"]
    p.targetInfo.scanLineOrdering = tgt["scan_line_ordering"]
    p.targetInfo.statusFlags = tgt.get("status_flags", 0)
    p.flags = d["flags"]
    return p


def _mode_from_dict(d: dict) -> DISPLAYCONFIG_MODE_INFO:
    m = DISPLAYCONFIG_MODE_INFO()
    m.infoType = d["info_type"]
    m.id = d["id"]
    m.adapterId = _luid_from_pair(d["adapter_luid"])
    if d["info_type"] == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
        sm = d["source_mode"]
        m.sourceMode.width = sm["width"]
        m.sourceMode.height = sm["height"]
        m.sourceMode.pixelFormat = sm["pixel_format"]
        m.sourceMode.position.x = sm["position"][0]
        m.sourceMode.position.y = sm["position"][1]
    else:
        tm = d["target_mode"]
        signal = m.targetMode.targetVideoSignalInfo
        signal.pixelRate = tm["pixel_rate"]
        signal.hSyncFreq.Numerator = tm["h_sync_freq"]["num"]
        signal.hSyncFreq.Denominator = tm["h_sync_freq"]["den"]
        signal.vSyncFreq.Numerator = tm["v_sync_freq"]["num"]
        signal.vSyncFreq.Denominator = tm["v_sync_freq"]["den"]
        signal.activeSize.cx = tm["active_size"][0]
        signal.activeSize.cy = tm["active_size"][1]
        signal.totalSize.cx = tm["total_size"][0]
        signal.totalSize.cy = tm["total_size"][1]
        signal.videoStandard = tm["video_standard"]
        signal.scanLineOrdering = tm["scan_line_ordering"]
    return m

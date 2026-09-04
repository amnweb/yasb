import ctypes
import json
import logging
from dataclasses import dataclass

from core.utils.win32.bindings.display_config import (
    DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME,
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME,
    DISPLAYCONFIG_MODE_INFO,
    DISPLAYCONFIG_MODE_INFO_TYPE_DESKTOP_IMAGE,
    DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE,
    DISPLAYCONFIG_MODE_INFO_TYPE_TARGET,
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
        "targets": [_target_identity(p) for p in paths if p.flags & DISPLAYCONFIG_PATH_ACTIVE],
    }


def get_active_monitor_names() -> list[str]:
    """Return friendly names of all currently active monitors, in path order."""
    try:
        paths, _ = _query_active_config()
    except MonitorProfileError:
        return []
    names: list[str] = []
    for path in paths:
        if not path.flags & DISPLAYCONFIG_PATH_ACTIVE:
            continue
        name = _get_target_name(path)
        if name:
            names.append(name)
    return names


def apply_profile(profile: dict) -> None:
    """Apply a previously captured profile. Raises MonitorProfileError on failure.

    Adapter LUIDs and GDI device names change across reboots, so stale LUIDs in
    the profile are remapped to the current adapters before applying.
    """
    paths, modes = _remap_profile_luids(profile)
    result = _set_display_config(paths, modes, _APPLY_FLAGS)
    if result != 0:
        raise MonitorProfileError(f"SetDisplayConfig failed with error code {result}")


def validate_profile(profile: dict) -> bool:
    """Return True when Windows reports the profile as applicable."""
    try:
        paths, modes = _remap_profile_luids(profile)
        if not paths or not modes:
            return False
        return _set_display_config(paths, modes, _VALIDATE_FLAGS) == 0
    except Exception:
        return False


def profile_matches_current(profile: dict, current: dict | None = None) -> bool:
    """Check if the given profile layout matches the current active display configuration."""
    if current is None:
        try:
            current = capture_profile()
        except Exception:
            return False

    prof_paths = [p for p in profile.get("paths", []) if p.get("flags", 0) & DISPLAYCONFIG_PATH_ACTIVE]
    curr_paths = [p for p in current.get("paths", []) if p.get("flags", 0) & DISPLAYCONFIG_PATH_ACTIVE]
    if len(prof_paths) != len(curr_paths):
        return False

    prof_modes = profile.get("modes", [])
    curr_modes = current.get("modes", [])
    prof_targets = profile.get("targets", [])
    curr_targets = current.get("targets", [])

    for i, pp in enumerate(prof_paths):
        pp_target_id = pp["target"]["id"]
        pp_dev_path = prof_targets[i].get("device_path") if i < len(prof_targets) else ""

        matching_cp = None
        for j, cp in enumerate(curr_paths):
            cp_dev_path = curr_targets[j].get("device_path") if j < len(curr_targets) else ""
            if pp_dev_path and cp_dev_path and pp_dev_path == cp_dev_path:
                matching_cp = cp
                break
            if cp["target"]["id"] == pp_target_id:
                matching_cp = cp
                break
        if not matching_cp:
            return False

        if matching_cp["target"].get("rotation") != pp["target"].get("rotation"):
            return False

        pp_src_luid = tuple(pp["source"]["adapter_luid"])
        pp_src_id = pp["source"]["id"]
        pp_sm = next(
            (
                m
                for m in prof_modes
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and tuple(m["adapter_luid"]) == pp_src_luid
                and m["id"] == pp_src_id
            ),
            None,
        )

        cp_src_luid = tuple(matching_cp["source"]["adapter_luid"])
        cp_src_id = matching_cp["source"]["id"]
        cp_sm = next(
            (
                m
                for m in curr_modes
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and tuple(m["adapter_luid"]) == cp_src_luid
                and m["id"] == cp_src_id
            ),
            None,
        )

        if not pp_sm or not cp_sm:
            return False

        if pp_sm.get("source_mode", {}).get("width") != cp_sm.get("source_mode", {}).get("width"):
            return False
        if pp_sm.get("source_mode", {}).get("height") != cp_sm.get("source_mode", {}).get("height"):
            return False
        if pp_sm.get("source_mode", {}).get("position") != cp_sm.get("source_mode", {}).get("position"):
            return False

    return True


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
    if not remaining:
        raise MonitorProfileError("Cannot disable the last active monitor")

    shift_x, shift_y = 0, 0
    first_sm = None
    for p in remaining:
        p_src_luid = (p.sourceInfo.adapterId.LowPart, p.sourceInfo.adapterId.HighPart)
        sm = next(
            (
                m
                for m in modes
                if m.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and (m.adapterId.LowPart, m.adapterId.HighPart) == p_src_luid
                and m.id == p.sourceInfo.id
            ),
            None,
        )
        if sm:
            first_sm = sm
            break
    if first_sm and (first_sm.sourceMode.position.x != 0 or first_sm.sourceMode.position.y != 0):
        shift_x = first_sm.sourceMode.position.x
        shift_y = first_sm.sourceMode.position.y

    kept_paths = []
    kept_modes = []

    for k, p in enumerate(remaining):
        p_copy = DISPLAYCONFIG_PATH_INFO()
        p_copy.sourceInfo = p.sourceInfo
        p_copy.targetInfo = p.targetInfo
        p_copy.flags = p.flags
        p_copy.sourceInfo.modeInfoIdx = ((k * 3 + 1) << 16) | 0xFFFF
        p_copy.targetInfo.modeInfoIdx = ((k * 3) << 16) | (k * 3 + 2)

        p_src_luid = (p.sourceInfo.adapterId.LowPart, p.sourceInfo.adapterId.HighPart)
        p_tgt_luid = (p.targetInfo.adapterId.LowPart, p.targetInfo.adapterId.HighPart)

        tm = next(
            (
                m
                for m in modes
                if m.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_TARGET
                and (m.adapterId.LowPart, m.adapterId.HighPart) == p_tgt_luid
                and m.id == p.targetInfo.id
            ),
            None,
        )
        sm = next(
            (
                m
                for m in modes
                if m.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and (m.adapterId.LowPart, m.adapterId.HighPart) == p_src_luid
                and m.id == p.sourceInfo.id
            ),
            None,
        )
        dm = next(
            (
                m
                for m in modes
                if m.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_DESKTOP_IMAGE
                and (m.adapterId.LowPart, m.adapterId.HighPart) == p_tgt_luid
                and m.id == p.targetInfo.id
            ),
            None,
        )

        if sm and (shift_x != 0 or shift_y != 0):
            sm_copy = DISPLAYCONFIG_MODE_INFO()
            sm_copy.infoType = sm.infoType
            sm_copy.id = sm.id
            sm_copy.adapterId = sm.adapterId
            sm_copy.sourceMode.width = sm.sourceMode.width
            sm_copy.sourceMode.height = sm.sourceMode.height
            sm_copy.sourceMode.pixelFormat = sm.sourceMode.pixelFormat
            sm_copy.sourceMode.position.x = sm.sourceMode.position.x - shift_x
            sm_copy.sourceMode.position.y = sm.sourceMode.position.y - shift_y
            sm = sm_copy

        kept_paths.append(p_copy)
        kept_modes.extend([m for m in (tm, sm, dm) if m is not None])

    result = _set_display_config(kept_paths, kept_modes, _APPLY_FLAGS)
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


def _get_target_device_path(path) -> str:
    r"""Return the stable monitor device path (\?\DISPLAY#...#guid), or empty.

    Unlike adapter LUIDs and GDI device names, this path persists across reboots
    and is therefore the reliable key for identifying a physical monitor.
    """
    info = DISPLAYCONFIG_TARGET_DEVICE_NAME()
    info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
    info.header.size = ctypes.sizeof(info)
    info.header.adapterId = path.targetInfo.adapterId
    info.header.id = path.targetInfo.id
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info.header)) == 0:
        return info.monitorDevicePath.split("\x00")[0] if info.monitorDevicePath else ""
    return ""


def _target_identity(path) -> dict:
    """Capture the stable identity of a path's monitor (survives reboots)."""
    return {
        "luid": [path.targetInfo.adapterId.LowPart, path.targetInfo.adapterId.HighPart],
        "target_id": path.targetInfo.id,
        "device_path": _get_target_device_path(path),
    }


def _query_all_system_paths() -> list:
    """Query all display paths in the system (active and available/inactive)."""
    flags = QDC_ALL_PATHS | QDC_VIRTUAL_MODE_AWARE
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
            return list(path_array)[: path_count.value]
        if result != 122:
            return []
    return []


def _remap_profile_luids(profile: dict) -> tuple[list, list]:
    """Decode a profile dict, remapping stale adapter LUIDs to the current ones.

    Windows assigns new adapter LUIDs on every boot, so profiles captured in a
    previous session reference LUIDs that are no longer valid. Monitors are
    matched by their stable device path (or by target ID / output technology for
    legacy profiles), then the profile's LUIDs (paths AND modes) are translated
    to the current ones. Paths for monitors that are physically disconnected or
    missing are omitted, and positions are normalized so the primary monitor
    remains at (0, 0).
    """
    path_dicts = profile.get("paths", [])
    mode_dicts = profile.get("modes", [])
    target_identities = profile.get("targets", [])

    if not path_dicts:
        return [], []

    # Gather all current hardware targets in the system
    all_paths = _query_all_system_paths()
    if not all_paths:
        active_paths, _ = _query_active_config()
        all_paths = active_paths

    current_targets = []
    seen_target_keys = set()
    for p in all_paths:
        if not p.targetInfo.targetAvailable and not (p.flags & DISPLAYCONFIG_PATH_ACTIVE):
            continue
        dev_path = _get_target_device_path(p)
        luid = (p.targetInfo.adapterId.LowPart, p.targetInfo.adapterId.HighPart)
        tid = p.targetInfo.id
        key = (luid, tid)
        if key not in seen_target_keys:
            seen_target_keys.add(key)
            current_targets.append({
                "dev_path": dev_path,
                "name": _get_target_name(p),
                "luid": luid,
                "target_id": tid,
                "source_id": p.sourceInfo.id,
                "output_tech": p.targetInfo.outputTechnology,
                "active": bool(p.flags & DISPLAYCONFIG_PATH_ACTIVE),
            })

    matched_paths = []
    claimed_target_keys = set()

    for i, pd in enumerate(path_dicts):
        identity = target_identities[i] if i < len(target_identities) else {}
        prof_dev_path = identity.get("device_path", "")
        prof_tgt_id = pd["target"]["id"]
        prof_tech = pd["target"].get("output_technology")

        matched_target = None
        # 1) Match by stable device path
        if prof_dev_path:
            for ct in current_targets:
                key = (ct["luid"], ct["target_id"])
                if key not in claimed_target_keys and ct["dev_path"] == prof_dev_path:
                    matched_target = ct
                    break

        # 2) Fallback: match by target ID
        if not matched_target and prof_tgt_id:
            for ct in current_targets:
                key = (ct["luid"], ct["target_id"])
                if key not in claimed_target_keys and ct["target_id"] == prof_tgt_id:
                    matched_target = ct
                    break

        # 3) Fallback: match by output technology
        if not matched_target and prof_tech is not None:
            for ct in current_targets:
                key = (ct["luid"], ct["target_id"])
                if key not in claimed_target_keys and ct["output_tech"] == prof_tech:
                    matched_target = ct
                    break

        # 4) Fallback: match by available hardware target
        if not matched_target:
            for ct in current_targets:
                key = (ct["luid"], ct["target_id"])
                if key not in claimed_target_keys:
                    matched_target = ct
                    break

        if matched_target:
            claimed_target_keys.add((matched_target["luid"], matched_target["target_id"]))
            matched_paths.append((pd, matched_target))
        else:
            logger.warning(
                "Monitor in profile (device_path='%s', target_id=%d) is not connected; skipping",
                prof_dev_path,
                prof_tgt_id,
            )

    if not matched_paths:
        raise MonitorProfileError("None of the monitors in the profile are currently connected")

    # Shift coordinates if no kept monitor is at (0, 0)
    kept_positions = []
    for pd, _ in matched_paths:
        src_id = pd["source"]["id"]
        src_luid = tuple(pd["source"]["adapter_luid"])
        sm = next(
            (
                m
                for m in mode_dicts
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and tuple(m["adapter_luid"]) == src_luid
                and m["id"] == src_id
            ),
            None,
        )
        if sm and "source_mode" in sm:
            kept_positions.append(sm["source_mode"]["position"])

    shift_x, shift_y = 0, 0
    if kept_positions and not any(pos == [0, 0] for pos in kept_positions):
        shift_x, shift_y = kept_positions[0][0], kept_positions[0][1]

    final_paths = []
    final_modes = []

    for k, (pd, ct) in enumerate(matched_paths):
        new_path_dict = json.loads(json.dumps(pd))
        new_luid_list = list(ct["luid"])
        old_src_luid = tuple(pd["source"]["adapter_luid"])
        old_tgt_luid = tuple(pd["target"]["adapter_luid"])
        old_src_id = pd["source"]["id"]
        old_tgt_id = pd["target"]["id"]

        new_path_dict["source"]["adapter_luid"] = new_luid_list
        new_path_dict["target"]["adapter_luid"] = new_luid_list
        new_path_dict["target"]["id"] = ct["target_id"]
        # Set clean mode indices for Virtual Mode Aware
        new_path_dict["source"]["mode_info_idx"] = ((k * 3 + 1) << 16) | 0xFFFF
        new_path_dict["target"]["mode_info_idx"] = ((k * 3) << 16) | (k * 3 + 2)

        # Target mode (type 2)
        tm = next(
            (
                json.loads(json.dumps(m))
                for m in mode_dicts
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_TARGET
                and tuple(m["adapter_luid"]) == old_tgt_luid
                and m["id"] == old_tgt_id
            ),
            None,
        )
        # Source mode (type 1)
        sm = next(
            (
                json.loads(json.dumps(m))
                for m in mode_dicts
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
                and tuple(m["adapter_luid"]) == old_src_luid
                and m["id"] == old_src_id
            ),
            None,
        )
        # Desktop image mode (type 3)
        dm = next(
            (
                json.loads(json.dumps(m))
                for m in mode_dicts
                if m.get("info_type") == DISPLAYCONFIG_MODE_INFO_TYPE_DESKTOP_IMAGE
                and tuple(m["adapter_luid"]) == old_tgt_luid
                and m["id"] == old_tgt_id
            ),
            None,
        )

        if tm:
            tm["adapter_luid"] = new_luid_list
            tm["id"] = ct["target_id"]
        if sm:
            sm["adapter_luid"] = new_luid_list
            sm["id"] = new_path_dict["source"]["id"]
            if shift_x != 0 or shift_y != 0:
                sm["source_mode"]["position"][0] -= shift_x
                sm["source_mode"]["position"][1] -= shift_y
        if dm:
            dm["adapter_luid"] = new_luid_list
            dm["id"] = ct["target_id"]

        final_paths.append(new_path_dict)
        final_modes.extend([m for m in (tm, sm, dm) if m is not None])

    luid_map = {tuple(pd["target"]["adapter_luid"]): ct["luid"] for pd, ct in matched_paths}
    if luid_map:
        logger.info("Remapped %d adapter LUID(s) in profile", len(luid_map))

    return [_path_from_dict(d) for d in final_paths], [_mode_from_dict(d) for d in final_modes]


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

"""Read-only fan/pump RPM decoding and unambiguous component association."""

import math
import re
from typing import Any, NamedTuple, cast

from core.widgets.services.gpu.libre import normalize_name


class FanReading(NamedTuple):
    sensor_id: str
    hardware_id: str
    hardware_name: str
    name: str
    rpm: float | None


def rpm_value(node: dict[str, Any]) -> float | None:
    for raw in (node.get("RawValue"), node.get("Value")):
        if raw is None or isinstance(raw, bool) or "%" in str(raw):
            continue
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", str(raw))
        if match is None:
            continue
        value = float(match.group().replace(",", "."))
        if math.isfinite(value) and 0 <= value <= 100000:
            return value
    return None


def decode_fans(root: dict[str, Any]) -> tuple[FanReading, ...]:
    readings: dict[str, FanReading] = {}

    def visit(node: dict[str, Any], hardware_id: str = "", hardware_name: str = "") -> None:
        identifier = str(node.get("HardwareId") or "")
        if identifier and identifier != hardware_id:
            hardware_id, hardware_name = identifier, str(node.get("Text") or identifier)
        sensor_id = str(node.get("SensorId") or "")
        if "/fan/" in sensor_id:
            owner = sensor_id.split("/fan/", 1)[0]
            readings[sensor_id] = FanReading(
                sensor_id,
                owner,
                hardware_name if hardware_id == owner else owner,
                str(node.get("Text") or "Fan"),
                rpm_value(node),
            )
        children = node.get("Children", [])
        if isinstance(children, list):
            for child in cast(list[Any], children):
                if isinstance(child, dict):
                    visit(cast(dict[str, Any], child), hardware_id, hardware_name)

    visit(root)
    return tuple(readings.values())


def gpu_fans(readings: tuple[FanReading, ...], gpu_name: str, hardware_id: str | None = None) -> tuple[FanReading, ...]:
    candidates = [
        item
        for item in readings
        if item.hardware_id.startswith("/gpu-")
        and (
            item.hardware_id == hardware_id
            if hardware_id
            else normalize_name(item.hardware_name) == normalize_name(gpu_name)
        )
    ]
    owners = {item.hardware_id for item in candidates}
    return tuple(candidates) if len(owners) == 1 else ()


def motherboard_fans(readings: tuple[FanReading, ...]) -> tuple[FanReading, ...]:
    return tuple(item for item in readings if not item.hardware_id.startswith("/gpu-"))

"""Optional GPU clocks from Libre's local HTTP server, read on the native GPU worker."""

import json
import math
import re
import urllib.request
from typing import Any, NamedTuple, cast


class GpuClocks(NamedTuple):
    sensor_id: str
    name: str
    core: float | None
    memory: float | None


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\((?:tm|r)\)", "", name.lower()))


def clock_mhz(node: dict[str, Any]) -> float | None:
    raw = str(node.get("RawValue", node.get("Value", "")))
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", raw)
    if not match:
        return None
    value = float(match.group().replace(",", "."))
    if "ghz" in raw.lower():
        value *= 1000
    return value if math.isfinite(value) and value >= 0 else None


def decode_clocks(root: dict[str, Any]) -> list[GpuClocks]:
    result: list[GpuClocks] = []

    def visit(node: dict[str, Any]) -> None:
        identifier = str(node.get("HardwareId", ""))
        if identifier.startswith(("/gpu-amd/", "/gpu-nvidia/", "/gpu-intel/")):
            core: float | None = None
            memory: float | None = None

            def sensors(branch: dict[str, Any]) -> None:
                nonlocal core, memory
                sensor = str(branch.get("SensorId", ""))
                if sensor.startswith(identifier + "/clock/"):
                    name = str(branch.get("Text", "")).lower()
                    if name in ("gpu core", "gpu clock"):
                        core = clock_mhz(branch)
                    elif name in ("gpu memory", "memory clock"):
                        memory = clock_mhz(branch)
                for child in branch.get("Children", []):
                    if isinstance(child, dict):
                        sensors(cast(dict[str, Any], child))

            sensors(node)
            result.append(GpuClocks(identifier, str(node.get("Text", "")), core, memory))
            return
        for child in node.get("Children", []):
            if isinstance(child, dict):
                visit(cast(dict[str, Any], child))

    visit(root)
    return result


def match_clocks(readings: list[GpuClocks], name: str, sensor_id: str | None = None) -> GpuClocks | None:
    matches = (
        [item for item in readings if item.sensor_id == sensor_id]
        if sensor_id
        else [item for item in readings if normalize_name(item.name) == normalize_name(name)]
    )
    return matches[0] if len(matches) == 1 else None


class LibreGpuClocks:
    def __init__(self, host: str, port: int) -> None:
        self.url = f"http://{host}:{port}/data.json"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def read(self) -> list[GpuClocks]:
        try:
            with self.opener.open(self.url, timeout=0.75) as response:
                data = json.load(response)
            return decode_clocks(cast(dict[str, Any], data)) if isinstance(data, dict) else []
        except OSError, ValueError, TypeError:
            return []

"""Read CPU/GPU temperatures from Libre's local HTTP endpoint on a shared worker."""

import json
import math
import re
import threading
import time
import urllib.request
from collections import deque
from typing import Any, NamedTuple, cast

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.widgets.services.cooling.libre import FanReading, decode_fans

type HistoryPoint = tuple[float, float | None]


class TemperatureReading(NamedTuple):
    sensor_id: str
    hardware_id: str
    hardware_name: str
    kind: str
    name: str
    value: float | None


class TemperatureSnapshot(NamedTuple):
    sensors: tuple[TemperatureReading, ...]
    histories: dict[str, tuple[HistoryPoint, ...]]
    timestamp: float
    status: str = ""
    fans: tuple[FanReading, ...] = ()


def celsius(node: dict[str, Any]) -> float | None:
    for raw in (node.get("RawValue"), node.get("Value")):
        if raw is None or isinstance(raw, bool):
            continue
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", str(raw))
        if match is None:
            continue
        value = float(match.group().replace(",", "."))
        if "°f" in str(raw).lower():
            value = (value - 32) * 5 / 9
        if math.isfinite(value) and -100 <= value <= 200:
            return value
    return None


def decode_temperatures(root: dict[str, Any]) -> tuple[TemperatureReading, ...]:
    readings: dict[str, TemperatureReading] = {}

    def visit(node: dict[str, Any], hardware_id: str = "", hardware_name: str = "") -> None:
        identifier = str(node.get("HardwareId") or "")
        if identifier.startswith(("/amdcpu/", "/intelcpu/", "/cpu/", "/gpu-amd/", "/gpu-nvidia/", "/gpu-intel/")):
            if identifier != hardware_id:
                hardware_name = str(node.get("Text") or identifier)
            hardware_id = identifier
        sensor_id = str(node.get("SensorId") or "")
        if hardware_id and sensor_id.startswith(hardware_id + "/temperature/"):
            readings[sensor_id] = TemperatureReading(
                sensor_id,
                hardware_id,
                hardware_name,
                "gpu" if hardware_id.startswith("/gpu-") else "cpu",
                str(node.get("Text") or "Temperature"),
                celsius(node),
            )
        children = node.get("Children", [])
        if isinstance(children, list):
            for child in cast(list[Any], children):
                if isinstance(child, dict):
                    visit(cast(dict[str, Any], child), hardware_id, hardware_name)

    visit(root)
    return tuple(readings.values())


class TemperatureHistory:
    def __init__(self, seconds: int):
        self.seconds = seconds
        self._sensors: dict[str, TemperatureReading] = {}
        self._history: dict[str, deque[HistoryPoint]] = {}
        self._fans: dict[str, FanReading] = {}

    def collect(
        self, readings: tuple[TemperatureReading, ...], now: float, status: str = "", fans: tuple[FanReading, ...] = ()
    ) -> TemperatureSnapshot:
        current = {reading.sensor_id: reading for reading in readings}
        self._sensors.update(current)
        result: list[TemperatureReading] = []
        for identifier, sensor in self._sensors.items():
            value = current[identifier].value if identifier in current else None
            result.append(sensor._replace(value=value))
            history = self._history.setdefault(identifier, deque())
            history.append((now, value))
            while history and history[0][0] < now - self.seconds:
                history.popleft()
        current_fans = {item.sensor_id: item for item in fans}
        self._fans.update(current_fans)
        fan_readings = tuple(
            item._replace(rpm=current_fans[key].rpm if key in current_fans else None)
            for key, item in self._fans.items()
        )
        return TemperatureSnapshot(
            tuple(result), {key: tuple(points) for key, points in self._history.items()}, now, status, fan_readings
        )


class LibreTemperatures:
    def __init__(self, host: str, port: int):
        self.url = f"http://{host}:{port}/data.json"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.fans: tuple[FanReading, ...] = ()

    def read(self) -> tuple[TemperatureReading, ...]:
        self.fans = ()
        with self.opener.open(self.url, timeout=0.75) as response:
            root = json.load(response)
        if not isinstance(root, dict):
            raise ValueError("Libre returned an invalid sensor tree")
        tree = cast(dict[str, Any], root)
        self.fans = decode_fans(tree)
        return decode_temperatures(tree)


class TemperatureWorker(QThread):
    data_ready = pyqtSignal(object)
    _instances: dict[tuple[str, int, int, int], TemperatureWorker] = {}

    @classmethod
    def get_instance(cls, host: str, port: int, interval: int, history_seconds: int) -> TemperatureWorker:
        key = (host, port, interval, history_seconds)
        if key not in cls._instances:
            cls._instances[key] = cls(host, port, interval, history_seconds)
        return cls._instances[key]

    def __init__(self, host: str, port: int, interval: int, history_seconds: int):
        super().__init__()
        self._key = (host, port, interval, history_seconds)
        self._client = LibreTemperatures(host, port)
        self._history = TemperatureHistory(history_seconds)
        self._stopped = threading.Event()
        self.latest = TemperatureSnapshot((), {}, time.monotonic(), "Connecting to Libre Hardware Monitor…")
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def stop(self) -> None:
        self._stopped.set()
        self.wait(2000)
        self._instances.pop(self._key, None)

    def poll(self, now: float) -> TemperatureSnapshot:
        try:
            readings = self._client.read()
            fans = self._client.fans
            status = (
                "" if any(item.value is not None for item in readings) else "No CPU/GPU temperature readings available"
            )
        except OSError, ValueError, TypeError:
            readings = ()
            fans = ()
            status = "Libre Hardware Monitor unavailable — retrying…"
        self.latest = self._history.collect(readings, now, status, fans)
        return self.latest

    def run(self) -> None:
        period = self._key[2] / 1000
        while not self._stopped.is_set():
            started = time.monotonic()
            snapshot = self.poll(started)
            if not self._stopped.is_set():
                self.data_ready.emit(snapshot)
            self._stopped.wait(max(0.0, period - (time.monotonic() - started)))

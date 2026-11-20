"""Reads wireless device batteries from BatteryHub (https://github.com/krisgfx9/Wireless-Device-Battery-Monitor).

BatteryHub prints a JSON array with ``BatteryHub.exe --json`` and exits, so no
background service or IPC is needed: we run it on a worker thread and parse the output.
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class WirelessDevice:
    key: str
    name: str
    via: str
    kind: str
    percent: int | None
    level: str
    detail: str
    charging: bool
    asleep: bool
    connected: bool
    millivolts: int | None


def _opt_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value >= 0 else None


def parse_devices(raw: str) -> list[WirelessDevice]:
    """Parse the output of ``BatteryHub.exe --json``. Raises ValueError on invalid output."""
    start = raw.find("[")  # tolerate any text printed before the array
    if start == -1:
        raise ValueError("no JSON array in BatteryHub output")
    payload = json.loads(raw[start:])
    if not isinstance(payload, list):
        raise ValueError("BatteryHub output is not a JSON array")

    devices: list[WirelessDevice] = []
    for item in payload:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            continue
        d: dict[str, object] = item  # pyright: ignore[reportUnknownVariableType]
        devices.append(
            WirelessDevice(
                key=str(d.get("key", "")),
                name=str(d.get("name", "")),
                via=str(d.get("via", "")),
                kind=str(d.get("kind", "")).lower(),
                percent=_opt_int(d.get("percent")),
                level=str(d.get("level", "")),
                detail=str(d.get("detail", "")),
                charging=bool(d.get("charging", False)),
                asleep=bool(d.get("asleep", False)),
                connected=bool(d.get("connected", True)),
                millivolts=_opt_int(d.get("millivolts")),
            )
        )
    return devices


def fetch_devices(executable: str, timeout: float = 15.0) -> list[WirelessDevice]:
    """Run BatteryHub once and return its devices. Raises on failure."""
    result = subprocess.run(
        [executable, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    return parse_devices(result.stdout)


class WirelessBatteryWorker(QThread):
    """Polls BatteryHub in a background thread. One shared worker for all widget instances."""

    _instance: WirelessBatteryWorker | None = None
    data_ready = pyqtSignal(object)  # list[WirelessDevice]
    error = pyqtSignal(str)

    @classmethod
    def get_instance(cls, executable: str, update_interval: int) -> WirelessBatteryWorker:
        if cls._instance is None:
            cls._instance = cls(executable, update_interval)
        return cls._instance

    def __init__(self, executable: str, update_interval: int, parent: QObject | None = None):
        super().__init__(parent)
        self._executable = executable
        self._update_interval = update_interval
        self._stop_event = threading.Event()
        self._refresh_event = threading.Event()
        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.aboutToQuit.connect(self.stop)

    def refresh(self) -> None:
        """Poll right away instead of waiting for the next interval."""
        self._refresh_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._refresh_event.set()
        self.wait(2000)
        WirelessBatteryWorker._instance = None

    def run(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                devices = fetch_devices(self._executable)
                if not self._stop_event.is_set():
                    self.data_ready.emit(devices)
            except FileNotFoundError:
                self.error.emit(f"BatteryHub executable not found: {self._executable}")
            except Exception as e:
                logging.debug("BatteryHub error: %s", e)
                self.error.emit(str(e))
            self._refresh_event.wait(self._update_interval / 1000)
            self._refresh_event.clear()

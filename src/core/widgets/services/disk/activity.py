"""Live logical-volume activity and read/write throughput from Windows PDH."""

import ctypes
import math
import threading
from ctypes import wintypes
from typing import NamedTuple

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.pdh import pdh
from core.utils.win32.constants import PDH_FMT_DOUBLE
from core.utils.win32.structs import PDH_FMT_COUNTERVALUE_DOUBLE


class DiskActivity(NamedTuple):
    usage: float | None = None
    read_bps: float | None = None
    write_bps: float | None = None


class DiskActivityReader:
    def __init__(self) -> None:
        query = wintypes.HANDLE()
        self.query = query if pdh.PdhOpenQueryW(None, None, ctypes.byref(query)) == 0 else None
        self.counters: dict[str, tuple[wintypes.HANDLE | None, ...]] = {}

    def add_volumes(self, volumes: set[str]) -> None:
        for label in volumes - self.counters.keys():
            counters: list[wintypes.HANDLE | None] = []
            for metric in ("% Idle Time", "Disk Read Bytes/sec", "Disk Write Bytes/sec"):
                counter = wintypes.HANDLE()
                path = f"\\LogicalDisk({label}:)\\{metric}"
                valid = (
                    self.query is not None
                    and pdh.PdhAddEnglishCounterW(self.query, path, None, ctypes.byref(counter)) == 0
                )
                counters.append(counter if valid else None)
            self.counters[label] = tuple(counters)

    @staticmethod
    def _value(counter: wintypes.HANDLE | None) -> float | None:
        if counter is None:
            return None
        value = PDH_FMT_COUNTERVALUE_DOUBLE()
        if pdh.PdhGetFormattedCounterValue(counter, PDH_FMT_DOUBLE, None, ctypes.byref(value)) != 0:
            return None
        return value.doubleValue if value.CStatus in (0, 1) and math.isfinite(value.doubleValue) else None

    def collect(self) -> dict[str, DiskActivity]:
        valid = self.query is not None and pdh.PdhCollectQueryData(self.query) == 0
        result: dict[str, DiskActivity] = {}
        for label, counters in self.counters.items():
            idle, read, write = (self._value(counter) if valid else None for counter in counters)
            result[label] = DiskActivity(
                min(100.0, max(0.0, 100 - idle)) if idle is not None else None,
                max(0.0, read) if read is not None else None,
                max(0.0, write) if write is not None else None,
            )
        return result

    def close(self) -> None:
        if self.query is not None:
            pdh.PdhCloseQuery(self.query)
            self.query = None


class DiskActivityWorker(QThread):
    _instance: DiskActivityWorker | None = None
    data_ready = pyqtSignal(dict)

    @classmethod
    def get_instance(cls) -> DiskActivityWorker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._volumes: set[str] = set()
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def add_volumes(self, volumes: list[str]) -> None:
        with self._lock:
            self._volumes.update(label.upper().rstrip(":\\") for label in volumes)

    def stop(self) -> None:
        self._stopped.set()
        self.wait(2000)
        DiskActivityWorker._instance = None

    def run(self) -> None:
        reader = DiskActivityReader()
        try:
            while not self._stopped.is_set():
                with self._lock:
                    volumes = set(self._volumes)
                reader.add_volumes(volumes)
                self.data_ready.emit(reader.collect())
                self._stopped.wait(1)
        finally:
            reader.close()

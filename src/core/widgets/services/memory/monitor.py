from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.widgets.services.memory.memory_api import MemoryData, MemoryWorker, SwapMemory, VirtualMemory

MIN_INTERVAL_MS = 1000
MAX_INTERVAL_MS = 60000


def memory_info(data: MemoryData) -> dict[str, Any]:
    return {"virtual": data.virtual._asdict(), "swap": data.swap._asdict(), "cached_bytes": data.cached_bytes}


class MemoryMonitor(QObject):
    dataChanged = pyqtSignal()
    updateIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._update_interval = 5000
        self._data = memory_info(MemoryData(VirtualMemory(0, 0, 0.0, 0, 0), SwapMemory(0, 0, 0, 0.0)))
        self._worker: MemoryWorker | None = None

        # QML sets updateInterval after creating the object, so the worker is joined once that is done
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

    @qml_property("QVariantMap", notify=dataChanged)
    def data(self) -> dict[str, Any]:
        return self._data

    def _get_update_interval(self) -> int:
        return self._update_interval

    def _set_update_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value == self._update_interval:
            return
        self._update_interval = value
        self.updateIntervalChanged.emit()
        if self._worker is not None:
            self._worker.set_update_interval(value)

    updateInterval = pyqtProperty(int, _get_update_interval, _set_update_interval, notify=updateIntervalChanged)

    def _start(self) -> None:
        self._worker = MemoryWorker.get_instance(self._update_interval)
        self._worker.set_update_interval(self._update_interval)
        self._worker.data_ready.connect(self._on_data)
        if not self._worker.isRunning():
            self._worker.start()

    @pyqtSlot(object)
    def _on_data(self, data: MemoryData) -> None:
        self._data = memory_info(data)
        self.dataChanged.emit()

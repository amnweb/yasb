from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.widgets.services.gpu.gpu_api import GpuData, GpuWorker

MIN_INTERVAL_MS = 2000
MAX_INTERVAL_MS = 60000


def gpu_info(data: GpuData) -> dict[str, Any]:
    return {
        "index": data.gpu_index,
        "name": data.name,
        "utilization": data.utilization,
        "mem_total": data.mem_total,
        "mem_used": data.mem_used,
        "mem_free": data.mem_free,
        "mem_shared_total": data.mem_shared_total,
        "mem_shared_used": data.mem_shared_used,
        "temp": data.temp,
        "fan_speed": data.fan_speed,
        "power_draw": data.power_draw,
    }


class GpuMonitor(QObject):
    dataChanged = pyqtSignal()
    availableChanged = pyqtSignal()
    gpuIndexChanged = pyqtSignal()
    updateIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._gpu_index = 0
        self._update_interval = MIN_INTERVAL_MS
        self._data = gpu_info(GpuData(0, "", 0.0, 0, 0, 0, 0, 0, 0, 0, 0.0))
        self._available = False
        self._worker: GpuWorker | None = None

        # QML sets gpuIndex and updateInterval after creating the object, so the worker is joined once that is done
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

    @qml_property("QVariantMap", notify=dataChanged)
    def data(self) -> dict[str, Any]:
        return self._data

    @qml_property(bool, notify=availableChanged)
    def available(self) -> bool:
        return self._available

    def _get_gpu_index(self) -> int:
        return self._gpu_index

    def _set_gpu_index(self, value: int) -> None:
        value = max(0, value)
        if value == self._gpu_index:
            return
        self._gpu_index = value
        self.gpuIndexChanged.emit()
        if self._worker is not None:
            self._worker.watch(value)

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

    gpuIndex = pyqtProperty(int, _get_gpu_index, _set_gpu_index, notify=gpuIndexChanged)
    updateInterval = pyqtProperty(int, _get_update_interval, _set_update_interval, notify=updateIntervalChanged)

    def _start(self) -> None:
        self._worker = GpuWorker.get_instance(self._update_interval)
        self._worker.set_update_interval(self._update_interval)
        self._worker.data_ready.connect(self._on_data)
        self._worker.watch(self._gpu_index)

    @pyqtSlot(list)
    def _on_data(self, gpus: list[GpuData]) -> None:
        gpu = next((gpu for gpu in gpus if gpu.gpu_index == self._gpu_index), None)
        if gpu is not None:
            self._data = gpu_info(gpu)
            self.dataChanged.emit()
        if (gpu is not None) != self._available:
            self._available = gpu is not None
            self.availableChanged.emit()

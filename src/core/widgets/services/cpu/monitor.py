from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.widgets.services.cpu.cpu_api import CpuData, CpuFreq, CpuWorker

MIN_INTERVAL_MS = 1000
MAX_INTERVAL_MS = 60000


def cpu_info(data: CpuData) -> dict[str, Any]:
    return {
        "cores": {"physical": data.cores_physical, "total": data.cores_logical},
        "freq": {"current": data.freq.current, "min": data.freq.min, "max": data.freq.max},
        "percent": {"total": data.percent, "core": list(data.percent_per_core)},
    }


class CpuMonitor(QObject):
    dataChanged = pyqtSignal()
    updateIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._update_interval = MIN_INTERVAL_MS
        self._data = cpu_info(CpuData(CpuFreq(0, 0, 0), 0, [0], 1, 1))
        self._worker: CpuWorker | None = None

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
        self._worker = CpuWorker.get_instance(self._update_interval)
        self._worker.set_update_interval(self._update_interval)
        self._worker.data_ready.connect(self._on_data)
        if not self._worker.isRunning():
            self._worker.start()

    @pyqtSlot(object)
    def _on_data(self, data: CpuData) -> None:
        self._data = cpu_info(data)
        self.dataChanged.emit()

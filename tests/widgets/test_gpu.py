import pytest
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.gpu import monitor as monitor_module
from core.widgets.services.gpu.gpu_api import GpuData
from core.widgets.services.gpu.monitor import GpuMonitor
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

GIB = 1024**3


def _gpu(index: int, utilization: float) -> GpuData:
    return GpuData(index, f"GPU {index}", utilization, 8 * GIB, GIB, 7 * GIB, 0, 0, 0, 0, 0.0)


class FakeWorker(QObject):
    data_ready = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.interval = 0
        self.watched: list[int] = []

    def set_update_interval(self, update_interval: int) -> None:
        self.interval = update_interval

    def watch(self, index: int) -> None:
        self.watched.append(index)


@pytest.fixture
def worker(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWorker:
    worker = FakeWorker()

    def get_instance(_update_interval: int) -> FakeWorker:
        return worker

    monkeypatch.setattr(monitor_module.GpuWorker, "get_instance", get_instance)
    return worker


def test_the_monitor_follows_its_gpu(worker: FakeWorker):
    monitor = GpuMonitor()
    monitor.setProperty("gpuIndex", 1)
    monitor.setProperty("updateInterval", 3000)
    wait(10)
    assert (worker.watched, worker.interval) == ([1], 3000)

    worker.data_ready.emit([_gpu(0, 10.0), _gpu(1, 55.5)])
    assert monitor.property("available")
    assert monitor.property("data")["name"] == "GPU 1"
    assert monitor.property("data")["utilization"] == 55.5

    worker.data_ready.emit([_gpu(0, 10.0)])
    assert not monitor.property("available")


def test_the_widget_shows_usage_and_memory(worker: FakeWorker):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Gpu" / "Gpu.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    assert widget.property("implicitWidth") == 0

    worker.data_ready.emit([_gpu(0, 12.5)])
    label = find_item(widget, "label")
    assert label is not None
    assert widget.property("implicitWidth") > 0
    assert label.property("text") == "12.5%"

    widget.setProperty("showAlternate", True)
    assert label.property("text") == "1.0G/8.0G"

import pytest
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.bar.manager import QML_IMPORT_PATH
from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.memory import monitor as monitor_module
from core.widgets.services.memory.memory_api import MemoryData, SwapMemory, VirtualMemory
from core.widgets.services.memory.monitor import MemoryMonitor
from tests.support.qt import find_item, wait

GIB = 1024**3
SAMPLE = MemoryData(
    VirtualMemory(16 * GIB, 8 * GIB, 50.0, 8 * GIB, 8 * GIB), SwapMemory(4 * GIB, GIB // 2, 3 * GIB, 12.5), GIB
)


class FakeWorker(QObject):
    data_ready = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.interval = 0
        self.running = False

    def set_update_interval(self, update_interval: int) -> None:
        self.interval = update_interval

    def isRunning(self) -> bool:
        return self.running

    def start(self) -> None:
        self.running = True


@pytest.fixture
def worker(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeWorker:
    worker = FakeWorker()

    def get_instance(_update_interval: int) -> FakeWorker:
        return worker

    monkeypatch.setattr(monitor_module.MemoryWorker, "get_instance", get_instance)
    return worker


def test_the_monitor_publishes_the_workers_data(worker: FakeWorker):
    monitor = MemoryMonitor()
    wait(10)
    assert (worker.interval, worker.running) == (5000, True)

    worker.data_ready.emit(SAMPLE)
    data = monitor.property("data")
    assert data["virtual"]["used"] == 8 * GIB
    assert data["swap"]["percent"] == 12.5
    assert data["cached_bytes"] == GIB


def test_the_widget_shows_free_memory_and_the_alternate_label(worker: FakeWorker):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Memory" / "Memory.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)

    worker.data_ready.emit(SAMPLE)
    label = find_item(widget, "label")
    assert label is not None
    assert label.property("text") == " 8.0G/16.0G"

    widget.setProperty("showAlternate", True)
    assert label.property("text") == " VIRT: 50% SWAP: 12.5%"

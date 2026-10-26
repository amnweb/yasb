import pytest
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.bar.manager import QML_IMPORT_PATH
from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.cpu import monitor as monitor_module
from core.widgets.services.cpu.cpu_api import CpuData, CpuFreq
from core.widgets.services.cpu.monitor import CpuMonitor
from tests.support.qt import find_item, wait

SAMPLE = CpuData(CpuFreq(3000.0, 0.0, 4000.0), 42.5, [40.0, 45.0], 1, 2)


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

    monkeypatch.setattr(monitor_module.CpuWorker, "get_instance", get_instance)
    return worker


def test_the_monitor_publishes_the_workers_data(worker: FakeWorker):
    monitor = CpuMonitor()
    monitor.setProperty("updateInterval", 2000)
    wait(10)
    assert (worker.interval, worker.running) == (2000, True)

    worker.data_ready.emit(SAMPLE)
    assert monitor.property("data") == {
        "cores": {"physical": 1, "total": 2},
        "freq": {"current": 3000.0, "min": 0.0, "max": 4000.0},
        "percent": {"total": 42.5, "core": [40.0, 45.0]},
    }


def test_the_widget_shows_the_histogram_and_the_alternate_label(worker: FakeWorker):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Cpu" / "Cpu.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)

    worker.data_ready.emit(SAMPLE)
    label = find_item(widget, "label")
    assert label is not None
    assert label.property("text") == " " + "▁" * 9 + "▃"

    widget.setProperty("showAlternate", True)
    assert label.property("text") == " CPU: 42.5% | freq: 3000.00 Mhz"

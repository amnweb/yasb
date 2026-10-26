from functools import cache

from PyQt6.QtQml import qmlRegisterType

from core.utils.commands import Commands
from core.utils.hotkey import Hotkey
from core.widgets.services.active_window.tracker import ActiveWindowTracker
from core.widgets.services.clock.time_zones import TimeZones
from core.widgets.services.cpu.monitor import CpuMonitor
from core.widgets.services.gpu.monitor import GpuMonitor
from core.widgets.services.memory.monitor import MemoryMonitor

QML_URI = "Yasb"


@cache
def register_qml_types() -> None:
    qmlRegisterType(TimeZones, QML_URI, 1, 0, "TimeZones")
    qmlRegisterType(Commands, QML_URI, 1, 0, "Commands")
    qmlRegisterType(Hotkey, QML_URI, 1, 0, "Hotkey")
    qmlRegisterType(ActiveWindowTracker, QML_URI, 1, 0, "ActiveWindowTracker")
    qmlRegisterType(CpuMonitor, QML_URI, 1, 0, "CpuMonitor")
    qmlRegisterType(GpuMonitor, QML_URI, 1, 0, "GpuMonitor")
    qmlRegisterType(MemoryMonitor, QML_URI, 1, 0, "MemoryMonitor")

from functools import cache

from PyQt6.QtQml import qmlRegisterType

from core.bar.backdrop import Backdrop
from core.utils.commands import Commands
from core.utils.hotkey import Hotkey
from core.widgets.services.active_window.tracker import ActiveWindowTracker
from core.widgets.services.clock.time_zones import TimeZones
from core.widgets.services.cpu.monitor import CpuMonitor
from core.widgets.services.github.notifications import GitHubNotifications
from core.widgets.services.gpu.monitor import GpuMonitor
from core.widgets.services.memory.monitor import MemoryMonitor
from core.widgets.services.quick_launch.search import QuickLaunchSearch

QML_URI = "Yasb"


@cache
def register_qml_types() -> None:
    qmlRegisterType(Backdrop, QML_URI, 1, 0, "Backdrop")
    qmlRegisterType(TimeZones, QML_URI, 1, 0, "TimeZones")
    qmlRegisterType(Commands, QML_URI, 1, 0, "Commands")
    qmlRegisterType(Hotkey, QML_URI, 1, 0, "Hotkey")
    qmlRegisterType(ActiveWindowTracker, QML_URI, 1, 0, "ActiveWindowTracker")
    qmlRegisterType(CpuMonitor, QML_URI, 1, 0, "CpuMonitor")
    qmlRegisterType(GpuMonitor, QML_URI, 1, 0, "GpuMonitor")
    qmlRegisterType(MemoryMonitor, QML_URI, 1, 0, "MemoryMonitor")
    qmlRegisterType(GitHubNotifications, QML_URI, 1, 0, "GitHubNotifications")
    qmlRegisterType(QuickLaunchSearch, QML_URI, 1, 0, "QuickLaunchSearch")

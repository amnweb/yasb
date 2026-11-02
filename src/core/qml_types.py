from functools import cache

from PyQt6.QtQml import qmlRegisterType

from core.bar.backdrop import Backdrop
from core.utils.commands import Commands
from core.utils.hotkey import Hotkey
from core.widgets.services.active_window.tracker import ActiveWindowTracker
from core.widgets.services.audio_visualizer.levels import AudioLevels
from core.widgets.services.clock.time_zones import TimeZones
from core.widgets.services.cpu.monitor import CpuMonitor
from core.widgets.services.github.notifications import GitHubNotifications
from core.widgets.services.glazewm.workspaces import GlazewmWorkspacesModel
from core.widgets.services.gpu.monitor import GpuMonitor
from core.widgets.services.media.now_playing import NowPlaying
from core.widgets.services.memory.monitor import MemoryMonitor
from core.widgets.services.notifications.center import NotificationCenter
from core.widgets.services.power_menu.session import PowerSession
from core.widgets.services.quick_launch.search import QuickLaunchSearch
from core.widgets.services.systray.model import SystrayModel
from core.widgets.services.volume.output import AudioOutput
from core.widgets.services.windows_desktops.desktops import VirtualDesktops

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
    qmlRegisterType(GlazewmWorkspacesModel, QML_URI, 1, 0, "GlazewmWorkspacesModel")
    qmlRegisterType(QuickLaunchSearch, QML_URI, 1, 0, "QuickLaunchSearch")
    qmlRegisterType(NowPlaying, QML_URI, 1, 0, "NowPlaying")
    qmlRegisterType(AudioOutput, QML_URI, 1, 0, "AudioOutput")
    qmlRegisterType(NotificationCenter, QML_URI, 1, 0, "NotificationCenter")
    qmlRegisterType(VirtualDesktops, QML_URI, 1, 0, "VirtualDesktops")
    qmlRegisterType(AudioLevels, QML_URI, 1, 0, "AudioLevels")
    qmlRegisterType(PowerSession, QML_URI, 1, 0, "PowerSession")
    qmlRegisterType(SystrayModel, QML_URI, 1, 0, "SystrayModel")

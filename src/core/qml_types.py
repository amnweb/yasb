from collections.abc import Callable
from functools import cache

from PyQt6.QtCore import QObject
from PyQt6.QtQml import QJSEngine, QQmlEngine, qmlRegisterSingletonType, qmlRegisterType, qmlRegisterUncreatableType

from core.bar.backdrop import Backdrop
from core.bar.window import BarContext
from core.services.active_window.tracker import ActiveWindowTracker
from core.services.audio_visualizer.levels import AudioLevels
from core.services.battery.monitor import BatteryMonitor
from core.services.bluetooth.monitor import BluetoothMonitor, DeviceList
from core.services.brightness.control import DisplayBrightness, DisplayList
from core.services.clock.time_zones import TimeZones
from core.services.cpu.monitor import CpuMonitor
from core.services.dnd.status import DoNotDisturb
from core.services.github.notifications import GitHubNotifications
from core.services.glazewm.workspaces import GlazewmWorkspacesModel
from core.services.gpu.monitor import GpuMonitor
from core.services.language.keyboard import KeyboardLanguage
from core.services.media.now_playing import NowPlaying
from core.services.memory.monitor import MemoryMonitor
from core.services.microphone.input import AudioInput
from core.services.network_traffic.monitor import NetworkTrafficMonitor
from core.services.notifications.center import NotificationCenter
from core.services.obs.studio import ObsStudio
from core.services.power_menu.session import PowerSession
from core.services.power_mode.power_mode_api import PowerModes
from core.services.power_plan.power_plan_api import PowerPlans
from core.services.process.process import Process
from core.services.quick_launch.search import QuickLaunchSearch, ResultModel
from core.services.recycle_bin.recycle_bin_monitor import RecycleBin
from core.services.server_monitor.service import ServerChecks
from core.services.systray.model import IconList, SystrayModel
from core.services.taskbar.apps import TaskbarApps
from core.services.taskbar.thumbnail import WindowThumbnail
from core.services.theme.mode import WindowsTheme
from core.services.updates.monitor import AvailableUpdates
from core.services.volume.output import AudioOutput
from core.services.wallpapers.library import WallpaperLibrary
from core.services.wallpapers.thumbnails import WallpaperThumbnail
from core.services.weather.forecast import WeatherForecast
from core.services.wifi.monitor import NetworkList, WifiMonitor
from core.services.windows_desktops.desktops import VirtualDesktops
from core.utils.commands import Commands
from core.utils.environment import Environment
from core.utils.hotkey import Hotkey

QML_URI = "Yasb"
QML_VERSION = (1, 0)

QML_TYPES: tuple[type[QObject], ...] = (
    Backdrop,
    TimeZones,
    Commands,
    Hotkey,
    ActiveWindowTracker,
    CpuMonitor,
    GpuMonitor,
    MemoryMonitor,
    NetworkTrafficMonitor,
    ServerChecks,
    GitHubNotifications,
    GlazewmWorkspacesModel,
    QuickLaunchSearch,
    NowPlaying,
    AudioOutput,
    AudioInput,
    KeyboardLanguage,
    NotificationCenter,
    DoNotDisturb,
    WindowsTheme,
    SystrayModel,
    BatteryMonitor,
    BluetoothMonitor,
    DisplayBrightness,
    WifiMonitor,
    WeatherForecast,
    AvailableUpdates,
    TaskbarApps,
    RecycleBin,
    ObsStudio,
    WindowThumbnail,
    Process,
    AudioLevels,
    PowerSession,
    VirtualDesktops,
    WallpaperLibrary,
    WallpaperThumbnail,
)

QML_SINGLETONS: tuple[type[QObject], ...] = (Environment, PowerPlans, PowerModes)

QML_UNCREATABLE_TYPES: tuple[type[QObject], ...] = (
    BarContext,
    DeviceList,
    DisplayList,
    IconList,
    NetworkList,
    ResultModel,
)


@cache
def register_qml_types() -> None:
    major, minor = QML_VERSION
    for typ in QML_TYPES:
        qmlRegisterType(typ, QML_URI, major, minor, typ.__name__)
    for typ in QML_UNCREATABLE_TYPES:
        qmlRegisterUncreatableType(typ, QML_URI, major, minor, f"{typ.__name__} is created by YASB", typ.__name__)
    for typ in QML_SINGLETONS:
        qmlRegisterSingletonType(typ, QML_URI, major, minor, _singleton(typ), typ.__name__)


def _singleton(typ: type[QObject]) -> Callable[[QQmlEngine, QJSEngine], QObject]:
    # Each engine makes its own and owns it
    return lambda _engine, _script_engine: typ()

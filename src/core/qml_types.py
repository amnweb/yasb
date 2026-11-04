from functools import cache

from PyQt6.QtCore import QObject
from PyQt6.QtQml import qmlRegisterType, qmlRegisterUncreatableType

from core.bar.backdrop import Backdrop
from core.bar.window import BarContext
from core.utils.commands import Commands
from core.utils.hotkey import Hotkey
from core.widgets.services.active_window.tracker import ActiveWindowTracker
from core.widgets.services.audio_visualizer.levels import AudioLevels
from core.widgets.services.battery.monitor import BatteryMonitor
from core.widgets.services.bluetooth.monitor import BluetoothMonitor, DeviceList
from core.widgets.services.brightness.control import DisplayBrightness, DisplayList
from core.widgets.services.clock.time_zones import TimeZones
from core.widgets.services.cpu.monitor import CpuMonitor
from core.widgets.services.dnd.status import DoNotDisturb
from core.widgets.services.github.notifications import GitHubNotifications
from core.widgets.services.glazewm.workspaces import GlazewmWorkspacesModel
from core.widgets.services.gpu.monitor import GpuMonitor
from core.widgets.services.media.now_playing import NowPlaying
from core.widgets.services.memory.monitor import MemoryMonitor
from core.widgets.services.microphone.input import AudioInput
from core.widgets.services.notifications.center import NotificationCenter
from core.widgets.services.power_menu.session import PowerSession
from core.widgets.services.quick_launch.search import QuickLaunchSearch, ResultModel
from core.widgets.services.systray.model import IconList, SystrayModel
from core.widgets.services.theme.mode import WindowsTheme
from core.widgets.services.volume.output import AudioOutput
from core.widgets.services.wallpapers.library import WallpaperLibrary
from core.widgets.services.wallpapers.thumbnails import WallpaperThumbnail
from core.widgets.services.weather.forecast import WeatherForecast
from core.widgets.services.wifi.monitor import NetworkList, WifiMonitor
from core.widgets.services.windows_desktops.desktops import VirtualDesktops

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
    GitHubNotifications,
    GlazewmWorkspacesModel,
    QuickLaunchSearch,
    NowPlaying,
    AudioOutput,
    AudioInput,
    NotificationCenter,
    DoNotDisturb,
    WindowsTheme,
    SystrayModel,
    BatteryMonitor,
    BluetoothMonitor,
    DisplayBrightness,
    WifiMonitor,
    WeatherForecast,
    AudioLevels,
    PowerSession,
    VirtualDesktops,
    WallpaperLibrary,
    WallpaperThumbnail,
)

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

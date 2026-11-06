import logging
from typing import Any, Protocol

from PyQt6.QtCore import QCoreApplication, QObject, Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QWindow

from core.services.recycle_bin.recycle_bin_monitor import RecycleBinMonitor, empty_recycle_bin
from core.services.taskbar.jump_list import is_recycle_bin, jump_list
from core.services.taskbar.peek import activate_live_preview, exclude_from_peek, is_live_preview_available
from core.services.taskbar.pin_manager import PinManager
from core.services.taskbar.window_manager import TaskbarWindowManager, start_shared_task_manager
from core.utils.icons.image_provider import icon_url, window_icon_url
from core.utils.icons.service import IconService
from core.utils.icons.sources import IconSource, StockIcon
from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import IsIconic, IsWindow
from core.utils.win32.composition import BackdropWindow
from core.utils.win32.utils import screen_monitor
from core.utils.win32.window_actions import can_minimize as window_can_minimize
from core.utils.win32.window_actions import (
    close_application,
    is_owner_root_active,
    minimize_window,
    resolve_base_and_focus,
    restore_window,
    set_foreground,
    show_window,
)

# The stock icons of the Recycle Bin, which a pin of it shows instead of the shell's, as that one does not change
RECYCLE_BIN_EMPTY = 31
RECYCLE_BIN_FULL = 32


class WindowSource(Protocol):
    """What OpenWindows needs of the window manager: its signals and the windows it tracks."""

    window_added: Any
    window_removed: Any
    window_updated: Any
    window_monitor_changed: Any
    window_minimize_changed: Any

    def get_windows(self) -> dict[int, Any]: ...


class OpenWindows(QObject):
    """Every window that belongs on a taskbar and every pinned app, shared by all taskbar widgets."""

    changed = pyqtSignal()

    def __init__(self, manager: WindowSource, pins: PinManager) -> None:
        super().__init__()
        self.manager = manager
        self.pins = pins
        self.pins.load_pinned_apps()
        # By hwnd, in the order the windows opened
        self.windows: dict[int, dict[str, Any]] = {}
        self._app_ids: dict[int, str] = {}
        # Whether the Recycle Bin holds anything, watched while it is pinned
        self.bin_full = False
        self._bin: RecycleBinMonitor | None = None
        self._watch_bin()
        manager.window_added.connect(self._store)
        manager.window_updated.connect(self._store)
        manager.window_monitor_changed.connect(self._store)
        manager.window_removed.connect(self._remove)
        manager.window_minimize_changed.connect(self._minimized)
        IconService.instance().icons_changed.connect(self.changed)
        for hwnd, window in manager.get_windows().items():
            self._store(hwnd, window.as_dict())

    def _store(self, hwnd: int, data: dict[str, Any]) -> None:
        known = self.windows.get(hwnd)
        if hwnd not in self._app_ids:
            # Resolved once: the shell and the process are asked, which is slow for some apps
            try:
                self._app_ids[hwnd] = self.pins.get_app_unique_id(hwnd, data) or f"window:{hwnd}"
            except Exception:
                logging.debug("Could not identify the app of window %s", hwnd, exc_info=True)
                self._app_ids[hwnd] = f"window:{hwnd}"
        window = {
            "hwnd": hwnd,
            "appId": self._app_ids[hwnd],
            "title": str(data.get("title") or ""),
            "process": str(data.get("process_name") or ""),
            "className": str(data.get("class_name") or ""),
            "active": bool(data.get("is_active")),
            "flashing": bool(data.get("is_flashing")),
            "cloaked": bool(data.get("is_cloaked")),
            "canMinimize": bool(data.get("can_minimize", True)),
            "monitor": int(data.get("monitor_handle") or 0),
            # Kept from the minimize events once known: a tiling manager can activate a window it just minimized,
            # and a window being restored still reads as iconic for a moment
            "minimized": known["minimized"] if known else bool(IsIconic(hwnd)),
        }
        if window != known:
            self.windows[hwnd] = window
            self.changed.emit()

    def _remove(self, hwnd: int, _data: dict[str, Any]) -> None:
        self._app_ids.pop(hwnd, None)
        if self.windows.pop(hwnd, None) is not None:
            self.changed.emit()

    def _minimized(self, hwnd: int, minimized: bool) -> None:
        window = self.windows.get(hwnd)
        if window is not None and window["minimized"] != minimized:
            self.windows[hwnd] = {**window, "minimized": minimized}
            self.changed.emit()

    def _watch_bin(self, *, stopping: bool = False) -> None:
        pinned = not stopping and any(is_recycle_bin(uid) for uid in self.pins.pinned_apps)
        if pinned and self._bin is None:
            self._bin = RecycleBinMonitor.join(None, self)
            self._bin.changed.connect(self._bin_updated)
            self._bin_updated()
        elif not pinned and self._bin is not None:
            self._bin.changed.disconnect(self._bin_updated)
            self._bin.leave(self)
            self._bin = None

    def stop(self) -> None:
        """Lets go of the Recycle Bin monitor as YASB exits; its threads stop with its last user."""
        self._watch_bin(stopping=True)

    def _bin_updated(self) -> None:
        full = self._bin is not None and self._bin.info["num_items"] > 0
        if full != self.bin_full:
            self.bin_full = full
            self.changed.emit()

    def icon(self, app_id: str, metadata: dict[str, str]) -> IconSource | None:
        """What a pinned app's icon is taken from."""
        if is_recycle_bin(app_id):
            return StockIcon(RECYCLE_BIN_FULL if self.bin_full else RECYCLE_BIN_EMPTY)
        return self.pins.icon_source(app_id, metadata)

    def name(self, app_id: str) -> str:
        """An app's name: its pinned name, else the one Windows shows for it, found from one of its windows."""
        if app_id in self.pins.pinned_apps:
            return self.pins.pinned_apps[app_id].get("title", "")
        hwnd = next((hwnd for hwnd, window in self.windows.items() if window["appId"] == app_id), None)
        window = self.manager.get_windows().get(hwnd) if hwnd is not None else None
        if hwnd is None or window is None:
            return ""
        try:
            return self.pins.get_app_name(hwnd, window.as_dict())
        except Exception:
            logging.debug("Could not find the name of app %s", app_id, exc_info=True)
            return ""

    def pinned(self) -> list[tuple[str, dict[str, str]]]:
        return [(uid, self.pins.pinned_apps[uid]) for uid in self.pins.pinned_order if uid in self.pins.pinned_apps]

    def pin(self, app_id: str, position: int = -1) -> None:
        hwnd = next((hwnd for hwnd, window in self.windows.items() if window["appId"] == app_id), None)
        if hwnd is None or app_id.startswith("window:"):
            return
        window = self.manager.get_windows().get(hwnd)
        if window is not None and self.pins.pin_app(hwnd, window.as_dict(), position):
            self._watch_bin()
            self.changed.emit()

    def unpin(self, app_id: str) -> None:
        if app_id in self.pins.pinned_apps:
            self.pins.unpin(app_id)
            self._watch_bin()
            self.changed.emit()

    def move_pin(self, app_id: str, index: int) -> None:
        order = [uid for uid, _metadata in self.pinned()]
        if app_id not in order:
            return
        order.remove(app_id)
        order.insert(max(0, min(index, len(order))), app_id)
        if order != self.pins.pinned_order:
            self.pins.update_pinned_order(order)
            self.changed.emit()


_shared: OpenWindows | None = None


def open_windows() -> OpenWindows:
    global _shared
    if _shared is None:
        _shared = OpenWindows(_start_manager(), PinManager())
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(_shared.stop)
    return _shared


def _start_manager() -> TaskbarWindowManager:
    return start_shared_task_manager()


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(apps: TaskbarApps) -> Any:
        return apps.setting(name)

    def set_value(apps: TaskbarApps, value: Any) -> None:
        apps.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class TaskbarApps(QObject):
    """The pinned apps and open windows for one taskbar widget, and acting on them.

    Every widget shares one window tracker and one set of pins; the settings choose which windows this one shows.
    """

    settingsChanged = pyqtSignal()
    appsChanged = pyqtSignal()

    # Only windows on this screen, by its name; every screen when empty
    screenName = _setting(str, "screenName", settingsChanged)
    # Leaves out cloaked windows, such as those on other virtual desktops
    onlyVisible = _setting(bool, "onlyVisible", settingsChanged)
    # Leaves out windows that cannot be minimized, such as some dialogs
    strictFiltering = _setting(bool, "strictFiltering", settingsChanged)
    # Windows to leave out, by their exact class, process or title
    ignoreClasses = _setting("QStringList", "ignoreClasses", settingsChanged)
    ignoreProcesses = _setting("QStringList", "ignoreProcesses", settingsChanged)
    ignoreTitles = _setting("QStringList", "ignoreTitles", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "screenName": "",
            "onlyVisible": False,
            "strictFiltering": True,
            "ignoreClasses": [],
            "ignoreProcesses": [],
            "ignoreTitles": [],
        }
        self._apps: list[dict[str, Any]] = []
        self._windows = open_windows()
        self._windows.changed.connect(self._publish)
        self._publish()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if isinstance(self._settings[name], list):
            value = [str(item) for item in value]
        if value == self._settings[name]:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        self._publish()

    # Each app in taskbar order, pinned ones first in their pinned order, then the others as they opened:
    # {id, name, pinned, icon, windows}, name the pinned name (empty for an app that is not pinned), icon an image URL
    # and windows the app's open windows on this taskbar, each {hwnd, appId, title, icon, process, className, active,
    # flashing, minimized, cloaked, canMinimize}
    @qml_property("QVariantList", notify=appsChanged)
    def apps(self) -> list[dict[str, Any]]:
        return self._apps

    # Goes up as icons finish loading; an icon URL made before, such as a menu's, asks again with it at its end
    @qml_property(int, notify=appsChanged)
    def iconRevision(self) -> int:
        return IconService.instance().revision

    def _shown(self, window: dict[str, Any], monitor: int | None) -> bool:
        settings = self._settings
        if not window["title"].strip() or not window["process"]:
            return False
        if (
            window["title"] in settings["ignoreTitles"]
            or window["className"] in settings["ignoreClasses"]
            or window["process"] in settings["ignoreProcesses"]
        ):
            return False
        if settings["strictFiltering"] and not window["canMinimize"]:
            return False
        if settings["onlyVisible"] and window["cloaked"]:
            return False
        return monitor is None or window["monitor"] == monitor

    def _publish(self) -> None:
        revision = IconService.instance().revision
        screen = self._settings["screenName"]
        monitor = screen_monitor(screen) if screen else None
        apps: dict[str, dict[str, Any]] = {}
        for uid, metadata in self._windows.pinned():
            source = self._windows.icon(uid, metadata)
            apps[uid] = {
                "id": uid,
                "name": metadata.get("title", ""),
                "pinned": True,
                "icon": icon_url(source, revision) if source is not None else "",
                "windows": [],
            }
        for hwnd, window in self._windows.windows.items():
            if not self._shown(window, monitor):
                continue
            entry = {key: value for key, value in window.items() if key != "monitor"} | {
                "icon": window_icon_url(hwnd, revision)
            }
            app = apps.setdefault(
                window["appId"],
                {"id": window["appId"], "name": "", "pinned": False, "icon": entry["icon"], "windows": []},
            )
            app["windows"].append(entry)
        published = list(apps.values())
        if published != self._apps:
            self._apps = published
            self.appsChanged.emit()

    # Brings a window to the front, restoring it when minimized, or minimizes it when it is already in front
    @pyqtSlot(int)
    def activate(self, hwnd: int) -> None:
        if not IsWindow(hwnd):
            return
        base, focus = resolve_base_and_focus(hwnd)
        window = self._windows.windows.get(base)
        if IsIconic(base):
            restore_window(base)
            set_foreground(base)
            # Some apps take the focus only once restored
            QTimer.singleShot(0, lambda: set_foreground(focus or base))
        elif (window is not None and window["active"]) or is_owner_root_active(base):
            if window_can_minimize(hwnd):
                minimize_window(base)
        else:
            show_window(base)
            set_foreground(base)

    # Brings a window to the front without ever minimizing it, as for a file dragged over its button
    @pyqtSlot(int)
    def focus(self, hwnd: int) -> None:
        if not IsWindow(hwnd):
            return
        base, focus = resolve_base_and_focus(hwnd)
        if IsIconic(base):
            restore_window(base)
        set_foreground(focus)

    # Asks a window to close, as its close button does
    @pyqtSlot(int)
    def close(self, hwnd: int) -> None:
        if IsWindow(hwnd):
            close_application(hwnd)

    # Starts an app by its id, with these arguments after its own
    @pyqtSlot(str)
    @pyqtSlot(str, str)
    def launch(self, app_id: str, arguments: str = "") -> None:
        if not app_id.startswith("window:"):
            self._windows.pins.launch_pinned_app(app_id, arguments)

    # Pins an open app at this place among the pinned ones, or after them for -1
    @pyqtSlot(str)
    @pyqtSlot(str, int)
    def pin(self, app_id: str, index: int = -1) -> None:
        self._windows.pin(app_id, index)

    @pyqtSlot(str)
    def unpin(self, app_id: str) -> None:
        self._windows.unpin(app_id)

    # What a button's menu offers for an app: {name, items}, name the app's name and items the extra ones for some
    # apps, each {kind, text, target, arguments}, kind window, private, profile, folder or explorer, launched with
    # launch(target, arguments); the Recycle Bin has one item of kind recycleBin with items and bytes, what it holds
    @pyqtSlot(str, result="QVariantMap")
    def jumpList(self, app_id: str) -> dict[str, Any]:
        try:
            items = jump_list(app_id)
        except Exception:
            logging.exception("Could not list the menu items of %s", app_id)
            items = []
        return {"name": self._windows.name(app_id), "items": items}

    # Whether this Windows build can fade the desktop to show one window
    @qml_property(bool, constant=True)
    def peekAvailable(self) -> bool:
        return is_live_preview_available()

    # Fades the desktop around the app, keeping YASB's windows visible. The first is the preview. 0 ends Peek.
    @pyqtSlot(int, "QVariantList")
    def peek(self, hwnd: int, keep: list[Any]) -> None:
        top_window = 0
        for window in keep:
            if not isinstance(window, QWindow):
                continue
            surfaces = [int(window.winId())]
            surfaces.extend(
                backdrop.hwnd
                for backdrop in window.findChildren(BackdropWindow, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if not backdrop.closed
            )
            if not top_window:
                # Place the app below the preview's blur, which already sits behind the preview content.
                top_window = surfaces[-1]
            if hwnd:
                for surface in surfaces:
                    exclude_from_peek(surface)
        activate_live_preview(bool(hwnd), hwnd, top_window)

    # Empties the Recycle Bin after Windows asks to confirm
    @pyqtSlot()
    def emptyRecycleBin(self) -> None:
        empty_recycle_bin()

    # Moves a pinned app to this place among the pinned ones
    @pyqtSlot(str, int)
    def move(self, app_id: str, index: int) -> None:
        self._windows.move_pin(app_id, index)

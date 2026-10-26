import logging
import os
import re
from typing import Any

from PyQt6.QtCore import QElapsedTimer, QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.utils.icons.image_provider import window_icon_url
from core.utils.icons.service import IconService
from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import (
    GetForegroundWindow,
    GetParent,
    enum_child_windows,
    get_window_thread_process_id,
)
from core.utils.win32.event_listener import win_event
from core.utils.win32.utils import (
    WindowInfo,
    get_app_name_from_aumid,
    get_app_name_from_pid,
    get_hwnd_info,
    screen_monitor,
)
from settings import APP_BAR_TITLE

CURRENT_PROCESS_ID = os.getpid()
IGNORED_TITLES = ["", " ", "FolderView", "Program Manager", "python3", "pythonw3", APP_BAR_TITLE, "Search", "Start"]
IGNORED_CLASSES = [
    "WorkerW",
    "TopLevelWindowForOverflowXamlIsland",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
]
IGNORED_PROCESSES = ["SearchHost.exe", "komorebi.exe", "yasb.exe", "Flow.Launcher.exe"]
# Windows whose title changes many times a second, like the Explorer copy dialog
THROTTLED_CLASSES = ["OperationStatusWindow"]
THROTTLE_MS = 250
CASES = {"lower": str.lower, "upper": str.upper, "title": str.title, "capitalize": str.capitalize}
DISPLAY_SETTINGS = {"label", "alternateLabel", "noWindowLabel", "showAlternate"}


def rewrite_text(text: str, rules: list[dict[str, Any]]) -> str:
    result = text
    for rule in rules:
        pattern, replacement = rule.get("pattern", ""), rule.get("replacement", "")
        if not pattern or not replacement:
            continue
        try:
            result, count = re.subn(pattern, replacement, result)
        except re.error as e:
            logging.warning("Invalid regex pattern '%s': %s", pattern, e)
            continue
        if count and (transform := CASES.get(rule.get("case") or "")) is not None:
            result = transform(result)
    return result


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty:
    def get(tracker: ActiveWindowTracker) -> Any:
        return tracker.setting(name)

    def set_(tracker: ActiveWindowTracker, value: Any) -> None:
        tracker.change_setting(name, value)

    return pyqtProperty(kind, get, set_, notify=notify)


class ActiveWindowTracker(QObject):
    settingsChanged = pyqtSignal()
    windowChanged = pyqtSignal()

    _workspace = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "screenName": "",
            "monitorExclusive": True,
            "label": "{win[title]}",
            "alternateLabel": "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]",
            "noWindowLabel": "",
            "showAlternate": False,
            "maxLength": 0,
            "ellipsis": "...",
            "rewrite": [],
            "ignoreTitles": [],
            "ignoreClasses": [],
            "ignoreProcesses": [],
        }
        self._win_info: WindowInfo | None = None
        self._text = ""
        self._icon_revision = 0
        self._uwp_retries = 0
        self._workspace_retries = 0
        self._app_names: dict[int, str] = {}

        self._retry_hwnd = 0
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(lambda: self._on_focus_change(self._retry_hwnd))

        self._throttled_hwnd = 0
        self._last_update = QElapsedTimer()
        self._last_update.start()
        self._throttle_timer = QTimer(self)
        self._throttle_timer.setSingleShot(True)
        self._throttle_timer.timeout.connect(self._update_throttled)

        # Settings arrive one by one while QML creates the object, so the window is looked at once after
        self._evaluate_timer = QTimer(self)
        self._evaluate_timer.setSingleShot(True)
        self._evaluate_timer.setInterval(0)
        self._evaluate_timer.timeout.connect(self._evaluate_foreground)
        self._evaluate_timer.start()

        win_event(WinEvent.EventSystemForeground).connect(self._on_focus_change)
        win_event(WinEvent.EventSystemMoveSizeEnd).connect(self._on_focus_change)
        win_event(WinEvent.EventObjectNameChange).connect(self._on_name_change)
        win_event(WinEvent.EventObjectStateChange).connect(self._on_name_change)
        win_event(WinEvent.EventObjectDestroy).connect(self._on_window_destroyed)
        self._workspace.connect(self._on_workspace)
        EventService().register_event("workspace_update", self._workspace)
        IconService.instance().icons_changed.connect(self._on_icons_changed)

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if self._settings[name] == value:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name in DISPLAY_SETTINGS:
            self._show(self._win_info)
        else:
            self._evaluate_timer.start()

    screenName = _setting(str, "screenName", settingsChanged)
    monitorExclusive = _setting(bool, "monitorExclusive", settingsChanged)
    label = _setting(str, "label", settingsChanged)
    alternateLabel = _setting(str, "alternateLabel", settingsChanged)
    noWindowLabel = _setting(str, "noWindowLabel", settingsChanged)
    showAlternate = _setting(bool, "showAlternate", settingsChanged)
    maxLength = _setting(int, "maxLength", settingsChanged)
    ellipsis = _setting(str, "ellipsis", settingsChanged)
    rewrite = _setting("QVariantList", "rewrite", settingsChanged)
    ignoreTitles = _setting("QStringList", "ignoreTitles", settingsChanged)
    ignoreClasses = _setting("QStringList", "ignoreClasses", settingsChanged)
    ignoreProcesses = _setting("QStringList", "ignoreProcesses", settingsChanged)

    @qml_property(bool, notify=windowChanged)
    def hasWindow(self) -> bool:
        return self._win_info is not None

    @qml_property(str, notify=windowChanged)
    def text(self) -> str:
        return self._text

    @qml_property(str, notify=windowChanged)
    def icon(self) -> str:
        return window_icon_url(self._win_info["hwnd"], self._icon_revision) if self._win_info else ""

    @qml_property("QVariantMap", notify=windowChanged)
    def window(self) -> dict[str, Any]:
        info = self._win_info
        if info is None:
            return {}
        process = info["process"]
        return {
            "hwnd": info["hwnd"],
            "title": info["title"],
            "class_name": info["class_name"] or "",
            "process": {"name": process["name"] or "", "pid": process["pid"], "path": process["path"] or ""},
            "app_name": info.get("app_name", ""),
            "monitor": info["monitor_info"]["device"],
        }

    @pyqtSlot()
    def toggleLabel(self) -> None:
        self.change_setting("showAlternate", not self.setting("showAlternate"))

    def _evaluate_foreground(self) -> None:
        hwnd = GetForegroundWindow()
        if hwnd:
            self._on_focus_change(hwnd)
        elif self._win_info is None:
            self._show(None)

    def _show(self, win_info: WindowInfo | None) -> None:
        self._win_info = win_info
        template = self.setting("alternateLabel") if self.setting("showAlternate") else self.setting("label")
        if win_info is None:
            self._text = self.setting("noWindowLabel")
        else:
            try:
                self._text = template.format(win=win_info)
            except Exception:
                self._text = template
        self.windowChanged.emit()

    def _retry(self, hwnd: int, delay_ms: int) -> None:
        self._retry_hwnd = hwnd
        self._retry_timer.start(delay_ms)

    @pyqtSlot(int, object)
    def _on_focus_change(self, hwnd: int, _event: WinEvent | None = None) -> None:
        win_info = get_hwnd_info(hwnd) if hwnd else None
        if (
            not win_info
            or not win_info["title"]
            or win_info["title"] == APP_BAR_TITLE
            or win_info["process"]["pid"] == CURRENT_PROCESS_ID
        ):
            return
        screen_name = self.setting("screenName")
        if self.setting("monitorExclusive") and screen_name and win_info["monitor_hwnd"] != screen_monitor(screen_name):
            self._show(None)
        else:
            self._update_window(hwnd, win_info)
        if win_info["title"] in IGNORED_TITLES:
            self._show(None)

    def _app_name(self, hwnd: int, win_info: WindowInfo) -> str | None:
        """Name of the app owning the window. A UWP app's frame belongs to ApplicationFrameHost.exe,
        the app itself runs in a child window's process, which can attach a moment after focus."""
        process = win_info["process"]
        pid = process["pid"]
        is_uwp = win_info["class_name"] == "ApplicationFrameWindow"
        if is_uwp:
            try:
                for child in enum_child_windows(hwnd):
                    _, child_pid = get_window_thread_process_id(child)
                    if child_pid and child_pid != process["pid"]:
                        pid = child_pid
                        break
            except Exception:
                pass
            if pid == process["pid"] and self._uwp_retries < 5:
                self._uwp_retries += 1
                self._retry(hwnd, 100)
                return None
        self._uwp_retries = 0

        name = self._app_names.get(pid)
        if name is None:
            if is_uwp and pid == process["pid"]:
                try:
                    from core.utils.win32.aumid import get_aumid_for_window

                    if aumid := get_aumid_for_window(hwnd):
                        name = get_app_name_from_aumid(aumid)
                except Exception:
                    pass
            name = name or get_app_name_from_pid(pid) or process["name"] or win_info["title"]
            self._app_names[pid] = name
        return name

    def _update_window(self, hwnd: int, win_info: WindowInfo) -> None:
        try:
            if hwnd != GetForegroundWindow():
                return
            if (app_name := self._app_name(hwnd, win_info)) is None:
                return
            win_info["app_name"] = app_name
            title, class_name, process = win_info["title"], win_info["class_name"], win_info["process"]
            if (
                title.strip() in self.setting("ignoreTitles") + IGNORED_TITLES
                or class_name in self.setting("ignoreClasses") + IGNORED_CLASSES
                or process["name"] in self.setting("ignoreProcesses") + IGNORED_PROCESSES
            ):
                return

            rules = self.setting("rewrite")
            win_info["title"] = rewrite_text(title, rules)
            if process["name"]:
                process["name"] = rewrite_text(process["name"], rules)
            win_info["app_name"] = rewrite_text(app_name, rules)
            max_length = self.setting("maxLength")
            if max_length > 0 and len(win_info["title"]) > max_length:
                win_info["title"] = win_info["title"][:max_length] + self.setting("ellipsis")
            self._show(win_info)
        except Exception:
            logging.exception("Failed to update the active window for HWND %s", hwnd)

    @pyqtSlot(int, object)
    def _on_name_change(self, hwnd: int, _event: WinEvent | None = None) -> None:
        if self._win_info is None or hwnd != self._win_info["hwnd"]:
            return
        if self._win_info["class_name"] in THROTTLED_CLASSES and self._last_update.elapsed() < THROTTLE_MS:
            self._throttled_hwnd = hwnd
            if not self._throttle_timer.isActive():
                self._throttle_timer.start(max(50, THROTTLE_MS - self._last_update.elapsed()))
            return
        self._on_focus_change(hwnd)
        self._last_update.restart()

    def _update_throttled(self) -> None:
        if self._throttled_hwnd:
            hwnd, self._throttled_hwnd = self._throttled_hwnd, 0
            self._on_focus_change(hwnd)
            self._last_update.restart()

    @pyqtSlot(int, object)
    def _on_window_destroyed(self, hwnd: int, _event: WinEvent | None = None) -> None:
        if self._win_info is None or hwnd != self._win_info["hwnd"]:
            return
        try:
            if GetParent(hwnd):
                return
            foreground = GetForegroundWindow()
            if foreground and foreground != hwnd:
                info = get_hwnd_info(foreground)
                if info and info["title"] and info["process"]["pid"] != CURRENT_PROCESS_ID:
                    self._on_focus_change(foreground)
                    return
        except Exception:
            logging.exception("Failed handling destroy event for HWND %s", hwnd)
        self._show(None)

    def _on_workspace(self, event: str) -> None:
        # komorebi's MoveWindow says nothing about the monitor, and the window is still animating,
        # so it is looked at again a few times
        if event in ("Hide", "Destroy"):
            self._show(None)
            return
        hwnd = GetForegroundWindow()
        if not hwnd:
            self._show(None)
            return
        self._on_focus_change(hwnd)
        if event == "MoveWindow" and self._workspace_retries < 3:
            self._workspace_retries += 1
            self._retry(hwnd, 200)
        else:
            self._workspace_retries = 0

    def _on_icons_changed(self) -> None:
        if self._win_info is not None:
            self._icon_revision += 1
            self.windowChanged.emit()

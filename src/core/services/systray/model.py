import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, override

from PyQt6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QCoreApplication,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QGuiApplication

from core.services.systray.systray import (
    SystrayIcons,
    TrayIcon,
    broadcast_taskbar_created,
    foreground_pid,
    menu_shown,
    other_window_in_front,
)
from core.utils.qml import qml_property
from core.utils.system import app_data_path
from core.utils.win32.undocumented import TRAY_BATTERY_ICON_GUID, TRAY_NETWORK_ICON_GUID, TRAY_VOLUME_ICON_GUID

logger = logging.getLogger("systray_widget")


@dataclass
class IconState:
    is_pinned: bool = False
    index: int = 0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> IconState:
        return IconState(is_pinned=bool(d["is_pinned"]), index=int(d["index"]))


ROLES = ["iconId", "tip", "source"]


class IconList(QAbstractListModel):
    """Icon rows for one view. In-place updates keep QML from interrupting a drag."""

    countChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._icons: list[dict[str, Any]] = []

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._icons)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < len(self._icons) or not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        return self._icons[index.row()][ROLES[role - Qt.ItemDataRole.UserRole]]

    @qml_property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._icons)

    @property
    def icons(self) -> list[dict[str, Any]]:
        return list(self._icons)

    def update(self, icons: list[dict[str, Any]]) -> None:
        """Update rows in place to match icons."""
        count = len(self._icons)
        wanted = {icon["iconId"] for icon in icons}
        for row in reversed(range(len(self._icons))):
            if self._icons[row]["iconId"] not in wanted:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._icons[row]
                self.endRemoveRows()
        for row, icon in enumerate(icons):
            current = next((i for i in range(row, len(self._icons)) if self._icons[i]["iconId"] == icon["iconId"]), -1)
            if current == -1:
                self.beginInsertRows(QModelIndex(), row, row)
                self._icons.insert(row, dict(icon))
                self.endInsertRows()
                continue
            if current != row:
                self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), row)
                self._icons.insert(row, self._icons.pop(current))
                self.endMoveRows()
            if self._icons[row] != icon:
                self._icons[row] = dict(icon)
                self.dataChanged.emit(self.index(row), self.index(row))
        if len(self._icons) != count:
            self.countChanged.emit()


def screen_id(screen_name: str) -> str:
    """Return the stable key for a screen's saved icon order."""
    screens = QGuiApplication.screens()
    screen = next((s for s in screens if s.name() == screen_name), QGuiApplication.primaryScreen())
    if screen is None:
        return ""
    return re.sub(r"\W+", "", f"{screen.manufacturer()}{screen.name()}{screen.serialNumber()}".upper())


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(model: SystrayModel) -> Any:
        return model.setting(name)

    def set_value(model: SystrayModel, value: Any) -> None:
        model.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class SystrayModel(QObject):
    """Pinned and unpinned icons for one bar. Reordered by user."""

    settingsChanged = pyqtSignal()
    menuOpenChanged = pyqtSignal()

    screenName = _setting(str, "screenName", settingsChanged)
    showBattery = _setting(bool, "showBattery", settingsChanged)
    showVolume = _setting(bool, "showVolume", settingsChanged)
    showNetwork = _setting(bool, "showNetwork", settingsChanged)
    # Process names without .exe, matched case-insensitively
    hideIcons = _setting("QStringList", "hideIcons", settingsChanged)
    # The first widget chooses the shared hook or monitor.
    useHook = _setting(bool, "useHook", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "screenName": "",
            "showBattery": False,
            "showVolume": False,
            "showNetwork": False,
            "hideIcons": [],
            "useHook": True,
        }
        self._tray: SystrayIcons | None = None
        self._pinned: list[TrayIcon] = []
        self._unpinned: list[TrayIcon] = []
        self._pinned_icons = IconList(self)
        self._unpinned_icons = IconList(self)
        self._state: dict[str, IconState] = {}
        self._screen_id = ""

        # QML supplies the settings after constructing the model
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

        # Batch icons received at startup or after a refresh.
        self._publish_timer = QTimer(self)
        self._publish_timer.setSingleShot(True)
        self._publish_timer.setInterval(16)
        self._publish_timer.timeout.connect(self._publish)

        # Keep the popup open while a clicked icon's app shows its menu.
        self._menu_open = False
        self._menu_pid = 0
        self._menu_since = 0.0
        self._menu_seen = False
        self._menu_missing_since: float | None = None
        self._menu_timer = QTimer(self)
        self._menu_timer.setInterval(100)
        self._menu_timer.timeout.connect(self._watch_menu)

        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self._save_state)

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if self._settings[name] == value:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name == "screenName":
            self._start_timer.start()
        else:
            self._publish()

    # On the bar
    @qml_property(QObject, constant=True)
    def pinnedIcons(self) -> IconList:
        return self._pinned_icons

    # In the popup
    @qml_property(QObject, constant=True)
    def unpinnedIcons(self) -> IconList:
        return self._unpinned_icons

    # Keep the popup open while a clicked icon's app shows its menu.
    @qml_property(bool, notify=menuOpenChanged)
    def menuOpen(self) -> bool:
        return self._menu_open

    def _start(self) -> None:
        if self._tray is None:
            self._tray = SystrayIcons.instance(self.setting("useHook"))
            self._tray.iconChanged.connect(self._on_icon_changed)
            self._tray.iconRemoved.connect(self._on_icon_removed)
        self._load_state()
        self._pinned, self._unpinned = [], []
        for icon in self._tray.icons:
            self._place(icon)
        self._publish()

    def _place(self, icon: TrayIcon) -> None:
        """Place an icon using its saved state."""
        saved = self._state.get(icon.state_key, self._state.get(icon.data.exe_path))
        icons = self._pinned if saved is not None and saved.is_pinned else self._unpinned
        index = saved.index if saved is not None else len(self._state)
        at = next((i for i, other in enumerate(icons) if self._sort_index(other) > index), len(icons))
        icons.insert(at, icon)

    def _sort_index(self, icon: TrayIcon) -> int:
        saved = self._state.get(icon.state_key)
        return saved.index if saved is not None else len(self._state)

    @pyqtSlot(object)
    def _on_icon_changed(self, icon: TrayIcon) -> None:
        if icon not in self._pinned and icon not in self._unpinned:
            self._place(icon)
        self._publish_timer.start()

    @pyqtSlot(object)
    def _on_icon_removed(self, icon: TrayIcon) -> None:
        for icons in (self._pinned, self._unpinned):
            if icon in icons:
                icons.remove(icon)
        self._publish_timer.start()

    def _shown(self, icon: TrayIcon) -> bool:
        filtered = {
            TRAY_BATTERY_ICON_GUID: not self.setting("showBattery"),
            TRAY_VOLUME_ICON_GUID: not self.setting("showVolume"),
            TRAY_NETWORK_ICON_GUID: not self.setting("showNetwork"),
        }
        if icon.data.guid is not None and filtered.get(icon.data.guid, False):
            return False
        if icon.data.exe.lower() in (name.lower() for name in self.setting("hideIcons")):
            return False
        return not icon.hidden

    def _publish(self) -> None:
        self._publish_timer.stop()
        self._pinned_icons.update([self._entry(icon) for icon in self._pinned if self._shown(icon)])
        self._unpinned_icons.update([self._entry(icon) for icon in self._unpinned if self._shown(icon)])

    @staticmethod
    def _entry(icon: TrayIcon) -> dict[str, Any]:
        return {"iconId": icon.id, "tip": icon.tip, "source": icon.source}

    def _find(self, icon_id: int) -> TrayIcon | None:
        return next((icon for icon in self._pinned + self._unpinned if icon.id == icon_id), None)

    @pyqtSlot(int, int)
    def click(self, icon_id: int, button: int) -> None:
        if (icon := self._find(icon_id)) is not None:
            self._watch_menu_of(icon)
            icon.send_click(Qt.MouseButton(button))

    @pyqtSlot(int)
    def doubleClick(self, icon_id: int) -> None:
        if (icon := self._find(icon_id)) is not None:
            self._watch_menu_of(icon)
            icon.send_double_click()

    def _watch_menu_of(self, icon: TrayIcon) -> None:
        if icon not in self._unpinned:
            return
        was_open = self._menu_open
        self._menu_open = True
        self._menu_pid = icon.pid
        self._menu_since = time.monotonic()
        self._menu_seen = False
        self._menu_missing_since = None
        self._menu_timer.start()
        if not was_open:
            self.menuOpenChanged.emit()

    def _watch_menu(self) -> None:
        now = time.monotonic()
        if menu_shown(self._menu_pid):
            self._menu_seen = True
            self._menu_missing_since = None
            return
        pid = foreground_pid()
        if pid is None:
            # Between windows
            return
        if pid == os.getpid():
            # The app showed no menu, has not responded, or the popup regained focus.
            if self._menu_seen or now - self._menu_since > 2:
                self._end_menu()
            return
        if other_window_in_front():
            return self._end_menu()
        # Allow time for the app to show its menu and release focus after it closes.
        if self._menu_missing_since is None:
            self._menu_missing_since = now
        elif now - self._menu_missing_since >= (0.2 if self._menu_seen else 1):
            self._end_menu()

    def _end_menu(self) -> None:
        self._menu_timer.stop()
        if self._menu_open:
            self._menu_open = False
            self.menuOpenChanged.emit()

    @pyqtSlot(int)
    def togglePinned(self, icon_id: int) -> None:
        if (icon := self._find(icon_id)) is not None:
            self.moveIcon(icon_id, icon not in self._pinned, -1)

    @pyqtSlot(int, bool, int)
    def moveIcon(self, icon_id: int, pinned: bool, index: int) -> None:
        """Move an icon before the shown icon at index, or to the end for -1."""
        if (icon := self._find(icon_id)) is None:
            return
        icons = self._pinned if pinned else self._unpinned
        # The index includes the dragged icon when it stays in the same list.
        shown = [other for other in icons if self._shown(other)]
        before = shown[index] if 0 <= index < len(shown) else None
        if before is icon:
            return
        for others in (self._pinned, self._unpinned):
            if icon in others:
                others.remove(icon)
        icons.insert(icons.index(before) if before is not None else len(icons), icon)
        self._publish()
        self._save_state()

    @pyqtSlot()
    def refresh(self) -> None:
        """Ask every app to add its tray icons again"""
        broadcast_taskbar_created()

    def _visible_state_keys(self, icons: list[TrayIcon]) -> list[str]:
        return list(dict.fromkeys(icon.state_key for icon in icons if self._shown(icon)))

    def _update_state(self) -> None:
        """Save the visible order while preserving positions for absent icons."""
        visible = {True: self._visible_state_keys(self._pinned), False: self._visible_state_keys(self._unpinned)}
        for is_pinned, keys in visible.items():
            moved_out = set(visible[not is_pinned])
            saved = sorted(
                (k for k, s in self._state.items() if s.is_pinned == is_pinned and k not in moved_out),
                key=lambda k: self._state[k].index,
            )
            on_screen = iter(keys)
            order = [next(on_screen) if k in keys else k for k in saved]
            order += on_screen
            for index, key in enumerate(order):
                self._state[key] = IconState(is_pinned=is_pinned, index=index)

    def _load_state(self) -> None:
        self._screen_id = screen_id(self.setting("screenName"))
        file_path = app_data_path(f"systray_state_{self._screen_id}.json")
        logger.debug("Loading state from %s", file_path)
        self._state = {}
        try:
            with open(file_path, encoding="utf-8") as f:
                self._state = {k: IconState.from_dict(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            logger.debug("State file not found.")
        except json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError:
            logger.debug("State file decode error. Ignoring.")

    @pyqtSlot()
    def _save_state(self) -> None:
        if self._tray is None:
            return
        self._update_state()
        file_path = app_data_path(f"systray_state_{self._screen_id}.json")
        logger.debug("Saving state to %s", file_path)
        saved_state: dict[str, Any] = {}
        try:
            with open(file_path, encoding="utf-8") as f:
                saved_state = json.load(f)
        except FileNotFoundError:
            logger.debug("State file not found.")
        except json.JSONDecodeError:
            logger.debug("State file decode error. Ignoring.")
        # Preserve entries saved by other bars on this screen.
        new_state = saved_state | {k: v.__dict__ for k, v in self._state.items()}
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_state, indent=2))

import json
import logging
from typing import Any, ClassVar, cast, override

from PyQt6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QWindow

from core.services.apps.service import StartApps
from core.utils.icons.image_provider import icon_url
from core.utils.icons.service import IconService
from core.utils.icons.sources import AppIcon
from core.utils.qml import qml_property
from core.utils.shell_utils import shell_open
from core.utils.system import app_data_path
from core.utils.win32.window_actions import force_foreground_focus

LAYOUT_FILE = "launchpad.json"
NEW_GROUP = "New group"
ACTIONS = ("run_as_admin", "open_file_location", "uninstall")
ROLES = ("group", "appId", "name", "apps")

# An app id, or a group {"name", "apps"}
type Item = str | dict[str, Any]


def is_app(name: str, app_id: str, target: str, arguments: str) -> bool:
    """Whether an entry of All apps starts an app, rather than opening a document, a web page, a console, a folder
    or an uninstaller."""
    if "!" in app_id:
        # A Store app
        return True
    program = target or app_id
    lowered = program.lower()
    if lowered.startswith(("http://", "https://")) or lowered.endswith(".url"):
        return False
    # A shell item such as File Explorer, or an app id with no file behind it
    if program.startswith("::{") or "\\" not in program:
        return True
    file = lowered.rsplit("\\", 1)[-1]
    if not file.endswith(".exe") or file.startswith(("unins", "uninstall")) or name.lower().startswith("uninstall"):
        return False
    if file == "msiexec.exe" and "/x" in arguments.lower():
        return False
    # explorer.exe with a path opens a folder
    return not (file == "explorer.exe" and arguments)


class LaunchpadLayout(QAbstractListModel):
    """Every app and group of the launchpad in the user's order, the same in every launchpad and saved between runs.

    Rows: {group, appId, name, apps}; an app row has its id in appId, a group row its name and its app ids in apps.
    The first time apps come A to Z; apps installed since come last and apps gone leave. Hidden apps are in no row.
    """

    countChanged = pyqtSignal()
    hiddenChanged = pyqtSignal()

    _instance: ClassVar[LaunchpadLayout | None] = None

    @classmethod
    def instance(cls) -> LaunchpadLayout:
        """The one layout every launchpad shares, so two bars never save over each other."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self.items, self._hidden = self._read()
        self._installed: set[str] = set()
        # No rows until the first read says which saved apps are still installed
        self._synced = False

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or not self._synced else len(self.items)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < self.rowCount() or not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        item = self.items[index.row()]
        group = isinstance(item, dict)
        return {
            "group": group,
            "appId": "" if group else item,
            "name": item["name"] if group else "",
            "apps": list(item["apps"]) if group else [],
        }[ROLES[role - Qt.ItemDataRole.UserRole]]

    @qml_property(int, notify=countChanged)
    def count(self) -> int:
        return self.rowCount()

    # The installed apps the user hid, in the order they were hidden
    @qml_property("QStringList", notify=hiddenChanged)
    def hidden(self) -> list[str]:
        return self._installed_hidden()

    def sync(self, installed: list[str]) -> None:
        """Keeps the installed apps in their place, adds those not placed yet at the end and drops the rest; a group
        left with one app turns back into it. Hidden apps stay hidden, also while they are not installed."""
        before = self._installed_hidden()
        self._installed = set(installed)
        if self._installed_hidden() != before:
            self.hiddenChanged.emit()
        known = self._installed - set(self._hidden)
        items: list[Item] = []
        placed: set[str] = set()
        for item in self.items:
            if isinstance(item, dict):
                apps = [app for app in item["apps"] if app in known and app not in placed]
                placed.update(apps)
                if len(apps) > 1:
                    items.append({"name": item["name"], "apps": apps})
                elif apps:
                    items.append(apps[0])
            elif item in known and item not in placed:
                items.append(item)
                placed.add(item)
        items.extend(app for app in installed if app in known and app not in placed)
        if self._synced and items == self.items:
            return
        self.beginResetModel()
        self.items = items
        self._synced = True
        self.endResetModel()
        self.countChanged.emit()
        self._save()

    # Moves the row at source before the row now at before, or last for the row count
    @pyqtSlot(int, int)
    def move(self, source: int, before: int) -> None:
        if not 0 <= source < len(self.items) or not 0 <= before <= len(self.items) or before in (source, source + 1):
            return
        self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), before)
        item = self.items.pop(source)
        self.items.insert(before - 1 if before > source else before, item)
        self.endMoveRows()

    # Saves the order, as move does not: it runs at every step of a drag
    @pyqtSlot()
    def commit(self) -> None:
        self._save()

    # Drops the app at row source on the row target: on an app the two become a new group in its place, on a group
    # the app joins it. The group's row then, or -1 when nothing changed
    @pyqtSlot(int, int, result="int")
    def group(self, source: int, target: int) -> int:
        if source == target or not (0 <= source < len(self.items) and 0 <= target < len(self.items)):
            return -1
        app = self.items[source]
        if isinstance(app, dict):
            return -1
        onto = self.items[target]
        if isinstance(onto, dict):
            onto["apps"].append(app)
        else:
            self.items[target] = {"name": NEW_GROUP, "apps": [onto, app]}
        self._changed(target)
        self.beginRemoveRows(QModelIndex(), source, source)
        del self.items[source]
        self.endRemoveRows()
        self.countChanged.emit()
        self._save()
        return target - 1 if source < target else target

    # Takes an app out of the group at row and places it before the row now at before; a group left with one app
    # turns back into it. The app's row then, or -1 when it was not in the group
    @pyqtSlot(int, str, int, result="int")
    def takeOut(self, row: int, app_id: str, before: int) -> int:
        group = self.items[row] if 0 <= row < len(self.items) else None
        if not isinstance(group, dict) or app_id not in group["apps"]:
            return -1
        group["apps"].remove(app_id)
        if len(group["apps"]) == 1:
            self.items[row] = group["apps"][0]
        self._changed(row)
        before = max(0, min(before, len(self.items)))
        self.beginInsertRows(QModelIndex(), before, before)
        self.items.insert(before, app_id)
        self.endInsertRows()
        self.countChanged.emit()
        self._save()
        return before

    # Takes these apps out of the grid and their groups
    @pyqtSlot("QStringList")
    def hide(self, app_ids: list[str]) -> None:
        hiding = [app for app in dict.fromkeys(app_ids) if app not in self._hidden]
        if not hiding:
            return
        self._take(set(hiding), 0)
        self._hidden.extend(hiding)
        self.countChanged.emit()
        self.hiddenChanged.emit()
        self._save()

    # Puts hidden apps back, at the end of the grid
    @pyqtSlot("QStringList")
    def unhide(self, app_ids: list[str]) -> None:
        showing = [app for app in self._hidden if app in app_ids]
        if not showing:
            return
        self._hidden = [app for app in self._hidden if app not in showing]
        installed = [app for app in showing if app in self._installed]
        if installed:
            self.beginInsertRows(QModelIndex(), len(self.items), len(self.items) + len(installed) - 1)
            self.items.extend(installed)
            self.endInsertRows()
            self.countChanged.emit()
        self.hiddenChanged.emit()
        self._save()

    # Makes a new group of these apps, taken from wherever they are, in the place of the first of them. Its row, or -1
    # for fewer than two apps in the grid
    @pyqtSlot("QStringList", result="int")
    def groupApps(self, app_ids: list[str]) -> int:
        wanted = set(app_ids)
        apps: list[str] = []
        first = -1
        for row, item in enumerate(self.items):
            members = [app for app in (item["apps"] if isinstance(item, dict) else [item]) if app in wanted]
            if members and first < 0:
                first = row
            apps.extend(members)
        if len(apps) < 2:
            return -1
        row = first - self._take(set(apps), first)
        self.beginInsertRows(QModelIndex(), row, row)
        self.items.insert(row, {"name": NEW_GROUP, "apps": apps})
        self.endInsertRows()
        self.countChanged.emit()
        self._save()
        return row

    # Puts the apps of the group at row in its place
    @pyqtSlot(int)
    def ungroup(self, row: int) -> None:
        group = self.items[row] if 0 <= row < len(self.items) else None
        if not isinstance(group, dict):
            return
        apps: list[str] = group["apps"]
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.items[row]
        self.endRemoveRows()
        self.beginInsertRows(QModelIndex(), row, row + len(apps) - 1)
        self.items[row:row] = apps
        self.endInsertRows()
        self.countChanged.emit()
        self._save()

    # Moves an app of the group at row before the app now at before in it, or last for the group's size
    @pyqtSlot(int, str, int)
    def moveInGroup(self, row: int, app_id: str, before: int) -> None:
        group = self.items[row] if 0 <= row < len(self.items) else None
        if not isinstance(group, dict) or app_id not in group["apps"]:
            return
        apps: list[str] = group["apps"]
        source = apps.index(app_id)
        if before in (source, source + 1) or not 0 <= before <= len(apps):
            return
        apps.pop(source)
        apps.insert(before - 1 if before > source else before, app_id)
        self._changed(row)
        self._save()

    @pyqtSlot(int, str)
    def renameGroup(self, row: int, name: str) -> None:
        group = self.items[row] if 0 <= row < len(self.items) else None
        if isinstance(group, dict) and (name.strip() or NEW_GROUP) != group["name"]:
            group["name"] = name.strip() or NEW_GROUP
            self._changed(row)
            self._save()

    # The row of an app not in a group, -1 when there is none
    @pyqtSlot(str, result="int")
    def rowOf(self, app_id: str) -> int:
        return self.items.index(app_id) if app_id in self.items else -1

    # The id of the app at row, empty for a group
    @pyqtSlot(int, result="QString")
    def appAt(self, row: int) -> str:
        item = self.items[row] if 0 <= row < len(self.items) else None
        return item if isinstance(item, str) else ""

    @pyqtSlot(int, result="bool")
    def isGroup(self, row: int) -> bool:
        return 0 <= row < len(self.items) and isinstance(self.items[row], dict)

    # The name and the app ids of the group at row
    @pyqtSlot(int, result="QString")
    def nameOf(self, row: int) -> str:
        group = self.items[row] if 0 <= row < len(self.items) else None
        return group["name"] if isinstance(group, dict) else ""

    @pyqtSlot(int, result="QStringList")
    def appsOf(self, row: int) -> list[str]:
        group = self.items[row] if 0 <= row < len(self.items) else None
        return list(group["apps"]) if isinstance(group, dict) else []

    def _changed(self, row: int) -> None:
        index = self.index(row)
        self.dataChanged.emit(index, index)

    def _installed_hidden(self) -> list[str]:
        return [app for app in self._hidden if app in self._installed]

    def _take(self, apps: set[str], before: int) -> int:
        """Takes these apps out of their rows and groups; a group left with one app turns back into it. Returns how
        many removed rows were above before."""
        gone = 0
        for row in reversed(range(len(self.items))):
            item = self.items[row]
            if isinstance(item, dict):
                kept = [app for app in item["apps"] if app not in apps]
                if len(kept) == len(item["apps"]):
                    continue
                if kept:
                    if len(kept) > 1:
                        item["apps"] = kept
                    else:
                        self.items[row] = kept[0]
                    self._changed(row)
                    continue
            elif item not in apps:
                continue
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.items[row]
            self.endRemoveRows()
            gone += row < before
        return gone

    def _read(self) -> tuple[list[Item], list[str]]:
        path = app_data_path(LAYOUT_FILE)
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except OSError, ValueError:
            logging.exception("Could not read the launchpad's order from %s", path)
            return [], []
        saved = cast(dict[str, object], raw).get("order") if isinstance(raw, dict) else None
        hidden = cast(dict[str, object], raw).get("hidden") if isinstance(raw, dict) else None
        items: list[Item] = []
        for item in cast(list[object], saved) if isinstance(saved, list) else []:
            if isinstance(item, str):
                items.append(item)
            elif isinstance(item, dict):
                group = cast(dict[str, object], item)
                members = group.get("apps")
                apps = [
                    app
                    for app in (cast(list[object], members) if isinstance(members, list) else [])
                    if isinstance(app, str)
                ]
                items.append({"name": str(group.get("name") or NEW_GROUP), "apps": apps})
        return items, [
            app for app in (cast(list[object], hidden) if isinstance(hidden, list) else []) if isinstance(app, str)
        ]

    def _save(self) -> None:
        path = app_data_path(LAYOUT_FILE)
        saved = {"order": self.items, "hidden": self._hidden}
        try:
            path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logging.exception("Could not save the launchpad's order to %s", path)


class LaunchpadApps(QObject):
    """The apps of Start's All apps, leaving out documents, web links, consoles and uninstallers, in the user's order
    with their groups."""

    appsChanged = pyqtSignal()
    loadingChanged = pyqtSignal()
    iconsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._apps: list[dict[str, Any]] = []
        self._targets: dict[str, tuple[str, str]] = {}
        self._layout = LaunchpadLayout.instance()
        self._start = StartApps.instance()
        self._loading = not self._start.loaded
        IconService.instance().icons_changed.connect(self.iconsChanged)
        self._start.changed.connect(self._update)
        self._update()

    # Each app A to Z: {id, name, kind, target, arguments, icon}. kind is store or desktop; target and arguments are
    # what a desktop app starts; icon is an image URL whose last part QML replaces with iconRevision
    @qml_property("QVariantList", notify=appsChanged)
    def apps(self) -> list[dict[str, Any]]:
        return self._apps

    # The apps and groups in the user's order, and moving and grouping them
    @qml_property(LaunchpadLayout, constant=True)
    def layout(self) -> LaunchpadLayout:
        return self._layout

    # Until Start's apps are first read
    @qml_property(bool, notify=loadingChanged)
    def loading(self) -> bool:
        return self._loading

    # Goes up as icons finish loading; an icon URL asks again with it at its end
    @qml_property(int, notify=iconsChanged)
    def iconRevision(self) -> int:
        return IconService.instance().revision

    def _update(self) -> None:
        # Before the first read every app looks uninstalled, and syncing would drop the saved order
        if not self._start.loaded:
            return
        apps: list[dict[str, Any]] = [
            {
                "id": app.id,
                "name": app.name,
                "kind": "store" if "!" in app.id else "desktop",
                "target": app.target or app.id,
                "arguments": app.arguments,
                "icon": icon_url(AppIcon(app.id), 0),
            }
            for app in self._start.apps
            if app.name and app.id and is_app(app.name, app.id, app.target, app.arguments)
        ]
        if apps != self._apps:
            self._apps = apps
            self._targets = {app["id"]: (app["target"], app["arguments"]) for app in apps if app["kind"] == "desktop"}
            self.appsChanged.emit()
        self._layout.sync([app["id"] for app in apps])
        if self._loading:
            self._loading = False
            self.loadingChanged.emit()

    # Starts an app as Start does
    @pyqtSlot(str)
    def launch(self, app_id: str) -> None:
        shell_open(f"shell:AppsFolder\\{app_id}")

    # Which of run_as_admin, open_file_location and uninstall this app offers: all three for a desktop app that starts
    # a program file, only uninstall for any other
    @pyqtSlot(str, result="QStringList")
    def actions(self, app_id: str) -> list[str]:
        target, _arguments = self._targets.get(app_id, ("", ""))
        return list(ACTIONS) if target.lower().endswith(".exe") and ":\\" in target else ["uninstall"]

    @pyqtSlot(str, str)
    def run(self, app_id: str, action: str) -> None:
        if action not in self.actions(app_id):
            return
        target, arguments = self._targets.get(app_id, ("", ""))
        if action == "run_as_admin":
            shell_open(target, verb="runas", parameters=arguments or None)
        elif action == "open_file_location":
            shell_open("explorer.exe", parameters=f'/select,"{target}"')
        else:
            shell_open("ms-settings:appsfeatures")

    # Gives a YASB window the foreground and the keyboard, as a popup opened from a hotkey needs
    @pyqtSlot(QWindow)
    def takeFocus(self, window: QWindow) -> None:
        force_foreground_focus(int(window.winId()))

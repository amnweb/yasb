import json
import logging
import subprocess
import time
from types import ModuleType
from typing import Any, ClassVar, cast

from PyQt6 import sip
from PyQt6.QtCore import QDateTime, QObject, pyqtProperty, pyqtSignal, pyqtSlot

from core.services.updates import scoop, windows, winget
from core.utils.feed import Feed
from core.utils.qml import qml_property
from core.utils.system import app_data_path
from core.utils.worker import run_in_worker

# Each source's module has NAME, installed() and check(), and winget and Scoop have install(ids)
SOURCES: dict[str, ModuleType] = {"windows": windows, "winget": winget, "scoop": scoop}
SKIPPED_FILE = "updates_skipped.json"
MIN_WINDOWS_INTERVAL_MS = 1800000
MIN_PACKAGE_INTERVAL_MS = 600000
MAX_INTERVAL_MS = 604800000
# The first checks wait a little, so starting YASB does not start three tools at once; nothing found before shows,
# as apps can be updated while YASB is closed
FIRST_CHECK_MS = {"windows": 20000, "winget": 10000, "scoop": 15000}


def now_ms() -> int:
    return int(time.time() * 1000)


def _read_json(name: str) -> dict[str, Any]:
    try:
        data = json.loads(app_data_path(name).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return cast(dict[str, Any], data) if isinstance(data, dict) else {}


def _write_json(name: str, data: dict[str, Any]) -> None:
    try:
        app_data_path(name).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        logging.debug("Could not save %s", name, exc_info=True)


class SourceFeed(Feed[tuple[str, int]]):
    """One source's updates, checked every interval and shared by every widget with the same key."""

    _feeds: ClassVar[dict[Any, Any]] = {}

    def __init__(self, key: tuple[str, int]) -> None:
        super().__init__(key)
        self.source, self.interval = key
        self.installed = SOURCES[self.source].installed()
        self.updates: list[dict[str, Any]] = []
        self.restart_required = False
        # When the source was last checked, in ms since the epoch
        self.checked_at = 0
        self.installing = False
        if self.installed:
            self._timer.start(FIRST_CHECK_MS[self.source])

    @pyqtSlot()
    def fetch(self) -> None:
        if self.loading or self.installing or not self.installed:
            return
        self._timer.stop()
        self._request += 1
        request = self._request
        self.loading = True
        self.changed.emit()
        run_in_worker(
            SOURCES[self.source].check,
            lambda result, error: self._receive(request, result, error),
            f"Could not check {SOURCES[self.source].NAME}.",
        )

    def _receive(self, request: int, result: object, error: str) -> None:
        # Answers to an earlier request are dropped, as are those reaching a feed that has gone with its last widget
        if request != self._request or sip.isdeleted(self):
            return
        if isinstance(result, dict):
            self._take(cast(dict[str, Any], result))
            self.checked_at = now_ms()
        # A failed check keeps the updates found before
        self.loading, self.error = False, error
        self._timer.start(self.interval)
        self.changed.emit()

    def _take(self, found: dict[str, Any]) -> None:
        """The updates and restart a check found."""
        updates = found.get("updates")
        self.updates = (
            [cast(dict[str, Any], update) for update in cast(list[Any], updates) if isinstance(update, dict)]
            if isinstance(updates, list)
            else []
        )
        self.restart_required = bool(found.get("restartRequired"))

    def install(self, ids: list[str]) -> None:
        """Opens a terminal that updates these packages, and checks again once it closes."""
        if self.installing or not ids or not hasattr(SOURCES[self.source], "install"):
            return
        try:
            process: subprocess.Popen[bytes] = SOURCES[self.source].install(ids)
        except OSError:
            logging.exception("Could not open a terminal for %s", SOURCES[self.source].NAME)
            self.error = "Could not open a terminal to update in."
            self.changed.emit()
            return

        def closed(_result: object, _error: str) -> None:
            if sip.isdeleted(self):
                return
            self.installing = False
            self.changed.emit()
            self.fetch()

        self.installing = True
        self.changed.emit()
        run_in_worker(process.wait, closed, "Could not wait for the update terminal.")


class SkippedVersions(QObject):
    """The versions people chose to skip, by source and package id, saved for every widget; a newer version shows."""

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.versions: dict[str, dict[str, dict[str, str]]] = {}
        for source, packages in _read_json(SKIPPED_FILE).items():
            for package, entry in cast(dict[str, Any], packages).items() if isinstance(packages, dict) else ():
                if isinstance(entry, dict):
                    entry = cast(dict[str, Any], entry)
                    self.versions.setdefault(source, {})[package] = {
                        "name": str(entry.get("name", package)),
                        "version": str(entry.get("version", "")),
                    }

    def skips(self, source: str, update: dict[str, Any]) -> bool:
        entry = self.versions.get(source, {}).get(update["id"])
        return entry is not None and entry.get("version", "") == update.get("availableVersion", "")

    def skip(self, source: str, update: dict[str, Any]) -> None:
        self.versions.setdefault(source, {})[update["id"]] = {
            "name": update.get("name", update["id"]),
            "version": update.get("availableVersion", ""),
        }
        self._save()

    def restore(self, source: str, package: str) -> None:
        if self.versions.get(source, {}).pop(package, None) is not None:
            self._save()

    def _save(self) -> None:
        _write_json(SKIPPED_FILE, self.versions)
        self.changed.emit()


_skipped: SkippedVersions | None = None


def skipped_versions() -> SkippedVersions:
    global _skipped
    if _skipped is None:
        _skipped = SkippedVersions()
    return _skipped


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(updates: AvailableUpdates) -> Any:
        return updates.setting(name)

    def set_value(updates: AvailableUpdates, value: Any) -> None:
        updates.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


class AvailableUpdates(QObject):
    """The updates Windows Update, winget and Scoop have for this PC, for one widget, and installing them.

    Each source is checked off the GUI thread on its own interval, from a feed every widget with the same interval
    shares; nothing shows before a source's first check, as apps can be updated while YASB is closed.
    """

    settingsChanged = pyqtSignal()
    updatesChanged = pyqtSignal()

    # Whether each source is checked; winget and Scoop are left out where they are not installed
    windowsUpdate = _setting(bool, "windowsUpdate", settingsChanged)
    winget = _setting(bool, "winget", settingsChanged)
    scoop = _setting(bool, "scoop", settingsChanged)
    # How often Windows Update is checked, in milliseconds
    windowsInterval = _setting(int, "windowsInterval", settingsChanged)
    # How often winget and Scoop are checked, in milliseconds
    packageInterval = _setting(int, "packageInterval", settingsChanged)
    # Updates to leave out, by a name or id they contain, in any case, such as "Microsoft.Edge" or "Defender"
    exclude = _setting("QStringList", "exclude", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "windowsUpdate": True,
            "winget": True,
            "scoop": True,
            "windowsInterval": 86400000,
            "packageInterval": 14400000,
            "exclude": [],
        }
        self._feeds: dict[str, SourceFeed] = {}
        self._model: dict[str, Any] = {"sources": [], "updates": [], "skipped": [], "restart": False}
        skipped_versions().changed.connect(self._publish)
        # QML sets the settings after creating the object, so the feeds are joined once they are in
        self._join_timer = self.startTimer(0)

    def timerEvent(self, event: Any) -> None:
        if event.timerId() == self._join_timer:
            self.killTimer(self._join_timer)
            self._join_timer = 0
            self._join()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if name == "windowsInterval":
            value = _clamp(int(value), MIN_WINDOWS_INTERVAL_MS, MAX_INTERVAL_MS)
        elif name == "packageInterval":
            value = _clamp(int(value), MIN_PACKAGE_INTERVAL_MS, MAX_INTERVAL_MS)
        elif name == "exclude":
            value = [str(item) for item in value if str(item).strip()]
        if value == self._settings[name]:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name == "exclude":
            self._publish()
        elif not self._join_timer:
            self._join_timer = self.startTimer(0)

    # Each source checked: {id, name, installed, checking, installing, error, checked, count}, id windows, winget or
    # scoop, installed false where the tool is missing, checked a QDateTime (invalid before the first check) and count
    # the updates shown for it
    @qml_property("QVariantList", notify=updatesChanged)
    def sources(self) -> list[dict[str, Any]]:
        return self._model["sources"]

    # Every update shown, by source: {source, id, name, installedVersion, availableVersion}, Windows updates with kb,
    # severity and downloaded too; without the excluded ones and the versions skipped
    @qml_property("QVariantList", notify=updatesChanged)
    def updates(self) -> list[dict[str, Any]]:
        return self._model["updates"]

    @qml_property(int, notify=updatesChanged)
    def count(self) -> int:
        return len(self._model["updates"])

    # Whether Windows waits for a restart to finish installing updates
    @qml_property(bool, notify=updatesChanged)
    def restartRequired(self) -> bool:
        return self._model["restart"]

    @qml_property(bool, notify=updatesChanged)
    def checking(self) -> bool:
        return any(source["checking"] for source in self._model["sources"])

    # When a source was last checked; invalid before the first check
    @qml_property(QDateTime, notify=updatesChanged)
    def checked(self) -> QDateTime:
        latest = max((feed.checked_at for feed in self._feeds.values()), default=0)
        return QDateTime.fromMSecsSinceEpoch(latest) if latest else QDateTime()

    # The versions skipped, each {source, id, name, version}
    @qml_property("QVariantList", notify=updatesChanged)
    def skipped(self) -> list[dict[str, Any]]:
        return self._model["skipped"]

    def _join(self) -> None:
        intervals = {
            "windows": self._settings["windowsInterval"] if self._settings["windowsUpdate"] else None,
            "winget": self._settings["packageInterval"] if self._settings["winget"] else None,
            "scoop": self._settings["packageInterval"] if self._settings["scoop"] else None,
        }
        for source, interval in intervals.items():
            feed = self._feeds.get(source)
            if feed is not None and feed.interval == interval:
                continue
            if feed is not None:
                feed.changed.disconnect(self._publish)
                feed.leave(self)
                del self._feeds[source]
            if interval is not None:
                feed = self._feeds[source] = SourceFeed.join((source, interval), self)
                feed.changed.connect(self._publish)
        self._publish()

    def _excluded(self, update: dict[str, Any]) -> bool:
        words = [word.lower() for word in self._settings["exclude"]]
        text = f"{update.get('name', '')} {update.get('id', '')}".lower()
        return any(word in text for word in words)

    def _publish(self) -> None:
        skipped = skipped_versions()
        sources: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        for source, feed in self._feeds.items():
            shown = [
                {**update, "source": source}
                for update in feed.updates
                if not self._excluded(update) and not skipped.skips(source, update)
            ]
            updates.extend(shown)
            sources.append(
                {
                    "id": source,
                    "name": SOURCES[source].NAME,
                    "installed": feed.installed,
                    "checking": feed.loading,
                    "installing": feed.installing,
                    "error": feed.error,
                    "checked": QDateTime.fromMSecsSinceEpoch(feed.checked_at) if feed.checked_at else QDateTime(),
                    "count": len(shown),
                }
            )
        model = {
            "sources": sources,
            "updates": updates,
            "skipped": [
                {
                    "source": source,
                    "id": package,
                    "name": entry.get("name", package),
                    "version": entry.get("version", ""),
                }
                for source, packages in skipped.versions.items()
                for package, entry in packages.items()
            ],
            "restart": any(feed.restart_required for feed in self._feeds.values()),
        }
        if model != self._model:
            self._model = model
            self.updatesChanged.emit()

    # Checks a source again now, or every source for ""
    @pyqtSlot(str)
    def check(self, source: str) -> None:
        for name, feed in self._feeds.items():
            if source in ("", name):
                feed.fetch()

    # Updates these packages of winget or Scoop in a terminal, checking the source again once it closes; Windows
    # Update opens Settings instead, as Windows installs its own
    @pyqtSlot(str, "QStringList")
    def install(self, source: str, ids: list[str]) -> None:
        if source == "windows":
            windows.open_settings()
        elif (feed := self._feeds.get(source)) is not None:
            feed.install(list(ids))

    # Hides this version of a package until a newer one comes
    @pyqtSlot(str, str)
    def skip(self, source: str, package: str) -> None:
        feed = self._feeds.get(source)
        update = next((update for update in feed.updates if update["id"] == package), None) if feed else None
        if update is not None:
            skipped_versions().skip(source, update)

    # Shows a skipped package again
    @pyqtSlot(str, str)
    def restore(self, source: str, package: str) -> None:
        skipped_versions().restore(source, package)

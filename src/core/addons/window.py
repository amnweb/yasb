"""The Addons window's backend."""

import logging
import re
import threading
import zipfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.addons import operations
from core.utils.markdown import strip_images_and_html
from core.utils.qml import qml_property
from core.utils.shell_utils import shell_open
from core.widget_files import manifest_problem
from settings import DEFAULT_CONFIG_FILENAME, YASB_ADDONS

_FAILED = (OSError, ValueError, KeyError, zipfile.BadZipFile)
# yasb-addons writes the change log after this, under a Changes heading
_CHANGES = "<!-- changes -->"


def _readme(text: str, description: str) -> tuple[str, str]:
    """The README's own text and its change log. The title, description and install command the page shows already
    are left out, each only where the README has it as yasb-addons writes it; anything else stays."""
    head, _, changes = text.replace("\r\n", "\n").partition(_CHANGES)
    blocks = head.strip().split("\n\n")
    if blocks and blocks[0].startswith("# ") and "\n" not in blocks[0]:
        blocks.pop(0)
    if blocks and blocks[0].strip() == description.strip():
        blocks.pop(0)
    if blocks and blocks[0].startswith("```") and "yasbc addons install" in blocks[0]:
        blocks.pop(0)
    changes = changes.strip().removeprefix("## Changes")
    return strip_images_and_html("\n\n".join(blocks)), strip_images_and_html(changes)


def _folder_url(entry: dict[str, Any]) -> str:
    login, _, name = entry["id"].partition(".")
    return f"{operations.ADDONS_RAW}/{entry['type']}s/{login}/{name}"


def _entry_row(entry: dict[str, Any]) -> dict[str, Any]:
    latest = operations.release(entry)
    login, _, name = entry["id"].partition(".")
    assets = f"{_folder_url(entry)}/assets"
    return {
        "id": entry["id"],
        "type": entry["type"],
        "author": entry["author"],
        "title": entry["title"],
        "description": entry["description"],
        "version": latest["version"],
        "released": latest["released"],
        "versions": sorted((version["version"] for version in entry["versions"]), reverse=True),
        "cover": f"{assets}/{entry['cover']}" if entry.get("cover") else "",
        "previews": [f"{assets}/{preview}" for preview in entry.get("previews", [])],
        "authorUrl": f"{operations.GITHUB}{entry['author']}",
        "pageUrl": f"{YASB_ADDONS}/tree/main/{entry['type']}s/{login}/{name}",
    }


def _installed_row(addon_id: str, kind: str, folder: Path) -> dict[str, Any]:
    data = operations.read_manifest(folder)
    update, note = 0, ""
    if data is None:
        note = "no manifest.json"
    else:
        try:
            newer = operations.newer(folder, data)
        except _FAILED as e:
            newer = f"could not check for an update: {e}"
        update, note = (newer, "") if isinstance(newer, int) else (0, newer)
    version = data.get("version") if data else None
    return {
        "id": addon_id,
        "type": kind,
        "title": operations.title(folder, data),
        "version": version if isinstance(version, int) else 0,
        "source": operations.source(data),
        "external": bool(data and "source" in data),
        "update": update,
        "note": note,
        "problem": (manifest_problem(addon_id) or "") if kind == "widget" else "",
        "folder": str(folder),
    }


def _install(addon_id: str, kind: str, unpack: Callable[[Path], None], title: str) -> str:
    """Installs with unpack; for a config, which replaces the user's, says where theirs is saved."""
    backup = operations.install(addon_id, kind, unpack)
    return "" if backup is None else f"{title} is your config now. Yours is saved in {backup.parent}."


class Addons(QObject):
    stateChanged = pyqtSignal()
    listsChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    # title, message
    messageRequested = pyqtSignal(str, str)
    # id, the README's text and its change log, both "" when it can't be read
    readmeLoaded = pyqtSignal(str, str, str)
    # A GitHub link's manifest, or only error
    linkChecked = pyqtSignal("QVariantMap")
    # Brings work done on a thread back to this one
    _finished = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "loading"
        self._error = ""
        self._addons: list[dict[str, Any]] = []
        self._installed: list[dict[str, Any]] = []
        self._busy: list[str] = []
        self._config_busy = False
        self._writes: set[threading.Thread] = set()
        # Counts checkLink calls, as only the last one's answer is sent
        self._checks = 0
        self._finished.connect(self._call)

    @staticmethod
    def _call(done: Callable[[], None]) -> None:
        done()

    def _run(self, work: Callable[[], Callable[[], None]], failed: Callable[[str], None], writes: bool = False) -> None:
        def run() -> None:
            try:
                done = work()
            except Exception as e:
                logging.exception("The Addons window's work failed")
                done = partial(failed, f"{type(e).__name__}: {e}" if str(e) else type(e).__name__)
            self._finished.emit(done)
            self._writes.discard(thread)

        thread = threading.Thread(target=run, daemon=not writes, name="AddonsWork")
        if writes:
            self._writes.add(thread)
        thread.start()

    def wait(self) -> None:
        """Waits for running installs, so none stops halfway."""
        for thread in list(self._writes):
            thread.join()

    # loading, ready or failed
    @qml_property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    # Newest first
    @qml_property("QVariantList", notify=listsChanged)
    def addons(self) -> list[dict[str, Any]]:
        return self._addons

    @qml_property("QVariantList", notify=listsChanged)
    def installed(self) -> list[dict[str, Any]]:
        return self._installed

    # The ids of the addons being installed or updated
    @qml_property("QVariantList", notify=busyChanged)
    def busy(self) -> list[str]:
        return self._busy

    # A config install replaces the whole config folder, so it runs alone: it waits for the others, and they for it
    @qml_property(bool, notify=busyChanged)
    def configBusy(self) -> bool:
        return self._config_busy

    @qml_property(str, constant=True)
    def repository(self) -> str:
        return operations.ADDONS_REPOSITORY

    @qml_property(str, constant=True)
    def configFile(self) -> str:
        return DEFAULT_CONFIG_FILENAME

    @pyqtSlot()
    def refresh(self) -> None:
        self._state = "loading"
        self.stateChanged.emit()
        operations.addons_index.cache_clear()

        def work() -> Callable[[], None]:
            try:
                rows = sorted(
                    (_entry_row(entry) for entry in operations.addons_index().values()), key=lambda row: row["id"]
                )
                rows.sort(key=lambda row: row["released"], reverse=True)
                error = ""
            except _FAILED as e:
                logging.warning("Could not read %s: %s", operations.ADDONS_REPOSITORY, e)
                rows, error = [], str(e)
            installed = [_installed_row(*addon) for addon in operations.installed()]
            return partial(self._loaded, rows, installed, error)

        self._run(work, lambda error: self._loaded([], self._installed, error))

    def _loaded(self, rows: list[dict[str, Any]], installed: list[dict[str, Any]], error: str) -> None:
        self._addons, self._installed = rows, installed
        self._state, self._error = ("failed", error) if error else ("ready", "")
        self.listsChanged.emit()
        self.stateChanged.emit()

    def _rescanned(self, installed: list[dict[str, Any]]) -> None:
        self._installed = installed
        self.listsChanged.emit()

    def _work_on(self, addon_id: str, kind: str, title: str, work: Callable[[], str]) -> None:
        if addon_id in self._busy:
            return
        if self._config_busy or (kind == "config" and self._busy):
            self.messageRequested.emit(
                "Not now",
                "A config replaces your whole config folder, so it installs on its own. Try again when the other "
                "installs have finished.",
            )
            return
        self._busy.append(addon_id)
        self._config_busy = kind == "config"
        self.busyChanged.emit()

        def run() -> Callable[[], None]:
            try:
                message, failed = work(), ""
            except _FAILED as e:
                logging.warning("%s: %s", title, e)
                message, failed = str(e), title
            installed = [_installed_row(*addon) for addon in operations.installed()]
            return partial(self._worked, addon_id, failed, message, installed)

        self._run(run, lambda error: self._worked(addon_id, title, error, self._installed), writes=True)

    def _worked(self, addon_id: str, failed: str, message: str, installed: list[dict[str, Any]]) -> None:
        self._busy.remove(addon_id)
        self._config_busy = False
        self.busyChanged.emit()
        self._rescanned(installed)
        if message:
            self.messageRequested.emit(failed or "Done", message[:1].upper() + message[1:])

    @pyqtSlot(str, int)
    def install(self, addon_id: str, version: int) -> None:
        """Installs version, or the newest for 0."""

        def work() -> str:
            entry = operations.addons_index()[addon_id.casefold()]
            chosen = operations.release(entry, version or None)
            return _install(
                entry["id"], entry["type"], partial(operations.install_release, entry, chosen), entry["title"]
            )

        kind = next((row["type"] for row in self._addons if row["id"] == addon_id), "")
        self._work_on(addon_id, kind, f"Could not install {addon_id}", work)

    @pyqtSlot(str)
    def checkLink(self, link: str) -> None:
        repository = link.strip().removesuffix("/").removesuffix(".git")
        self._checks += 1
        check = self._checks

        def answer(result: dict[str, Any]) -> None:
            if check == self._checks:
                self.linkChecked.emit(result)

        def work() -> Callable[[], None]:
            try:
                manifest = operations.repository_manifest(repository)
            except _FAILED as e:
                error = str(e)
                return partial(answer, {"error": error[:1].upper() + error[1:]})
            exists = manifest["type"] != "config" and operations.target(manifest["id"], manifest["type"]).exists()
            return partial(answer, {**manifest, "link": repository, "exists": exists})

        self._run(work, lambda error: answer({"error": error}))

    @pyqtSlot("QVariantMap")
    def installLink(self, checked: dict[str, Any]) -> None:
        repository = str(checked["link"])
        manifest = {key: value for key, value in checked.items() if key not in ("link", "exists")}

        def work() -> str:
            unpack = partial(operations.install_repository, repository, manifest)
            return _install(manifest["id"], manifest["type"], unpack, manifest["title"])

        self._work_on(manifest["id"], str(manifest["type"]), f"Could not install {repository}", work)

    @pyqtSlot(str)
    def update(self, addon_id: str) -> None:
        row = next((row for row in self._installed if row["id"] == addon_id), None)
        if row is None:
            return
        folder = Path(row["folder"])

        def work() -> str:
            data = operations.read_manifest(folder) or {}
            if row["type"] != "config":
                message = operations.update(folder, data)
                return "" if re.fullmatch(r"updated to v\d+", message) else f"{row['title']}: {message}"
            if "source" in data:
                repository = str(data["source"])
                unpack = partial(operations.install_repository, repository, operations.repository_manifest(repository))
            else:
                entry = operations.addons_index()[addon_id.casefold()]
                unpack = partial(operations.install_release, entry, operations.release(entry))
            return _install(addon_id, "config", unpack, row["title"])

        self._work_on(addon_id, row["type"], f"Could not update {addon_id}", work)

    @pyqtSlot()
    def updateAll(self) -> None:
        """Updates everything but a config."""
        for row in self._installed:
            if row["update"] and row["type"] != "config":
                self.update(row["id"])

    @pyqtSlot(str)
    def loadReadme(self, addon_id: str) -> None:
        row = next((row for row in self._addons if row["id"] == addon_id), None)
        if row is None:
            self.readmeLoaded.emit(addon_id, "", "")
            return

        def work() -> Callable[[], None]:
            try:
                text = operations.download(f"{_folder_url(row)}/README.md").decode("utf-8")
            except _FAILED as e:
                logging.warning("Could not read the README of %s: %s", addon_id, e)
                text = ""
            return partial(self.readmeLoaded.emit, addon_id, *_readme(text, row["description"]))

        self._run(work, lambda _error: self.readmeLoaded.emit(addon_id, "", ""))

    @pyqtSlot(str)
    def openFolder(self, folder: str) -> None:
        shell_open(folder)

    @pyqtSlot(str)
    def open(self, url: str) -> None:
        shell_open(url)

    @pyqtSlot(str)
    def copy(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

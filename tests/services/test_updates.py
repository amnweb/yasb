import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtCore import QMetaObject, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.updates import monitor as monitor_module
from core.services.updates import scoop, winget
from core.services.updates.monitor import SKIPPED_FILE, AvailableUpdates, SourceFeed
from core.services.updates.terminal import quote
from core.utils.system import app_data_path
from core.utils.worker import run_in_worker
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


def winget_table(header: tuple[str, ...], rows: list[tuple[str, ...]], summary: str) -> str:
    """A table as winget prints it, each column as wide as its widest value, with a spinner left before it."""
    widths = [max(len(line[index]) for line in (header, *rows)) + 1 for index in range(len(header))]

    def line(values: tuple[str, ...]) -> str:
        return "".join(value.ljust(width) for value, width in zip(values, widths, strict=True)).rstrip()

    table = [line(header), "-" * sum(widths), *(line(row) for row in rows), summary]
    return "\r   - \r   \\ \r\n" + "\r\n".join(table) + "\r\n"


WINGET_TABLE = winget_table(
    ("Name", "Id", "Version", "Available", "Source"),
    [
        ("Internet Download Manager", "Tonec.InternetDownloadManager", "6.43.16", "6.43.17", "winget"),
        ("Telegram Desktop", "Telegram.TelegramDesktop", "7.3.3", "7.3.5", "winget"),
        ("Mystery Tool", "Some.Tool", "Unknown", "2.0", "winget"),
    ],
    "3 upgrades available.",
)

# The same table as German Windows prints it, the titles translated
WINGET_GERMAN = winget_table(
    ("Name", "ID", "Version", "Verfügbar", "Quelle"),
    [("PowerToys", "Microsoft.PowerToys", "0.86.0", "0.87.1", "winget")],
    "1 Aktualisierungen verfügbar.",
)

SCOOP_TABLE = """\x1b[32mName    Installed Version Latest Version Missing Dependencies Info\x1b[0m
----    ----------------- -------------- -------------------- ----
ffmpeg  7.1               7.1.1
git     2.47.0            2.47.1                              Held package
nodejs  20.1.0            22.0.0         python
"""


def test_the_winget_table_is_read_by_where_its_columns_start():
    packages = winget.parse_table(WINGET_TABLE)
    assert [(p["name"], p["id"], p["installedVersion"], p["availableVersion"]) for p in packages] == [
        ("Internet Download Manager", "Tonec.InternetDownloadManager", "6.43.16", "6.43.17"),
        ("Telegram Desktop", "Telegram.TelegramDesktop", "7.3.3", "7.3.5"),
        ("Mystery Tool", "Some.Tool", "Unknown", "2.0"),
    ]
    assert [p["id"] for p in winget.parse_table(WINGET_GERMAN)] == ["Microsoft.PowerToys"]
    assert winget.parse_table("No installed package found matching input criteria.") == []


# What scoop status printed on a PC with jq 1.6 installed from the main bucket
SCOOP_REAL = """Scoop is up to date.

Name Installed Version Latest Version Missing Dependencies Info
---- ----------------- -------------- -------------------- ----
jq   1.6               1.8.2
"""


def test_the_scoop_table_leaves_out_held_apps():
    apps = scoop.parse_table(SCOOP_TABLE)
    assert [(a["name"], a["installedVersion"], a["availableVersion"]) for a in apps] == [
        ("ffmpeg", "7.1", "7.1.1"),
        ("nodejs", "20.1.0", "22.0.0"),
    ]
    assert scoop.parse_table("Everything is ok!") == []
    assert [(a["name"], a["installedVersion"], a["availableVersion"]) for a in scoop.parse_table(SCOOP_REAL)] == [
        ("jq", "1.6", "1.8.2")
    ]


def test_scoop_installed_after_yasb_started_is_found_in_its_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def not_on_path(_name: str) -> None:
        return None

    monkeypatch.setattr(scoop.shutil, "which", not_on_path)
    monkeypatch.setenv("SCOOP", str(tmp_path))
    assert not scoop.installed()
    (tmp_path / "shims").mkdir()
    (tmp_path / "shims" / "scoop.cmd").write_text("", encoding="utf-8")
    assert scoop.executable() == str(tmp_path / "shims" / "scoop.cmd")


def test_names_in_a_terminal_command_are_quoted():
    assert quote("it's") == "'it''s'"


def until(condition: Callable[[], Any]) -> None:
    for _ in range(300):
        if condition():
            return
        wait(10)
    assert condition()


class FakeProcess:
    """An update terminal the test closes."""

    def __init__(self) -> None:
        self.closed = False

    def wait(self) -> int:
        while not self.closed:
            wait(5)
        return 0


class Sources:
    """Stands in for Windows Update, winget and Scoop, so the tests never run them."""

    def __init__(self) -> None:
        self.found: dict[str, Any] = {
            "windows": {
                "updates": [
                    {"id": "u1", "name": "Cumulative Update", "category": "Security Updates", "kb": "KB5049981", "severity": "Important",
                     "downloaded": True, "installedVersion": "", "availableVersion": ""}
                ],
                "restartRequired": True,
            },
            "winget": {
                "updates": [
                    {"id": "Git.Git", "name": "Git", "installedVersion": "2.47.0", "availableVersion": "2.47.1"},
                    {"id": "Microsoft.Edge", "name": "Microsoft Edge", "installedVersion": "130", "availableVersion": "131"},
                ]
            },
            "scoop": {"updates": [{"id": "ffmpeg", "name": "ffmpeg", "installedVersion": "7.1", "availableVersion": "7.1.1"}]},
        }  # fmt: skip
        self.errors: dict[str, str] = {}
        self.missing: set[str] = set()
        self.checks: list[str] = []
        self.installs: list[tuple[str, list[str]]] = []
        self.processes: list[FakeProcess] = []
        self.settings_opened = 0

    def module(self, source: str, name: str) -> SimpleNamespace:
        def check() -> dict[str, Any]:
            self.checks.append(source)
            if source in self.errors:
                raise RuntimeError(self.errors[source])
            return self.found[source]

        def install(ids: list[str]) -> FakeProcess:
            self.installs.append((source, ids))
            process = FakeProcess()
            self.processes.append(process)
            return process

        return SimpleNamespace(NAME=name, installed=lambda: source not in self.missing, check=check, install=install)


@pytest.fixture
def sources(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Sources:
    fake = Sources()
    modules = {
        "windows": fake.module("windows", "Windows Update"),
        "winget": fake.module("winget", "winget"),
        "scoop": fake.module("scoop", "Scoop"),
    }
    monkeypatch.setattr(monitor_module, "SOURCES", modules)
    monkeypatch.setattr(monitor_module, "FIRST_CHECK_MS", dict.fromkeys(modules, 0))
    monkeypatch.setattr(monitor_module, "_skipped", None)
    monkeypatch.setattr(SourceFeed, "_feeds", {})
    monkeypatch.setattr(monitor_module.windows, "open_settings", lambda: setattr(fake, "settings_opened", 1))
    app_data_path(SKIPPED_FILE).unlink(missing_ok=True)
    return fake


def available(**settings: Any) -> AvailableUpdates:
    updates = AvailableUpdates()
    for name, value in settings.items():
        updates.setProperty(name, value)
    return updates


def shown(updates: AvailableUpdates) -> list[tuple[str, str]]:
    return [(update["source"], update["id"]) for update in updates.property("updates")]


def test_every_source_is_checked_and_shown(sources: Sources):
    updates = available()
    until(lambda: updates.property("count") == 4)
    assert shown(updates) == [
        ("windows", "u1"),
        ("winget", "Git.Git"),
        ("winget", "Microsoft.Edge"),
        ("scoop", "ffmpeg"),
    ]
    assert updates.property("restartRequired") and updates.property("checked").isValid()
    assert [(s["id"], s["count"], s["installed"]) for s in updates.property("sources")] == [
        ("windows", 1, True),
        ("winget", 2, True),
        ("scoop", 1, True),
    ]


def test_a_missing_tool_is_not_checked(sources: Sources):
    sources.missing.add("scoop")
    updates = available()
    until(lambda: updates.property("count") == 3)
    assert "scoop" not in sources.checks
    assert next(s for s in updates.property("sources") if s["id"] == "scoop")["installed"] is False


def test_a_source_turned_off_is_left_out(sources: Sources):
    updates = available(windowsUpdate=False)
    until(lambda: updates.property("count") == 3)
    assert "windows" not in sources.checks and not updates.property("restartRequired")


def test_excluded_updates_are_left_out(sources: Sources):
    updates = available(exclude=["microsoft.edge", "Cumulative"])
    until(lambda: updates.property("count") == 2)
    assert shown(updates) == [("winget", "Git.Git"), ("scoop", "ffmpeg")]


def test_a_skipped_version_hides_until_a_newer_one(sources: Sources):
    updates = available()
    until(lambda: updates.property("count") == 4)
    updates.skip("winget", "Git.Git")
    assert ("winget", "Git.Git") not in shown(updates)
    assert updates.property("skipped") == [{"source": "winget", "id": "Git.Git", "name": "Git", "version": "2.47.1"}]
    sources.found["winget"]["updates"][0]["availableVersion"] = "2.48.0"
    updates.check("winget")
    until(lambda: ("winget", "Git.Git") in shown(updates))
    updates.restore("winget", "Git.Git")
    assert updates.property("skipped") == []


def test_a_failed_check_keeps_the_updates_found_before(sources: Sources):
    updates = available()
    until(lambda: updates.property("count") == 4)
    sources.errors["winget"] = "Could not run winget."
    updates.check("winget")
    until(
        lambda: next(s for s in updates.property("sources") if s["id"] == "winget")["error"] == "Could not run winget."
    )
    assert updates.property("count") == 4


def test_installing_checks_again_once_the_terminal_closes(sources: Sources):
    updates = available()
    until(lambda: updates.property("count") == 4)
    sources.found["winget"]["updates"] = []
    updates.install("winget", ["Git.Git", "Microsoft.Edge"])
    assert sources.installs == [("winget", ["Git.Git", "Microsoft.Edge"])]
    until(lambda: next(s for s in updates.property("sources") if s["id"] == "winget")["installing"])
    checks = sources.checks.count("winget")
    sources.processes[0].closed = True
    until(lambda: updates.property("count") == 2)
    assert sources.checks.count("winget") == checks + 1


def test_windows_updates_open_settings(sources: Sources):
    updates = available()
    until(lambda: updates.property("count") == 4)
    updates.install("windows", ["u1"])
    assert sources.settings_opened == 1 and sources.installs == []


def test_a_new_start_checks_again_instead_of_showing_old_updates(sources: Sources):
    first = available()
    until(lambda: first.property("count") == 4)
    first.deleteLater()
    until(lambda: not SourceFeed._feeds)  # pyright: ignore[reportPrivateUsage]
    # Updated while YASB was closed
    sources.found["winget"]["updates"] = []
    sources.checks.clear()
    second = available()
    assert second.property("count") == 0
    until(lambda: second.property("count") == 2)
    assert sorted(sources.checks) == ["scoop", "windows", "winget"]


def load_widget() -> Iterator[tuple[QQuickItem, list[str]]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Updates" / "Updates.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    # An item counts as visible only in a window, as on a bar
    host = QQuickWindow()
    item.setParentItem(host.contentItem())
    host.show()
    yield item, warnings
    popup = item.findChild(QObject, "popup")
    if popup is not None:
        QMetaObject.invokeMethod(popup, "hide")
    item.setParentItem(None)
    item.deleteLater()
    host.close()
    wait(20)


@pytest.fixture
def widget(sources: Sources) -> Iterator[tuple[QQuickItem, list[str]]]:
    yield from load_widget()


def open_popup(item: QQuickItem) -> QQuickItem:
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    return window.contentItem()


def test_the_popup_lists_each_source_with_its_updates(widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    label = find_item(item, "label")
    assert label is not None
    until(lambda: label.property("text") == "4")
    assert item.isVisible()
    content = open_popup(item)
    sections = find_item(content, "sources")
    restart = find_item(content, "restart")
    assert sections is not None and sections.isVisible()
    assert restart is not None and restart.isVisible()
    up_to_date = find_item(content, "upToDate")
    assert up_to_date is not None and not up_to_date.isVisible()
    assert not warnings, warnings


def test_with_nothing_to_update_the_widget_hides(sources: Sources):
    for found in sources.found.values():
        found["updates"] = []
    sources.found["windows"]["restartRequired"] = False
    loaded = load_widget()
    item, warnings = next(loaded)
    updates = item.findChild(AvailableUpdates)
    assert updates is not None
    until(lambda: updates.property("checked").isValid() and not updates.property("checking"))
    assert not item.isVisible()
    content = open_popup(item)
    up_to_date = find_item(content, "upToDate")
    assert up_to_date is not None and up_to_date.isVisible()
    assert not warnings, warnings
    next(loaded, None)


def test_checks_never_hold_up_exiting(qapp: QGuiApplication):
    # A thread pool waits for its jobs at exit, and a check can take minutes; a daemon thread is left behind
    answers: list[tuple[object, str]] = []
    run_in_worker(lambda: threading.current_thread().daemon, lambda result, error: answers.append((result, error)), "")
    until(lambda: bool(answers))
    assert answers == [(True, "")]

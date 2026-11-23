import hashlib
import io
import json
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QByteArray, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError

from core import widget_files
from core.bar.revisions import Revisions
from core.cli import addons
from core.cli.addons import ADDONS_RAW, CLIAddonsHandler, builtin_widgets, settings_copy
from core.qml_types import register_qml_types
from core.theme_files import config_qml_file, load_theme
from settings import QML_IMPORT_PATH

WIDGET = """pragma ComponentBehavior: Bound

import QtQuick
import Yasb.Themes

Item {
    id: thing

    component PopupIcons: QtObject {
        property string pin
    }

    component Settings: QtObject {
        required property Theme theme

        // Shown on the bar, such as "{value}"
        property string label: "{value} }"
        property string title: label
        property var devices: ({
            phone: "a",
            mouse: "b"
        })
        property font font
        property font popupFont
        popupFont.pixelSize: 13
        readonly property PopupIcons popupIcons: PopupIcons {
            pin: "P"
        }
    }

    required property Item bar
}
"""

# A line of a copy's settings block: an option with its value, a group's start, or a group's option
_SETTING = re.compile(r"^ {8}([\w.]+): (.*)$")
_GROUP = re.compile(r"^ {8}(\w+) \{$")
_IN_GROUP = re.compile(r"^ {12}(\w+): (.*)$")


def _builtin_text(widget: str) -> str:
    return (widget_files.BUILTIN_WIDGETS_DIR / widget / f"{widget}.qml").read_text(encoding="utf-8")


WITH_SETTINGS = [widget for widget in builtin_widgets() if settings_copy(widget, _builtin_text(widget)) is not None]


@pytest.fixture
def user_widgets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", tmp_path)
    monkeypatch.setattr(addons, "DEFAULT_CONFIG_DIRECTORY", str(tmp_path))
    return tmp_path


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, bytes]]:
    """The addons repository's files by URL."""
    files: dict[str, bytes] = {}
    monkeypatch.setattr(addons, "_download", files.__getitem__)
    addons.addons_index.cache_clear()
    yield files
    addons.addons_index.cache_clear()


def _publish(repository: dict[str, bytes], addon_id: str, kind: str, *versions: int) -> None:
    """Puts each version of the addon in the repository, and index.json listing them."""
    login, name = addon_id.split(".")
    entries: list[dict[str, int | str]] = []
    for version in versions:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(f"{name.capitalize()}.qml", f"// v{version}\n")
            archive.writestr("manifest.json", json.dumps({"id": addon_id, "version": version}))
        data = buffer.getvalue()
        repository[f"{ADDONS_RAW}/{kind}s/{login}/{name}/{version}/{name}.zip"] = data
        entries.append({"version": version, "sha256": hashlib.sha256(data).hexdigest()})
    entry = {"id": addon_id, "type": kind, "author": login, "title": name, "description": f"A {kind}"}
    index = {"addons": [{**entry, "versions": entries}]}
    repository[f"{ADDONS_RAW}/index.json"] = json.dumps(index).encode()
    addons.addons_index.cache_clear()


@pytest.fixture
def engine(qapp: QGuiApplication) -> Iterator[QQmlEngine]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    yield engine
    sip.delete(engine)


def _settings(copy: str) -> list[tuple[str, str]]:
    """Each setting of a copy, a group's as group.name, with a value over several lines joined."""
    found: list[tuple[str, list[str]]] = []
    group = ""
    for line in copy.splitlines():
        if group and line == "        }":
            group = ""
        elif group and (match := _IN_GROUP.match(line)):
            found.append((f"{group}.{match[1]}", [match[2]]))
        elif match := _GROUP.match(line):
            group = match[1]
        elif match := _SETTING.match(line):
            found.append((match[1], [match[2]]))
        elif line.startswith("        ") and not line.strip().startswith("//") and found:
            found[-1][1].append(line.strip())
    return [(name, "\n".join(parts)) for name, parts in found]


def test_a_settings_copy_sets_every_setting():
    copy = settings_copy("Thing", WIDGET)
    assert copy is not None
    assert copy.startswith("import Yasb.Widgets\n\n")
    assert "Thing {\n    settings {\n" in copy and copy.endswith("    }\n}\n")
    for line in [
        '        // Shown on the bar, such as "{value}"',
        '        label: "{value} }"',
        "        title: settings.label",
        "        devices: ({",
        '            mouse: "b"',
        "        })",
        "        popupFont.pixelSize: 13",
        "        popupIcons {",
        '            pin: "P"',
    ]:
        assert line in copy.splitlines()
    # The font with no value keeps its default, so the copy leaves it out
    assert "theme" not in copy and not any(line.strip().startswith("font") for line in copy.splitlines())
    assert settings_copy("Thing", "import QtQuick\n\nItem {}\n") is None


@pytest.mark.parametrize("widget", WITH_SETTINGS)
def test_every_settings_copy_works_with_only_its_one_import(engine: QQmlEngine, tmp_path: Path, widget: str):
    copy = settings_copy(widget, _builtin_text(widget))
    assert copy is not None
    # The copy compiles as it's written
    path = tmp_path / widget / f"{widget}.qml"
    path.parent.mkdir()
    path.write_text(copy, encoding="utf-8")
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    assert not component.isError(), [error.toString() for error in component.errors()]

    # Every value is worked out with only what a user's file has at the widget's top: import Yasb.Widgets, theme, and
    # the other settings only as settings.name
    settings = _settings(copy)
    group = "".join(
        f"        property var {name}: root.setting{index}\n"
        for index, (name, _) in enumerate(settings)
        if "." not in name
    )
    head = (
        "import QtQml\nimport Yasb.Widgets\n\nQtObject {\n    id: root\n\n    property QtObject theme\n"
        f"    readonly property QtObject settings: QtObject {{\n{group}    }}\n"
    )
    # The setting each line of the document holds, so a failure names the setting, not a line number
    names = [""] * (head.count("\n") + 1)
    values = ""
    for index, (name, value) in enumerate(settings):
        values += f"    property var setting{index}: {value}\n"
        names += [name] * (value.count("\n") + 1)
    document = f"{head}{values}}}\n"
    warnings: list[str] = []

    def warned(errors: list[QQmlError]) -> None:
        warnings.extend(f"settings.{names[error.line()]}: {error.description()}" for error in errors)

    engine.warnings.connect(warned)
    theme, _, _ = load_theme(engine, Revisions(), None, engine)
    values_component = QQmlComponent(engine)
    values_component.setData(QByteArray(document.encode()), QUrl.fromLocalFile(str(tmp_path / "Values.qml")))
    created = values_component.createWithInitialProperties({"theme": theme})
    assert created is not None, [error.toString() for error in values_component.errors()]
    assert not warnings, warnings


def test_copy_writes_the_settings_and_its_manifest(user_widgets: Path, capsys: pytest.CaptureFixture[str]):
    handler = CLIAddonsHandler()
    assert handler.install("clock") == 0
    path = user_widgets / "Clock" / "Clock.qml"
    assert '        format: "HH:mm"' in path.read_text(encoding="utf-8")
    manifest = json.loads((user_widgets / "Clock" / "manifest.json").read_text(encoding="utf-8"))
    assert list(manifest) == ["id", "title", "description", "version", "released"]
    assert manifest == widget_files.builtin_manifests()["Clock"]
    path.write_text("mine", encoding="utf-8")
    assert handler.install("Clock") == 1
    assert path.read_text(encoding="utf-8") == "mine"
    assert "Use --force to replace it" in capsys.readouterr().out


def test_force_replaces_a_copy_with_a_clean_one(user_widgets: Path):
    handler = CLIAddonsHandler()
    handler.install("Clock")
    (user_widgets / "Clock" / "extra.txt").write_text("x", encoding="utf-8")
    assert handler.install("clock", full=True, force=True) == 0
    builtin = {path.name for path in (widget_files.BUILTIN_WIDGETS_DIR / "Clock").iterdir()}
    assert {path.name for path in (user_widgets / "Clock").iterdir()} == builtin | {"manifest.json"}
    original = (widget_files.BUILTIN_WIDGETS_DIR / "Clock" / "Clock.qml").read_bytes()
    assert (user_widgets / "Clock" / "Clock.qml").read_bytes() == original
    assert handler.install("clock", force=True) == 0
    assert sorted(path.name for path in (user_widgets / "Clock").iterdir()) == ["Clock.qml", "manifest.json"]


def test_unknown_widgets_and_widgets_without_settings_are_refused(
    user_widgets: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    builtin = tmp_path_factory.mktemp("builtin")
    (builtin / "Plain").mkdir()
    (builtin / "Plain" / "Plain.qml").write_text("import QtQuick\n\nItem {}\n", encoding="utf-8")
    (builtin / "widgets.json").write_text(json.dumps({"widgets": [{"id": "Plain", "version": 1}]}), encoding="utf-8")
    monkeypatch.setattr(widget_files, "BUILTIN_WIDGETS_DIR", builtin)
    handler = CLIAddonsHandler()
    assert handler.install("nothing") == 1
    assert handler.install("plain") == 1
    assert "Use --full to install the whole widget" in capsys.readouterr().out
    assert not any(user_widgets.iterdir())


def test_list_shows_the_config_folders_widgets_one_line_each(user_widgets: Path, capsys: pytest.CaptureFixture[str]):
    handler = CLIAddonsHandler()
    handler.install("Clock")
    (user_widgets / "amnweb.clock").mkdir()
    (user_widgets / "amnweb.clock" / "Clock.qml").write_text("import QtQuick\n\nItem {}\n", encoding="utf-8")
    note = {"id": "amnweb.note", "title": "Note", "version": 2}
    (user_widgets / "amnweb.note").mkdir()
    (user_widgets / "amnweb.note" / "Note.qml").write_text("import QtQuick\n\nItem {}\n", encoding="utf-8")
    (user_widgets / "amnweb.note" / "manifest.json").write_text(json.dumps(note), encoding="utf-8")
    capsys.readouterr()
    assert handler.list() == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split() for line in lines] == [
        ["Name", "Id", "Type", "Version", "Source"],
        ["-" * len(lines[0])],
        ["amnweb.clock", "amnweb.clock", "widget", "-", "custom"],
        ["Note", "amnweb.note", "widget", "2", addons.ADDONS_REPOSITORY],
        ["Clock", "Clock", "widget", "1", "YASB"],
    ]

    manifest = user_widgets / "Clock" / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"version": 1', '"version": 0'))
    handler.list()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].endswith("Warning")
    assert lines[4].endswith("copy of v0, YASB's Clock is v1")


def test_update_refreshes_a_settings_copy_and_keeps_the_users_settings(
    user_widgets: Path, capsys: pytest.CaptureFixture[str]
):
    handler = CLIAddonsHandler()
    handler.install("Clock")
    path = user_widgets / "Clock" / "Clock.qml"
    text = path.read_text(encoding="utf-8").replace('        format: "HH:mm"', '        format: "HH"')
    text = text.replace("    settings {\n", "    settings {\n        gone: 1\n")
    path.write_text(text.replace("    }\n}\n", "    }\n    visible: false\n}\n"), encoding="utf-8")
    manifest = user_widgets / "Clock" / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"version": 1', '"version": 0'))
    capsys.readouterr()
    assert handler.update("clock") == 0
    out = capsys.readouterr().out
    assert "updated to v1. Removed settings: gone" in out
    lines = path.read_text(encoding="utf-8").splitlines()
    assert '        format: "HH"' in lines and '        locale: ""' in lines
    # Lines outside the settings block are kept as they are
    assert lines[-3:] == ["    }", "    visible: false", "}"]
    assert not any("gone" in line for line in lines)
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == 1


def test_install_takes_the_newest_version_and_update_lists_before_it_changes_anything(
    user_widgets: Path, repository: dict[str, bytes], capsys: pytest.CaptureFixture[str]
):
    _publish(repository, "someone.note", "widget", 1, 2)
    handler = CLIAddonsHandler()
    assert handler.install("someone.note") == 0
    note = user_widgets / "someone.note" / "Note.qml"
    assert note.read_text(encoding="utf-8") == "// v2\n"
    assert handler.install("someone.note") == 1
    assert handler.install("someone.note", version=3, force=True) == 1
    assert handler.install("someone.note", version=1, force=True) == 0
    assert note.read_text(encoding="utf-8") == "// v1\n"
    _publish(repository, "someone.note", "widget", 1, 2, 4)
    capsys.readouterr()
    assert handler.update() == 0
    assert ["someone.note", "someone.note", "widget", "1", "4", addons.ADDONS_REPOSITORY] in [
        line.split() for line in capsys.readouterr().out.splitlines()
    ]
    assert note.read_text(encoding="utf-8") == "// v1\n"
    assert handler.update(everything=True) == 0
    assert note.read_text(encoding="utf-8") == "// v4\n"


def test_search_lists_yasbs_widgets_and_the_addons(repository: dict[str, bytes], capsys: pytest.CaptureFixture[str]):
    handler = CLIAddonsHandler()
    _publish(repository, "someone.note", "widget", 1, 2)
    assert handler.search("nothing") == 0
    assert capsys.readouterr().out == "No widgets or addons match 'nothing'.\n"
    assert handler.search("SOMEONE") == 0
    assert capsys.readouterr().out.splitlines()[2].split() == [
        "note",
        "someone.note",
        "widget",
        "2",
        addons.ADDONS_REPOSITORY,
        "A",
        "widget",
    ]
    assert handler.search("time and date") == 0
    assert capsys.readouterr().out.splitlines()[2].split()[:5] == ["Clock", "Clock", "widget", "1", "YASB"]


def test_a_theme_gets_its_own_folder_and_a_download_that_does_not_match_changes_nothing(
    user_widgets: Path, repository: dict[str, bytes]
):
    _publish(repository, "someone.nord", "theme", 1)
    handler = CLIAddonsHandler()
    assert handler.install("someone.nord") == 0
    themes = user_widgets / "themes"
    assert config_qml_file("someone.nord", themes) == (themes / "someone.nord" / "Nord.qml").resolve()
    url = next(url for url in repository if url.endswith(".zip"))
    repository[url] += b"\0"
    assert handler.install("someone.nord", force=True) == 1
    assert (themes / "someone.nord" / "Nord.qml").is_file()


def test_a_config_replaces_the_users_which_is_saved_first(
    tmp_path: Path, repository: dict[str, bytes], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config = tmp_path / "yasb"
    (config / "widgets" / "Mine").mkdir(parents=True)
    for name in ("config.yaml", ".env", "yasb.log", "widgets/Mine/Mine.qml"):
        (config / name).write_text(name)
    monkeypatch.setattr(addons, "DEFAULT_CONFIG_DIRECTORY", str(config))
    monkeypatch.setattr(addons, "is_process_running", set[str]().__contains__)
    monkeypatch.setattr("builtins.input", "y{:.0}".format)
    _publish(repository, "someone.frame", "config", 1)
    handler = CLIAddonsHandler()

    before = sorted(config.rglob("*"))
    with addons.os.scandir(config / "widgets" / "Mine") as opened:
        next(opened)
        assert handler.install("someone.frame") == 1
    assert "widgets is in use, so nothing was changed" in capsys.readouterr().out
    assert sorted(config.rglob("*")) == before
    assert list(tmp_path.iterdir()) == [config]

    assert handler.install("someone.frame") == 0
    assert sorted(path.name for path in config.iterdir()) == [".env", "Frame.qml", "manifest.json", "yasb.log"]
    capsys.readouterr()
    handler.list()
    row = capsys.readouterr().out.splitlines()[2].split()
    assert row == ["yasb", "someone.frame", "config", "1", addons.ADDONS_REPOSITORY]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["yasb", "yasb-backups"]
    backup = next((tmp_path / "yasb-backups").glob("backup_mine_*.zip"))
    with zipfile.ZipFile(backup) as archive:
        assert {"config.yaml", "widgets/Mine/Mine.qml"} <= set(archive.namelist())
        assert not {".env", "yasb.log"} & set(archive.namelist())

    _publish(repository, "someone.frame", "config", 1, 2)
    capsys.readouterr()
    assert handler.update() == 0
    assert ["yasb", "someone.frame", "config", "1", "2", addons.ADDONS_REPOSITORY] in [
        line.split() for line in capsys.readouterr().out.splitlines()
    ]
    # Only by its id, as it replaces the whole config
    assert handler.update(everything=True) == 0
    assert (config / "Frame.qml").read_text() == "// v1\n"
    assert handler.update("someone.frame") == 0
    assert (config / "Frame.qml").read_text() == "// v2\n"
    # Once installed, it is saved under its own id
    assert list((tmp_path / "yasb-backups").glob("backup_someone.frame_*.zip"))


def test_an_addon_installs_from_github_and_updates_from_there(
    user_widgets: Path,
    repository: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    link = "https://github.com/Someone/my-note"
    manifest: dict[str, object] = {
        "id": "someone.note",
        "type": "widget",
        "title": "Note",
        "description": "A note",
        "version": 1,
    }

    def push(**changes: object) -> None:
        manifest.update(changes)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in ("Note.qml", ".github/workflow.yaml", "icons/note.svg"):
                archive.writestr(f"my-note-abc/{name}", f"v{manifest['version']}")
            archive.writestr("my-note-abc/manifest.json", json.dumps(manifest))
        repository["https://raw.githubusercontent.com/Someone/my-note/HEAD/manifest.json"] = json.dumps(
            manifest
        ).encode()
        repository[f"{link}/archive/HEAD.zip"] = buffer.getvalue()

    handler = CLIAddonsHandler()
    note = user_widgets / "someone.note"
    monkeypatch.setattr("builtins.input", "y{:.0}".format)
    for changes in ({"id": "amnweb.note"}, {"type": "script"}, {"title": "a\033[2Jb"}, {"version": "1"}):
        kept = dict(manifest)
        push(**changes)
        assert handler.install(link) == 1
        manifest = kept
    push()
    assert handler.install("https://example.com/Someone/my-note") == 1
    with monkeypatch.context() as answer:
        answer.setattr("builtins.input", "n{:.0}".format)
        assert handler.install(link) == 1
    assert not note.exists()

    capsys.readouterr()
    assert handler.install(f"{link}.git") == 0
    assert "not responsible for any damage" in capsys.readouterr().out
    assert sorted(path.name for path in note.iterdir()) == ["Note.qml", "icons", "manifest.json"]
    assert json.loads((note / "manifest.json").read_text(encoding="utf-8")) == {**manifest, "source": link}
    handler.list()
    assert ["Note", "someone.note", "widget", "1", "Someone/my-note"] in [
        line.split() for line in capsys.readouterr().out.splitlines()
    ]

    push(version=2)
    assert handler.update("someone.note") == 0
    assert (note / "Note.qml").read_text() == "v2"
    installed = note / "manifest.json"
    text = installed.read_text(encoding="utf-8")
    installed.write_text(text.replace("https://github.com", "https://example.com"), encoding="utf-8")
    assert handler.update("someone.note") == 1
    assert "only GitHub repositories work" in capsys.readouterr().out
    installed.write_text(text, encoding="utf-8")
    push(version=3, id="someone.other")
    handler.update("someone.note")
    assert "now holds the widget someone.other" in capsys.readouterr().out
    assert (note / "Note.qml").read_text() == "v2"


def test_install_copies_yasbs_own_widget(user_widgets: Path):
    handler = CLIAddonsHandler()
    assert handler.install("clock", version=1) == 1
    assert handler.install("someone.note", full=True) == 1
    assert handler.install("clock") == 0
    assert (user_widgets / "Clock" / "Clock.qml").is_file()

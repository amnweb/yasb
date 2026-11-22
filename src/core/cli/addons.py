import hashlib
import io
import json
import re
import shutil
import textwrap
import zipfile
from functools import cache
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from core import widget_files
from core.widget_files import (
    MANIFEST,
    builtin_manifest,
    builtin_manifests,
    file_name,
    folder_manifest,
    manifest_problem,
)
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, SERVICE_API_VERSION, YASB_ADDONS

ADDONS_REPOSITORY = YASB_ADDONS.rstrip("/").rpartition("/")[2]
ADDONS_RAW = YASB_ADDONS.rstrip("/").replace("https://github.com/", "https://raw.githubusercontent.com/", 1) + "/main"

_PROPERTY = re.compile(r"(?:readonly )?property \S+ (\w+)(?:: (.*))?")


def _statements(lines: list[str], start: int) -> list[list[str]]:
    """What the object opened on line start holds, each line one step in with the lines under it: those further
    in, and those that close its brackets."""
    outer = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    indent = f"{outer}    "
    statements: list[list[str]] = []
    for line in lines[start + 1 : lines.index(f"{outer}}}", start)]:
        if not line.strip():
            continue
        if statements and not (line.startswith(indent) and line[len(indent)] not in " }])"):
            statements[-1].append(line.removeprefix(indent))
        else:
            statements.append([line.removeprefix(indent)])
    return statements


def _options(text: str) -> list[list[str]] | None:
    """The lines of the widget's component Settings, None for a widget without one."""
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == "component Settings: QtObject {"), None)
    return None if start is None else _statements(lines, start)


def _setting(first: str, rest: list[str], names: set[str]) -> list[str]:
    """An option as the lines a user's settings block sets it with; none for one with no value, which keeps its
    default."""
    match = _PROPERTY.fullmatch(first)
    if match is None:
        # A part, such as popupFont.pixelSize: 13
        return [first, *rest]
    name, value = match[1], match[2]
    if value is None:
        return []
    # A group, such as popupIcons: PopupIcons {, with its lines as they are
    if value[0].isupper() and value.endswith("{"):
        return [f"{name} {{", *rest]
    return [f"{name}: {f'settings.{value}' if value in names else value}", *rest]


def _copy_text(widget: str, settings: list[list[str]], others: list[list[str]] | None = None) -> str:
    """The user's file: the settings block, then the file's other lines."""
    block = "".join(f"        {line}\n" for statement in settings for line in statement)
    more = "".join(f"    {line}\n" for statement in others or [] for line in statement)
    return (
        f"import Yasb.Widgets\n\n// YASB's {widget} with its settings; change any value here\n"
        f"{widget} {{\n    settings {{\n{block}    }}\n{more}}}\n"
    )


def _copy_statements(text: str) -> list[list[str]] | None:
    options = _options(text)
    if options is None:
        return None
    names = {match[1] for first, *_ in options if (match := _PROPERTY.fullmatch(first))}
    copied: list[list[str]] = []
    comments: list[list[str]] = []
    for first, *rest in options:
        if first.startswith("//"):
            comments.append([first])
            continue
        setting = [] if first.startswith("required ") else _setting(first, rest, names)
        if setting:
            copied += [*comments, setting]
            comments = []
        # An option with no value keeps its comments for its parts set below it
        elif not (match := _PROPERTY.fullmatch(first)) or not any(o[0].startswith(f"{match[1]}.") for o in options):
            comments = []
    return copied


def settings_copy(widget: str, text: str) -> str | None:
    """The user's file of a widget: a settings block with every option of its component Settings that has a value,
    the value and the comments above it as written; None for a widget without one."""
    statements = _copy_statements(text)
    return None if statements is None else _copy_text(widget, statements)


def _setting_name(line: str) -> str | None:
    """The option a line of a settings block sets, such as apps for apps {; None for a comment."""
    match = re.match(r"([\w.]+)\s*[:{]", line)
    return match[1] if match else None


def refresh_copy(widget: str, old: str, text: str) -> tuple[str, list[str]]:
    """A fresh settings copy of the built-in widget whose file is text, with each option old's settings block sets
    put back where it still exists, and old's other lines kept; returns the copy and the options that no longer
    exist."""
    lines = old.splitlines()
    start = next(index for index, line in enumerate(lines) if re.match(rf"{widget}\s*\{{$", line))
    kept: dict[str, list[str]] = {}
    others: list[list[str]] = []
    for statement in _statements(lines, start):
        if re.fullmatch(r"settings\s*\{", statement[0]):
            kept |= {name: inner for inner in _statements(statement, 0) if (name := _setting_name(inner[0]))}
        else:
            others.append(statement)
    statements = _copy_statements(text) or []
    for index, statement in enumerate(statements):
        statements[index] = kept.pop(_setting_name(statement[0]) or "", statement)
    return _copy_text(widget, statements, others), list(kept)


def _widgets(folder: Path) -> list[str]:
    """The widgets or addons in a folder by name, each a folder holding its QML file."""
    if not folder.is_dir():
        return []
    names = (child.name for child in folder.iterdir() if (child / file_name(child.name)).is_file())
    return sorted(names, key=str.lower)


def builtin_widgets() -> list[str]:
    return sorted(builtin_manifests(), key=str.lower)


def _named(name: str, widgets: list[str]) -> str | None:
    """The widget of that name, in any case, spelled as on disk."""
    return next((widget for widget in widgets if widget.casefold() == name.casefold()), None)


def copy_manifest(widget: str) -> dict[str, Any]:
    """The manifest of a copy of YASB's own widget of that id."""
    return {**builtin_manifests()[widget], "yasbApi": SERVICE_API_VERSION[0]}


def _write_manifest(folder: Path, data: dict[str, Any]) -> None:
    (folder / MANIFEST).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_manifest(folder: Path) -> dict[str, Any] | None:
    """The manifest in a widget's or addon's folder; None without one, or with one that can't be read."""
    try:
        return folder_manifest(folder)
    except ValueError:
        return None


def _addons_folder(kind: str) -> Path:
    """Where addons of a type from the addons repository go: widget, theme or layout."""
    return widget_files.USER_WIDGETS_DIR if kind == "widget" else Path(DEFAULT_CONFIG_DIRECTORY) / f"{kind}s"


def _installed() -> list[Path]:
    """The folders of the widgets folder, then the addons in the themes and layouts folders."""
    widgets = [widget_files.USER_WIDGETS_DIR / name for name in _widgets(widget_files.USER_WIDGETS_DIR)]
    folders = (_addons_folder("theme"), _addons_folder("layout"))
    return widgets + [folder / name for folder in folders for name in _widgets(folder) if "." in name]


def _download(url: str) -> bytes:
    with urlopen(url, timeout=15) as response:
        return response.read()


@cache
def addons_index() -> dict[str, dict[str, Any]]:
    """The addons repository's addons by id in lower case."""
    data = json.loads(_download(f"{ADDONS_RAW}/index.json"))
    return {entry["id"].casefold(): entry for entry in data["addons"]}


def _release(entry: dict[str, Any], number: int | None = None) -> dict[str, Any]:
    """The addon's version of that number, or its newest, for this YASB's API; raises ValueError when there is
    none."""
    api = SERVICE_API_VERSION[0]
    if number is not None:
        release = next((version for version in entry["versions"] if version["version"] == number), None)
        if release is None:
            numbers = ", ".join(str(version["version"]) for version in entry["versions"])
            raise ValueError(f"no v{number}, versions: {numbers}")
        if release["yasbApi"] != api:
            raise ValueError(f"v{number} is for YASB API {release['yasbApi']}, this YASB has API {api}")
        return release
    fitting = [version for version in entry["versions"] if version["yasbApi"] == api]
    if not fitting:
        apis = ", ".join(sorted({str(version["yasbApi"]) for version in entry["versions"]}))
        raise ValueError(f"no version for YASB API {api}, only for API {apis}")
    return max(fitting, key=lambda version: version["version"])


def _install(entry: dict[str, Any], release: dict[str, Any], target: Path) -> None:
    """Downloads the version's ZIP file, checks it against index.json and unpacks it as the target folder."""
    login, _, name = entry["id"].partition(".")
    data = _download(f"{ADDONS_RAW}/{entry['type']}s/{login}/{name}/{release['version']}/{name}.zip")
    if hashlib.sha256(data).hexdigest() != release["sha256"]:
        raise ValueError(f"the download of v{release['version']} does not match its sha256 in index.json")
    shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(target)


def _source(data: dict[str, Any] | None) -> str:
    """Where a widget or addon came from, by its manifest."""
    return "custom" if data is None else ADDONS_REPOSITORY if "." in str(data.get("id")) else "YASB"


def _title(folder: Path, data: dict[str, Any] | None) -> str:
    """The name a widget or addon is shown with: its manifest's title, or its folder's name."""
    return str(data.get("title") or folder.name) if data else folder.name


def _row(widget: str) -> tuple[str, str, str, str, str]:
    """The widget's name, id, version, where it came from, and why it no longer fits YASB, if it doesn't."""
    folder = widget_files.USER_WIDGETS_DIR / widget
    data = _read_manifest(folder)
    version = data.get("version") if data else None
    return (
        _title(folder, data),
        widget,
        str(version) if version is not None else "-",
        _source(data),
        (manifest_problem(widget) or ""),
    )


def _print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    """The rows in columns lined up under their headers and a line."""
    widths = [max(len(row[column]) for row in (headers, *rows)) for column in range(len(headers))]
    header = "  ".join(f"{cell:<{width}}" for cell, width in zip(headers, widths, strict=True)).rstrip()
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(f"{cell:<{width}}" for cell, width in zip(row, widths, strict=True)).rstrip())


class CLIAddonsHandler:
    """Copies YASB's widgets into the config folder, and updates, lists and removes what is there."""

    def copy(self, name: str, full: bool = False, force: bool = False) -> int:
        widget = _named(name, builtin_widgets())
        if widget is None:
            print(f"Unknown widget '{name}'. Available: {', '.join(builtin_widgets())}")
            return 1
        source = widget_files.BUILTIN_WIDGETS_DIR / widget
        target = widget_files.USER_WIDGETS_DIR / widget
        copy = None if full else settings_copy(widget, (source / f"{widget}.qml").read_text(encoding="utf-8"))
        if copy is None and not full:
            print(f"{widget} has no settings. Use --full to copy the whole widget.")
            return 1
        if target.exists() and not force:
            print(f"{target} already exists. Use --force to replace it.")
            return 1
        try:
            shutil.rmtree(target, ignore_errors=True)
            if copy is None:
                shutil.copytree(source, target)
            else:
                target.mkdir(parents=True)
                (target / f"{widget}.qml").write_text(copy, encoding="utf-8")
            _write_manifest(target, copy_manifest(widget))
        except OSError as e:
            print(f"Failed to copy {widget}: {e}")
            return 1
        if copy is None:
            print(f"Copied {widget} to {target}")
        else:
            print(f"Copied {widget} settings to {target / f'{widget}.qml'}")
        return 0

    def search(self, text: str | None = None) -> int:
        """Lists YASB's widgets and the addons for this YASB whose name, id, description, author or type has text."""
        query = (text or "").casefold()

        def matches(*fields: object) -> bool:
            return any(query in str(field).casefold() for field in fields)

        builtins = [
            (entry["title"], entry["id"], "widget", str(entry["version"]), "YASB", entry["description"])
            for entry in builtin_manifests().values()
            if matches(entry["id"], entry["title"], entry["description"], "widget", "YASB")
        ]
        addons: list[tuple[str, str, str, str, str, str]] = []
        failed = None
        try:
            for entry in addons_index().values():
                if not matches(entry["id"], entry["title"], entry["description"], entry["author"], entry["type"]):
                    continue
                try:
                    version = _release(entry)["version"]
                except ValueError:
                    # No version for this YASB's API, so install would refuse it
                    continue
                addons.append(
                    (entry["title"], entry["id"], entry["type"], str(version), ADDONS_REPOSITORY, entry["description"])
                )
        except (OSError, ValueError) as e:
            failed = e
        rows = sorted(builtins, key=lambda row: row[0].casefold()) + sorted(addons, key=lambda row: row[0].casefold())
        if rows:
            rows = [(*row[:-1], textwrap.shorten(row[-1], 60, placeholder="...")) for row in rows]
            _print_table(("Name", "Id", "Type", "Version", "Source", "Description"), rows)
            footer = f"{len(rows)} found."
            if addons:
                footer += " Run 'yasbc addons install <id>' to install an addon."
            print(footer)
        elif failed is None:
            print(f"No widgets or addons match '{text}'." if text else "No widgets or addons found.")
        if failed is not None:
            print(f"Could not search {ADDONS_REPOSITORY}: {failed}")
            return 1
        return 0

    def install(self, addon_id: str, version: int | None = None, force: bool = False) -> int:
        try:
            entry = addons_index().get(addon_id.casefold())
            if entry is None:
                raise ValueError(f"not in {ADDONS_REPOSITORY}")
            release = _release(entry, version)
        except (OSError, ValueError) as e:
            print(f"Could not install {addon_id}: {e}")
            return 1
        addon, kind = entry["id"], entry["type"]
        target = _addons_folder(kind) / addon
        if target.exists() and not force:
            print(f"{target} already exists. Use update, or --force to replace it.")
            return 1
        try:
            _install(entry, release, target)
        except (OSError, ValueError) as e:
            print(f"Could not install {addon}: {e}")
            return 1
        print(f"Installed {entry['title']} v{release['version']} to {target}")
        where = f"Add {addon} to a bar's widgets" if kind == "widget" else f"Set a bar's {kind} to {addon}"
        print(f"{where} in {DEFAULT_CONFIG_FILENAME} to use it.")
        return 0

    def update(self, name: str | None = None, everything: bool = False) -> int:
        """Lists the updates there are; updates the widget or addon of that name, or with everything all of them."""
        if name is not None and everything:
            print("Name a widget or use --all, not both.")
            return 1
        folders = _installed()
        if name is not None:
            folder = next((folder for folder in folders if folder.name.casefold() == name.casefold()), None)
            if folder is None:
                print(f"No widget, theme or layout named '{name}' in {DEFAULT_CONFIG_DIRECTORY}")
                return 1
            folders = [folder]
        found: list[tuple[Path, dict[str, Any], int]] = []
        failed = False
        for folder in folders:
            data = _read_manifest(folder)
            if data is None:
                if name is not None:
                    print(f"{folder.name}: no {MANIFEST}, skipped")
                continue
            try:
                newer = self._newer(folder, data)
            except (OSError, ValueError) as e:
                print(f"{folder.name}: could not check for an update: {e}")
                failed = True
                continue
            if isinstance(newer, int):
                found.append((folder, data, newer))
            elif name is not None:
                print(f"{folder.name}: {newer}")
        if name is None and not found:
            if not failed:
                print("Everything is up to date.")
        elif name is None and not everything:
            rows = [
                (_title(folder, data), folder.name, str(data.get("version")), str(version), _source(data))
                for folder, data, version in found
            ]
            _print_table(("Name", "Id", "Version", "Available", "Source"), rows)
            print(f"{len(found)} update{'s' if len(found) > 1 else ''} available.")
            print("Run 'yasbc addons update <id>' for one, or 'yasbc addons update --all' for all.")
        else:
            for folder, data, _ in found:
                try:
                    print(f"{folder.name}: {self._update(folder, data)}")
                except (OSError, ValueError) as e:
                    print(f"{folder.name}: could not update: {e}")
                    failed = True
        return 1 if failed else 0

    def _newer(self, folder: Path, data: dict[str, Any]) -> int | str:
        """The version an update would bring, or why there is none."""
        installed = data.get("version")
        if "." in str(data.get("id")):
            entry = addons_index().get(str(data["id"]).casefold())
            if entry is None:
                return f"not in {ADDONS_REPOSITORY}, skipped"
            version = _release(entry)["version"]
            return "up to date" if isinstance(installed, int) and installed >= version else version
        entry = builtin_manifest(folder.name)
        if entry is None:
            return "not a YASB widget, skipped"
        return "up to date" if installed == entry["version"] else entry["version"]

    def _update(self, folder: Path, data: dict[str, Any]) -> str:
        """Updates a widget or addon that _newer found an update for."""
        if "." in str(data.get("id")):
            entry = addons_index()[str(data["id"]).casefold()]
            release = _release(entry)
            _install(entry, release, folder)
            return f"updated to v{release['version']}"
        widget = folder.name
        entry = builtin_manifest(widget)
        if entry is None:
            return "not a YASB widget, skipped"
        builtin, version = entry["id"], entry["version"]
        source = widget_files.BUILTIN_WIDGETS_DIR / builtin / f"{builtin}.qml"
        path = folder / file_name(widget)
        old, text = path.read_text(encoding="utf-8"), source.read_text(encoding="utf-8")
        if not re.search(rf"^{builtin}\s*\{{", old, re.MULTILINE) or _options(text) is None:
            return f"full copy of v{data.get('version')}, YASB has v{version}. Use copy --full --force to replace it"
        copy, dropped = refresh_copy(builtin, old, text)
        path.write_text(copy, encoding="utf-8")
        _write_manifest(path.parent, copy_manifest(builtin))
        note = f". Removed settings: {', '.join(dropped)}" if dropped else ""
        return f"updated to v{version}{note}"

    def remove(self, name: str, yes: bool = False) -> int:
        widget = _named(name, _widgets(widget_files.USER_WIDGETS_DIR))
        if widget is None:
            print(f"No widget named '{name}' in {widget_files.USER_WIDGETS_DIR}")
            return 1
        target = widget_files.USER_WIDGETS_DIR / widget
        if not yes and input(f"Delete {target}? [y/N] ") != "y":
            return 1
        try:
            shutil.rmtree(target)
        except OSError as e:
            print(f"Could not delete {target}: {e}")
            return 1
        print(f"Deleted {target}.")
        return 0

    def list(self) -> int:
        widgets = _widgets(widget_files.USER_WIDGETS_DIR)
        if not widgets:
            print(f"No widgets in {widget_files.USER_WIDGETS_DIR}")
            return 0
        rows = [_row(widget) for widget in widgets]
        headers = ("Name", "Id", "Version", "Source", "Warning")
        # The warning column only when a widget has one
        width = len(headers) if any(row[-1] for row in rows) else len(headers) - 1
        _print_table(headers[:width], [row[:width] for row in rows])
        return 0

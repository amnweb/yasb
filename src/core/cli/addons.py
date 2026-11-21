import json
import re
import shutil
from pathlib import Path
from typing import Any

from core import widget_files
from core.widget_files import MANIFEST, builtin_manifest, builtin_manifests, file_name, manifest, manifest_problem
from settings import SERVICE_API_VERSION, YASB_ADDONS

ADDONS_REPOSITORY = YASB_ADDONS.rstrip("/").rpartition("/")[2]

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
    """The widgets in a folder by name, each a folder holding its QML file."""
    if not folder.is_dir():
        return []
    names = (child.name for child in folder.iterdir() if (child / file_name(child.name)).is_file())
    return sorted(names, key=str.lower)


def builtin_widgets() -> list[str]:
    return sorted(builtin_manifests(), key=str.lower)


def _named(name: str, widgets: list[str]) -> str | None:
    """The widget of that name, in any case, spelled as on disk."""
    return next((widget for widget in widgets if widget.lower() == name.lower()), None)


def copy_manifest(widget: str) -> dict[str, Any]:
    """The manifest of a copy of YASB's own widget of that id."""
    return {**builtin_manifests()[widget], "yasbApi": SERVICE_API_VERSION[0]}


def _write_manifest(folder: Path, data: dict[str, Any]) -> None:
    (folder / MANIFEST).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_manifest(widget: str) -> dict[str, Any] | None:
    """The widget's manifest; None without one, or with one that can't be read."""
    try:
        return manifest(widget)
    except ValueError:
        return None


def _row(widget: str) -> tuple[str, str, str, str]:
    """The widget, its version, where it came from, and why it no longer fits YASB, if it doesn't."""
    data = _read_manifest(widget)
    version = data.get("version") if data else None
    source = "custom" if data is None else ADDONS_REPOSITORY if "." in str(data.get("id")) else "YASB"
    problem = manifest_problem(widget)
    return widget, f"v{version}" if version is not None else "-", source, f"warning: {problem}" if problem else ""


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

    def update(self, name: str | None = None) -> int:
        widgets = _widgets(widget_files.USER_WIDGETS_DIR)
        if name is not None:
            widget = _named(name, widgets)
            if widget is None:
                print(f"No widget named '{name}' in {widget_files.USER_WIDGETS_DIR}")
                return 1
            widgets = [widget]
        failed = False
        for widget in widgets:
            data = _read_manifest(widget)
            if data is None:
                if name is not None:
                    print(f"{widget}: no {MANIFEST}, skipped")
                continue
            try:
                print(f"{widget}: {self._update(widget, data)}")
            except (OSError, ValueError) as e:
                print(f"{widget}: could not update: {e}")
                failed = True
        return 1 if failed else 0

    def _update(self, widget: str, data: dict[str, Any]) -> str:
        if "." in str(data.get("id")):
            return "addon updates are not supported yet"
        entry = builtin_manifest(widget)
        if entry is None:
            return "not a YASB widget, skipped"
        builtin, version = entry["id"], entry["version"]
        if data.get("version") == version:
            return "up to date"
        source = widget_files.BUILTIN_WIDGETS_DIR / builtin / f"{builtin}.qml"
        path = widget_files.USER_WIDGETS_DIR / widget / file_name(widget)
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
        widths = [max(len(row[column]) for row in rows) + 2 for column in range(3)]
        for row in rows:
            print("".join(f"{cell:<{width}}" for cell, width in zip(row, [*widths, 0], strict=True)).rstrip())
        return 0

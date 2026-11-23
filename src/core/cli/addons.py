import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import zipfile
from collections.abc import Callable
from datetime import datetime
from functools import cache, partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.error import HTTPError
from urllib.request import urlopen

from core import widget_files
from core.utils.process import is_process_running
from core.widget_files import (
    MANIFEST,
    builtin_manifest,
    builtin_manifests,
    file_name,
    folder_manifest,
    manifest_problem,
)
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, DEFAULT_LOG_FILENAME, YASB_ADDONS

ADDONS_REPOSITORY = YASB_ADDONS.rstrip("/").rpartition("/")[2]
ADDONS_RAW = YASB_ADDONS.rstrip("/").replace("https://github.com/", "https://raw.githubusercontent.com/", 1) + "/main"
GITHUB = "https://github.com/"

_ADDON_ID = re.compile(r"([a-z0-9-]+)\.([a-z][a-z0-9]*)")
_GITHUB_LINK = re.compile(rf"{GITHUB}([A-Za-z0-9-]+)/[\w.-]+")
# The user's keys, their repository and YASB's log
_KEPT_IN_CONFIG = shutil.ignore_patterns(".env", ".git", f"{DEFAULT_LOG_FILENAME}*")
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


def _installed() -> list[tuple[str, str, Path]]:
    """The id, type and folder of the installed config, then of all widgets, then of the installed themes and layouts."""
    config = Path(DEFAULT_CONFIG_DIRECTORY)
    config_id = _config_id(config)
    installed = [(config_id, "config", config)] if config_id else []
    for kind in ("widget", "theme", "layout"):
        folder = _addons_folder(kind)
        installed += [(name, kind, folder / name) for name in _widgets(folder) if kind == "widget" or "." in name]
    return installed


def _download(url: str) -> bytes:
    with urlopen(url, timeout=15) as response:
        return response.read()


@cache
def addons_index() -> dict[str, dict[str, Any]]:
    """The addons repository's addons by id in lower case."""
    data = json.loads(_download(f"{ADDONS_RAW}/index.json"))
    return {entry["id"].casefold(): entry for entry in data["addons"]}


def _release(entry: dict[str, Any], number: int | None = None) -> dict[str, Any]:
    """The addon's version of that number, or its newest; raises ValueError when there is none."""
    if number is not None:
        release = next((version for version in entry["versions"] if version["version"] == number), None)
        if release is None:
            numbers = ", ".join(str(version["version"]) for version in entry["versions"])
            raise ValueError(f"no v{number}, versions: {numbers}")
        return release
    return max(entry["versions"], key=lambda version: version["version"])


def _install(entry: dict[str, Any], release: dict[str, Any], target: Path) -> None:
    """Downloads the version's ZIP file, checks it against index.json and unpacks it as the target folder."""
    login, _, name = entry["id"].partition(".")
    data = _download(f"{ADDONS_RAW}/{entry['type']}s/{login}/{name}/{release['version']}/{name}.zip")
    if hashlib.sha256(data).hexdigest() != release["sha256"]:
        raise ValueError(f"the download of v{release['version']} does not match its sha256 in index.json")
    shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(target)


def _repository_manifest(repository: str) -> dict[str, Any]:
    """The manifest of an addon in its author's GitHub repository; raises ValueError for one YASB can't install."""
    link = _GITHUB_LINK.fullmatch(repository)
    if link is None:
        raise ValueError(f"only GitHub repositories work, such as {GITHUB}amnweb/clock")
    try:
        manifest = json.loads(
            _download(f"{repository.replace(GITHUB, 'https://raw.githubusercontent.com/')}/HEAD/{MANIFEST}")
        )
    except HTTPError as e:
        raise ValueError(f"it has no {MANIFEST}, or is private" if e.code == 404 else str(e)) from None
    if not isinstance(manifest, dict):
        raise ValueError(f"{MANIFEST} is not a JSON object")
    data = cast(dict[str, Any], manifest)
    owner = link[1].lower()
    addon_id = _ADDON_ID.fullmatch(str(data.get("id")))
    if addon_id is None or addon_id[1] != owner:
        raise ValueError(f"the id in {MANIFEST} must be {owner}.<name>, in lower case")
    if data.get("type") not in ("widget", "theme", "layout", "config"):
        raise ValueError(f"the type in {MANIFEST} must be widget, theme, layout or config")
    if not all(isinstance(text := data.get(key), str) and text.isprintable() for key in ("title", "description")):
        raise ValueError(f"the title and description in {MANIFEST} must be text on one line")
    if type(data.get("version")) is not int:
        raise ValueError(f"the version in {MANIFEST} must be a whole number")
    return data


def _install_repository(repository: str, manifest: dict[str, Any], target: Path) -> None:
    """Downloads the GitHub repository and unpacks it as the target folder, with the repository in its manifest."""
    with zipfile.ZipFile(io.BytesIO(_download(f"{repository}/archive/HEAD.zip"))) as archive:
        files: dict[str, zipfile.ZipInfo] = {}
        for info in archive.infolist():
            # GitHub puts the repository in a folder of its own
            path = info.filename.partition("/")[2]
            if path and not info.is_dir() and not any(part.startswith(".") for part in path.split("/")):
                files[path] = info
        if MANIFEST not in files or json.loads(archive.read(files[MANIFEST])) != manifest:
            raise ValueError("the repository has just changed, try again in a few minutes")
        if programs := [path for path in files if path.lower().endswith((".exe", ".dll"))]:
            raise ValueError(f"addons can't include .exe or .dll files: {', '.join(programs)}")
        is_config = manifest["type"] == "config"
        main_file = DEFAULT_CONFIG_FILENAME if is_config else file_name(manifest["id"])
        if main_file.casefold() not in (path.casefold() for path in files):
            raise ValueError(f"it has no {main_file}")
        shutil.rmtree(target, ignore_errors=True)
        for path, info in files.items():
            info.filename = path
            archive.extract(info, target)
    _write_manifest(target, {**manifest, "source": repository})


def _config_id(config: Path) -> str | None:
    """The id of an installed config; None for the user's own."""
    config_id = str((_read_manifest(config) or {}).get("id"))
    return config_id if _ADDON_ID.fullmatch(config_id) else None


def _backup_config(config: Path, old_config: Path) -> Path:
    """Saves the old config beside the config folder as a ZIP file named by its id."""
    backup_id = _config_id(old_config) or "mine"
    backup = config.with_name(f"{config.name}-backups") / f"backup_{backup_id}_{datetime.now():%Y-%m-%d_%H%M%S}.zip"
    backup.parent.mkdir(exist_ok=True)
    return Path(shutil.make_archive(str(old_config), "zip", old_config)).rename(backup)


def _replace_config(config: Path, new_config: Path, old_config: Path) -> None:
    """Moves everything out of the config folder and the new config in, or leaves it as it was and raises OSError."""
    moved: list[tuple[Path, Path]] = []

    def move_all(source: Path, target: Path) -> None:
        names = os.listdir(source)
        for name in set(names) - _KEPT_IN_CONFIG(str(source), names):
            (source / name).rename(target / name)
            moved.append((source / name, target / name))

    try:
        move_all(config, old_config)
        print(f"Saved your config to {_backup_config(config, old_config)}")
        move_all(new_config, config)
    except OSError as e:
        for source, target in reversed(moved):
            target.rename(source)
        if isinstance(e, PermissionError):
            raise OSError(
                f"{e.filename} is in use, so nothing was changed.\nClose every program that has a file or folder in "
                f"{config} open, such as File Explorer, a terminal or an editor, and try again."
            ) from e
        raise


def _stop_yasb_and_wait() -> None:
    subprocess.run(["yasbc", "stop", "--silent"], creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    deadline = time.monotonic() + 15
    while is_process_running("yasb.exe"):
        if time.monotonic() > deadline:
            raise OSError("YASB did not stop")
        time.sleep(0.25)


def _install_config(config: Path, unpack: Callable[[Path], None]) -> None:
    """Saves the config, then replaces it with what unpack puts in a folder, with the bar stopped meanwhile."""
    config.mkdir(parents=True, exist_ok=True)
    # Beside the config, as only there it can be moved
    with TemporaryDirectory(dir=config.resolve().parent, ignore_cleanup_errors=True) as folder:
        new_config, old_config = Path(folder, "new"), Path(folder, "old")
        old_config.mkdir()
        unpack(new_config)
        was_running = is_process_running("yasb.exe")
        try:
            if was_running:
                _stop_yasb_and_wait()
            _replace_config(config, new_config, old_config)
        finally:
            if was_running:
                subprocess.Popen(["yasb.exe"])


def _external_warning(repository: str, manifest: dict[str, Any]) -> str:
    yellow, reset = ("\033[93m", "\033[0m") if sys.stdout.isatty() else ("", "")
    return textwrap.dedent(f"""\
        {yellow}WARNING: This addon is not from {ADDONS_REPOSITORY}{reset}

          {manifest["title"]} v{manifest["version"]} ({manifest["type"]})
          {repository}

        {yellow}YASB's developers have not reviewed it and are not responsible for any damage it causes.
        Addons run code with your user rights: they can read, change and delete your files.
        Review the code yourself and install it only if you trust the author.{reset}
    """)


def _source(data: dict[str, Any] | None) -> str:
    """Where a widget or addon came from, by its manifest."""
    if data is None:
        return "custom"
    if "source" in data:
        return str(data["source"]).removeprefix(GITHUB)
    return ADDONS_REPOSITORY if "." in str(data.get("id")) else "YASB"


def _title(folder: Path, data: dict[str, Any] | None) -> str:
    """The name a widget or addon is shown with: its manifest's title, or its folder's name."""
    return str(data.get("title") or folder.name) if data else folder.name


def _row(addon_id: str, kind: str, folder: Path) -> tuple[str, str, str, str, str, str]:
    """The widget's or addon's name, id, type, version, source, and why it no longer fits YASB, if it doesn't."""
    data = _read_manifest(folder)
    version = data.get("version") if data else None
    return (
        _title(folder, data),
        addon_id,
        kind,
        str(version) if version is not None else "-",
        _source(data),
        (manifest_problem(addon_id) or "") if kind == "widget" else "",
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
    """Searches, installs, updates and lists widgets, themes and layouts."""

    def install(self, name: str, version: int | None = None, full: bool = False, force: bool = False) -> int:
        """Installs an addon by its id, which has a dot, or its GitHub link, or YASB's own widget to change it."""
        is_link = "/" in name
        is_builtin = "." not in name and not is_link
        if full and not is_builtin:
            print("--full is only for YASB's own widgets.")
            return 1
        if version is not None and (is_builtin or is_link):
            print(f"--version is only for addons from {ADDONS_REPOSITORY}.")
            return 1
        if is_link:
            return self._install_from_github(name, force)
        if is_builtin:
            return self._install_builtin(name, full, force)
        return self._install_addon(name, version, force)

    def _install_builtin(self, name: str, full: bool, force: bool) -> int:
        widget = _named(name, builtin_widgets())
        if widget is None:
            print(f"YASB has no widget '{name}'. Run 'yasbc addons search {name}' to look for an addon.")
            return 1
        source = widget_files.BUILTIN_WIDGETS_DIR / widget
        target = widget_files.USER_WIDGETS_DIR / widget
        settings = None if full else settings_copy(widget, (source / f"{widget}.qml").read_text(encoding="utf-8"))
        if settings is None and not full:
            print(f"{widget} has no settings. Use --full to install the whole widget.")
            return 1
        if target.exists() and not force:
            print(f"{target} already exists. Use --force to replace it.")
            return 1
        try:
            shutil.rmtree(target, ignore_errors=True)
            if settings is None:
                shutil.copytree(source, target)
            else:
                target.mkdir(parents=True)
                (target / f"{widget}.qml").write_text(settings, encoding="utf-8")
            _write_manifest(target, builtin_manifests()[widget])
        except OSError as e:
            print(f"Could not install {widget}: {e}")
            return 1
        if settings is None:
            print(f"Installed {widget} to {target}")
        else:
            print(f"Installed {widget} settings to {target / f'{widget}.qml'}")
        return 0

    def search(self, text: str | None = None) -> int:
        """Lists YASB's widgets and the addons whose name, id, description, author or type has text."""
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
                version = _release(entry)["version"]
                addons.append(
                    (entry["title"], entry["id"], entry["type"], str(version), ADDONS_REPOSITORY, entry["description"])
                )
        except (OSError, ValueError) as e:
            failed = e
        rows = sorted(builtins, key=lambda row: row[0].casefold()) + sorted(addons, key=lambda row: row[0].casefold())
        if rows:
            rows = [(*row[:-1], textwrap.shorten(row[-1], 60, placeholder="...")) for row in rows]
            _print_table(("Name", "Id", "Type", "Version", "Source", "Description"), rows)
            print(f"\n{len(rows)} found. Run 'yasbc addons install <id>' to install one.")
        elif failed is None:
            print(f"No widgets or addons match '{text}'." if text else "No widgets or addons found.")
        if failed is not None:
            print(f"Could not search {ADDONS_REPOSITORY}: {failed}")
            return 1
        return 0

    def _install_addon(self, addon_id: str, version: int | None, force: bool) -> int:
        try:
            entry = addons_index().get(addon_id.casefold())
            if entry is None:
                raise ValueError(f"not in {ADDONS_REPOSITORY}")
            release = _release(entry, version)
        except (OSError, ValueError) as e:
            print(f"Could not install {addon_id}: {e}")
            return 1
        title = f"{entry['title']} v{release['version']}"
        return self._install_files(entry["id"], entry["type"], title, partial(_install, entry, release), force)

    def _install_from_github(self, link: str, force: bool) -> int:
        repository = link.removesuffix("/").removesuffix(".git")
        try:
            manifest = _repository_manifest(repository)
        except (OSError, ValueError) as e:
            print(f"Could not install {repository}: {e}")
            return 1
        title = f"{manifest['title']} v{manifest['version']}"
        unpack = partial(_install_repository, repository, manifest)
        warning = _external_warning(repository, manifest)
        return self._install_files(manifest["id"], manifest["type"], title, unpack, force, warning)

    def _install_files(
        self, addon_id: str, kind: str, title: str, unpack: Callable[[Path], None], force: bool, warning: str = ""
    ) -> int:
        """Installs the addon with unpack, which puts its files in a folder, after the user agreed to the warning."""
        is_config = kind == "config"
        target = Path(DEFAULT_CONFIG_DIRECTORY) if is_config else _addons_folder(kind) / addon_id
        if not is_config and target.exists() and not force:
            print(f"{target} already exists. Use update, or --force to replace it.")
            return 1
        if warning:
            print(warning)
        if is_config:
            print(f"{title} replaces your whole config. Yours is saved first.")
        if (warning or is_config) and input("Do you want to install it? [y/N] ") != "y":
            return 1
        try:
            if is_config:
                _install_config(target, unpack)
            else:
                unpack(target)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"Could not install {addon_id}: {e}")
            return 1
        if is_config:
            print(f"{title} is your config now.")
            return 0
        print(f"Installed {title} to {target}")
        where = f"Add {addon_id} to a bar's widgets" if kind == "widget" else f"Set a bar's {kind} to {addon_id}"
        print(f"{where} in {DEFAULT_CONFIG_FILENAME} to use it.")
        return 0

    def update(self, name: str | None = None, everything: bool = False) -> int:
        """Lists the updates there are; updates the widget or addon of that name, or with everything all of them."""
        if name is not None and everything:
            print("Name a widget or use --all, not both.")
            return 1
        installed = _installed()
        if name is not None:
            installed = [addon for addon in installed if addon[0].casefold() == name.casefold()]
            if not installed:
                print(f"No widget, theme, layout or config named '{name}' in {DEFAULT_CONFIG_DIRECTORY}")
                return 1
        found: list[tuple[str, str, Path, dict[str, Any], int]] = []
        failed = False
        for addon_id, kind, folder in installed:
            data = _read_manifest(folder)
            if data is None:
                if name is not None:
                    print(f"{addon_id}: no {MANIFEST}, skipped")
                continue
            try:
                newer = self._newer(folder, data)
            except (OSError, ValueError) as e:
                print(f"{addon_id}: could not check for an update: {e}")
                failed = True
                continue
            if isinstance(newer, int):
                found.append((addon_id, kind, folder, data, newer))
            elif name is not None:
                print(f"{addon_id}: {newer}")
        if name is None and not found:
            if not failed:
                print("Everything is up to date.")
        elif name is None and not everything:
            rows = [
                (_title(folder, data), addon_id, kind, str(data.get("version")), str(version), _source(data))
                for addon_id, kind, folder, data, version in found
            ]
            _print_table(("Name", "Id", "Type", "Version", "Available", "Source"), rows)
            print(f"\n{len(found)} update{'s' if len(found) > 1 else ''} available.")
            print("Run 'yasbc addons update <id>' for one, or 'yasbc addons update --all' for all.")
        else:
            for addon_id, kind, folder, data, version in found:
                if kind == "config":
                    if not everything:
                        return self.install(str(data.get("source") or addon_id))
                    print(
                        f"{addon_id}: v{version} replaces your whole config. Run 'yasbc addons update {addon_id}' for it."
                    )
                    continue
                try:
                    print(f"{addon_id}: {self._update(folder, data)}")
                except (OSError, ValueError, zipfile.BadZipFile) as e:
                    print(f"{addon_id}: could not update: {e}")
                    failed = True
        return 1 if failed else 0

    def _newer(self, folder: Path, data: dict[str, Any]) -> int | str:
        """The version an update would bring, or why there is none."""
        installed = data.get("version")
        if "source" in data:
            manifest = _repository_manifest(str(data["source"]))
            if any(manifest[key] != data.get(key) for key in ("id", "type")):
                return f"{data['source']} now holds the {manifest['type']} {manifest['id']}, skipped"
            return (
                "up to date" if isinstance(installed, int) and installed >= manifest["version"] else manifest["version"]
            )
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
        if "source" in data:
            manifest = _repository_manifest(str(data["source"]))
            _install_repository(str(data["source"]), manifest, folder)
            return f"updated to v{manifest['version']}"
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
            installed = data.get("version")
            return f"full copy of v{installed}, YASB has v{version}. Use install {builtin} --full --force to replace it"
        copy, dropped = refresh_copy(builtin, old, text)
        path.write_text(copy, encoding="utf-8")
        _write_manifest(path.parent, entry)
        note = f". Removed settings: {', '.join(dropped)}" if dropped else ""
        return f"updated to v{version}{note}"

    def list(self) -> int:
        rows = [_row(addon_id, kind, folder) for addon_id, kind, folder in _installed()]
        if not rows:
            print(f"No widgets, themes or layouts in {DEFAULT_CONFIG_DIRECTORY}")
            return 0
        headers = ("Name", "Id", "Type", "Version", "Source", "Warning")
        # The warning column only when a widget has one
        width = len(headers) if any(row[-1] for row in rows) else len(headers) - 1
        _print_table(headers[:width], [row[:width] for row in rows])
        return 0

"""Installs, updates and lists widgets, themes, layouts and configs, for yasbc addons and the Addons window."""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable
from datetime import datetime
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.error import HTTPError
from urllib.request import urlopen

from core import widget_files
from core.addons.settings_copy import has_settings, refresh_copy
from core.utils.process import is_process_running
from core.widget_files import MANIFEST, builtin_manifest, builtin_manifests, file_name, folder_manifest
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, DEFAULT_LOG_FILENAME, YASB_ADDONS

ADDONS_REPOSITORY = YASB_ADDONS.rstrip("/").rpartition("/")[2]
ADDONS_RAW = YASB_ADDONS.rstrip("/").replace("https://github.com/", "https://raw.githubusercontent.com/", 1) + "/main"
GITHUB = "https://github.com/"

_ADDON_ID = re.compile(r"([a-z0-9-]+)\.([a-z][a-z0-9]*)")
_GITHUB_LINK = re.compile(rf"{GITHUB}([A-Za-z0-9-]+)/[\w.-]+")
# The user's keys, their repository and YASB's log
_KEPT_IN_CONFIG = shutil.ignore_patterns(".env", ".git", f"{DEFAULT_LOG_FILENAME}*")


def _widgets(folder: Path) -> list[str]:
    """The widgets or addons in a folder by name, each a folder holding its QML file."""
    if not folder.is_dir():
        return []
    names = (child.name for child in folder.iterdir() if (child / file_name(child.name)).is_file())
    return sorted(names, key=str.lower)


def write_manifest(folder: Path, data: dict[str, Any]) -> None:
    (folder / MANIFEST).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_manifest(folder: Path) -> dict[str, Any] | None:
    """The manifest in a widget's or addon's folder; None without one, or with one that can't be read."""
    try:
        return folder_manifest(folder)
    except ValueError:
        return None


def addons_folder(kind: str) -> Path:
    """Where addons of a type from the addons repository go: widget, theme or layout."""
    return widget_files.USER_WIDGETS_DIR if kind == "widget" else Path(DEFAULT_CONFIG_DIRECTORY) / f"{kind}s"


def target(addon_id: str, kind: str) -> Path:
    """Where an addon goes: a config is the config folder, anything else a folder of its own."""
    return Path(DEFAULT_CONFIG_DIRECTORY) if kind == "config" else addons_folder(kind) / addon_id


def installed() -> list[tuple[str, str, Path]]:
    """The id, type and folder of the installed config, then of all widgets, then of the installed themes and layouts."""
    config = Path(DEFAULT_CONFIG_DIRECTORY)
    config_id = _config_id(config)
    found = [(config_id, "config", config)] if config_id else []
    for kind in ("widget", "theme", "layout"):
        folder = addons_folder(kind)
        found += [(name, kind, folder / name) for name in _widgets(folder) if kind == "widget" or "." in name]
    return found


def download(url: str) -> bytes:
    with urlopen(url, timeout=15) as response:
        return response.read()


@cache
def addons_index() -> dict[str, dict[str, Any]]:
    """The addons repository's addons by id in lower case."""
    data = json.loads(download(f"{ADDONS_RAW}/index.json"))
    return {entry["id"].casefold(): entry for entry in data["addons"]}


def release(entry: dict[str, Any], number: int | None = None) -> dict[str, Any]:
    """The addon's version of that number, or its newest; raises ValueError when there is none."""
    if number is not None:
        found = next((version for version in entry["versions"] if version["version"] == number), None)
        if found is None:
            numbers = ", ".join(str(version["version"]) for version in entry["versions"])
            raise ValueError(f"no v{number}, versions: {numbers}")
        return found
    return max(entry["versions"], key=lambda version: version["version"])


def install_release(entry: dict[str, Any], chosen: dict[str, Any], folder: Path) -> None:
    """Downloads the version's ZIP file, checks it against index.json and unpacks it as the folder."""
    login, _, name = entry["id"].partition(".")
    data = download(f"{ADDONS_RAW}/{entry['type']}s/{login}/{name}/{chosen['version']}/{name}.zip")
    if hashlib.sha256(data).hexdigest() != chosen["sha256"]:
        raise ValueError(f"the download of v{chosen['version']} does not match its sha256 in index.json")
    shutil.rmtree(folder, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(folder)


def repository_manifest(repository: str) -> dict[str, Any]:
    """The manifest of an addon in its author's GitHub repository; raises ValueError for one YASB can't install."""
    link = _GITHUB_LINK.fullmatch(repository)
    if link is None:
        raise ValueError(f"only GitHub repositories work, such as {GITHUB}amnweb/clock")
    try:
        manifest = json.loads(
            download(f"{repository.replace(GITHUB, 'https://raw.githubusercontent.com/')}/HEAD/{MANIFEST}")
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


def install_repository(repository: str, manifest: dict[str, Any], folder: Path) -> None:
    """Downloads the GitHub repository and unpacks it as the folder, with the repository in its manifest."""
    with zipfile.ZipFile(io.BytesIO(download(f"{repository}/archive/HEAD.zip"))) as archive:
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
        shutil.rmtree(folder, ignore_errors=True)
        for path, info in files.items():
            info.filename = path
            archive.extract(info, folder)
    write_manifest(folder, {**manifest, "source": repository})


def _config_id(config: Path) -> str | None:
    """The id of an installed config; None for the user's own."""
    config_id = str((read_manifest(config) or {}).get("id"))
    return config_id if _ADDON_ID.fullmatch(config_id) else None


def _backup_config(config: Path, old_config: Path) -> Path:
    """Saves the old config beside the config folder as a ZIP file named by its id."""
    backup_id = _config_id(old_config) or "mine"
    backup = config.with_name(f"{config.name}-backups") / f"backup_{backup_id}_{datetime.now():%Y-%m-%d_%H%M%S}.zip"
    backup.parent.mkdir(exist_ok=True)
    return Path(shutil.make_archive(str(old_config), "zip", old_config)).rename(backup)


def _replace_config(config: Path, new_config: Path, old_config: Path) -> Path:
    """Moves everything out of the config folder and the new config in, and returns where the old one is saved; or
    leaves it as it was and raises OSError."""
    moved: list[tuple[Path, Path]] = []

    def move_all(source: Path, target: Path) -> None:
        names = os.listdir(source)
        for name in set(names) - _KEPT_IN_CONFIG(str(source), names):
            (source / name).rename(target / name)
            moved.append((source / name, target / name))

    try:
        move_all(config, old_config)
        backup = _backup_config(config, old_config)
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
    return backup


def _stop_yasb_and_wait() -> None:
    subprocess.run(["yasbc", "stop", "--silent"], creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    deadline = time.monotonic() + 15
    while is_process_running("yasb.exe"):
        if time.monotonic() > deadline:
            raise OSError("YASB did not stop")
        time.sleep(0.25)


def install_config(config: Path, unpack: Callable[[Path], None]) -> Path:
    """Saves the config, then replaces it with what unpack puts in a folder, with the bar stopped meanwhile; returns
    where the old config is saved."""
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
            return _replace_config(config, new_config, old_config)
        finally:
            if was_running:
                subprocess.Popen(["yasb.exe"])


def install(addon_id: str, kind: str, unpack: Callable[[Path], None]) -> Path | None:
    """Puts what unpack writes where the addon goes; a config replaces the user's, and returns where theirs is saved."""
    if kind == "config":
        return install_config(target(addon_id, kind), unpack)
    unpack(target(addon_id, kind))
    return None


def copy_builtin(widget: str, settings: str | None) -> Path:
    """Copies YASB's own widget to the user's widgets: whole without settings, otherwise as that settings copy; returns
    its folder."""
    source = widget_files.BUILTIN_WIDGETS_DIR / widget
    folder = target(widget, "widget")
    shutil.rmtree(folder, ignore_errors=True)
    if settings is None:
        shutil.copytree(source, folder)
    else:
        folder.mkdir(parents=True)
        (folder / f"{widget}.qml").write_text(settings, encoding="utf-8")
    write_manifest(folder, builtin_manifests()[widget])
    return folder


def source(data: dict[str, Any] | None) -> str:
    """Where a widget or addon came from, by its manifest."""
    if data is None:
        return "custom"
    if "source" in data:
        return str(data["source"]).removeprefix(GITHUB)
    return ADDONS_REPOSITORY if "." in str(data.get("id")) else "YASB"


def title(folder: Path, data: dict[str, Any] | None) -> str:
    """The name a widget or addon is shown with: its manifest's title, or its folder's name."""
    return str(data.get("title") or folder.name) if data else folder.name


def newer(folder: Path, data: dict[str, Any]) -> int | str:
    """The version an update would bring, or why there is none."""
    current = data.get("version")
    if "source" in data:
        manifest = repository_manifest(str(data["source"]))
        if any(manifest[key] != data.get(key) for key in ("id", "type")):
            return f"{data['source']} now holds the {manifest['type']} {manifest['id']}, skipped"
        return "up to date" if isinstance(current, int) and current >= manifest["version"] else manifest["version"]
    if "." in str(data.get("id")):
        entry = addons_index().get(str(data["id"]).casefold())
        if entry is None:
            return f"not in {ADDONS_REPOSITORY}, skipped"
        version = release(entry)["version"]
        return "up to date" if isinstance(current, int) and current >= version else version
    entry = builtin_manifest(folder.name)
    if entry is None:
        return "not a YASB widget, skipped"
    return "up to date" if current == entry["version"] else entry["version"]


def update(folder: Path, data: dict[str, Any]) -> str:
    """Updates a widget or addon that newer found an update for."""
    if "source" in data:
        manifest = repository_manifest(str(data["source"]))
        install_repository(str(data["source"]), manifest, folder)
        return f"updated to v{manifest['version']}"
    if "." in str(data.get("id")):
        entry = addons_index()[str(data["id"]).casefold()]
        chosen = release(entry)
        install_release(entry, chosen, folder)
        return f"updated to v{chosen['version']}"
    widget = folder.name
    entry = builtin_manifest(widget)
    if entry is None:
        return "not a YASB widget, skipped"
    builtin, version = entry["id"], entry["version"]
    builtin_file = widget_files.BUILTIN_WIDGETS_DIR / builtin / f"{builtin}.qml"
    path = folder / file_name(widget)
    old, text = path.read_text(encoding="utf-8"), builtin_file.read_text(encoding="utf-8")
    if not re.search(rf"^{builtin}\s*\{{", old, re.MULTILINE) or not has_settings(text):
        current = data.get("version")
        return f"full copy of v{current}, YASB has v{version}. Use install {builtin} --full --force to replace it"
    copy, dropped = refresh_copy(builtin, old, text)
    path.write_text(copy, encoding="utf-8")
    write_manifest(path.parent, entry)
    note = f". Removed settings: {', '.join(dropped)}" if dropped else ""
    return f"updated to v{version}{note}"

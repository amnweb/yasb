import hashlib
import io
import json
import os
import re
import shutil
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import certifi
from pydantic import BaseModel, ValidationError

from core.plugins.discovery import DiscoveredPlugin, discover_plugins, plugin_data_path, read_manifest
from core.plugins.manifest import (
    MANIFEST_FILENAME,
    PLUGIN_API_VERSION,
    PluginError,
    PluginManifest,
    is_plugin_id,
    version_tuple,
)
from settings import BUILD_VERSION, PLUGIN_INDEX_URL

INSTALL_RECORD = ".yasb-install.json"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
USER_AGENT = f"YASB/{BUILD_VERSION}"
GITHUB_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?(?:@([A-Za-z0-9._-]+))?",
    re.IGNORECASE,
)

type Confirm = Callable[[PluginManifest, str], bool]
type ConfirmReplace = Callable[[PluginManifest], bool]


class InstallCancelled(Exception):
    pass


class IndexEntry(BaseModel):
    name: str
    version: str
    author: str
    description: str = ""
    api: str
    min_yasb: str
    zip: str
    sha256: str
    disabled: bool = False


class PluginIndex(BaseModel):
    plugins: dict[str, IndexEntry] = {}


@dataclass(frozen=True)
class Installed:
    manifest: PluginManifest
    directory: Path
    source: str

    @property
    def official(self) -> bool:
        return self.source == "official"


@dataclass(frozen=True)
class GitHubSource:
    owner: str
    repo: str
    ref: str | None = None

    @property
    def label(self) -> str:
        return f"github.com/{self.owner}/{self.repo}" + (f"@{self.ref}" if self.ref else "")

    @property
    def archive_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/archive/{self.ref or 'HEAD'}.zip"

    @property
    def manifest_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.ref or 'HEAD'}/{MANIFEST_FILENAME}"


def github_source(source: str) -> GitHubSource | None:
    match = GITHUB_PATTERN.fullmatch(source.strip())
    return GitHubSource(match[1], match[2], match[3]) if match else None


def index_url() -> str:
    return os.environ.get("YASB_PLUGIN_INDEX_URL") or PLUGIN_INDEX_URL


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise PluginError(f"{url} answered {e.code} {e.reason}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise PluginError(f"cannot reach {url}: {e}") from e
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PluginError(f"{url} is larger than {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB")
    return data


def fetch_index() -> PluginIndex:
    url = index_url()
    try:
        return PluginIndex.model_validate_json(fetch(url))
    except ValidationError as e:
        raise PluginError(f"the plugin index at {url} is not valid: {e}") from e


def _official_entry(index: PluginIndex, plugin_id: str) -> IndexEntry:
    entry = index.plugins.get(plugin_id)
    if entry is None:
        raise PluginError(
            f'There is no plugin named "{plugin_id}" in the official plugin repository. '
            "Find one with `yasbc plugin search`, or install a folder or .zip by its path, like .\\my-plugin"
        )
    if entry.disabled:
        raise PluginError(
            f'Plugin "{plugin_id}" is temporarily disabled in the official plugin repository, '
            "so it cannot be installed right now"
        )
    if entry.api != str(PLUGIN_API_VERSION):
        raise PluginError(
            f'Plugin "{plugin_id}" {entry.version} is made for plugin API {entry.api}, '
            f"but this YASB supports plugin API {PLUGIN_API_VERSION}"
        )
    if version_tuple(BUILD_VERSION) < version_tuple(entry.min_yasb):
        raise PluginError(
            f'Plugin "{plugin_id}" {entry.version} needs YASB {entry.min_yasb} or newer. Update YASB with `yasbc update`.'
        )
    return entry


def _plugin_root(folder: Path) -> Path:
    if (folder / MANIFEST_FILENAME).is_file():
        return folder
    entries = [entry for entry in folder.iterdir() if not entry.name.startswith((".", "__MACOSX"))]
    if len(entries) == 1 and entries[0].is_dir() and (entries[0] / MANIFEST_FILENAME).is_file():
        return entries[0]
    raise PluginError(f"no {MANIFEST_FILENAME} at the top of the plugin")


def extract_zip(data: bytes, dest: Path) -> Path:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise PluginError(f"not a valid .zip file: {e}") from e
    root = dest.resolve()
    with archive:
        members = archive.infolist()
        if sum(member.file_size for member in members) > MAX_EXTRACTED_BYTES:
            raise PluginError(f"the archive unpacks to more than {MAX_EXTRACTED_BYTES // (1024 * 1024)} MB")
        for member in members:
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root) or target == root:
                raise PluginError(f'the archive entry "{member.filename}" points outside the plugin folder')
        archive.extractall(root)
    return _plugin_root(root)


def _download(plugin_id: str, entry: IndexEntry, dest: Path) -> Path:
    data = fetch(urllib.parse.urljoin(index_url(), entry.zip))
    if hashlib.sha256(data).hexdigest() != entry.sha256.lower():
        raise PluginError(
            f'The download of "{plugin_id}" does not match the official plugin repository (its SHA-256 differs), '
            "so nothing was installed"
        )
    plugin_dir = extract_zip(data, dest)
    _, found = read_manifest(plugin_dir)
    if found.manifest and (found.manifest.id, found.manifest.version) != (plugin_id, entry.version):
        raise PluginError(
            f'The download of "{plugin_id}" {entry.version} contains '
            f'"{found.manifest.id}" {found.manifest.version}, so nothing was installed'
        )
    return plugin_dir


def _fetch_github(github: GitHubSource, url: str) -> bytes:
    try:
        return fetch(url)
    except PluginError as e:
        if " answered 404 " in str(e):
            raise PluginError(
                f"{github.label} doesn't exist on GitHub, or has no {MANIFEST_FILENAME} at the top"
            ) from e
        raise


def _from_github(github: GitHubSource, dest: Path) -> tuple[Path, PluginManifest]:
    data = _fetch_github(github, github.archive_url)
    try:
        plugin_dir = extract_zip(data, dest)
    except PluginError as e:
        raise PluginError(f"{github.label}: {e}") from e
    key, found = read_manifest(plugin_dir)
    if found.manifest is None:
        raise PluginError(f'Plugin "{key}" from {github.label} {found.error}')
    return plugin_dir, found.manifest


def read_install_record(directory: Path) -> dict[str, Any]:
    try:
        record = json.loads((directory / INSTALL_RECORD).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return cast(dict[str, Any], record) if isinstance(record, dict) else {}


def _origin(record: dict[str, Any]) -> str:
    source = str(record.get("source", "local"))
    if source == "github":
        return "github:" + str(record.get("url", "")).partition("@")[0].lower()
    if source in ("local", "zip"):
        return f"{source}:{os.path.normcase(str(record.get('path', '')))}"
    return source


def is_official(directory: Path) -> bool:
    return read_install_record(directory).get("source") == "official"


def installed_plugins(root: Path) -> dict[str, DiscoveredPlugin]:
    return discover_plugins(root, log_errors=False)


def install_directory(
    source: Path,
    root: Path,
    record: dict[str, Any],
    replace: bool = False,
    confirm_replace: ConfirmReplace | None = None,
) -> Installed:
    key, found = read_manifest(source)
    if found.manifest is None:
        raise PluginError(f'Plugin "{key}" {found.error}')
    manifest = found.manifest
    existing = installed_plugins(root).get(manifest.id)
    target = existing.directory if existing else root / manifest.id
    different = target.exists() and _origin(read_install_record(target)) != _origin(record)
    if different and confirm_replace is not None:
        if not confirm_replace(manifest):
            raise InstallCancelled
    elif target.exists() and not replace:
        raise PluginError(
            f'Plugin "{manifest.id}" is already installed in {target}. '
            "Use `yasbc plugin update` or add --force to replace it."
        )
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".staging-{manifest.id}"
    backup = root / f".old-{manifest.id}"
    for leftover in (staging, backup):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", ".git", ".github", INSTALL_RECORD))
    (staging / INSTALL_RECORD).write_text(json.dumps(record, indent=2), encoding="utf-8")
    if target.exists():
        target.rename(backup)
    try:
        staging.rename(target)
    except OSError:
        if backup.exists():
            backup.rename(target)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(backup, ignore_errors=True)
    return Installed(manifest, target, str(record.get("source", "local")))


def is_local_source(source: str) -> bool:
    return "/" in source or "\\" in source or source.lower().endswith(".zip") or source in (".", "..")


def install(
    source: str,
    root: Path,
    replace: bool = False,
    confirm: Confirm | None = None,
    confirm_replace: ConfirmReplace | None = None,
) -> Installed:
    if github := github_source(source):
        with tempfile.TemporaryDirectory(prefix="yasb-plugin-") as temp:
            plugin_dir, manifest = _from_github(github, Path(temp))
            if confirm is not None and not confirm(manifest, github.label):
                raise InstallCancelled
            record = {"source": "github", "url": github.label}
            return install_directory(plugin_dir, root, record, replace, confirm_replace)
    if is_local_source(source):
        local = Path(source).expanduser()
        if local.is_dir():
            record = {"source": "local", "path": str(local.resolve())}
            return install_directory(_plugin_root(local), root, record, replace, confirm_replace)
        if not local.is_file():
            raise PluginError(f"{local} does not exist")
        with tempfile.TemporaryDirectory(prefix="yasb-plugin-") as temp:
            plugin_dir = extract_zip(local.read_bytes(), Path(temp))
            record = {"source": "zip", "path": str(local.resolve())}
            return install_directory(plugin_dir, root, record, replace, confirm_replace)
    if not is_plugin_id(source):
        raise PluginError(
            f'"{source}" is not a plugin name. Names use lowercase letters, digits and "-", like "lyrics". '
            "To install a folder or .zip, give its path, like .\\my-plugin"
        )
    entry = _official_entry(fetch_index(), source)
    with tempfile.TemporaryDirectory(prefix="yasb-plugin-") as temp:
        plugin_dir = _download(source, entry, Path(temp))
        record = {"source": "official", "version": entry.version}
        return install_directory(plugin_dir, root, record, replace, confirm_replace)


def update(plugin_id: str, root: Path, index: PluginIndex) -> tuple[str, Installed | None]:
    plugin = installed_plugins(root).get(plugin_id)
    if plugin is None:
        raise PluginError(f'Plugin "{plugin_id}" is not installed')
    record = read_install_record(plugin.directory)
    current = plugin.manifest.version if plugin.manifest else "0.0.0"
    if record.get("source") == "github" and (github := github_source(str(record.get("url", "")))):
        try:
            latest = json.loads(_fetch_github(github, github.manifest_url)).get("version", "")
        except ValueError, AttributeError:
            latest = ""
        if latest and version_tuple(str(latest)) <= version_tuple(current):
            return f"up to date ({current})", None
        with tempfile.TemporaryDirectory(prefix="yasb-plugin-") as temp:
            plugin_dir, manifest = _from_github(github, Path(temp))
            if version_tuple(manifest.version) <= version_tuple(current):
                return f"up to date ({current})", None
            installed = install_directory(plugin_dir, root, record, True)
        return f"updated {current} -> {manifest.version} from {github.label}", installed
    if record.get("source") != "official":
        return f"installed from {record.get('path', 'a local folder')}, install it again to update it", None
    entry = index.plugins.get(plugin_id)
    if entry is None:
        return "no longer in the official plugin repository, it keeps working until you remove it", None
    if entry.disabled:
        return "temporarily disabled in the official plugin repository, so it cannot be updated right now", None
    if version_tuple(entry.version) <= version_tuple(current):
        return f"up to date ({current})", None
    entry = _official_entry(index, plugin_id)
    with tempfile.TemporaryDirectory(prefix="yasb-plugin-") as temp:
        plugin_dir = _download(plugin_id, entry, Path(temp))
        installed = install_directory(plugin_dir, root, {"source": "official", "version": entry.version}, True)
    return f"updated {current} -> {entry.version}", installed


def remove(plugin_id: str, root: Path, purge_data: bool = False) -> None:
    plugin = installed_plugins(root).get(plugin_id)
    if plugin is None:
        raise PluginError(f'Plugin "{plugin_id}" is not installed')
    shutil.rmtree(plugin.directory)
    if purge_data:
        shutil.rmtree(plugin_data_path(plugin_id), ignore_errors=True)

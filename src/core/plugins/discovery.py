import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from core.plugins.manifest import MANIFEST_FILENAME, PLUGIN_API_VERSION, PluginManifest, plugin_slug, version_tuple
from core.utils.system import app_data_path
from settings import BUILD_VERSION, DEFAULT_CONFIG_DIRECTORY


@dataclass(frozen=True)
class DiscoveredPlugin:
    directory: Path
    manifest: PluginManifest | None = None
    error: str | None = None


def plugins_dir() -> Path:
    return Path(DEFAULT_CONFIG_DIRECTORY) / "plugins"


def plugin_data_path(plugin_id: str) -> Path:
    return app_data_path("plugin-data") / plugin_slug(plugin_id)


def plugin_data_dir(plugin_id: str) -> Path:
    folder = plugin_data_path(plugin_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _validation_summary(error: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'manifest'}: {e['msg']}" for e in error.errors())


def read_manifest(directory: Path) -> tuple[str, DiscoveredPlugin]:
    key = directory.name
    try:
        raw: object = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return key, DiscoveredPlugin(directory, error=f"has an unreadable {MANIFEST_FILENAME}: {e}")
    if not isinstance(raw, dict):
        return key, DiscoveredPlugin(directory, error=f"has a {MANIFEST_FILENAME} that is not a JSON object")
    data = cast(dict[str, Any], raw)
    if isinstance(plugin_id := data.get("id"), str):
        key = plugin_id
    api = data.get("api")
    if api is not None and str(api) != str(PLUGIN_API_VERSION):
        return key, DiscoveredPlugin(
            directory, error=f"targets plugin API {api}, but this YASB supports plugin API {PLUGIN_API_VERSION}"
        )
    try:
        manifest = PluginManifest.model_validate(data)
    except ValidationError as e:
        return key, DiscoveredPlugin(directory, error=f"has an invalid {MANIFEST_FILENAME}: {_validation_summary(e)}")
    if version_tuple(BUILD_VERSION) < version_tuple(manifest.min_yasb):
        return key, DiscoveredPlugin(
            directory, error=f"requires YASB {manifest.min_yasb} or newer, this is YASB {BUILD_VERSION}"
        )
    return key, DiscoveredPlugin(directory, manifest=manifest)


def discover_plugins(root: Path, log_errors: bool = True) -> dict[str, DiscoveredPlugin]:
    found: dict[str, DiscoveredPlugin] = {}
    if not root.is_dir():
        return found
    for directory in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")):
        if not (directory / MANIFEST_FILENAME).is_file():
            if log_errors:
                logging.warning("Ignoring %s: it has no %s", directory, MANIFEST_FILENAME)
            continue
        key, plugin = read_manifest(directory)
        if key in found:
            plugin = DiscoveredPlugin(directory, error=f"is installed twice, in {found[key].directory} and {directory}")
        if plugin.error and log_errors:
            logging.error('Skipping plugin "%s" in %s: it %s', key, directory, plugin.error)
        found[key] = plugin
    return found

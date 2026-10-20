import argparse
import io
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from core.cli.format import Format
from core.plugins import install as installer
from core.plugins.discovery import plugins_dir
from core.plugins.manifest import PluginError, PluginManifest, plugin_id_of
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME


def _confirm(question: str, default: bool = True) -> bool:
    answer = input(f"{question} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def _widgets_using(plugin_id: str) -> list[str]:
    try:
        with open(Path(DEFAULT_CONFIG_DIRECTORY) / DEFAULT_CONFIG_FILENAME, encoding="utf-8") as file:
            widgets = cast(dict[str, dict[str, Any]], yaml.safe_load(file)["widgets"])
        return [name for name, widget in widgets.items() if plugin_id_of(str(widget.get("type"))) == plugin_id]
    except OSError, yaml.YAMLError, KeyError, TypeError, AttributeError:
        return []


def cmd_install(root: Path, source: str, force: bool, assume_yes: bool) -> int:
    def confirm(manifest: PluginManifest, label: str) -> bool:
        print(f"{manifest.id} {manifest.version} by {manifest.author}, from {label}")
        print(
            f"{Format.yellow}This plugin isn't from the official repository. Use it only if you trust the author.{Format.reset}"
        )
        return assume_yes or _confirm("Install it?", default=False)

    try:
        installed = installer.install(source, root, replace=force, confirm=confirm)
    except installer.InstallCancelled:
        print("Nothing was installed.")
        return 1
    manifest = installed.manifest
    print(f"Installed {manifest.id} {manifest.version} by {manifest.author}.")
    if installed.source in ("local", "zip"):
        print(
            f"{Format.yellow}This plugin isn't from the official repository. Use it only if you trust the author.{Format.reset}"
        )
    if _widgets_using(manifest.id):
        print("Run `yasbc reload` to load it.")
    return 0


def cmd_list(root: Path) -> int:
    plugins = installer.installed_plugins(root)
    if not plugins:
        print(f"No plugins installed in {root}")
        return 0
    width = max(len(plugin_id) for plugin_id in plugins)
    for plugin_id, plugin in plugins.items():
        if plugin.manifest is None:
            print(f"{plugin_id:<{width}}  skipped: it {plugin.error}")
            continue
        record = installer.read_install_record(plugin.directory)
        origins = {"official": "official repository", "github": str(record.get("url", "GitHub"))}
        origin = origins.get(str(record.get("source")), f"local: {record.get('path', '?')}")
        print(f"{plugin_id:<{width}}  {plugin.manifest.version:<10}  {origin}")
    return 0


def cmd_remove(root: Path, plugin_id: str, purge: bool, assume_yes: bool) -> int:
    if not assume_yes and not _confirm(f'Uninstall plugin "{plugin_id}"?'):
        print("Nothing was changed.")
        return 1
    installer.remove(plugin_id, root, purge_data=purge)
    print(f"Removed {plugin_id}.")
    if names := _widgets_using(plugin_id):
        them = "it" if len(names) == 1 else "them"
        print(
            f"{DEFAULT_CONFIG_FILENAME} still uses it ({', '.join(names)}). Remove {them} there, or YASB will show an error."
        )
    return 0


def cmd_update(root: Path, plugin_id: str | None) -> int:
    plugins = installer.installed_plugins(root)
    targets = [plugin_id] if plugin_id else list(plugins)
    if not targets:
        print(f"No plugins installed in {root}")
        return 0
    needs_index = any(target in plugins and installer.is_official(plugins[target].directory) for target in targets)
    index = installer.fetch_index() if needs_index else installer.PluginIndex()
    failures = 0
    for target in targets:
        try:
            outcome, _ = installer.update(target, root, index)
        except PluginError as e:
            failures += 1
            outcome = f"failed: {e}"
        print(f"{target}: {outcome}")
    return 1 if failures else 0


def cmd_search(query: str) -> int:
    index = installer.fetch_index()
    words = query.lower().split()
    matches = {
        plugin_id: entry
        for plugin_id, entry in sorted(index.plugins.items())
        if all(word in f"{plugin_id} {entry.name} {entry.author} {entry.description}".lower() for word in words)
    }
    if not matches:
        print("No plugins found.")
        return 0
    for plugin_id, entry in matches.items():
        disabled = "  (temporarily disabled)" if entry.disabled else ""
        print(f"{plugin_id}  {entry.version}  by {entry.author}{disabled}\n    {entry.description or entry.name}")
    print("\nInstall one with `yasbc plugin install <name>`.")
    return 0


def cmd_path(root: Path) -> int:
    print(root)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yasbc plugin", description="Install and manage widget plugins.")
    commands = parser.add_subparsers(dest="action", metavar="<command>", title="commands")

    install = commands.add_parser("install", help="Install a plugin")
    install.add_argument(
        "source",
        help='A plugin name from the official repository, like "lyrics", github.com/owner/repo, or a folder or .zip',
    )
    install.add_argument("-f", "--force", action="store_true", help="Replace the plugin if it is already installed")
    install.add_argument("-y", "--yes", action="store_true", help="Don't ask before installing a plugin from GitHub")

    commands.add_parser("list", help="List installed plugins")

    remove = commands.add_parser("remove", help="Uninstall a plugin")
    remove.add_argument("plugin", help="Plugin name")
    remove.add_argument("--purge", action="store_true", help="Also delete the data the plugin saved")
    remove.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation")

    update = commands.add_parser("update", help="Update plugins from the official repository or GitHub")
    update.add_argument("plugin", nargs="?", help="Only this plugin")

    search = commands.add_parser("search", help="Search the official plugin repository")
    search.add_argument("query", nargs="?", default="", help="Words to look for in the name, author or description")

    commands.add_parser("path", help="Print the plugins folder")
    return parser


def run(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = _parser()
    args = parser.parse_args(argv)
    if args.action is None:
        parser.print_help()
        return 0

    root = plugins_dir()
    actions: dict[str, Callable[[argparse.Namespace], int]] = {
        "install": lambda a: cmd_install(root, a.source, a.force, a.yes),
        "list": lambda a: cmd_list(root),
        "remove": lambda a: cmd_remove(root, a.plugin, a.purge, a.yes),
        "update": lambda a: cmd_update(root, a.plugin),
        "search": lambda a: cmd_search(a.query),
        "path": lambda a: cmd_path(root),
    }
    try:
        action = actions.get(args.action)
        return action(args) if action else 0
    except (PluginError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 1

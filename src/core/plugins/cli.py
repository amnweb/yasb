import argparse
import io
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from core.cli.format import Format
from core.plugins import install as installer
from core.plugins import template
from core.plugins.discovery import plugins_dir
from core.plugins.manifest import (
    DESCRIPTION_MAX_LENGTH,
    PluginError,
    PluginManifest,
    is_plugin_id,
    plugin_id_of,
)
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME


def _confirm(question: str, default: bool = True) -> bool:
    answer = input(f"{question} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def _ask(title: str, explanation: str, check: Callable[[str], str | None] | None = None) -> str:
    print(f"\n{title}\n{explanation}")
    while True:
        if not (answer := input("> ").strip()):
            if sys.stdout.isatty():
                # ANSI: back to the start of the previous line, then clear it
                print("\033[F\033[K", end="", flush=True)
            continue
        if (problem := check(answer) if check else None) is None:
            return answer
        print(f"{Format.red}{problem}{Format.reset}")


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(row[column]) for row in (headers, *rows)) for column in range(len(headers) - 1)]
    room = max(shutil.get_terminal_size().columns - sum(widths) - 2 * len(widths) - 1, 20)
    last_width = min(max(len(row[-1]) for row in (headers, *rows)), room)

    def line(row: list[str]) -> str:
        *cells, last = row
        last = last if len(last) <= room else last[: room - 3] + "..."
        return "  ".join([*(cell.ljust(width) for cell, width in zip(cells, widths, strict=True)), last]).rstrip()

    print(line(headers))
    print("-" * (sum(widths) + 2 * len(widths) + last_width))
    for row in rows:
        print(line(row))


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

    def confirm_replace(manifest: PluginManifest) -> bool:
        print(f'"{manifest.id}" is already installed. This is a different plugin with the same ID.')
        return assume_yes or _confirm("Replace it?", default=False)

    try:
        installed = installer.install(source, root, replace=force, confirm=confirm, confirm_replace=confirm_replace)
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
    rows: list[list[str]] = []
    skipped: list[str] = []
    for plugin_id, plugin in plugins.items():
        if plugin.manifest is None:
            skipped.append(f"{plugin_id} was skipped: it {plugin.error}")
            continue
        record = installer.read_install_record(plugin.directory)
        origins = {"official": "official repository", "github": str(record.get("url", "GitHub"))}
        origin = origins.get(str(record.get("source")), f"local: {record['path']}" if "path" in record else "local")
        rows.append([plugin_id, plugin.manifest.name, plugin.manifest.version, origin])
    if rows:
        _print_table(["ID", "Name", "Version", "Source"], rows)
    for message in skipped:
        print(f"{Format.yellow}{message}{Format.reset}")
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
    rows = [
        [
            plugin_id,
            entry.name,
            f"{entry.version} (disabled)" if entry.disabled else entry.version,
            entry.author,
            entry.description,
        ]
        for plugin_id, entry in matches.items()
    ]
    _print_table(["ID", "Name", "Version", "Author", "Description"], rows)
    print("\nInstall one with `yasbc plugin install <id>`.")
    return 0


def cmd_create(root: Path) -> int:
    def check_id(answer: str) -> str | None:
        if not is_plugin_id(answer) or not answer[0].isalpha():
            return "Use lowercase letters, digits and -, starting with a letter, like now-playing."
        if (root / answer).exists():
            return f"{root / answer} already exists."
        return None

    def check_description(answer: str) -> str | None:
        if len(answer) > DESCRIPTION_MAX_LENGTH:
            return f"Keep it to {DESCRIPTION_MAX_LENGTH} characters, this one has {len(answer)}."
        return None

    print("Create a new YASB plugin. All answers are required.")
    plugin_id = _ask(
        "Plugin ID:",
        "ID Used in `yasbc plugin install <id>`, in config.yaml, and as the folder name.\n"
        "Lowercase letters, digits and -, for example: now-playing",
        check_id,
    )
    name = _ask(
        "Name:",
        "The name people see in `yasbc plugin search` and `yasbc plugin list`.\nFor example: Now Playing",
    )
    author = _ask("Author:", "Your name or GitHub username.")
    description = _ask(
        "Description:",
        f"One sentence about what your widget does, up to {DESCRIPTION_MAX_LENGTH} characters.\n"
        "For example: Shows the song that's playing in Spotify.",
        check_description,
    )
    directory = template.create_plugin(root, plugin_id, name, author, description)
    print(f"\nCreated {plugin_id} in {directory}")
    print(f"Add it to {DEFAULT_CONFIG_FILENAME} as README.md shows, then run `yasbc reload`.")
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
    install.add_argument("-y", "--yes", action="store_true", help="Answer yes to every question")

    commands.add_parser("list", help="List installed plugins")

    remove = commands.add_parser("remove", help="Uninstall a plugin")
    remove.add_argument("plugin", help="Plugin name")
    remove.add_argument("--purge", action="store_true", help="Also delete the data the plugin saved")
    remove.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation")

    update = commands.add_parser("update", help="Update plugins from the official repository or GitHub")
    update.add_argument("plugin", nargs="?", help="Only this plugin")

    search = commands.add_parser("search", help="Search the official plugin repository")
    search.add_argument("query", nargs="?", default="", help="Words to look for in the name, author or description")

    commands.add_parser("create", help="Create a new plugin in the plugins folder, step by step")

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
        "create": lambda a: cmd_create(root),
        "path": lambda a: cmd_path(root),
    }
    try:
        action = actions.get(args.action)
        return action(args) if action else 0
    except (PluginError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt, EOFError:
        print("\nCancelled.", file=sys.stderr)
        return 1

import argparse
import io
import sys
from collections.abc import Callable
from pathlib import Path

from core.plugins import config_edit
from core.plugins import install as installer
from core.plugins.discovery import plugins_dir
from core.plugins.manifest import PluginError, PluginManifest, plugin_widget_type

UNREVIEWED_WARNING = (
    "Warning: this plugin is not from the official plugin repository, so nobody has reviewed its code.\n"
    "It runs with the same access to your PC as YASB. Only use plugins from people you trust.\n"
)


def _confirm(question: str, default: bool = True) -> bool:
    answer = input(f"{question} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def _config_text() -> str | None:
    try:
        return config_edit.config_path().read_text(encoding="utf-8")
    except OSError:
        return None


def _usage_hint(installed: installer.Installed) -> str:
    manifest = installed.manifest
    if manifest.example_config and (example := installed.directory / manifest.example_config).is_file():
        return "Add it to the widgets section of config.yaml, for example:\n\n" + example.read_text(encoding="utf-8")
    types = "\n".join(f"  type: {plugin_widget_type(manifest.id, name)}" for name in manifest.widgets)
    return f"Use it in config.yaml with:\n{types}\n"


def _add_to_config(installed: installer.Installed) -> int:
    path = config_edit.config_path()
    manifest = installed.manifest
    if not path.is_file():
        print(f"There is no {path} yet.")
        print(_usage_hint(installed))
        return 0
    try:
        added = config_edit.edit_config(path, lambda text: config_edit.add_widget(text, manifest, installed.directory))
    except PluginError as e:
        print(f"The plugin is installed, but config.yaml was not changed: {e}", file=sys.stderr)
        print(_usage_hint(installed))
        return 1
    if added is None:
        names = ", ".join(config_edit.plugin_widget_names(path.read_text(encoding="utf-8"), manifest.id))
        print(f"config.yaml already uses this plugin ({names}), so it was left as it is.")
        return 0
    if added.bar is None:
        print(f'Added the widget "{added.name}" to {path}. Put "{added.name}" on a bar to show it.')
    else:
        print(f'Added the widget "{added.name}" to {path}, first on the left of bar "{added.bar}".')
        print("Move it anywhere you like in config.yaml.")
    others = [plugin_widget_type(manifest.id, name) for name in manifest.widgets]
    others = [widget_type for widget_type in others if widget_type != added.widget_type]
    if others:
        print(f"The plugin also provides: {', '.join(others)}")
    print(f"The previous config is saved as {path.name}.bak.")
    return 0


def cmd_install(root: Path, source: str, force: bool, keep_config: bool, assume_yes: bool) -> int:
    def confirm(manifest: PluginManifest, label: str) -> bool:
        print(f"{manifest.id} {manifest.version} by {manifest.author}, from {label}\n")
        print(UNREVIEWED_WARNING)
        return assume_yes or _confirm("Install it?", default=False)

    try:
        installed = installer.install(source, root, replace=force, confirm=confirm)
    except installer.InstallCancelled:
        print("Nothing was installed.")
        return 1
    manifest = installed.manifest
    print(f"Installed {manifest.id} {manifest.version} by {manifest.author} to {installed.directory}\n")
    if installed.source in ("local", "zip"):
        print(UNREVIEWED_WARNING)
    if keep_config:
        print(_usage_hint(installed))
        status = 0
    else:
        status = _add_to_config(installed)
    print("Run `yasbc reload` if YASB doesn't reload on its own.")
    return status


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


def cmd_remove(root: Path, plugin_id: str, purge: bool, assume_yes: bool, keep_config: bool) -> int:
    text = None if keep_config else _config_text()
    names = config_edit.plugin_widget_names(text, plugin_id) if text else []
    from_config = f" and remove {', '.join(names)} from config.yaml" if names else ""
    if not assume_yes and not _confirm(f'Uninstall plugin "{plugin_id}"{from_config}?'):
        print("Nothing was changed.")
        return 1
    directory = installer.remove(plugin_id, root, purge_data=purge)
    print(f"Removed {plugin_id} from {directory}.")
    if names:
        path = config_edit.config_path()
        removed = config_edit.edit_config(path, lambda t: config_edit.remove_plugin_widgets(t, plugin_id))
        print(f"Removed {', '.join(removed)} from {path}. The previous config is saved as {path.name}.bak.")
    print("Run `yasbc reload` if YASB is running.")
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

    install = commands.add_parser("install", help="Install a plugin and add its widget to the left of your bar")
    install.add_argument(
        "source",
        help='A plugin name from the official repository, like "lyrics", github.com/owner/repo, or a folder or .zip',
    )
    install.add_argument("-f", "--force", action="store_true", help="Replace the plugin if it is already installed")
    install.add_argument("--keep-config", action="store_true", help="Don't add the widget to config.yaml")
    install.add_argument("-y", "--yes", action="store_true", help="Don't ask before installing a plugin from GitHub")

    commands.add_parser("list", help="List installed plugins")

    remove = commands.add_parser("remove", help="Uninstall a plugin and take its widgets out of config.yaml")
    remove.add_argument("plugin", help="Plugin name")
    remove.add_argument("--purge", action="store_true", help="Also delete the data the plugin saved")
    remove.add_argument("--keep-config", action="store_true", help="Leave the plugin's widgets in config.yaml")
    remove.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation")

    update = commands.add_parser("update", help="Update plugins from the official repository")
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
        "install": lambda a: cmd_install(root, a.source, a.force, a.keep_config, a.yes),
        "list": lambda a: cmd_list(root),
        "remove": lambda a: cmd_remove(root, a.plugin, a.purge, a.yes, a.keep_config),
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

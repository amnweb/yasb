import sys
import textwrap
import zipfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from core import widget_files
from core.addons import operations
from core.addons.operations import ADDONS_REPOSITORY
from core.addons.settings_copy import settings_copy
from core.widget_files import MANIFEST, builtin_manifests, manifest_problem
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME


def builtin_widgets() -> list[str]:
    return sorted(builtin_manifests(), key=str.lower)


def _named(name: str, widgets: list[str]) -> str | None:
    """The widget of that name, in any case, spelled as on disk."""
    return next((widget for widget in widgets if widget.casefold() == name.casefold()), None)


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


def _row(addon_id: str, kind: str, folder: Path) -> tuple[str, str, str, str, str, str]:
    """The widget's or addon's name, id, type, version, source, and why it no longer fits YASB, if it doesn't."""
    data = operations.read_manifest(folder)
    version = data.get("version") if data else None
    return (
        operations.title(folder, data),
        addon_id,
        kind,
        str(version) if version is not None else "-",
        operations.source(data),
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
        source = widget_files.BUILTIN_WIDGETS_DIR / widget / f"{widget}.qml"
        target = operations.target(widget, "widget")
        settings = None if full else settings_copy(widget, source.read_text(encoding="utf-8"))
        if settings is None and not full:
            print(f"{widget} has no settings. Use --full to install the whole widget.")
            return 1
        if target.exists() and not force:
            print(f"{target} already exists. Use --force to replace it.")
            return 1
        try:
            operations.copy_builtin(widget, settings)
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
            for entry in operations.addons_index().values():
                if not matches(entry["id"], entry["title"], entry["description"], entry["author"], entry["type"]):
                    continue
                version = operations.release(entry)["version"]
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
            entry = operations.addons_index().get(addon_id.casefold())
            if entry is None:
                raise ValueError(f"not in {ADDONS_REPOSITORY}")
            release = operations.release(entry, version)
        except (OSError, ValueError) as e:
            print(f"Could not install {addon_id}: {e}")
            return 1
        title = f"{entry['title']} v{release['version']}"
        unpack = partial(operations.install_release, entry, release)
        return self._install_files(entry["id"], entry["type"], title, unpack, force)

    def _install_from_github(self, link: str, force: bool) -> int:
        repository = link.removesuffix("/").removesuffix(".git")
        try:
            manifest = operations.repository_manifest(repository)
        except (OSError, ValueError) as e:
            print(f"Could not install {repository}: {e}")
            return 1
        title = f"{manifest['title']} v{manifest['version']}"
        unpack = partial(operations.install_repository, repository, manifest)
        warning = _external_warning(repository, manifest)
        return self._install_files(manifest["id"], manifest["type"], title, unpack, force, warning)

    def _install_files(
        self, addon_id: str, kind: str, title: str, unpack: Callable[[Path], None], force: bool, warning: str = ""
    ) -> int:
        """Installs the addon with unpack, which puts its files in a folder, after the user agreed to the warning."""
        is_config = kind == "config"
        target = operations.target(addon_id, kind)
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
            backup = operations.install(addon_id, kind, unpack)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"Could not install {addon_id}: {e}")
            return 1
        if backup is not None:
            print(f"Saved your config to {backup}")
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
        installed = operations.installed()
        if name is not None:
            installed = [addon for addon in installed if addon[0].casefold() == name.casefold()]
            if not installed:
                print(f"No widget, theme, layout or config named '{name}' in {DEFAULT_CONFIG_DIRECTORY}")
                return 1
        found: list[tuple[str, str, Path, dict[str, Any], int]] = []
        failed = False
        for addon_id, kind, folder in installed:
            data = operations.read_manifest(folder)
            if data is None:
                if name is not None:
                    print(f"{addon_id}: no {MANIFEST}, skipped")
                continue
            try:
                newer = operations.newer(folder, data)
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
                (
                    operations.title(folder, data),
                    addon_id,
                    kind,
                    str(data.get("version")),
                    str(version),
                    operations.source(data),
                )
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
                    print(f"{addon_id}: {operations.update(folder, data)}")
                except (OSError, ValueError, zipfile.BadZipFile) as e:
                    print(f"{addon_id}: could not update: {e}")
                    failed = True
        return 1 if failed else 0

    def list(self) -> int:
        rows = [_row(addon_id, kind, folder) for addon_id, kind, folder in operations.installed()]
        if not rows:
            print(f"No widgets, themes or layouts in {DEFAULT_CONFIG_DIRECTORY}")
            return 0
        headers = ("Name", "Id", "Type", "Version", "Source", "Warning")
        # The warning column only when a widget has one
        width = len(headers) if any(row[-1] for row in rows) else len(headers) - 1
        _print_table(headers[:width], [row[:width] for row in rows])
        return 0

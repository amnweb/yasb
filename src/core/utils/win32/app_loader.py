import os
from collections.abc import Callable

from core.utils.icons.sources import AppIcon, FileIcon, IconSource
from core.utils.win32.bindings.shell32 import read_shortcut

# (name, path, description) - path is a file, "UWP::<appid>" or "CPL::<clsid>::<canonical name>".
type AppEntry = tuple[str, str, str | None]


def app_icon_source(path: str) -> IconSource:
    """What the icon of an app entry's path is taken from."""
    if path.startswith("UWP::"):
        return AppIcon(path[5:])
    if path.startswith("CPL::"):
        clsid = path[5:].split("::", 1)[0]
        return FileIcon(f"shell:::{clsid}")
    return FileIcon(path)


class ShortcutResolver:
    @staticmethod
    def resolve_lnk_target(
        lnk_path: str, warning_callback: Callable[[str], object] | None = None
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Resolve the launch command and display name from a .lnk file.
        If warning_callback is provided, it will be called with an error message on failure.
        Returns (full_command, app_name) or (None, None) on error.
        """
        shortcut = read_shortcut(lnk_path)
        if shortcut is None:
            if warning_callback:
                warning_callback(f"Failed to resolve shortcut: {lnk_path}")
            return None, None
        app_name = os.path.splitext(os.path.basename(lnk_path))[0]
        # Combine target and arguments for the real launch command
        if shortcut.arguments:
            return f'"{shortcut.target}" {shortcut.arguments}', app_name
        return shortcut.target, app_name

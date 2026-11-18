"""What Start lists: All apps, the Start menu shortcut files and the Control Panel items."""

import glob
import logging
import os
import winreg
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_dispatch
from core.utils.win32.bindings.shlwapi import SHLoadIndirectString
from core.utils.win32.registry_keys import CLSID_KEY, CONTROL_PANEL_NAMESPACE_KEY

# Start's All apps
APPS_FOLDER = "shell:::{4234d49b-0245-4df3-b780-3893943456e1}"
# The user's Start menu and every user's
START_MENUS = (r"%APPDATA%\Microsoft\Windows\Start Menu", r"%PROGRAMDATA%\Microsoft\Windows\Start Menu")


@dataclass(frozen=True)
class StartApp:
    """An entry of All apps."""

    # Family!App for a Store app, else an app id or a path; shell:AppsFolder\<id> opens it
    id: str
    name: str
    # The program a desktop entry's shortcut starts and its arguments; empty for a Store app
    target: str
    arguments: str


@dataclass(frozen=True)
class Shortcut:
    """A .lnk or .url file in a Start menu, named after the file."""

    name: str
    path: str


@dataclass(frozen=True)
class ControlPanelItem:
    name: str
    clsid: str
    # Its System.ApplicationName, which control.exe /name opens
    canonical: str
    description: str | None


def read_start_apps() -> tuple[list[StartApp], list[Shortcut], list[ControlPanelItem]]:
    """All apps A to Z, the Start menus' shortcut files and the Control Panel items. A part that cannot be read comes
    back empty."""
    return (
        _or_empty(_read_all_apps, "All apps"),
        _or_empty(_read_shortcuts, "the Start menu shortcuts"),
        _or_empty(_read_control_panel, "the Control Panel items"),
    )


def _or_empty[T](read: Callable[[], list[T]], what: str) -> list[T]:
    try:
        return read()
    except Exception:
        logging.exception("Could not read %s", what)
        return []


def _read_all_apps() -> list[StartApp]:
    initialized = CoInitialize()
    try:
        apps: list[StartApp] = []
        for item in create_dispatch("Shell.Application").NameSpace(APPS_FOLDER).Items():
            app_id = str(item.Path or "")
            store = "!" in app_id
            apps.append(
                StartApp(
                    id=app_id,
                    name=str(item.Name or ""),
                    target="" if store else str(item.ExtendedProperty("System.Link.TargetParsingPath") or ""),
                    arguments="" if store else str(item.ExtendedProperty("System.Link.Arguments") or ""),
                )
            )
    finally:
        if initialized >= 0:
            CoUninitialize()
    return sorted(apps, key=lambda app: app.name.casefold())


def _read_shortcuts() -> list[Shortcut]:
    shortcuts: list[Shortcut] = []
    for menu in START_MENUS:
        folder = os.path.expandvars(menu)
        for pattern in ("*.lnk", "*.url"):
            for path in glob.glob(os.path.join(folder, "**", pattern), recursive=True):
                shortcuts.append(Shortcut(os.path.splitext(os.path.basename(path))[0], path))
    return shortcuts


def _read_control_panel() -> list[ControlPanelItem]:
    items: list[ControlPanelItem] = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CONTROL_PANEL_NAMESPACE_KEY) as namespace:
        index = 0
        while True:
            try:
                clsid = winreg.EnumKey(namespace, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{CLSID_KEY}\\{clsid}") as key:
                    canonical = _value(key, "System.ApplicationName")
                    if not canonical:
                        continue
                    name = _text(key, "LocalizedString") or _value(key, "")
                    if not name or name.startswith("@"):
                        continue
                    items.append(ControlPanelItem(name, clsid, canonical, _text(key, "InfoTip")))
            except OSError:
                continue
    return items


def _value(key: winreg.HKEYType, name: str) -> Any:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _text(key: winreg.HKEYType, name: str) -> str | None:
    """A registry string, with an @resource reference resolved."""
    raw = _value(key, name)
    if not raw:
        return None
    return SHLoadIndirectString(raw) if raw.startswith("@") else raw

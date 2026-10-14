"""Where each icon comes from.

Window: its own icon if it's big enough, else its app's icon, else its class icon.
Process: its app's icon, else one of its windows' icons.
App: the icon shell:AppsFolder shows for the AUMID. For a window or process only Store apps go this way, the rest
use their exe.
File: the icon inside the file (exe, dll, cpl, ico), or the one a shortcut, .msc or Control Panel item points to;
anything else gets the shell's icon.

Files keep one picture per size. Like LoadIconWithScaleDown we take the exact size, else the next bigger one, else
the biggest.
"""

import os
import re
from dataclasses import dataclass
from typing import Protocol, cast

import pythoncom
import pywintypes
from PIL import Image
from win32comext.shell import shell, shellcon

from core.utils.icons.extract import (
    get_class_icons,
    get_default_app_icon,
    get_ico_icon,
    get_own_icon,
    get_resource_icon,
    get_shell_icon,
)
from core.utils.win32.aumid import get_aumid_for_process, get_aumid_for_window
from core.utils.win32.utils import get_process_info, get_process_path, get_process_window

# BHID_SFUIObject, to get a shell item's IExtractIcon
BHID_SFUIOBJECT = pywintypes.IID("{3981E225-F559-11D3-8E3A-00C04F6837D5}")


# pywin32's COM objects are untyped, these tell pyright what we call on them. Delete with pywin32 later.
class _PersistFile(Protocol):
    def Load(self, filename: str, /) -> None: ...


class _ShellLink(Protocol):
    def QueryInterface(self, iid: object, /) -> _PersistFile: ...
    def GetIconLocation(self) -> tuple[str, int]: ...
    def GetPath(self, flags: int, /) -> tuple[str, object]: ...


class _ExtractIcon(Protocol):
    def GetIconLocation(self, flags: int, /) -> tuple[int, str, int, int]: ...


class _ShellItem(Protocol):
    def BindToHandler(self, bind_context: object, handler: object, iid: object, /) -> _ExtractIcon: ...


@dataclass(frozen=True)
class WindowIcon:
    hwnd: int


@dataclass(frozen=True)
class ProcessIcon:
    pid: int


@dataclass(frozen=True)
class AppIcon:
    # App User Model ID
    aumid: str


@dataclass(frozen=True)
class FileIcon:
    # file, folder, shortcut, or a shell name like shell:::{CLSID}
    path: str


type IconSource = WindowIcon | ProcessIcon | AppIcon | FileIcon


@dataclass
class LoadedIcon:
    image: Image.Image | None
    # False if the window didn't answer in time, it's asked again later
    complete: bool = True


def load_icon(source: IconSource, size: int) -> LoadedIcon:
    """The icon of source for size px (real pixels). Waits for Windows; widgets use IconService instead."""
    match source:
        case WindowIcon(hwnd):
            return _window_icon(hwnd, size)
        case ProcessIcon(pid):
            return LoadedIcon(_process_icon(pid, size) or get_default_app_icon())
        case AppIcon(aumid):
            return LoadedIcon(_store_app_icon(aumid, size) or get_default_app_icon())
        case FileIcon(path):
            return LoadedIcon(_file_icon(path, size) or get_default_app_icon())


def _window_icon(hwnd: int, size: int) -> LoadedIcon:
    own_icon, answered = get_own_icon(hwnd)
    image = own_icon if own_icon is not None and own_icon.width >= size else None
    if image is None:
        image = _app_icon(get_aumid_for_window(hwnd), get_process_info(hwnd)["path"], size)
    if image is None:
        image = max(get_class_icons(hwnd), key=lambda picture: picture.width, default=None)
    return LoadedIcon(image or get_default_app_icon(), answered)


def _process_icon(pid: int, size: int) -> Image.Image | None:
    image = _app_icon(get_aumid_for_process(pid), get_process_path(pid), size)
    if image is None:
        # elevated processes can't be opened, but their windows still answer
        hwnd = get_process_window(pid)
        image = _window_icon(hwnd, size).image if hwnd else None
    return image


def _app_icon(aumid: str | None, exe: str | None, size: int) -> Image.Image | None:
    # only Store app IDs (Family!App) give the real icon, their exe has a generic one
    if aumid and "!" in aumid:
        image = _store_app_icon(aumid, size)
        if image is not None:
            return image
    return _file_icon(exe, size) if exe else None


def _store_app_icon(aumid: str, size: int) -> Image.Image | None:
    return get_shell_icon(f"shell:AppsFolder\\{aumid}", size)


def _file_icon(path: str, size: int) -> Image.Image | None:
    icon_file, index = _icon_location(path)
    # the shell frames exe/ico icons that have no 256 px picture, so read the file ourselves
    if os.path.isfile(icon_file):
        if icon_file.lower().endswith(".ico"):
            image = get_ico_icon(icon_file, size)
        else:
            image = get_resource_icon(icon_file, index, size)
        if image is not None:
            return image
    return get_shell_icon(path, size)


def _icon_location(path: str) -> tuple[str, int]:
    """The file and index of the icon a file shows. A negative index is a resource ID, as in Windows icon locations."""
    extension = os.path.splitext(path)[1].lower()
    if extension == ".lnk":
        return _shortcut_icon_location(path)
    if extension == ".msc":
        return _console_icon_location(path)
    if path.startswith(("shell:::", "::")):
        return _shell_item_icon_location(path)
    return path, 0


def _shortcut_icon_location(path: str) -> tuple[str, int]:
    """The icon set in a shortcut, else its target's."""
    try:
        link = cast(
            _ShellLink,
            pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
            ),
        )
        link.QueryInterface(pythoncom.IID_IPersistFile).Load(path)
        icon_file, index = link.GetIconLocation()
        if icon_file:
            return os.path.expandvars(icon_file), index
        target = link.GetPath(0)[0]
    except Exception:
        return path, 0
    return (target, 0) if target else (path, 0)


def _console_icon_location(path: str) -> tuple[str, int]:
    """The icon an MMC console names in its <Icon Index="..." File="..."> tag."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as file:
            tag = re.search(r"<Icon\s[^>]*>", file.read())
    except OSError:
        return path, 0
    icon_file = re.search(r'File="([^"]+)"', tag[0]) if tag else None
    index = re.search(r'Index="(-?\d+)"', tag[0]) if tag else None
    if not icon_file:
        return path, 0
    return os.path.expandvars(icon_file[1]), int(index[1]) if index else 0


def _shell_item_icon_location(path: str) -> tuple[str, int]:
    """The icon Explorer shows for a shell item such as a Control Panel item (IExtractIcon::GetIconLocation)."""
    try:
        # pywin32's stub wants a bind context, the API doesn't
        item = cast(
            _ShellItem,
            shell.SHCreateItemFromParsingName(path, None, shell.IID_IShellItem),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
        )
        extract = item.BindToHandler(None, BHID_SFUIOBJECT, shell.IID_IExtractIconW)
        result, icon_file, index, flags = extract.GetIconLocation(shellcon.GIL_FORSHELL)
    except Exception:
        return path, 0
    if result != 0 or flags & shellcon.GIL_NOTFILENAME:
        return path, 0
    return os.path.expandvars(icon_file), index

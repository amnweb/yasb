import logging
import os
from functools import cmp_to_key

import comtypes.client  # pyright: ignore[reportMissingTypeStubs]
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.services.wallpapers import thumbnails
from core.utils.system import get_build_and_ubr
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import CLSID_DesktopWallpaper, IDesktopWallpaper
from core.utils.win32.bindings.shlwapi import StrCmpLogical
from core.utils.win32.bindings.user32 import EnumDisplayDevices, GetMonitorInfo, MonitorFromRect
from core.utils.win32.constants import EDD_GET_DEVICE_INTERFACE_NAME

FILE_TYPES = ("png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff")
WEBP_BUILDS = ((26220, 7653), (26100, 8037))


def supported_types() -> tuple[str, ...]:
    """The extensions this Windows build can use as a wallpaper."""
    build, ubr = get_build_and_ubr()
    if any(build >= least_build and ubr >= least_ubr for least_build, least_ubr in WEBP_BUILDS):
        return FILE_TYPES + ("webp",)
    return FILE_TYPES


def collect_image_files(image_paths: str | list[str]) -> list[str]:
    """Every usable wallpaper under *image_paths*, in name order."""
    if isinstance(image_paths, str):
        image_paths = [image_paths]

    file_types = supported_types()
    files: list[str] = []
    for path in image_paths:
        if not os.path.exists(path):
            continue
        for root, _, names in os.walk(path):
            for name in names:
                if name.lower().endswith(file_types):
                    files.append(os.path.join(root, name))

    return sorted(files, key=cmp_to_key(StrCmpLogical))


def current_wallpapers(screens: dict[str, tuple[int, int, int, int]]) -> dict[str, str]:
    """The wallpaper Windows shows on each of *screens*, by screen name."""
    CoInitialize()
    desktop = comtypes.client.CreateObject(CLSID_DesktopWallpaper, interface=IDesktopWallpaper)
    wallpapers: dict[str, str] = {}
    for name, rect in screens.items():
        try:
            info = GetMonitorInfo(MonitorFromRect(rect) or 0)
            # The monitor's device interface path is the monitor ID IDesktopWallpaper takes.
            device = EnumDisplayDevices(info.szDevice, 0, EDD_GET_DEVICE_INTERFACE_NAME) if info else None
            if device is None:
                logging.debug("Could not find the monitor of %s", name)
                continue
            wallpapers[name] = desktop.GetWallpaper(device.DeviceID)
        except Exception:
            logging.debug("Could not read the wallpaper on %s", name, exc_info=True)
    return wallpapers


def find_wallpapers(files: list[str], wallpapers: dict[str, str]) -> dict[str, int]:
    """Where each screen's wallpaper sits in *files*, by screen name."""
    wanted: dict[str, list[str]] = {}
    for name, path in wallpapers.items():
        if path:
            wanted.setdefault(os.path.normcase(os.path.normpath(path)), []).append(name)

    found: dict[str, int] = {}
    for index, file in enumerate(files):
        if not wanted:
            break
        for name in wanted.pop(os.path.normcase(os.path.normpath(file)), ()):
            found[name] = index
    return found


class ScanSignals(QObject):
    finished = pyqtSignal(list, dict)


class FolderScanner(QRunnable):
    """Walks the wallpaper folders off the GUI thread and finds each screen's wallpaper in them."""

    def __init__(self, image_paths: str | list[str], screens: dict[str, tuple[int, int, int, int]]):
        super().__init__()
        self.image_paths = image_paths
        self.screens = screens
        self.signals = ScanSignals()

    def run(self):
        try:
            files = collect_image_files(self.image_paths)
        except Exception:
            logging.exception("Failed to scan wallpaper folders")
            files = []

        current: dict[str, int] = {}
        if files:
            try:
                current = find_wallpapers(files, current_wallpapers(self.screens))
            except Exception:
                logging.debug("Could not read the current wallpapers", exc_info=True)
        self.signals.finished.emit(files, current)
        thumbnails.prune()

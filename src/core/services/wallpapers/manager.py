import logging
import os
from functools import partial
from typing import Any

import comtypes.client  # pyright: ignore[reportMissingTypeStubs]

from core.services.wallpapers.engine import WallpaperEngine
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import CLSID_DesktopWallpaper, IDesktopWallpaper


def _desktop_wallpaper() -> Any:
    CoInitialize()
    return comtypes.client.CreateObject(CLSID_DesktopWallpaper, interface=IDesktopWallpaper)


class WallpaperManager:
    """Sets the desktop wallpaper, after the YASB transition when one is asked for. One transition plays at a time."""

    _engine: WallpaperEngine | None = None

    @classmethod
    def monitor_ids(cls) -> list[str]:
        """The monitor IDs Windows takes for a wallpaper on one screen, in its own order."""
        try:
            desktop = _desktop_wallpaper()
            return [desktop.GetMonitorDevicePathAt(index) for index in range(desktop.GetMonitorDevicePathCount())]
        except Exception:
            logging.exception("Failed to list the monitors for wallpapers")
            return []

    @classmethod
    def transition_playing(cls) -> bool:
        return cls._engine is not None

    @classmethod
    def set_wallpaper(cls, image_path: str, monitor_id: str | None = None, animation: str = "") -> bool:
        """Sets *image_path* on *monitor_id*, or on every screen after the transition *animation* when there is one.

        False when a transition is still playing and the request is dropped.
        """
        if animation and monitor_id is None:
            if cls._engine is not None:
                logging.info("A wallpaper transition is still playing, %s is not set", image_path)
                return False
            try:
                engine = WallpaperEngine(image_path, animation)
            except Exception:
                logging.exception("Wallpaper engine failed, setting the wallpaper without it")
            else:
                cls._engine = engine
                engine.finished.connect(partial(cls._after_transition, image_path))
                engine.start()
                return True
        cls._apply(image_path, monitor_id)
        return True

    @classmethod
    def _after_transition(cls, image_path: str) -> None:
        cls._engine = None
        cls._apply(image_path, None)

    @classmethod
    def _apply(cls, image_path: str, monitor_id: str | None) -> None:
        try:
            _desktop_wallpaper().SetWallpaper(monitor_id, os.path.abspath(image_path))
        except Exception:
            logging.exception("Failed to set the wallpaper %s", image_path)

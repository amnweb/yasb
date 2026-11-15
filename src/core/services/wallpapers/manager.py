import logging
import os
import time
from typing import Any

import comtypes.client
from PyQt6.QtCore import pyqtBoundSignal

from core.services.wallpapers.engine import WallpaperEngine
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import CLSID_DesktopWallpaper, IDesktopWallpaper


def _desktop_wallpaper() -> Any:
    CoInitialize()
    return comtypes.client.CreateObject(CLSID_DesktopWallpaper, interface=IDesktopWallpaper)


class WallpaperManager:
    """Sets the desktop wallpaper, after the YASB transition when one is asked for. One transition at a time: its window
    stays on the desktop until Windows destroys it, putting the wallpaper up, and no other wallpaper is set until then.
    """

    # The transition on the desktop, until its window is gone
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
    def set_wallpaper(
        cls,
        image_path: str,
        monitor_id: str | None = None,
        animation: str = "",
        announce: pyqtBoundSignal | None = None,
    ) -> bool:
        """Sets *image_path* on *monitor_id*, or on every screen after the transition *animation* when there is one,
        then, once Windows took it, emits *announce* with the path.

        False when a transition is still on the desktop, and nothing is set: Windows would destroy the next transition
        with the window it is about to destroy.
        """
        if cls._engine is not None:
            logging.info("A wallpaper transition is still on the desktop, %s is not set", image_path)
            return False
        if animation and monitor_id is None:
            try:
                engine = WallpaperEngine(image_path, animation, cls._shown_wallpaper())
            except Exception:
                logging.exception("Wallpaper engine failed, setting the wallpaper without it")
            else:
                cls._engine = engine
                engine.finished.connect(cls._after_transition)
                if announce is not None:
                    # Connected, so Qt drops it if the one asking is gone before the transition ends
                    engine.wallpaperSet.connect(announce)
                engine.closed.connect(cls._on_closed)
                engine.start()
                return True
        if cls._apply(image_path, monitor_id) and announce is not None:
            announce.emit(image_path)
        return True

    @classmethod
    def _shown_wallpaper(cls) -> str:
        """The wallpaper Windows was last given for every screen, or "" when the screens show different ones."""
        try:
            return _desktop_wallpaper().GetWallpaper(None)
        except Exception:
            logging.debug("Could not read the wallpaper Windows shows", exc_info=True)
            return ""

    @classmethod
    def _after_transition(cls, image_path: str) -> None:
        engine = cls._engine
        assert engine is not None
        if cls._apply(image_path, None):
            engine.wallpaperSet.emit(image_path)
        else:
            # Windows has no new wallpaper to put up, so it would never destroy the window
            engine.close()

    @classmethod
    def _on_closed(cls) -> None:
        cls._engine = None

    @classmethod
    def _apply(cls, image_path: str, monitor_id: str | None) -> bool:
        start = time.perf_counter()
        try:
            _desktop_wallpaper().SetWallpaper(monitor_id, os.path.abspath(image_path))
        except Exception:
            logging.exception("Failed to set the wallpaper %s", image_path)
            return False
        logging.debug("SetWallpaper of %s took %.0f ms", image_path, (time.perf_counter() - start) * 1000)
        return True

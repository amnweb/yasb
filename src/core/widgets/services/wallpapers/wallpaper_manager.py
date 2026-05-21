import logging
import os
import random
import subprocess
import threading

import comtypes.client
import pythoncom
from comtypes import GUID
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.events.service import EventService
from core.utils.win32.bindings.shell32 import IDesktopWallpaper
from core.widgets.services.wallpapers.wallpaper_engine import WallpaperEngine


class WallpaperManager(QObject):
    _instance = None
    toggle_gallery_signal = pyqtSignal(str)
    _set_wallpaper_signal = pyqtSignal(str)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True

        self._image_path = None
        self._run_after = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._timer_callback)
        self._is_running = False
        self._last_image = None
        self._timer_running = False
        self._engine_config = None
        self._engine = None

        self._event_service = EventService()

        # Register Set Wallpaper handler
        self._set_wallpaper_signal.connect(self.change_background)
        self._event_service.register_event("set_wallpaper_signal", self._set_wallpaper_signal)

    def configure(
        self,
        image_path: str | list[str],
        update_interval: int,
        change_automatically: bool,
        run_after: list[str],
        engine=None,
    ):
        """
        Configure the manager.
        """
        if isinstance(image_path, str):
            self._image_paths = [image_path]
        else:
            self._image_paths = image_path

        self._run_after = run_after
        self._engine_config = engine

        if change_automatically and not self._timer_running:
            if update_interval and update_interval > 0:
                self._timer.start(int(update_interval * 1000))
                self._timer_running = True
        elif not change_automatically and self._timer_running:
            self._timer.stop()
            self._timer_running = False

    def _timer_callback(self):
        self.change_background()

    def set_wallpaper(self, image_path: str, monitor_id: str | None = None, animate: bool = True):
        """Set the desktop wallpaper, using the YASB engine animation when enabled."""
        eng = self._engine_config
        if animate and monitor_id is None and eng and eng.enabled:
            try:
                self._engine = WallpaperEngine(image_path, eng.animation)
                self._engine.finished.connect(lambda: self.set_wallpaper(image_path, animate=False))
                self._engine.start()
                return
            except Exception as e:
                logging.error("Wallpaper engine failed, falling back: %s", e)

        pythoncom.CoInitialize()
        try:
            clsid = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")
            dwp = comtypes.client.CreateObject(clsid, interface=IDesktopWallpaper)
            dwp.SetWallpaper(monitor_id, os.path.abspath(image_path))
        except Exception as e:
            logging.error("Failed to set wallpaper: %s", e)
            self._is_running = False
            return
        self._run_after_thread(image_path)

    def get_monitor_ids(self) -> list[str]:
        """Return COM monitor device paths for all connected monitors."""
        pythoncom.CoInitialize()
        try:
            clsid = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")
            dwp = comtypes.client.CreateObject(clsid, interface=IDesktopWallpaper)
            count = dwp.GetMonitorDevicePathCount()
            return [dwp.GetMonitorDevicePathAt(i) for i in range(count)]
        except Exception as e:
            logging.error("Failed to enumerate monitors: %s", e)
            return []

    def change_background(self, image_path: str = None):
        """Change the desktop wallpaper to a new image."""
        if self._is_running:
            return

        if not self._image_paths:
            logging.error("No image paths configured")
            return

        self._is_running = True

        wallpapers = []
        for path in self._image_paths:
            if not os.path.exists(path):
                logging.warning("Invalid image path: %s", path)
                continue

            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                        wallpapers.append(os.path.join(root, f))

        if not wallpapers:
            logging.warning("No wallpapers found in %s", self._image_paths)
            self._is_running = False
            return

        if image_path:
            new_wallpaper = image_path
        else:
            """Randomly select a new wallpaper and prevent the same wallpaper from being selected """
            new_wallpaper = random.choice(wallpapers)
            while new_wallpaper == self._last_image and len(wallpapers) > 1:
                new_wallpaper = random.choice(wallpapers)

        try:
            self.set_wallpaper(new_wallpaper)
            self._last_image = new_wallpaper
        except Exception as e:
            logging.error("Error setting wallpaper %s: %s", new_wallpaper, e)
            self._is_running = False

    def _run_after_thread(self, image_path: str):
        if self._run_after:
            threading.Thread(target=self._run_after_command, args=(image_path,)).start()
        else:
            self._is_running = False

    def _run_after_command(self, new_wallpaper):
        """Run post-change commands after setting the wallpaper."""
        if self._run_after:
            for command in self._run_after:
                formatted_command = command.replace("{image}", f'"{new_wallpaper}"')
                logging.debug("Running command: %s", formatted_command)
                result = subprocess.run(
                    formatted_command, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                if result.stderr:
                    logging.error("error: %s", result.stderr)

        self._is_running = False

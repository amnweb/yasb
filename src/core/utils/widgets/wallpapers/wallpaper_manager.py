import logging
import os
import random
import subprocess
import threading

import comtypes.client
import pythoncom
from comtypes import GUID
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.event_service import EventService
from core.utils.win32.bindings.shell32 import IDesktopWallpaper
from settings import DEBUG


class WallpaperManager(QObject):
    _instance = None
    toggle_gallery_signal = pyqtSignal(str)
    _handle_widget_cli = pyqtSignal(str, str)
    _set_wallpaper_signal = pyqtSignal(str)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WallpaperManager, cls).__new__(cls)
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

        self._event_service = EventService()

        # Register CLI handler
        self._handle_widget_cli.connect(self._on_handle_widget_cli)
        self._event_service.register_event("handle_widget_cli", self._handle_widget_cli)

        # Register Set Wallpaper handler
        self._set_wallpaper_signal.connect(self.change_background)
        self._event_service.register_event("set_wallpaper_signal", self._set_wallpaper_signal)

    def configure(
        self, image_path: str | list[str], update_interval: int, change_automatically: bool, run_after: list[str]
    ):
        """
        Configure the manager.
        """
        if isinstance(image_path, str):
            self._image_paths = [image_path]
        else:
            self._image_paths = image_path

        self._run_after = run_after

        if change_automatically and not self._timer_running:
            if update_interval and update_interval > 0:
                self._timer.start(int(update_interval * 1000))
                self._timer_running = True
        elif not change_automatically and self._timer_running:
            self._timer.stop()
            self._timer_running = False

    def _timer_callback(self):
        self.change_background()

    def _on_handle_widget_cli(self, widget: str, screen: str):
        if widget == "wallpapers":
            self.toggle_gallery_signal.emit(screen)

    def set_wallpaper(self, image_path: str):
        """
        Set the desktop wallpaper using the IDesktopWallpaper COM interface.
        Args:
            image_path: Absolute path to the wallpaper image file
        """
        pythoncom.CoInitialize()
        try:
            # Create IDesktopWallpaper COM object
            # CLSID: {C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}
            desktop_wallpaper_clsid = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")
            desktop_wallpaper = comtypes.client.CreateObject(desktop_wallpaper_clsid, interface=IDesktopWallpaper)

            # Convert to absolute path
            abs_path = os.path.abspath(image_path)

            # Set wallpaper for all monitors (None = all monitors)
            desktop_wallpaper.SetWallpaper(None, abs_path)

        except Exception as e:
            logging.error("Failed to set wallpaper using IDesktopWallpaper: %s", e)
            raise

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
                logging.warning(f"Invalid image path: {path}")
                continue

            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                        wallpapers.append(os.path.join(root, f))

        if not wallpapers:
            logging.warning(f"No wallpapers found in {self._image_paths}")
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
            logging.error(f"Error setting wallpaper {new_wallpaper}: {e}")

        if self._run_after:
            threading.Thread(target=self._run_after_command, args=(new_wallpaper,)).start()
        else:
            self._is_running = False

    def _run_after_command(self, new_wallpaper):
        """Run post-change commands after setting the wallpaper."""
        if self._run_after:
            for command in self._run_after:
                formatted_command = command.replace("{image}", f'"{new_wallpaper}"')
                if DEBUG:
                    logging.debug(f"Running command: {formatted_command}")
                result = subprocess.run(formatted_command, shell=True, capture_output=True, text=True)
                if result.stderr:
                    logging.error(f"error: {result.stderr}")

        self._is_running = False

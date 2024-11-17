import os
import subprocess
import ctypes
import random
import re
import logging
import subprocess
import pythoncom
import pywintypes
import pathlib
import psutil
from itertools import chain
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.wallpapers import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from typing import List
import win32gui
from win32comext.shell import shell, shellcon
from settings import DEBUG
import threading
from core.event_service import EventService
from core.utils.widgets.wallpapers_gallery import ImageGallery
from core.utils.alert_dialog import raise_info_alert


class WallpapersWidget(BaseWidget):
    set_wallpaper_signal = pyqtSignal(str)

    user32 = ctypes.windll.user32
    validation_schema = VALIDATION_SCHEMA
    _timer_running = False

    def __init__(
        self,
        label: str,
        update_interval: int,
        change_automatically: bool,
        image_path: str,
        run_after: list[str],
        gallery: dict = None,
        wallpaper_engine: dict = None,
    ):
        """Initialize the WallpapersWidget with configuration parameters."""
        super().__init__(int(update_interval * 1000), class_name="wallpapers-widget")
        self._image_gallery = None

        self._event_service = EventService()
        self._label_content = label
        self._change_automatically = change_automatically
        self._image_path = image_path
        self._run_after = run_after
        self._gallery = gallery
        self._wallpaper_engine = wallpaper_engine

        self._last_image = None
        self._is_running = False

        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content)

        self.set_wallpaper_signal.connect(self.change_background)
        self._event_service.register_event(
            "set_wallpaper_signal", self.set_wallpaper_signal
        )

        self.register_callback("change_background", self.change_background)
        self.register_callback(
            "change_background_we", self.change_background_wallpaper_engine
        )

        if self._wallpaper_engine:
            self.callback_timer = "change_background_we"
        else:
            self.callback_timer = "change_background"

        if self._change_automatically:
            self.start_timer()

    def start_timer(self):
        """Start the timer for automatic wallpaper changes."""
        if not self._timer_running:
            if self.timer_interval and self.timer_interval > 0:
                self.timer.timeout.connect(self._timer_callback)
                self.timer.start(self.timer_interval)
                self._timer_running = True

    def _create_dynamically_label(self, content: str):
        """Create labels dynamically based on the provided content."""

        def process_content(content, is_alt=False):
            label_parts = re.split("(<span.*?>.*?</span>)", content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.setToolTip(f"Change Wallaper")
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                    label.setToolTip(f"Change Wallaper")
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                label.mousePressEvent = self.handle_mouse_events

            return widgets

        self._widgets = process_content(content)

    def _update_label(self):
        """Update the label content dynamically."""
        active_widgets = self._widgets
        active_label_content = self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if part:
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1

    def _make_filter(self, class_name: str, title: str):
        """
        Create a filter function for enumerating windows.
        https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows
        """

        def enum_windows(handle: int, h_list: list):
            if not (class_name or title):
                h_list.append(handle)
            if class_name and class_name not in win32gui.GetClassName(handle):
                return True  # continue enumeration
            if title and title not in win32gui.GetWindowText(handle):
                return True  # continue enumeration
            h_list.append(handle)

        return enum_windows

    def find_window_handles(
        self, parent: int = None, window_class: str = None, title: str = None
    ) -> List[int]:
        """Find window handles based on class name and title."""
        cb = self._make_filter(window_class, title)
        try:
            handle_list = []
            if parent:
                win32gui.EnumChildWindows(parent, cb, handle_list)
            else:
                win32gui.EnumWindows(cb, handle_list)
            return handle_list
        except pywintypes.error:
            return []

    def force_refresh(self):
        """Force a system refresh of user parameters."""
        self.user32.UpdatePerUserSystemParameters(1)

    def enable_activedesktop(self):
        """Enable the Active Desktop feature."""
        try:
            progman = self.find_window_handles(window_class="Progman")[0]
            cryptic_params = (0x52C, 0, 0, 0, 500, None)
            self.user32.SendMessageTimeoutW(progman, *cryptic_params)
        except IndexError as e:
            raise WindowsError("Cannot enable Active Desktop") from e

    def set_wallpaper(self, image_path: str, use_activedesktop: bool = True):
        """Set the desktop wallpaper to the specified image."""
        if use_activedesktop:
            self.enable_activedesktop()

        if self._wallpaper_engine:

            self.change_background_wallpaper_engine(str(image_path))

        else:

            pythoncom.CoInitialize()
            iad = pythoncom.CoCreateInstance(
                shell.CLSID_ActiveDesktop,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IActiveDesktop,
            )
            iad.SetWallpaper(str(image_path), 0)
            iad.ApplyChanges(shellcon.AD_APPLY_ALL)
            self.force_refresh()

    def handle_mouse_events(self, event=None):
        """Handle mouse events for changing wallpapers."""

        if not os.path.exists(self._image_path):
            raise_info_alert(
                title=f"Error",
                msg=f"The specified directory does not exist\n{self._image_path}",
                informative_msg=f"Please check the path and set a valid directory in the configuration.",
                rich_text=True,
            )
            return

        if self._gallery["enabled"]:
            if event is None or event.button() == Qt.MouseButton.LeftButton:
                if self._image_gallery is not None and self._image_gallery.isVisible():
                    self._image_gallery.fade_out_and_close_gallery()
                else:
                    if self._wallpaper_engine:
                        wallpaper_engine = self._wallpaper_engine.get(
                            "wallpaper_engine_exe"
                        )
                        running = self.is_wallpaper_engine_running()

                        if not running:
                            try:
                                subprocess.Popen(
                                    f"{wallpaper_engine} -control mute", shell=True
                                )

                            except Exception as e:
                                logging.error(f"Failed to start wallpaper_engine: {e}")

                        self._image_gallery = ImageGallery(
                            self._wallpaper_engine.get("wallpaper_engine_dir"),
                            self._gallery,
                            self._wallpaper_engine,
                        )
                        self._image_gallery.fade_in_gallery()
                    else:
                        self._image_gallery = ImageGallery(
                            self._image_path, self._gallery
                        )
                        self._image_gallery.fade_in_gallery()
            if event is None or event.button() == Qt.MouseButton.RightButton:
                if self._wallpaper_engine:
                    wallpaper_engine = self._wallpaper_engine.get(
                        "wallpaper_engine_exe"
                    )
                    running = self.is_wallpaper_engine_running()

                    if not running:
                        try:
                            subprocess.Popen(
                                f"{wallpaper_engine} -control mute", shell=True
                            )
                        except Exception as e:
                            logging.error(f"Failed to start wallpaper_engine: {e}")

                    self.change_background_wallpaper_engine()
                else:
                    self.change_background()

        else:
            if event is None or event.button() == Qt.MouseButton.LeftButton:
                if self._wallpaper_engine:
                    wallpaper_engine = self._wallpaper_engine.get(
                        "wallpaper_engine_exe"
                    )
                    running = self.is_wallpaper_engine_running()

                    if not running:
                        try:
                            subprocess.Popen(
                                f"{wallpaper_engine} -control mute", shell=True
                            )

                        except Exception as e:
                            logging.error(f"Failed to start wallpaper_engine: {e}")

                    self.change_background_wallpaper_engine()

                else:
                    self.change_background()

    def is_wallpaper_engine_running(self):
        """Checks if wallpaper engine is running."""
        try:
            process_names = [p.name().lower() for p in psutil.process_iter()]
            if "wallpaper64.exe" in process_names or "wallpaper32.exe" in process_names:
                return True
        except Exception as e:
            logging.warning(f"Wallpaper Engine is not running: {e}")
        return False

    def change_background_wallpaper_engine(self, image_path: str = None):
        """Changes the background if wallpaper_engine is running."""

        if self._is_running:
            return

        if image_path:
            wallpaper_engine = self._wallpaper_engine.get("wallpaper_engine_exe")
            dir_str = image_path.replace("preview.jpg", "").replace("preview.gif", "")

            # Error check | Was having issues with getting just directories.
            # Not sure why but adding the dir fixes the issues.
            if not os.path.exists(dir_str):
                wallpaper_dir = self._wallpaper_engine.get("wallpaper_engine_dir")
                dir_str = f"{wallpaper_dir}\\{dir_str}"

            try:
                # find PKG
                pkg = [
                    file
                    for file in os.listdir(dir_str)
                    if file.endswith(("pkg", "mp4"))
                ][0]
                # Remove spaces frpm file names so CLI can fine.
                pkg = f'"{dir_str}\\{pkg}"'

            except Exception as e:
                logging.error(f"Failed to change wallpaper: {dir_str}:{e}")

            change_wall_command = (
                f"{wallpaper_engine} -control openWallpaper -file {pkg}"
            )

            subprocess.Popen(change_wall_command, shell=True)
            subprocess.Popen(f"{wallpaper_engine} -control mute", shell=True)
            self.force_refresh()

            new_wallpaper = image_path

        else:

            image_folder = self._wallpaper_engine.get("wallpaper_engine_dir")
            folders = [folders for folders in os.listdir(image_folder)]
            imgs = []

            for folder in folders:
                path = f"{image_folder}\\{folder}"
                images = chain(
                    pathlib.Path(path).glob("*.jpg"), pathlib.Path(path).glob("*.gif")
                )
                selected_img = [image for image in images]

                if selected_img:
                    # Get the first image in the list and convert it to a string
                    just_img = str(selected_img[0]).rsplit("\\", maxsplit=1)[-1]
                    # Assign the image filename to the folder key in the dictionary
                    imgs.append(f"{folder}\\{just_img}")

            final_list = list([path for path in imgs])
            new_wallpaper = f"{image_folder}\\{random.choice(final_list)}"
            while new_wallpaper == self._last_image and len(final_list) > 1:
                new_wallpaper = random.choice(final_list)

            try:
                self.change_background_wallpaper_engine(new_wallpaper)
                self._last_image = new_wallpaper
            except Exception as e:
                logging.error(f"Error setting wallpaper {new_wallpaper}: {e}")

        if self._run_after:
            threading.Thread(
                target=self.run_after_command, args=(new_wallpaper,)
            ).start()

    def change_background(self, image_path: str = None):
        """Change the desktop wallpaper to a new image."""
        if self._is_running:
            return
        if self._run_after:
            self._is_running = True
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.5)
            self._widget_container.setGraphicsEffect(opacity_effect)

        wallpapers = [
            os.path.join(self._image_path, f)
            for f in os.listdir(self._image_path)
            if f.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
        ]

        if image_path:
            new_wallpaper = image_path
        else:
            """Randomly select a new wallpaper and prevent the same wallpaper from being selected"""
            new_wallpaper = random.choice(wallpapers)
            while new_wallpaper == self._last_image and len(wallpapers) > 1:
                new_wallpaper = random.choice(wallpapers)

        try:
            self.set_wallpaper(new_wallpaper)
            self._last_image = new_wallpaper
        except Exception as e:
            logging.error(f"Error setting wallpaper {new_wallpaper}: {e}")

        if self._run_after:
            threading.Thread(
                target=self.run_after_command, args=(new_wallpaper,)
            ).start()

    def run_after_command(self, new_wallpaper):
        """Run post-change commands after setting the wallpaper."""
        if self._run_after:
            for command in self._run_after:
                formatted_command = command.replace("{image}", f'"{new_wallpaper}"')
                if DEBUG:
                    logging.debug(f"Running command: {formatted_command}")
                result = subprocess.run(
                    formatted_command, shell=True, capture_output=True, text=True
                )
                if result.stderr:
                    logging.error(f"error: {result.stderr}")
        reset_effect = QGraphicsOpacityEffect()
        reset_effect.setOpacity(1.0)
        self._widget_container.setGraphicsEffect(reset_effect)
        self._is_running = False

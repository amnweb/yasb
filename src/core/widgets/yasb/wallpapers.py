import os
import ctypes
import random
import re
import logging
import subprocess
import pythoncom
import pywintypes
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.wallpapers import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from typing import List
import win32gui
from win32comext.shell import shell, shellcon
from settings import DEBUG

class WallpapersWidget(BaseWidget):
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
    ):
        super().__init__(int(update_interval * 1000), class_name="wallpapers-widget")

        self._label_content = label
        self._change_automatically = change_automatically
        self._image_path = image_path
        self._run_after = run_after
        
        self._last_image = None  # Track the last selected image

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

        self.register_callback("change_background", self.change_background)

        self.callback_timer = "change_background"
        if self._change_automatically:
            self.start_timer()

    def start_timer(self):
        if not WallpapersWidget._timer_running:
            if self.timer_interval and self.timer_interval > 0:
                self.timer.timeout.connect(self._timer_callback)
                self.timer.start(self.timer_interval)
                WallpapersWidget._timer_running = True

    def _create_dynamically_label(self, content: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content) 
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.setToolTip(f'Change Wallaper')
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label") 
                    label.setToolTip(f'Change Wallaper')
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                label.mousePressEvent = self.change_background
 
            return widgets
        self._widgets = process_content(content)

        
    def _update_label(self):
        active_widgets = self._widgets
        active_label_content = self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        for part in label_parts:
            part = part.strip()
            if part:              
                if '<span' in part and '</span>' in part:
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1
 

    def _make_filter(self, class_name: str, title: str):
        """https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows"""
        def enum_windows(handle: int, h_list: list):
            if not (class_name or title):
                h_list.append(handle)
            if class_name and class_name not in win32gui.GetClassName(handle):
                return True  # continue enumeration
            if title and title not in win32gui.GetWindowText(handle):
                return True  # continue enumeration
            h_list.append(handle)
        return enum_windows


    def find_window_handles(self, parent: int = None, window_class: str = None, title: str = None) -> List[int]:
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
        self.user32.UpdatePerUserSystemParameters(1)


    def enable_activedesktop(self):
        try:
            progman = self.find_window_handles(window_class='Progman')[0]
            cryptic_params = (0x52c, 0, 0, 0, 500, None)
            self.user32.SendMessageTimeoutW(progman, *cryptic_params)
        except IndexError as e:
            raise WindowsError('Cannot enable Active Desktop') from e


    def set_wallpaper(self, image_path: str, use_activedesktop: bool = True):
        if use_activedesktop:
            self.enable_activedesktop()
        pythoncom.CoInitialize()
        iad = pythoncom.CoCreateInstance(shell.CLSID_ActiveDesktop,
                                        None,
                                        pythoncom.CLSCTX_INPROC_SERVER,
                                        shell.IID_IActiveDesktop)
        iad.SetWallpaper(str(image_path), 0)
        iad.ApplyChanges(shellcon.AD_APPLY_ALL)
        self.force_refresh()


    def change_background(self, event=None):
        if event is None or event.button() == Qt.MouseButton.LeftButton:
            # Get a list of all image files in the folder
            wallpapers = [os.path.join(self._image_path, f) for f in os.listdir(self._image_path) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
            # Randomly select a new wallpaper
            new_wallpaper = random.choice(wallpapers)
            # prevent the same wallpaper from being selected 
            while new_wallpaper == self._last_image and len(wallpapers) > 1:
                new_wallpaper = random.choice(wallpapers)

            try:
                self.set_wallpaper(new_wallpaper)
                self._last_image = new_wallpaper
            except Exception as e:
                logging.error(f"Error setting wallpaper {new_wallpaper}: {e}")

            if self._run_after:
                self.run_after_command(new_wallpaper)


    def run_after_command(self, new_wallpaper):
        for command in self._run_after:
            formatted_command = command.replace("{image}", f'"{new_wallpaper}"')
            if DEBUG:
                logging.debug(f"Running command: {formatted_command}")
            result = subprocess.run(formatted_command, shell=True, capture_output=True, text=True)    
            if result.stderr:
                logging.error(f"error: {result.stderr}")              
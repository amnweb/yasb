import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.volume import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWheelEvent
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import ctypes
import logging

# Disable comtypes logging
logging.getLogger('comtypes').setLevel(logging.CRITICAL)

# Constants from the Windows API
VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
KEYEVENTF_KEYUP = 0x0002
UPDATE_INTERVAL = 1000

class VolumeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        volume_icons: list[str],
        callbacks: dict[str, str]
    ):
        super().__init__(UPDATE_INTERVAL, class_name="volume-widget")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        self.volume = None
        self._volume_icons = volume_icons
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_mute", self.toggle_mute)
        self.callback_left = "toggle_mute"
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        try:
            self._initialize_volume_interface()
            mute_status = self.volume.GetMute()
            icon_volume = self._get_volume_icon()
            level_volume = "mute" if mute_status == 1 else f'{round(self.volume.GetMasterVolumeLevelScalar() * 100)}%'
        except Exception:
            icon_volume, level_volume = "N/A", "N/A"

        label_options = {
            "{icon}": icon_volume,
            "{level}": level_volume
        }

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if '<span' in part and '</span>' in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def _get_volume_icon(self):
        current_mute_status = self.volume.GetMute()
        current_volume_level = round(self.volume.GetMasterVolumeLevelScalar() * 100)
        self.setToolTip(f'Volume {current_volume_level}')
        if current_mute_status == 1:
            volume_icon = self._volume_icons[0]
        elif (current_volume_level >= 0 and current_volume_level < 11):
            volume_icon = self._volume_icons[1]
        elif (current_volume_level >= 11 and current_volume_level < 30):
            volume_icon = self._volume_icons[2]
        elif (current_volume_level >= 30 and current_volume_level < 60):
            volume_icon = self._volume_icons[3]
        elif (current_volume_level >= 60):
            volume_icon = self._volume_icons[4]
        return volume_icon

    def _simulate_key_press(self, vk_code):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def _increase_volume(self):
        self._simulate_key_press(VK_VOLUME_UP)
        self._update_label()

    def _decrease_volume(self):
        self._simulate_key_press(VK_VOLUME_DOWN)
        self._update_label()

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()

    def toggle_mute(self):
        current_mute_status = self.volume.GetMute()
        self.volume.SetMute(not current_mute_status, None)
        self._update_label()

    def _initialize_volume_interface(self):
        CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = interface.QueryInterface(IAudioEndpointVolume)
        finally:
            CoUninitialize()
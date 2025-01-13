import re
import ctypes
import logging
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.volume import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, COMObject
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioEndpointVolumeCallback
from pycaw.callbacks import MMNotificationClient
from core.utils.win32.system_function import KEYEVENTF_KEYUP, VK_VOLUME_UP, VK_VOLUME_DOWN
from core.utils.widgets.animation_manager import AnimationManager
# Disable comtypes logging
logging.getLogger('comtypes').setLevel(logging.CRITICAL)
 
class AudioEndpointChangeCallback(MMNotificationClient):
    def __init__(self,parent):
        super().__init__()
        self.parent = parent
 
    def on_property_value_changed(self, device_id, property_struct, fmtid, pid):        
        self.parent.update_label_signal.emit()
        
class AudioEndpointVolumeCallback(COMObject):
    _com_interfaces_ = [IAudioEndpointVolumeCallback]
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
    def OnNotify(self, pNotify):
        self.parent.update_label_signal.emit()
 
          
class VolumeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    update_label_signal = pyqtSignal()

    def __init__(
        self,
        label: str,
        label_alt: str,
        tooltip: bool,
        volume_icons: list[str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str]
    ):
        super().__init__(class_name="volume-widget")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip = tooltip
        self._animation = animation
        self._padding = container_padding
        self.volume = None
        self._volume_icons = volume_icons
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
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
        self._padding = container_padding
        
        self.cb = AudioEndpointChangeCallback(self)
        self.enumerator = AudioUtilities.GetDeviceEnumerator()
        self.enumerator.RegisterEndpointNotificationCallback(self.cb)
        
        self._initialize_volume_interface()
        self.update_label_signal.connect(self._update_label)
        
        self._update_label()

        
    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets
        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

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
            icon_volume, level_volume = "", "No Device"

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
        if self._tooltip:
            self.setToolTip(f'Volume {current_volume_level}')
        if current_mute_status == 1:
            volume_icon = self._volume_icons[0]
        elif 0 <= current_volume_level < 11:
            volume_icon = self._volume_icons[1]
        elif 11 <= current_volume_level < 30:
            volume_icon = self._volume_icons[2]
        elif 30 <= current_volume_level < 60:
            volume_icon = self._volume_icons[3]
        else:
            volume_icon = self._volume_icons[4]
        return volume_icon

    def _simulate_key_press(self, vk_code):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def _increase_volume(self):
        if self.volume is None:
            logging.warning("Cannot increase volume: No audio device connected.")
            return
        try:
            self._simulate_key_press(VK_VOLUME_UP)
            self._update_label()
        except Exception as e:
            logging.error(f"Failed to increase volume: {e}")

    def _decrease_volume(self):
        if self.volume is None:
            logging.warning("Cannot decrease volume: No audio device connected.")
            return
        try:
            self._simulate_key_press(VK_VOLUME_DOWN)
            self._update_label()
        except Exception as e:
            logging.error(f"Failed to decrease volume: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()


    def toggle_mute(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        if self.volume is None:
            logging.warning("Cannot toggle mute: No audio device connected.")
            return
        try:
            current_mute_status = self.volume.GetMute()
            self.volume.SetMute(not current_mute_status, None)
            self._update_label()
        except Exception as e:
            logging.error(f"Failed to toggle mute: {e}")
   
   
    def _initialize_volume_interface(self):
        CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            if not devices:
                self.volume = None
                return
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = interface.QueryInterface(IAudioEndpointVolume)
            self.callback = AudioEndpointVolumeCallback(self)
            self.volume.RegisterControlChangeNotify(self.callback)
        except Exception as e:
            logging.error(f"Failed to initialize volume interface: {e}")
            self.volume = None
        finally:
            CoUninitialize()        
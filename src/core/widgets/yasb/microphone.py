import re
import ctypes
import logging
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.microphone import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, COMObject
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioEndpointVolumeCallback
from pycaw.callbacks import MMNotificationClient
from core.utils.win32.system_function import KEYEVENTF_KEYUP
from core.utils.widgets.animation_manager import AnimationManager

# Disable comtypes logging
logging.getLogger('comtypes').setLevel(logging.CRITICAL)

class AudioEndpointChangeCallback(MMNotificationClient):
    def __init__(self, parent):
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

class MicrophoneWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    update_label_signal = pyqtSignal()

    def __init__(
        self,
        label: str,
        label_alt: str,
        tooltip: bool,
        icons: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str]
    ):
        super().__init__(class_name="microphone-widget")

        self._initializing = True
        self.audio_endpoint = None
        
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip = tooltip
        self._icons = icons
        self._padding = container_padding
        self._animation = animation
        
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_mute", self.toggle_mute)
         
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        
        self.cb = AudioEndpointChangeCallback(self)
        self.enumerator = AudioUtilities.GetDeviceEnumerator()
        self.enumerator.RegisterEndpointNotificationCallback(self.cb)
        
        self._initialize_microphone_interface()
        self.update_label_signal.connect(self._update_label)

        self._update_label()
        self._initializing = False
                

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
        if self.audio_endpoint:
            if self.isHidden() and not self._initializing:
                self.show()
        else:
            self.hide()
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        try:
            self._initialize_microphone_interface()
            mute_status = self.audio_endpoint.GetMute() if self.audio_endpoint else None
            min_icon = self._get_mic_icon()
            min_level = "mute" if mute_status == 1 else f'{round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)}%' if self.audio_endpoint else "N/A"
        except Exception:
            min_icon, min_level = "N/A", "N/A"
        label_options = {
            "{icon}": min_icon,
            "{level}": min_level
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
                
                
    def _initialize_microphone_interface(self):
        CoInitialize()
        try:
            devices = AudioUtilities.GetMicrophone()
            if not devices:
                logging.error("Microphone not found")
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.audio_endpoint = interface.QueryInterface(IAudioEndpointVolume)
            self.callback = AudioEndpointVolumeCallback(self)
            self.audio_endpoint.RegisterControlChangeNotify(self.callback)
        except Exception:
            self.audio_endpoint = None
        finally:
            CoUninitialize()


    def _get_mic_icon(self):
        if not self.audio_endpoint:
            return self._icons['normal']
        current_mute_status = self.audio_endpoint.GetMute()
        current_level = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
        if current_mute_status == 1:
            mic_icon = self._icons['muted']
            tooltip = f'Muted: Volume {current_level}'
        else:
            mic_icon = self._icons['normal']
            tooltip = f'Volume {current_level}'
        if self._tooltip:
            self.setToolTip(tooltip)
        return mic_icon


    def toggle_mute(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        if self.audio_endpoint:
            current_mute_status = self.audio_endpoint.GetMute()
            self.audio_endpoint.SetMute(not current_mute_status, None)
            self._update_label()


    def _simulate_key_press(self, vk_code):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


    def _increase_volume(self):
        if self.audio_endpoint:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + 0.05, 1.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            self._update_label()


    def _decrease_volume(self):
        if self.audio_endpoint:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - 0.05, 0.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            self._update_label()


    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()
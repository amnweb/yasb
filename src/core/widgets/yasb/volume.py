import re
import comtypes
from comtypes import COMMETHOD, GUID
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, COMObject
import logging
import enum
import ctypes
from ctypes import HRESULT, POINTER
from ctypes import c_int as enum
from ctypes.wintypes import BOOL, INT, LPCWSTR, WORD
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.volume import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QVBoxLayout, QSlider, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QWheelEvent
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioEndpointVolumeCallback, EDataFlow, IMMDeviceEnumerator
from pycaw.callbacks import MMNotificationClient
from core.utils.win32.system_function import KEYEVENTF_KEYUP, VK_VOLUME_UP, VK_VOLUME_DOWN
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.utilities import PopupWidget
# Disable comtypes logging
logging.getLogger('comtypes').setLevel(logging.CRITICAL)
 
IID_IPolicyConfig = GUID('{f8679f50-850a-41cf-9c72-430f290290c8}')
CLSID_PolicyConfigClient = GUID('{870af99c-171d-4f9e-af0d-e63df40c2bc9}')
IID_AudioSes = ('{00000000-0000-0000-0000-000000000000}')

REFERENCE_TIME = ctypes.c_longlong
# LPCGUID = POINTER(GUID)
LPREFERENCE_TIME = POINTER(REFERENCE_TIME)

class DeviceSharedMode(ctypes.Structure):
    _fields_ = [
        ('dummy_', INT)
    ]

PDeviceSharedMode = POINTER(DeviceSharedMode)

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ('wFormatTag', WORD),
        ('nChannels', WORD),
        ('nSamplesPerSec', WORD),
        ('nAvgBytesPerSec', WORD),
        ('nBlockAlign', WORD),
        ('wBitsPerSample', WORD),
        ('cbSize', WORD),
    ]


PWAVEFORMATEX = POINTER(WAVEFORMATEX)

class _tagpropertykey(ctypes.Structure):
    pass

class tag_inner_PROPVARIANT(ctypes.Structure):
    pass

PROPVARIANT = tag_inner_PROPVARIANT
PPROPVARIANT = POINTER(PROPVARIANT)
#PROPERTYKEY = _tagpropertykey
PPROPERTYKEY = POINTER(_tagpropertykey)

class ERole(enum):
    eConsole = 0
    eMultimedia = 1
    eCommunications = 2
    ERole_enum_count = 3


class IPolicyConfig(comtypes.IUnknown):
    _case_insensitive_ = True
    _iid_ = IID_IPolicyConfig
    _methods_ = (
        COMMETHOD(
            [],
            HRESULT,
            'GetMixFormat',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['out'], POINTER(PWAVEFORMATEX), 'pFormat')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'GetDeviceFormat',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], BOOL, 'bDefault'),
            (['out'], POINTER(PWAVEFORMATEX), 'pFormat')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'ResetDeviceFormat',
            (['in'], LPCWSTR, 'pwstrDeviceId')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetDeviceFormat',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], PWAVEFORMATEX, 'pEndpointFormat'),
            (['in'], PWAVEFORMATEX, 'pMixFormat')
        ),

        COMMETHOD(
            [],
            HRESULT,
            'GetProcessingPeriod',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], BOOL, 'bDefault'),
            (['out'], LPREFERENCE_TIME, 'hnsDefaultDevicePeriod'),
            (['out'], LPREFERENCE_TIME, 'hnsMinimumDevicePeriod')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetProcessingPeriod',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], LPREFERENCE_TIME, 'hnsDevicePeriod')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'GetShareMode',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['out'], PDeviceSharedMode, 'pMode')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetShareMode',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], PDeviceSharedMode, 'pMode')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'GetPropertyValue',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], PPROPERTYKEY, 'key'),
            (['out'], PPROPVARIANT, 'pValue')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetPropertyValue',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], PPROPERTYKEY, 'key'),
            (['in'], PPROPVARIANT, 'pValue')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetDefaultEndpoint',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], ERole, 'ERole')
        ),
        COMMETHOD(
            [],
            HRESULT,
            'SetEndpointVisibility',
            (['in'], LPCWSTR, 'pwstrDeviceId'),
            (['in'], BOOL, 'bVisible')
        )
    )

#PIPolicyConfig = POINTER(IPolicyConfig)
class AudioSes(object):
    name = u'AudioSes'
    _reg_typelib_ = (IID_AudioSes, 1, 0)

class CPolicyConfigClient (comtypes.CoClass):
    _reg_clsid_ = CLSID_PolicyConfigClient
    _idlflags_ = []
    _reg_typelib_ = (IID_AudioSes, 1, 0)
    _com_interfaces_ = [IPolicyConfig]
    
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
        audio_menu: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str]
    ):
        super().__init__(class_name="volume-widget")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._tooltip = tooltip
        self._audio_menu = audio_menu
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
        self.register_callback("toggle_volume_menu", self._toggle_volume_menu)
 
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.cb = AudioEndpointChangeCallback(self)
        self.enumerator = AudioUtilities.GetDeviceEnumerator()
        self.enumerator.RegisterEndpointNotificationCallback(self.cb)
        
        self._initialize_volume_interface()
        self.update_label_signal.connect(self._update_label)
        self.update_label_signal.connect(self._update_slider_value)
        
        self._update_label()

    def _toggle_volume_menu(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self.show_volume_menu()


    def _on_slider_value_changed(self, value):
        if self.volume is not None:
            try:
                self.volume.SetMasterVolumeLevelScalar(value / 100, None)
                self._update_label()
            except Exception as e:
                logging.error(f"Failed to set volume: {e}")

                
    def _list_audio_devices(self):
        CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
        devices = []
        Flow = EDataFlow.eRender.value
        comtypes.CoInitialize()
        try:
            deviceEnumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                comtypes.CLSCTX_INPROC_SERVER)
                
            if deviceEnumerator is None:
                return devices

            collection = deviceEnumerator.EnumAudioEndpoints(Flow, 1)
            if collection is None:
                return devices

            count = collection.GetCount()
            for i in range(count):
                dev = collection.Item(i)
                
                if dev is not None:
                    createDev = AudioUtilities.CreateDevice(dev)
                    if not ": None" in str(createDev):
                        devices.append((createDev.id, createDev.FriendlyName))
            return devices
        finally:
            comtypes.CoUninitialize()    
 
    def _update_slider_value(self):
        """Helper method to update slider value based on current volume"""
        if hasattr(self, 'volume_slider') and self.volume is not None:
            try:
                current_volume = round(self.volume.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.setValue(current_volume)
            except:
                pass
            
    def _update_device_buttons(self, active_device_id):
        # Update classes for all device buttons
        for device_id, btn in self.device_buttons.items():
            if device_id == active_device_id:
                btn.setProperty("class", "device selected")
            else:
                btn.setProperty("class", "device")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            

    def _set_default_device(self, device_id: str):
        """Set default audio device with error handling and multiple interface attempts"""
        CoInitialize()
        
        sender = self.sender()
        device_id = sender.property('device_id')

        try:
            logging.debug(f"Attempting PolicyConfig interface with device: {device_id}")
            pc = comtypes.CoCreateInstance(
                CLSID_PolicyConfigClient,
                interface=IPolicyConfig,
                clsctx=CLSCTX_ALL
            )
            # eConsole = 0, eMultimedia = 1, eCommunications = 2
            pc.SetDefaultEndpoint(device_id, 0)
            # Re-initialize volume interface for new device
            self._initialize_volume_interface()
            # Update the slider value
            self._update_slider_value()
            # Update the device buttons
            self._update_device_buttons(device_id)
            return
        except Exception as e:
            logging.debug(f"PolicyConfig failed: {e}")           
        finally:
            CoUninitialize()
            self._update_label()
    

                
    def show_volume_menu(self):  
        self.dialog = PopupWidget(self, self._audio_menu['blur'], self._audio_menu['round_corners'], self._audio_menu['round_corners_type'], self._audio_menu['border_color'])
        self.dialog.setProperty("class", "audio-menu")
        self.dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.dialog.setWindowFlag(Qt.WindowType.Popup)
        self.dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        
        # Create vertical layout for the dialog
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)
        

        # Create a container widget and layout
        self.container = QWidget()
        self.container.setProperty("class", "audio-container")
        self.container_layout = QVBoxLayout()
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 10)
            

    
        self.devices = self._list_audio_devices()
        if len(self.devices) > 1:
            current_device = AudioUtilities.GetSpeakers()
            current_device_id = current_device.GetId()
            self.device_buttons = {}
            for device_id, device_name in self.devices:
                btn = QPushButton(device_name)
                if device_id == current_device_id:
                    btn.setProperty("class", "device selected")
                else:
                    btn.setProperty("class", "device")
                btn.setProperty("device_id", device_id)
                btn.clicked.connect(self._set_default_device)
                self.container_layout.addWidget(btn)
                self.device_buttons[device_id] = btn

            self.container.setLayout(self.container_layout)
    
        layout.addWidget(self.container)
    
        # Create volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setProperty("class", "volume-slider")
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
 
        # Set current volume
        try:
            current_volume = round(self.volume.GetMasterVolumeLevelScalar() * 100)
            self.volume_slider.setValue(current_volume)
        except:
            self.volume_slider.setValue(0)
            
        # Connect slider value change to volume control
        self.volume_slider.valueChanged.connect(self._on_slider_value_changed)
        
        # Add slider to layout
        layout.addWidget(self.volume_slider)
        self.dialog.setLayout(layout)
        

        # Position the dialog 
        self.dialog.adjustSize()
        widget_global_pos = self.mapToGlobal(QPoint(0, self.height() + self._audio_menu['distance']))
        if self._audio_menu['direction'] == 'up':
            global_y = self.mapToGlobal(QPoint(0, 0)).y() - self.dialog.height() - self._audio_menu['distance']
            widget_global_pos = QPoint(self.mapToGlobal(QPoint(0, 0)).x(), global_y)

        if self._audio_menu['alignment'] == 'left':
            global_position = widget_global_pos
        elif self._audio_menu['alignment'] == 'right':
            global_position = QPoint(
                widget_global_pos.x() + self.width() - self.dialog.width(),
                widget_global_pos.y()
            )
        elif self._audio_menu['alignment'] == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (self.width() - self.dialog.width()) // 2,
                widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos
        
        self.dialog.move(global_position)
        self.dialog.show()  
               
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
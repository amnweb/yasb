import ctypes
import logging
import re
from ctypes import HRESULT, POINTER
from ctypes import c_int as enum
from ctypes.wintypes import BOOL, INT, LPCWSTR, WORD

import comtypes
from comtypes import CLSCTX_ALL, COMMETHOD, GUID, CoInitialize, CoUninitialize
from PIL import Image
from pycaw.callbacks import AudioEndpointVolumeCallback as PycawAudioEndpointVolumeCallback
from pycaw.callbacks import MMNotificationClient
from pycaw.pycaw import (
    AudioUtilities,
    EDataFlow,
    IMMDeviceEnumerator,
    ISimpleAudioVolume,
)
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from core.utils.tooltip import CustomToolTip, set_tooltip
from core.utils.utilities import (
    PopupWidget,
    add_shadow,
    build_progress_widget,
    build_widget_label,
    refresh_widget_style,
)
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.app_icons import get_process_icon
from core.utils.win32.utilities import get_app_name_from_pid
from core.validation.widgets.yasb.volume import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

# Disable comtypes logging
logging.getLogger("comtypes").setLevel(logging.CRITICAL)
logging.getLogger("icoextract").setLevel(logging.ERROR)

# Blacklist of process names to exclude from audio menu
BLACKLISTED_PROCESSES = [
    "taskhostw.exe",
    "audiodg.exe",
    "svchost.exe",
    "shellhost.exe",
]

IID_IPolicyConfig = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
CLSID_PolicyConfigClient = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")
IID_AudioSes = "{00000000-0000-0000-0000-000000000000}"

REFERENCE_TIME = ctypes.c_longlong
# LPCGUID = POINTER(GUID)
LPREFERENCE_TIME = POINTER(REFERENCE_TIME)


class DeviceSharedMode(ctypes.Structure):
    _fields_ = [("dummy_", INT)]


PDeviceSharedMode = POINTER(DeviceSharedMode)


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", WORD),
        ("nChannels", WORD),
        ("nSamplesPerSec", WORD),
        ("nAvgBytesPerSec", WORD),
        ("nBlockAlign", WORD),
        ("wBitsPerSample", WORD),
        ("cbSize", WORD),
    ]


PWAVEFORMATEX = POINTER(WAVEFORMATEX)


class _tagpropertykey(ctypes.Structure):
    pass


class tag_inner_PROPVARIANT(ctypes.Structure):
    pass


PROPVARIANT = tag_inner_PROPVARIANT
PPROPVARIANT = POINTER(PROPVARIANT)
# PROPERTYKEY = _tagpropertykey
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
            "GetMixFormat",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["out"], POINTER(PWAVEFORMATEX), "pFormat"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetDeviceFormat",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], BOOL, "bDefault"),
            (["out"], POINTER(PWAVEFORMATEX), "pFormat"),
        ),
        COMMETHOD([], HRESULT, "ResetDeviceFormat", (["in"], LPCWSTR, "pwstrDeviceId")),
        COMMETHOD(
            [],
            HRESULT,
            "SetDeviceFormat",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], PWAVEFORMATEX, "pEndpointFormat"),
            (["in"], PWAVEFORMATEX, "pMixFormat"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetProcessingPeriod",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], BOOL, "bDefault"),
            (["out"], LPREFERENCE_TIME, "hnsDefaultDevicePeriod"),
            (["out"], LPREFERENCE_TIME, "hnsMinimumDevicePeriod"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetProcessingPeriod",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], LPREFERENCE_TIME, "hnsDevicePeriod"),
        ),
        COMMETHOD(
            [], HRESULT, "GetShareMode", (["in"], LPCWSTR, "pwstrDeviceId"), (["out"], PDeviceSharedMode, "pMode")
        ),
        COMMETHOD(
            [], HRESULT, "SetShareMode", (["in"], LPCWSTR, "pwstrDeviceId"), (["in"], PDeviceSharedMode, "pMode")
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetPropertyValue",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], PPROPERTYKEY, "key"),
            (["out"], PPROPVARIANT, "pValue"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetPropertyValue",
            (["in"], LPCWSTR, "pwstrDeviceId"),
            (["in"], PPROPERTYKEY, "key"),
            (["in"], PPROPVARIANT, "pValue"),
        ),
        COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR, "pwstrDeviceId"), (["in"], ERole, "ERole")),
        COMMETHOD([], HRESULT, "SetEndpointVisibility", (["in"], LPCWSTR, "pwstrDeviceId"), (["in"], BOOL, "bVisible")),
    )


# PIPolicyConfig = POINTER(IPolicyConfig)
class AudioSes(object):
    name = "AudioSes"
    _reg_typelib_ = (IID_AudioSes, 1, 0)


class CPolicyConfigClient(comtypes.CoClass):
    _reg_clsid_ = CLSID_PolicyConfigClient
    _idlflags_ = []
    _reg_typelib_ = (IID_AudioSes, 1, 0)
    _com_interfaces_ = [IPolicyConfig]


class AudioEndpointChangeCallback(MMNotificationClient):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def on_property_value_changed(self, device_id, property_struct, fmtid, pid):
        self.parent.update_label_signal.emit()


class AudioEndpointVolumeCallback(PycawAudioEndpointVolumeCallback):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def on_notify(self, new_volume, new_mute, event_context, channels, channel_volumes):
        """Called when audio endpoint volume or mute state changes"""
        self.parent.update_label_signal.emit()


class VolumeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    update_label_signal = pyqtSignal()

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        mute_text: str,
        tooltip: bool,
        scroll_step: int,
        slider_beep: bool,
        volume_icons: list[str],
        audio_menu: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
    ):
        super().__init__(class_name=f"volume-widget {class_name}")
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._mute_text = mute_text
        self._tooltip = tooltip
        self._scroll_step = int(scroll_step) / 100
        self._slider_beep = slider_beep
        self._audio_menu = audio_menu
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self.volume = None
        self._volume_icons = volume_icons
        self._progress_bar = progress_bar
        self._icon_cache = {}
        self._dpi = 1.0

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self._progress_bar)

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_mute", self.toggle_mute)
        self.register_callback("toggle_volume_menu", self._toggle_volume_menu)

        self.callback_left = callbacks["on_left"]
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
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_volume_menu()

    def _on_slider_released(self):
        # Hide tooltip when slider is released
        if hasattr(self, "_slider_tooltip") and self._slider_tooltip:
            self._slider_tooltip.hide()  # Hide instantly without animation
            # Reset tooltip for next use
            self._slider_tooltip = None
        if self._slider_beep:
            # Play a beep sound when slider is released
            try:
                ctypes.windll.user32.MessageBeep(0)
            except Exception as e:
                logging.debug(f"Failed to play volume sound: {e}")

    def _get_slider_handle_geometry(self, slider):
        """Calculate the geometry for the slider handle position"""

        value = slider.value()
        slider_range = slider.maximum() - slider.minimum()
        if slider_range > 0:
            handle_pos = (value - slider.minimum()) / slider_range
            x_offset = int(slider.width() * handle_pos)

            # Get slider position in global coordinates
            widget_rect = slider.rect()
            widget_global_pos = slider.mapToGlobal(widget_rect.topLeft())
            widget_global_pos.setX(widget_global_pos.x() + x_offset)

            # Create geometry at handle position (thin vertical rect)
            handle_geometry = QRect(widget_global_pos.x(), widget_global_pos.y(), 1, slider.height())
            return handle_geometry
        return None

    def _setup_slider_tooltip(self, slider):
        """Setup tooltip for slider (only show during drag)"""
        # Remove the tooltip filter to disable hover tooltips
        if hasattr(slider, "_tooltip_filter"):
            slider.removeEventFilter(slider._tooltip_filter)
            delattr(slider, "_tooltip_filter")

    def _show_slider_tooltip(self, slider, value):
        """Helper method to show/update tooltip for slider during drag"""
        if not self._tooltip or not slider.isSliderDown():
            return

        if not hasattr(self, "_slider_tooltip") or not self._slider_tooltip:
            # Create new tooltip
            self._slider_tooltip = CustomToolTip()
            self._slider_tooltip._position = "top"
            handle_geometry = self._get_slider_handle_geometry(slider)
            if handle_geometry:
                self._slider_tooltip.label.setText(f"{value}%")
                self._slider_tooltip.adjustSize()
                self._slider_tooltip._base_pos = self._slider_tooltip._calculate_position(handle_geometry)
                self._slider_tooltip.move(self._slider_tooltip._base_pos.x(), self._slider_tooltip._base_pos.y())
                self._slider_tooltip.setWindowOpacity(1.0)
                self._slider_tooltip.show()
        else:
            # Update existing tooltip
            handle_geometry = self._get_slider_handle_geometry(slider)
            if handle_geometry:
                self._slider_tooltip.label.setText(f"{value}%")
                self._slider_tooltip.adjustSize()
                base_pos = self._slider_tooltip._calculate_position(handle_geometry)
                self._slider_tooltip.move(base_pos.x(), base_pos.y())

    def _on_slider_value_changed(self, value):
        if self.volume is not None:
            try:
                self.volume.SetMasterVolumeLevelScalar(value / 100, None)
                # self._update_label()
                # Show tooltip while actively dragging
                if hasattr(self, "volume_slider"):
                    self._show_slider_tooltip(self.volume_slider, value)
            except Exception as e:
                logging.error(f"Failed to set volume: {e}")

    def _set_app_volume(self, volume_interface, value, slider=None):
        """Set volume for a specific application"""
        try:
            volume_interface.SetMasterVolume(value / 100, None)
            # Show tooltip while actively dragging
            if slider:
                self._show_slider_tooltip(slider, value)
        except Exception as e:
            logging.error(f"Failed to set application volume: {e}")

    def _toggle_app_mute(self, volume_interface, icon_label, slider, pid):
        """Toggle mute state for a specific application"""
        try:
            current_mute = volume_interface.GetMute()
            new_mute = not current_mute
            volume_interface.SetMute(new_mute, None)
            # Update icon and slider state
            self._update_app_mute_state(icon_label, slider, new_mute, pid)
        except Exception as e:
            logging.error(f"Failed to toggle application mute: {e}")

    def _update_app_mute_state(self, icon_label, slider, is_muted, pid):
        """Update the visual state of an app's icon and slider based on mute status"""
        try:
            # Get the original icon
            app_icon = self._get_process_icon_pixmap(pid, icon_size=16, force_grayscale=is_muted)
            if app_icon:
                icon_label.setPixmap(app_icon)

            # Enable/disable the slider
            slider.setEnabled(not is_muted)
        except Exception as e:
            logging.error(f"Failed to update app mute state: {e}")

    def _toggle_app_volumes(self):
        """Toggle the visibility of application volume sliders with animation"""
        if not hasattr(self, "app_volumes_container") or not hasattr(self, "app_volumes_expanded"):
            return

        # Toggle the expanded state
        self.app_volumes_expanded = not self.app_volumes_expanded

        if self.app_volumes_expanded:
            # Show container first
            self.app_volumes_container.show()
            content_height = self.app_volumes_container.sizeHint().height()
            target_height = content_height
            current_height = 0
            self.app_toggle_btn.setText(self._audio_menu["app_icons"]["toggle_up"])
            self.app_toggle_btn.setProperty("class", "toggle-apps expanded")
            if self._tooltip:
                set_tooltip(self.app_toggle_btn, "Collapse application volumes")
        else:
            target_height = 0
            current_height = self.app_volumes_container.height()
            self.app_toggle_btn.setText(self._audio_menu["app_icons"]["toggle_down"])
            self.app_toggle_btn.setProperty("class", "toggle-apps")
            if self._tooltip:
                set_tooltip(self.app_toggle_btn, "Expand application volumes")

        refresh_widget_style(self.app_toggle_btn)

        # Stop any existing animation
        if (
            hasattr(self, "app_volume_animation")
            and self.app_volume_animation.state() == QPropertyAnimation.State.Running
        ):
            self.app_volume_animation.stop()

        # Set the starting height immediately before animation
        self.app_volumes_container.setMaximumHeight(current_height)

        # Create animation
        self.app_volume_animation = QPropertyAnimation(self.app_volumes_container, b"maximumHeight")
        self.app_volume_animation.setDuration(200)
        self.app_volume_animation.setStartValue(current_height)
        self.app_volume_animation.setEndValue(target_height)
        self.app_volume_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Update dialog size during animation
        self.app_volume_animation.valueChanged.connect(self._resize_dialog)

        # Hide container after animation completes if collapsing
        if not self.app_volumes_expanded:
            self.app_volume_animation.finished.connect(lambda: self.app_volumes_container.hide())

        self.app_volume_animation.start()

    def _resize_dialog(self):
        """Resize the dialog to fit its content during animation"""
        if hasattr(self, "dialog"):
            self.dialog.adjustSize()

    def _list_audio_devices(self):
        CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
        devices = []
        Flow = EDataFlow.eRender.value
        comtypes.CoInitialize()
        try:
            deviceEnumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER
            )

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
                    if ": None" not in str(createDev):
                        devices.append((createDev.id, createDev.FriendlyName))
            return devices
        finally:
            comtypes.CoUninitialize()

    def _update_slider_value(self):
        """Helper method to update slider value based on current volume"""
        if hasattr(self, "volume_slider") and self.volume is not None:
            try:
                current_volume = round(self.volume.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.setValue(current_volume)
            except:
                pass

    def _format_session_label(self, name: str) -> str:
        """Format session label by removing file extensions and truncating if necessary"""
        name = name.replace(".exe", "")
        name = name.replace(".", " ")
        name = name.title()
        # Truncate if longer than 20 characters
        if len(name) > 23:
            name = name[:20] + "..."
        return name

    def _get_process_icon_pixmap(self, pid: int, icon_size: int = 16, force_grayscale: bool = False) -> QPixmap | None:
        """Get icon for a process and convert to QPixmap with DPI-aware caching"""
        try:
            # Create cache key with PID, icon_size, DPI, and grayscale state
            cache_key = (pid, icon_size, self._dpi, force_grayscale)

            if cache_key in self._icon_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                # Get current DPI
                self._dpi = self.screen().devicePixelRatio()
                icon_img = get_process_icon(pid)
                if icon_img:
                    # Resize and convert to RGBA with DPI scaling
                    scaled_size = int(icon_size * self._dpi)
                    icon_img = icon_img.resize((scaled_size, scaled_size), Image.LANCZOS)
                    icon_img = icon_img.convert("RGBA")

                    # Apply grayscale if muted
                    if force_grayscale:
                        # Convert to grayscale while preserving alpha channel
                        grayscale = icon_img.convert("L")
                        icon_img.paste(grayscale, (0, 0), icon_img)

                    # Cache the resized image
                    self._icon_cache[cache_key] = icon_img

            if not icon_img:
                return None

            # Convert to QPixmap
            data = icon_img.tobytes("raw", "RGBA")
            qimage = QImage(data, icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            pixmap.setDevicePixelRatio(self._dpi)
            return pixmap
        except Exception as e:
            logging.debug(f"Failed to get icon pixmap for PID {pid}: {e}")

        return None

    def _get_active_audio_sessions(self):
        """Get all active audio sessions (applications with audio)"""
        sessions = []
        seen_sessions = {}  # Track unique sessions by (PID, GroupingParam)

        try:
            devices = AudioUtilities.GetSpeakers()
            if not devices:
                return sessions

            sessions_enum = AudioUtilities.GetAllSessions()
            for session in sessions_enum:
                if session.Process and session.Process.name():
                    # Skip blacklisted processes
                    if session.Process.name().lower() in [p.lower() for p in BLACKLISTED_PROCESSES]:
                        continue

                    try:
                        pid = session.ProcessId

                        try:
                            grouping_param = str(session.GroupingParam)
                        except:
                            grouping_param = ""

                        session_key = (pid, grouping_param)

                        if session_key in seen_sessions:
                            continue

                        seen_sessions[session_key] = True
                    except Exception as e:
                        logging.debug(f"Failed to process session grouping: {e}")
                        continue

                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    pid = session.Process.pid

                    # Check if app set a DisplayName for the audio session
                    app_name = None
                    if session.DisplayName:
                        display_name = session.DisplayName.strip()
                        # Skip resource strings (starts with @ or ms-resource:) - these need special resolution
                        if (
                            display_name
                            and not display_name.startswith("@")
                            and not display_name.startswith("ms-resource:")
                        ):
                            app_name = display_name

                    # Get FileDescription from executable version info
                    if not app_name:
                        app_name = get_app_name_from_pid(pid)
                        # Clean up result - remove extra whitespace
                        if app_name:
                            app_name = app_name.strip()
                            # If it's just whitespace or empty, treat as None
                            if not app_name:
                                app_name = None

                    # Fall back to formatted process name
                    if not app_name:
                        app_name = self._format_session_label(session.Process.name())

                    sessions.append(
                        {
                            "name": session.Process.name(),
                            "app_name": app_name,
                            "volume_interface": volume,
                            "session": session,
                            "pid": pid,
                        }
                    )
        except Exception as e:
            logging.error(f"Failed to get audio sessions: {e}")

        sessions.sort(key=lambda s: s["app_name"].lower())

        return sessions

    def _update_device_buttons(self, active_device_id):
        # Update classes for all device buttons
        for device_id, btn in self.device_buttons.items():
            if device_id == active_device_id:
                btn.setProperty("class", "device selected")
            else:
                btn.setProperty("class", "device")
            refresh_widget_style(btn)

    def _set_default_device(self, device_id: str):
        """Set default audio device with error handling and multiple interface attempts"""
        CoInitialize()

        sender = self.sender()
        device_id = sender.property("device_id")

        try:
            if DEBUG:
                logging.debug(f"Attempting PolicyConfig interface with device: {device_id}")
            pc = comtypes.CoCreateInstance(CLSID_PolicyConfigClient, interface=IPolicyConfig, clsctx=CLSCTX_ALL)
            # eConsole = 0, eMultimedia = 1, eCommunications = 2
            pc.SetDefaultEndpoint(device_id, 0)
            # Re-initialize volume interface for new device
            self._initialize_volume_interface()
            # Update the slider value
            self._update_slider_value()
            # Update the device buttons
            self._update_device_buttons(device_id)

            # Close and reopen the menu to refresh audio sessions
            if hasattr(self, "dialog") and self.dialog:
                self.dialog.hide()
                self.show_volume_menu()

            return
        except Exception as e:
            logging.debug(f"PolicyConfig failed: {e}")
        finally:
            CoUninitialize()
            self._update_label()

    def show_volume_menu(self):
        self.dialog = PopupWidget(
            self,
            self._audio_menu["blur"],
            self._audio_menu["round_corners"],
            self._audio_menu["round_corners_type"],
            self._audio_menu["border_color"],
        )
        self.dialog.setProperty("class", "audio-menu")

        # Create vertical layout for the dialog
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create a container widget and layout
        self.container = QWidget()
        self.container.setProperty("class", "audio-container")
        self.container_layout = QVBoxLayout()
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        self.devices = self._list_audio_devices()
        if len(self.devices) > 1:
            current_device = AudioUtilities.GetSpeakers()
            # Use .id property instead of .GetId() method (new pycaw API)
            current_device_id = current_device.id
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

        # Create global volume section (at the top)
        global_container = QFrame()
        global_container.setProperty("class", "system-volume-container")
        global_layout = QVBoxLayout()
        global_layout.setSpacing(0)
        global_layout.setContentsMargins(0, 0, 0, 0)

        # Slider row with toggle button
        slider_row = QHBoxLayout()
        slider_row.setSpacing(0)
        slider_row.setContentsMargins(0, 0, 0, 0)

        # System volume slider
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
        # Connect slider release to hide tooltip and optionally beep
        self.volume_slider.sliderReleased.connect(self._on_slider_released)

        slider_row.addWidget(self.volume_slider)

        self._setup_slider_tooltip(self.volume_slider)

        audio_sessions = []
        if self._audio_menu["show_apps"]:
            # Get active audio sessions
            audio_sessions = self._get_active_audio_sessions()
            # Add app toggle button on the right (only if there are audio sessions)
            if audio_sessions:
                self.app_toggle_btn = QPushButton(self._audio_menu["app_icons"]["toggle_down"])
                self.app_toggle_btn.setProperty("class", "toggle-apps")
                self.app_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self.app_toggle_btn.clicked.connect(lambda: self._toggle_app_volumes())
                if self._tooltip:
                    set_tooltip(self.app_toggle_btn, "Expand application volumes")
                slider_row.addWidget(self.app_toggle_btn)

        global_layout.addLayout(slider_row)
        global_container.setLayout(global_layout)
        layout.addWidget(global_container)

        # Create per-application volume sliders section
        if audio_sessions and self._audio_menu["show_apps"]:
            self.app_volumes_container = QFrame()
            self.app_volumes_container.setProperty("class", "apps-container")
            app_volumes_layout = QVBoxLayout()
            app_volumes_layout.setSpacing(0)
            app_volumes_layout.setContentsMargins(0, 0, 0, 0)

            for session_info in audio_sessions:
                app_container = QFrame()
                app_container.setProperty("class", "app-volume")
                app_layout = QVBoxLayout()
                app_layout.setSpacing(0)
                app_layout.setContentsMargins(0, 0, 0, 0)

                display_name = session_info.get("app_name", self._format_session_label(session_info["name"]))
                if self._audio_menu["show_app_labels"]:
                    app_label = QLabel(display_name)
                    app_label.setProperty("class", "app-label")
                    app_layout.addWidget(app_label)

                slider_layout = QHBoxLayout()
                slider_layout.setSpacing(0)
                slider_layout.setContentsMargins(0, 0, 0, 0)

                try:
                    is_muted = session_info["volume_interface"].GetMute()
                except:
                    is_muted = False

                if self._audio_menu["show_app_icons"]:
                    icon_frame = QFrame()
                    icon_frame.setContentsMargins(0, 0, 0, 0)
                    icon_frame.setProperty("class", "app-icon-container")
                    icon_frame.setCursor(Qt.CursorShape.PointingHandCursor)
                    if self._tooltip:
                        set_tooltip(icon_frame, display_name, delay=800, position="top")

                    icon_frame_layout = QHBoxLayout()
                    icon_frame_layout.setContentsMargins(0, 0, 0, 0)
                    icon_frame_layout.setSpacing(0)
                    icon_frame.setLayout(icon_frame_layout)

                    icon_label = QLabel()
                    icon_label.setProperty("class", "app-icon")
                    icon_label.setFixedSize(16, 16)

                    # Try to get the app icon (grayscale if muted)
                    app_icon = self._get_process_icon_pixmap(
                        session_info["pid"], icon_size=16, force_grayscale=is_muted
                    )
                    if app_icon:
                        icon_label.setPixmap(app_icon)

                    icon_frame_layout.addWidget(icon_label)
                    slider_layout.addWidget(icon_frame)

                # Application volume slider
                app_slider = QSlider(Qt.Orientation.Horizontal)
                app_slider.setProperty("class", "app-slider")
                app_slider.setMinimum(0)
                app_slider.setMaximum(100)

                try:
                    app_volume = int(session_info["volume_interface"].GetMasterVolume() * 100)
                    app_slider.setValue(app_volume)
                except:
                    app_slider.setValue(100)
                # Disable slider if muted
                app_slider.setEnabled(not is_muted)

                # Connect to change app volume
                app_slider.valueChanged.connect(
                    lambda value,
                    vol_interface=session_info["volume_interface"],
                    slider=app_slider: self._set_app_volume(vol_interface, value, slider)
                )
                # Connect slider release to hide tooltip
                app_slider.sliderReleased.connect(self._on_slider_released)

                # Disable hover tooltips (we only show during drag)
                self._setup_slider_tooltip(app_slider)
                if self._audio_menu["show_app_icons"]:
                    # Make icon frame clickable to toggle mute
                    icon_frame.mousePressEvent = lambda event, vol_interface=session_info[
                        "volume_interface"
                    ], icon=icon_label, slider=app_slider, pid=session_info["pid"]: self._toggle_app_mute(
                        vol_interface, icon, slider, pid
                    )

                slider_layout.addWidget(app_slider)
                app_layout.addLayout(slider_layout)
                app_container.setLayout(app_layout)
                app_volumes_layout.addWidget(app_container)

            self.app_volumes_container.setLayout(app_volumes_layout)

            # Initially hide the app volumes
            self.app_volumes_container.setMaximumHeight(0)
            self.app_volumes_container.hide()
            layout.addWidget(self.app_volumes_container)

            # Store expanded state
            self.app_volumes_expanded = False
        self.dialog.setLayout(layout)

        # Position the dialog
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._audio_menu["alignment"],
            direction=self._audio_menu["direction"],
            offset_left=self._audio_menu["offset_left"],
            offset_top=self._audio_menu["offset_top"],
        )
        self.dialog.show()
        # Automatically expand app volumes if configured
        if audio_sessions and self._audio_menu["show_apps_expanded"] and self._audio_menu["show_apps"]:
            self._toggle_app_volumes()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if self.volume is None:
            logging.error("No volume interface available")
            mute_status, icon_volume, level_volume = None, "", "No Device"
        else:
            try:
                mute_status = self.volume.GetMute()
                icon_volume = self._get_volume_icon()
                level_volume = (
                    self._mute_text if mute_status == 1 else f"{round(self.volume.GetMasterVolumeLevelScalar() * 100)}%"
                )
            except Exception as e:
                logging.error(f"Failed to get volume info: {e}")
                mute_status, icon_volume, level_volume = None, "", "No Device"

        label_options = {"{icon}": icon_volume, "{level}": level_volume}

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            numeric_value = int(re.search(r"\d+", level_volume).group()) if re.search(r"\d+", level_volume) else 0
            self.progress_widget.set_value(numeric_value)

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_muted_class(active_widgets[widget_index], mute_status == 1)
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        self._set_muted_class(active_widgets[widget_index], mute_status == 1)
                widget_index += 1

    def _set_muted_class(self, widget, muted: bool):
        """Set or remove the 'muted' class on the widget."""
        current_class = widget.property("class") or ""
        classes = set(current_class.split())
        if muted:
            classes.add("muted")
        else:
            classes.discard("muted")
        widget.setProperty("class", " ".join(classes))
        refresh_widget_style(widget)

    def _get_volume_icon(self):
        current_mute_status = self.volume.GetMute()
        current_volume_level = round(self.volume.GetMasterVolumeLevelScalar() * 100)
        if self._tooltip:
            set_tooltip(self, f"Volume {current_volume_level}% {'(Muted)' if current_mute_status == 1 else ''}")
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

    def _increase_volume(self):
        if self.volume is None:
            logging.warning("Cannot increase volume: No audio device connected.")
            return
        try:
            current_volume = self.volume.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + self._scroll_step, 1.0)
            self.volume.SetMasterVolumeLevelScalar(new_volume, None)
            if self.volume.GetMute() and new_volume > 0.0:
                self.volume.SetMute(False, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to increase volume: {e}")

    def _decrease_volume(self):
        if self.volume is None:
            logging.warning("Cannot decrease volume: No audio device connected.")
            return
        try:
            current_volume = self.volume.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - self._scroll_step, 0.0)
            self.volume.SetMasterVolumeLevelScalar(new_volume, None)
            if new_volume == 0.0:
                self.volume.SetMute(True, None)
            self._update_label()
            self._update_slider_value()
        except Exception as e:
            logging.error(f"Failed to decrease volume: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()

    def toggle_mute(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
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
            self.volume = devices.EndpointVolume
            self.callback = AudioEndpointVolumeCallback(self)
            self.volume.RegisterControlChangeNotify(self.callback)
        except Exception as e:
            logging.error(f"Failed to initialize volume interface: {e}")
            self.volume = None
        finally:
            CoUninitialize()

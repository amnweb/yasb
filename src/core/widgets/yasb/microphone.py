import logging
import re

from comtypes import (
    CLSCTX_ALL,
    CoInitialize,
    COMObject,
    CoUninitialize,
)
from pycaw.callbacks import MMNotificationClient
from pycaw.pycaw import (
    AudioUtilities,
    IAudioEndpointVolume,
    IAudioEndpointVolumeCallback,  # import the public enumerator
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.microphone import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

# Disable comtypes logging
logging.getLogger("comtypes").setLevel(logging.CRITICAL)


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
        mute_text: str,
        tooltip: bool,
        scroll_step: int,
        icons: dict[str, str],
        mic_menu: dict[str, str],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="microphone-widget")

        self._initializing = True
        self.audio_endpoint = None

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._mute_text = mute_text
        self._tooltip = tooltip
        self._scroll_step = int(scroll_step) / 100
        self._icons = icons
        self._mic_menu = mic_menu
        self._padding = container_padding
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_mute", self.toggle_mute)
        self.register_callback("toggle_mic_menu", self.show_menu)

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
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        if self.audio_endpoint:
            if self.isHidden() and not self._initializing:
                self.show()
        else:
            self.hide()
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        try:
            self._initialize_microphone_interface()
            mute_status = self.audio_endpoint.GetMute() if self.audio_endpoint else None
            mic_level = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100) if self.audio_endpoint else None
            min_icon = self._get_mic_icon()
            min_level = self._mute_text if mute_status == 1 else f"{mic_level}%" if self.audio_endpoint else "N/A"
        except Exception:
            min_icon, min_level = "N/A", "N/A"
        label_options = {"{icon}": min_icon, "{level}": min_level}

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

    def _set_muted_class(self, widget, muted: bool):
        """Set or remove the 'muted' class on the widget."""
        current_class = widget.property("class") or ""
        classes = set(current_class.split())
        if muted:
            classes.add("muted")
        else:
            classes.discard("muted")
        widget.setProperty("class", " ".join(classes))
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _get_mic_icon(self):
        if not self.audio_endpoint:
            return self._icons["normal"]
        current_mute_status = self.audio_endpoint.GetMute()
        current_level = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
        if current_mute_status == 1:
            mic_icon = self._icons["muted"]
            tooltip = f"Muted: Volume {current_level}"
        else:
            mic_icon = self._icons["normal"]
            tooltip = f"Volume {current_level}"
        if self._tooltip:
            self.setToolTip(tooltip)
        return mic_icon

    def toggle_mute(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if self.audio_endpoint:
            current_mute_status = self.audio_endpoint.GetMute()
            self.audio_endpoint.SetMute(not current_mute_status, None)
            self._update_label()

    def _increase_volume(self):
        if self.audio_endpoint:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + self._scroll_step, 1.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            if self.audio_endpoint.GetMute() and new_volume > 0.0:
                self.audio_endpoint.SetMute(False, None)
            self._update_label()

    def _decrease_volume(self):
        if self.audio_endpoint:
            current_volume = self.audio_endpoint.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - self._scroll_step, 0.0)
            self.audio_endpoint.SetMasterVolumeLevelScalar(new_volume, None)
            if new_volume == 0.0:
                self.audio_endpoint.SetMute(True, None)
            self._update_label()

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self._increase_volume()
        elif event.angleDelta().y() < 0:
            self._decrease_volume()

    def show_menu(self):
        self.dialog = PopupWidget(
            self,
            self._mic_menu["blur"],
            self._mic_menu["round_corners"],
            self._mic_menu["round_corners_type"],
            self._mic_menu["border_color"],
        )
        self.dialog.setProperty("class", "microphone-menu")

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setProperty("class", "microphone-slider")
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        try:
            if self.audio_endpoint:
                current_volume = round(self.audio_endpoint.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.setValue(current_volume)
        except Exception:
            self.volume_slider.setValue(0)
        self.volume_slider.valueChanged.connect(self._on_slider_value_changed)
        layout.addWidget(self.volume_slider)

        self.dialog.setLayout(layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._mic_menu["alignment"],
            direction=self._mic_menu["direction"],
            offset_left=self._mic_menu["offset_left"],
            offset_top=self._mic_menu["offset_top"],
        )
        self.dialog.show()

    def _on_slider_value_changed(self, value):
        if self.audio_endpoint:
            try:
                self.audio_endpoint.SetMasterVolumeLevelScalar(value / 100, None)
                self._update_label()
            except Exception as e:
                logging.error(f"Failed to set microphone volume: {e}")

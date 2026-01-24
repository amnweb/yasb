import logging
import threading

from pycaw.callbacks import AudioEndpointVolumeCallback, MMNotificationClient
from pycaw.constants import DEVICE_STATE
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole
from PyQt6.QtCore import QObject, pyqtSignal


class AudioInputService(QObject):
    """Singleton service that manages shared pycaw instances for all microphone widgets."""

    _instance = None
    device_change_requested = pyqtSignal()
    volume_change_requested = pyqtSignal()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        super().__init__()

        self._widgets = []
        self._microphone_interface = None
        self._enumerator = None
        self._device_callback = None
        self._volume_callback = None

        self._cached_microphone = None
        self._cached_devices = None
        self._cache_lock = threading.Lock()
        self._microphone_checked = False

        logging.info("AudioInputService starting...")
        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
        except Exception as e:
            logging.error(f"AudioInputService failed to initialize: {e}")

    def _initialize_audio(self):
        """Fetch microphone and devices in background thread."""

        def fetch():
            try:
                with self._cache_lock:
                    if self._cached_microphone is None:
                        mic = self._get_microphone_device()
                        if mic:
                            self._cached_microphone = mic
                            if self._microphone_interface is None:
                                self._microphone_interface = mic.EndpointVolume

                    if self._cached_devices is None:
                        devices = AudioUtilities.GetAllDevices(
                            data_flow=EDataFlow.eCapture.value, device_state=DEVICE_STATE.ACTIVE.value
                        )
                        self._cached_devices = [(d.id, d.FriendlyName) for d in devices]
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _get_microphone_device(self):
        """Get default microphone as AudioDevice. Returns None if no mic available."""
        try:
            mic_pointer = AudioUtilities.GetMicrophone()
            if mic_pointer:
                return AudioUtilities.CreateDevice(mic_pointer)
        except Exception:
            pass
        return None

    def _invalidate_cache(self):
        """Clear cached data when devices change."""
        with self._cache_lock:
            self._cached_microphone = None
            self._cached_devices = None
            self._microphone_checked = False

    def register_widget(self, widget):
        """Add widget to the service."""
        if widget not in self._widgets:
            self._widgets.append(widget)

        if len(self._widgets) == 1:
            self._initialize_audio()
            self.device_change_requested.connect(self._on_device_change)
            self.volume_change_requested.connect(self._on_volume_change)
            self._register_callbacks()

    def unregister_widget(self, widget):
        """Remove widget from service."""
        if widget in self._widgets:
            self._widgets.remove(widget)
            if not self._widgets:
                self._unregister_callbacks()

    def _register_callbacks(self):
        """Hook up device and volume change notifications."""
        try:
            if self._enumerator and not self._device_callback:
                self._device_callback = _SharedDeviceCallback(self)
                self._enumerator.RegisterEndpointNotificationCallback(self._device_callback)

            volume = self.get_microphone_interface()
            if volume and not self._volume_callback:
                self._volume_callback = _SharedVolumeCallback(self)
                volume.RegisterControlChangeNotify(self._volume_callback)
        except Exception:
            pass

    def _unregister_callbacks(self):
        """Unhook device and volume notifications."""
        try:
            if self._device_callback and self._enumerator:
                self._enumerator.UnregisterEndpointNotificationCallback(self._device_callback)
                self._device_callback = None

            if self._volume_callback and self._microphone_interface:
                self._microphone_interface.UnregisterControlChangeNotify(self._volume_callback)
                self._volume_callback = None
        except Exception:
            pass

    def _on_volume_change(self):
        """Push volume updates to all widgets."""
        for widget in self._widgets[:]:
            try:
                widget._update_label()
                if hasattr(widget, "dialog") and widget.dialog and widget.dialog.isVisible():
                    widget._update_slider_value()
            except:
                pass

    def _on_device_change(self):
        """Handle audio device add/remove/change."""
        # Unregister old volume callback
        if self._volume_callback and self._microphone_interface:
            try:
                self._microphone_interface.UnregisterControlChangeNotify(self._volume_callback)
            except:
                pass
            self._volume_callback = None

        # Clear cached data and interface
        self._invalidate_cache()
        self._microphone_interface = None

        # Get new microphone (may be None if no mic connected)
        mic = self._get_microphone_device()
        if mic:
            try:
                self._microphone_interface = mic.EndpointVolume
                with self._cache_lock:
                    self._cached_microphone = mic
            except:
                pass

        # Re-register volume callback if we have a mic
        if self._widgets and self._microphone_interface:
            try:
                self._volume_callback = _SharedVolumeCallback(self)
                self._microphone_interface.RegisterControlChangeNotify(self._volume_callback)
            except Exception:
                pass

        # Notify all widgets
        for widget in self._widgets[:]:
            try:
                widget._reinitialize_microphone()
            except:
                pass

    def get_microphone_interface(self):
        """Get volume control interface for microphone."""
        if self._microphone_interface is None:
            mic = self.get_microphone()
            if mic:
                try:
                    self._microphone_interface = mic.EndpointVolume
                except:
                    pass
        return self._microphone_interface

    def get_microphone(self):
        """Get default microphone device. Returns None if no mic available."""
        with self._cache_lock:
            if self._cached_microphone is not None:
                return self._cached_microphone
            if self._microphone_checked:
                return None

        self._microphone_checked = True
        mic = self._get_microphone_device()
        if mic:
            with self._cache_lock:
                self._cached_microphone = mic
        return mic

    def get_all_devices(self):
        """List all active microphone devices."""
        with self._cache_lock:
            if self._cached_devices is not None:
                return self._cached_devices

        try:
            devices = AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eCapture.value, device_state=DEVICE_STATE.ACTIVE.value
            )
            result = [(d.id, d.FriendlyName) for d in devices]
            with self._cache_lock:
                self._cached_devices = result
            return result
        except Exception:
            return []

    def set_default_device(self, device_id):
        """Switch default microphone."""
        try:
            AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole])
            return True
        except Exception as e:
            logging.error(f"Failed to set default microphone: {e}")
            return False


class _SharedVolumeCallback(AudioEndpointVolumeCallback):
    """Forwards volume changes to the service."""

    def __init__(self, service):
        super().__init__()
        self.service = service

    def on_notify(self, new_volume, new_mute, event_context, channels, channel_volumes):
        self.service.volume_change_requested.emit()


class _SharedDeviceCallback(MMNotificationClient):
    """Forwards device changes to the service."""

    def __init__(self, service):
        super().__init__()
        self.service = service
        self._last_device_id = None

    def on_default_device_changed(self, flow, flow_id, role, role_id, default_device_id):
        """Handle default microphone device changes."""
        # Only care about capture (input) devices with console role
        if flow_id != EDataFlow.eCapture.value or role_id != ERole.eConsole.value:
            return
        # Deduplicate rapid events
        if default_device_id == self._last_device_id:
            return
        self._last_device_id = default_device_id
        self.service.device_change_requested.emit()

    def on_device_state_changed(self, device_id, new_state, new_state_id):
        """Handle device state changes (connected/disconnected)."""
        # React to Active, Disabled, and Unplugged states
        if new_state_id not in (DEVICE_STATE.ACTIVE.value, DEVICE_STATE.DISABLED.value, DEVICE_STATE.UNPLUGGED.value):
            return
        self.service.device_change_requested.emit()

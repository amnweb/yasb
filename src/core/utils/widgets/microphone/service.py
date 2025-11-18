import logging

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
        self._widgets = []  # List of registered widgets
        self._microphone_interface = None
        self._enumerator = None
        self._device_callback = None
        self._volume_callback = None

        # Initialize audio on first instance
        self._initialize_microphone()

    def _initialize_microphone(self):
        """Initialize the shared pycaw microphone interface."""
        logging.info("AudioInputService starting...")
        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
        except Exception as e:
            logging.error(f"AudioInputService failed to initialize enumerator: {e}")
            self._microphone_interface = None
            return

        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                device = AudioUtilities.CreateDevice(devices)
                self._microphone_interface = device.EndpointVolume
            else:
                self._microphone_interface = None
        except Exception:
            self._microphone_interface = None

    def register_widget(self, widget):
        """Register a widget to use the shared service."""
        if widget not in self._widgets:
            self._widgets.append(widget)

        # Register callbacks on first widget
        if len(self._widgets) == 1:
            # Connect signals to slots for thread-safe callbacks
            self.device_change_requested.connect(self._on_device_change)
            self.volume_change_requested.connect(self._on_volume_change)
            self._register_callbacks()

    def unregister_widget(self, widget):
        """Unregister a widget from the shared service."""
        if widget in self._widgets:
            self._widgets.remove(widget)
            # Unregister callbacks when no widgets remain
            if not self._widgets:
                self._unregister_callbacks()

    def _register_callbacks(self):
        """Register shared pycaw callbacks."""
        try:
            # Device change callback
            if self._enumerator and not self._device_callback:
                self._device_callback = _SharedDeviceCallback(self)
                self._enumerator.RegisterEndpointNotificationCallback(self._device_callback)

            # Volume change callback
            if self._microphone_interface and not self._volume_callback:
                self._volume_callback = _SharedVolumeCallback(self)
                self._microphone_interface.RegisterControlChangeNotify(self._volume_callback)
        except Exception as e:
            logging.error(f"Failed to register shared callbacks: {e}")

    def _unregister_callbacks(self):
        """Unregister shared pycaw callbacks."""
        try:
            if self._device_callback and self._enumerator:
                self._enumerator.UnregisterEndpointNotificationCallback(self._device_callback)
                self._device_callback = None

            if self._volume_callback and self._microphone_interface:
                self._microphone_interface.UnregisterControlChangeNotify(self._volume_callback)
                self._volume_callback = None
        except Exception as e:
            logging.error(f"Failed to unregister shared callbacks: {e}")

    def _on_volume_change(self):
        """Notify all registered widgets of volume change."""
        for widget in self._widgets[:]:
            try:
                widget._update_label()
                # Update slider only if menu is open
                if hasattr(widget, "dialog") and widget.dialog and widget.dialog.isVisible():
                    widget._update_slider_value()
            except:
                pass

    def _on_device_change(self):
        """Notify all registered widgets of device change and reinitialize."""
        # Unregister old volume callback (device callback stays registered)
        if self._volume_callback and self._microphone_interface:
            try:
                self._microphone_interface.UnregisterControlChangeNotify(self._volume_callback)
            except:
                pass
            self._volume_callback = None

        # Get new default device
        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                device = AudioUtilities.CreateDevice(devices)
                self._microphone_interface = device.EndpointVolume
            else:
                self._microphone_interface = None
        except Exception:
            self._microphone_interface = None

        # Re-register volume callback if we have widgets and a device
        if self._widgets and self._microphone_interface:
            try:
                self._volume_callback = _SharedVolumeCallback(self)
                self._microphone_interface.RegisterControlChangeNotify(self._volume_callback)
            except Exception as e:
                logging.error(f"Failed to register volume callback: {e}")

        # Notify all widgets
        for widget in self._widgets[:]:
            try:
                widget._reinitialize_microphone()
            except:
                pass

    def get_microphone_interface(self):
        """Get the shared microphone interface."""
        return self._microphone_interface

    def get_microphone(self):
        """Get the current default microphone device."""
        try:
            mic_pointer = AudioUtilities.GetMicrophone()
            if mic_pointer:
                return AudioUtilities.CreateDevice(mic_pointer)
            return None
        except Exception as e:
            logging.debug(f"No microphone available: {e}")
            return None

    def get_all_devices(self):
        """Get all active microphone/input devices as list of (device_id, device_name) tuples."""
        try:
            devices_list = AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eCapture.value, device_state=DEVICE_STATE.ACTIVE.value
            )
            return [(device.id, device.FriendlyName) for device in devices_list]
        except Exception as e:
            logging.error(f"Failed to list microphone devices: {e}")
            return []

    def set_default_device(self, device_id: str):
        """Set the default microphone device."""
        try:
            AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole])
            return True
        except Exception as e:
            logging.error(f"Failed to set default microphone device: {e}")
            return False


class _SharedVolumeCallback(AudioEndpointVolumeCallback):
    """Shared callback for volume changes."""

    def __init__(self, service):
        super().__init__()
        self.service = service

    def on_notify(self, new_volume, new_mute, event_context, channels, channel_volumes):
        self.service.volume_change_requested.emit()


class _SharedDeviceCallback(MMNotificationClient):
    """Shared callback for device changes."""

    def __init__(self, service):
        super().__init__()
        self.service = service
        self._last_device_id = None
        self._last_state_changes = {}  # Track (device_id, state) to deduplicate

    def on_default_device_changed(self, flow, flow_id, role, role_id, default_device_id):
        """Handle default microphone device changes."""
        # Only care about capture (input) devices with console role
        if flow_id != EDataFlow.eCapture.value or role_id != ERole.eConsole.value:
            return

        # Only process if device actually changed (prevents spam during transitions)
        if default_device_id == self._last_device_id:
            return

        self._last_device_id = default_device_id
        self.service.device_change_requested.emit()

    def on_device_state_changed(self, device_id, new_state, new_state_id):
        # Only care about specific state changes
        if new_state_id in (DEVICE_STATE.DISABLED.value, DEVICE_STATE.ACTIVE.value, DEVICE_STATE.UNPLUGGED.value):
            # Deduplicate: only emit once per device+state combination
            if self._last_state_changes.get(device_id) == new_state_id:
                return

            self._last_state_changes[device_id] = new_state_id
            self.service.device_change_requested.emit()

import logging

from pycaw.callbacks import AudioEndpointVolumeCallback, MMNotificationClient
from pycaw.constants import DEVICE_STATE
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole
from PyQt6.QtCore import QObject, pyqtSignal

# Blacklist of process names to exclude from audio menu
BLACKLISTED_PROCESSES = [
    "taskhostw.exe",
    "audiodg.exe",
    "svchost.exe",
    "shellhost.exe",
    "shellexperiencehost.exe",
]


class AudioOutputService(QObject):
    """Singleton service that manages shared pycaw instances for all volume widgets."""

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
        self._volume_interface = None
        self._enumerator = None
        self._device_callback = None
        self._volume_callback = None

        # Initialize audio on first instance
        self._initialize_audio()

    def _initialize_audio(self):
        """Initialize the shared pycaw audio interface."""
        logging.info("AudioOutputService starting...")
        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
        except Exception as e:
            logging.error(f"AudioOutputService failed to initialize enumerator: {e}")
            self._volume_interface = None
            return

        try:
            devices = AudioUtilities.GetSpeakers()
            if devices:
                self._volume_interface = devices.EndpointVolume
            else:
                self._volume_interface = None
        except Exception:
            self._volume_interface = None

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
            if self._volume_interface and not self._volume_callback:
                self._volume_callback = _SharedVolumeCallback(self)
                self._volume_interface.RegisterControlChangeNotify(self._volume_callback)
        except Exception as e:
            logging.error(f"Failed to register shared callbacks: {e}")

    def _unregister_callbacks(self):
        """Unregister shared pycaw callbacks."""
        try:
            if self._device_callback and self._enumerator:
                self._enumerator.UnregisterEndpointNotificationCallback(self._device_callback)
                self._device_callback = None

            if self._volume_callback and self._volume_interface:
                self._volume_interface.UnregisterControlChangeNotify(self._volume_callback)
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
        if self._volume_callback and self._volume_interface:
            try:
                self._volume_interface.UnregisterControlChangeNotify(self._volume_callback)
            except:
                pass
            self._volume_callback = None

        # Get new default device
        try:
            devices = AudioUtilities.GetSpeakers()
            self._volume_interface = devices.EndpointVolume if devices else None
        except Exception:
            self._volume_interface = None

        # Re-register volume callback if we have widgets and a device
        if self._widgets and self._volume_interface:
            try:
                self._volume_callback = _SharedVolumeCallback(self)
                self._volume_interface.RegisterControlChangeNotify(self._volume_callback)
            except Exception as e:
                logging.error(f"Failed to register volume callback: {e}")

        # Notify all widgets
        for widget in self._widgets[:]:
            try:
                widget._reinitialize_audio()
            except:
                pass

    def get_volume_interface(self):
        """Get the shared volume interface."""
        return self._volume_interface

    def get_all_devices(self):
        """Get all active audio output devices as list of (device_id, device_name) tuples."""
        try:
            devices_list = AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eRender.value, device_state=DEVICE_STATE.ACTIVE.value
            )
            return [(device.id, device.FriendlyName) for device in devices_list]
        except Exception as e:
            logging.error(f"Failed to list audio devices: {e}")
            return []

    def get_speakers(self):
        """Get the current default speakers/audio output device."""
        try:
            return AudioUtilities.GetSpeakers()
        except Exception as e:
            # This is expected when no audio devices are available
            logging.debug(f"No speakers available: {e}")
            return None

    def get_all_sessions(self):
        """Get all active audio sessions."""
        try:
            return AudioUtilities.GetAllSessions()
        except Exception as e:
            logging.error(f"Failed to get audio sessions: {e}")
            return []

    def set_default_device(self, device_id):
        """Set the default audio output device."""
        try:
            AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole])
            return True
        except Exception as e:
            logging.error(f"Failed to set default device: {e}")
            return False

    def get_active_audio_sessions(self, get_app_name_callback=None, format_name_callback=None):
        """
        Get all active audio sessions with deduplication.
        """
        sessions = []
        seen_sessions = {}

        try:
            devices = self.get_speakers()
            if not devices:
                return sessions

            sessions_enum = self.get_all_sessions()
            for session in sessions_enum:
                if not session.Process or not session.Process.name():
                    continue

                # Skip blacklisted processes
                if session.Process.name().lower() in [p.lower() for p in BLACKLISTED_PROCESSES]:
                    continue

                try:
                    pid = session.ProcessId
                    grouping_param = ""
                    try:
                        grouping_param = str(session.GroupingParam)
                    except:
                        pass

                    session_key = (pid, grouping_param)
                    if session_key in seen_sessions:
                        continue
                    seen_sessions[session_key] = True

                except Exception as e:
                    logging.debug(f"Failed to process session grouping: {e}")
                    continue

                # Get volume interface and basic info
                volume_interface = session.SimpleAudioVolume
                process_name = session.Process.name()
                process_pid = session.Process.pid

                # Get app name with priority: DisplayName -> callback -> formatted name
                app_name = None
                if session.DisplayName:
                    name = session.DisplayName.strip()
                    if name and not name.startswith("@") and not name.startswith("ms-resource:"):
                        app_name = name

                # Try callback for app name
                if not app_name and get_app_name_callback:
                    app_name = get_app_name_callback(process_pid)
                    if app_name:
                        app_name = app_name.strip() or None

                # Fall back to formatted process name
                if not app_name and format_name_callback:
                    app_name = format_name_callback(process_name)
                elif not app_name:
                    app_name = process_name
                sessions.append(
                    {
                        "name": process_name,
                        "app_name": app_name,
                        "volume_interface": volume_interface,
                        "session": session,
                        "pid": process_pid,
                    }
                )

        except Exception as e:
            logging.error(f"Failed to get audio sessions: {e}")

        # Sort by app name
        sessions.sort(key=lambda s: s["app_name"].lower())
        return sessions


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
        """Handle default output device changes."""
        # Only care about output (render) devices with console role
        if flow_id != EDataFlow.eRender.value or role_id != ERole.eConsole.value:
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

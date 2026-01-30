import logging
import threading

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

        self._widgets = []
        self._volume_interface = None
        self._enumerator = None
        self._device_callback = None
        self._volume_callback = None

        self._cached_speakers = None
        self._cached_devices = None
        self._cached_sessions = None
        self._cache_lock = threading.Lock()
        self._initializing = False
        self._speakers_checked = False

        logging.info("AudioOutputService starting...")
        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
        except Exception as e:
            logging.error(f"AudioOutputService failed to initialize: {e}")

    def _initialize_audio(self):
        """Fetch speakers, devices and sessions in background thread."""
        if self._initializing:
            return
        self._initializing = True

        def fetch():
            try:
                if self._cached_speakers is None:
                    speakers = AudioUtilities.GetSpeakers()
                    self._cached_speakers = speakers
                    if speakers and self._volume_interface is None:
                        self._volume_interface = speakers.EndpointVolume

                with self._cache_lock:
                    if self._cached_devices is None:
                        devices = AudioUtilities.GetAllDevices(
                            data_flow=EDataFlow.eRender.value, device_state=DEVICE_STATE.ACTIVE.value
                        )
                        self._cached_devices = [(d.id, d.FriendlyName) for d in devices]

                with self._cache_lock:
                    if self._cached_sessions is None:
                        self._cached_sessions = AudioUtilities.GetAllSessions()

            except Exception:
                pass
            finally:
                self._initializing = False

        threading.Thread(target=fetch, daemon=True).start()

    def _invalidate_cache(self):
        """Clear cached data when devices change."""
        with self._cache_lock:
            self._cached_speakers = None
            self._cached_devices = None
            self._cached_sessions = None
            self._speakers_checked = False

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

            volume = self.get_volume_interface()
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

            if self._volume_callback and self._volume_interface:
                self._volume_interface.UnregisterControlChangeNotify(self._volume_callback)
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
        self._invalidate_cache()

        if self._volume_callback and self._volume_interface:
            try:
                self._volume_interface.UnregisterControlChangeNotify(self._volume_callback)
            except:
                pass
            self._volume_callback = None

        self._volume_interface = None

        if self._widgets:
            volume = self.get_volume_interface()
            if volume:
                try:
                    self._volume_callback = _SharedVolumeCallback(self)
                    volume.RegisterControlChangeNotify(self._volume_callback)
                except Exception:
                    pass

        self._initialize_audio()

        for widget in self._widgets[:]:
            try:
                widget._reinitialize_audio()
            except:
                pass

    def get_volume_interface(self):
        """Get volume control interface."""
        if self._volume_interface is None:
            speakers = self.get_speakers()
            if speakers:
                try:
                    self._volume_interface = speakers.EndpointVolume
                except:
                    pass
        return self._volume_interface

    def get_all_devices(self):
        """List all active audio output devices."""
        with self._cache_lock:
            if self._cached_devices is not None:
                return self._cached_devices

        try:
            devices = AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eRender.value, device_state=DEVICE_STATE.ACTIVE.value
            )
            result = [(d.id, d.FriendlyName) for d in devices]
            with self._cache_lock:
                self._cached_devices = result
            return result
        except Exception:
            return []

    def get_speakers(self):
        """Get default audio output device."""
        if self._cached_speakers is not None:
            return self._cached_speakers
        if self._speakers_checked:
            return None

        self._speakers_checked = True
        try:
            result = AudioUtilities.GetSpeakers()
            self._cached_speakers = result
            return result
        except Exception:
            return None

    def get_all_sessions(self):
        """Get audio sessions."""
        with self._cache_lock:
            if self._cached_sessions is not None:
                result = self._cached_sessions
                self._cached_sessions = None
                return result

        try:
            return AudioUtilities.GetAllSessions()
        except Exception:
            return []

    def set_default_device(self, device_id):
        """Switch default audio output."""
        try:
            AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole])
            return True
        except Exception as e:
            logging.error(f"Failed to set default audio device: {e}")
            return False

    def get_active_audio_sessions(self, get_app_name_callback=None, format_name_callback=None):
        """Get running apps with audio, excluding system processes."""
        sessions = []
        seen = {}

        try:
            if not self.get_speakers():
                return sessions

            for session in self.get_all_sessions():
                if not session.Process or not session.Process.name():
                    continue

                proc_name = session.Process.name()
                if proc_name.lower() in [p.lower() for p in BLACKLISTED_PROCESSES]:
                    continue

                try:
                    grouping = ""
                    try:
                        grouping = str(session.GroupingParam)
                    except:
                        pass
                    key = (session.ProcessId, grouping)
                    if key in seen:
                        continue
                    seen[key] = True
                except:
                    continue

                app_name = None
                if session.DisplayName:
                    name = session.DisplayName.strip()
                    if name and not name.startswith("@") and not name.startswith("ms-resource:"):
                        app_name = name

                if not app_name and get_app_name_callback:
                    app_name = get_app_name_callback(session.Process.pid)
                    if app_name:
                        app_name = app_name.strip() or None

                if not app_name:
                    app_name = format_name_callback(proc_name) if format_name_callback else proc_name

                sessions.append(
                    {
                        "name": proc_name,
                        "app_name": app_name,
                        "volume_interface": session.SimpleAudioVolume,
                        "session": session,
                        "pid": session.Process.pid,
                    }
                )

        except Exception:
            pass

        sessions.sort(key=lambda s: s["app_name"].lower())
        return sessions


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
        self._last_state_changes = {}

    def on_default_device_changed(self, flow, flow_id, role, role_id, default_device_id):
        if flow_id != EDataFlow.eRender.value or role_id != ERole.eConsole.value:
            return
        if default_device_id == self._last_device_id:
            return
        self._last_device_id = default_device_id
        self.service.device_change_requested.emit()

    def on_device_state_changed(self, device_id, new_state, new_state_id):
        if new_state_id not in (DEVICE_STATE.DISABLED.value, DEVICE_STATE.ACTIVE.value, DEVICE_STATE.UNPLUGGED.value):
            return
        if self._last_state_changes.get(device_id) == new_state_id:
            return
        self._last_state_changes[device_id] = new_state_id
        self.service.device_change_requested.emit()

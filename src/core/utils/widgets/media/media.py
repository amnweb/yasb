import asyncio
import ctypes
import io
import logging
import re
import threading
from typing import Any, Callable

from PIL import Image, ImageFile
from pycaw.pycaw import AudioUtilities
from PyQt6.QtCore import QDateTime, QTimer
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSession as Session
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winrt.windows.media.control import (
    MediaPropertiesChangedEventArgs,
    PlaybackInfoChangedEventArgs,
    SessionsChangedEventArgs,
    TimelinePropertiesChangedEventArgs,
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference

from core.utils.utilities import Singleton
from settings import DEBUG

# Virtual Key Codes for media controls
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_NEXT_TRACK = 0xB0

# Windows constants for SendInput
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

# Windows constants for WM_APPCOMMAND (alternative approach)
WM_APPCOMMAND = 0x319
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
HWND_BROADCAST = 0xFFFF


# Define INPUT structure for SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]


# Make PIL logger not pollute logs
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


# Mock classes for fallback mode
class MockMediaControls:
    """Mock controls object for fallback mode - all controls enabled"""

    def __init__(self):
        self.is_play_pause_toggle_enabled = True
        self.is_previous_enabled = True
        self.is_next_enabled = True
        self.is_playback_position_enabled = False  # No seeking in fallback mode


class MockPlaybackInfo:
    """Mock playback info for fallback mode"""

    def __init__(self, initial_playing=False):
        # 3 = Paused, 4 = Playing
        self.playback_status = 4 if initial_playing else 3
        self.controls = MockMediaControls()

    def toggle_playback_status(self):
        """Toggle between playing and paused"""
        if self.playback_status == 3:  # Was paused
            self.playback_status = 4  # Now playing
        else:  # Was playing
            self.playback_status = 3  # Now paused


class WindowsMedia(metaclass=Singleton):
    """
    Use double thread for media info because I expect subscribers to take some time, and I don't know if holding up the callback from windsdk is a problem.
    To also not create and manage too many threads, I made the others direct callbacks
    """

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session_manager: SessionManager = None
        self._current_session: Session = None
        self._current_session_lock = threading.RLock()

        self._event_loop = asyncio.new_event_loop()

        self._media_info_lock = threading.RLock()
        self._media_info = None

        self._playback_info_lock = threading.RLock()
        self._playback_info = None

        self._timeline_info_lock = threading.RLock()
        self._timeline_info = None

        self._subscription_channels = {
            channel: []
            for channel in ["media_info", "playback_info", "timeline_info", "session_status", "timeline_interpolated"]
        }
        self._subscription_channels_lock = threading.RLock()
        self._registration_tokens = {}

        # Add timeline interpolation properties
        self._timeline_info = None
        self._last_position = 0
        self._last_update_time = 0
        self._duration = 0
        self._is_playing = False

        # Fallback mode flag - True when using direct media key controls
        self._fallback_mode = False

        # Fallback mode state tracking
        self._last_has_media_app = False
        self._last_is_playing = False
        self._is_browser_media = False  # Track if media is from browser
        self._fallback_manual_state = False  # Manual play/pause state tracking for fallback

        # Create a timer for interpolation
        self._interpolation_timer = QTimer()
        self._interpolation_timer.setInterval(200)
        self._interpolation_timer.timeout.connect(self._interpolate_timeline)
        self._interpolation_timer.start()

        # Create a timer for fallback mode media detection
        self._fallback_detection_timer = QTimer()
        self._fallback_detection_timer.setInterval(250)  # Check every 250ms for responsive updates
        self._fallback_detection_timer.timeout.connect(self._check_fallback_media_state)

        self._run_setup()

    def force_update(self):
        if self._session_manager is not None:
            self._on_current_session_changed(self._session_manager, None)
        elif self._fallback_mode:
            # In fallback mode, manually trigger callbacks to update widgets
            with self._subscription_channels_lock:
                session_callbacks = self._subscription_channels.get("session_status", [])
                media_callbacks = self._subscription_channels.get("media_info", [])

            for callback in session_callbacks:
                callback(True)

            for callback in media_callbacks:
                callback(self._media_info)

    def subscribe(self, callback: Callable, channel: str):
        with self._subscription_channels_lock:
            try:
                self._subscription_channels[channel].append(callback)
            except KeyError:
                raise ValueError(
                    f"Incorrect channel subscription type provided ({channel}). "
                    f"Valid options are {list(self._subscription_channels.keys())}"
                )

        # Auto-send current data if available
        if channel == "timeline_interpolated" and hasattr(self, "_last_position"):
            callback({"position": self._last_position, "duration": self._duration})

    def stop(self):
        # Clear subscriptions
        with self._subscription_channels_lock:
            self._subscription_channels = {k: [] for k in self._subscription_channels.keys()}

        with self._current_session_lock:
            session = self._current_session

        # Remove all our subscriptions
        if session is not None:
            session.remove_media_properties_changed(self._registration_tokens["media_info"])
            session.remove_timeline_properties_changed(self._registration_tokens["timeline_info"])
            session.remove_playback_info_changed(self._registration_tokens["playback_info"])

    def _register_session_callbacks(self):
        with self._current_session_lock:
            self._registration_tokens["playback_info"] = self._current_session.add_playback_info_changed(
                self._on_playback_info_changed
            )
            self._registration_tokens["timeline_info"] = self._current_session.add_timeline_properties_changed(
                self._on_timeline_properties_changed
            )
            self._registration_tokens["media_info"] = self._current_session.add_media_properties_changed(
                self._on_media_properties_changed
            )

    @staticmethod
    def _get_browser_media_windows():
        """
        Check if any browser window has a media-playing page open.
        Returns True if a browser window title contains YouTube, Spotify, SoundCloud, etc.
        """
        media_patterns = [
            r"youtube",
            r"spotify",
            r"soundcloud",
            r"twitch",
            r"netflix",
            r"amazon prime",
            r"disney\+",
            r"apple music",
            r"tidal",
            r"deezer",
            r"pandora",
        ]

        found_media_window = False

        def enum_windows_callback(hwnd, _):
            nonlocal found_media_window
            try:
                # Get window title
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True

                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()

                # Check if title matches any media pattern
                if title and any(re.search(pattern, title) for pattern in media_patterns):
                    found_media_window = True
                    return False  # Stop enumeration
            except Exception:
                pass
            return True

        # Enumerate all windows
        try:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
        except Exception as e:
            logging.debug(f"Error enumerating windows: {e}")

        return found_media_window

    def _check_fallback_media_state(self):
        """Periodically check media state in fallback mode and notify if changed."""
        if not self._fallback_mode:
            return

        has_media_app, is_playing, is_browser = self._detect_audio_playing()

        # Get track info from Spotify window title if available
        track_info_changed = False
        if has_media_app and self._is_process_running("spotify.exe"):
            title = self._get_spotify_window_title()
            if title:
                artist, track = self._parse_spotify_title(title)
                logging.debug(f"Parsed: artist='{artist}', track='{track}'")
                with self._media_info_lock:
                    current_artist = self._media_info.get("artist", "")
                    current_title = self._media_info.get("title", "")
                    if artist != current_artist or track != current_title:
                        self._media_info["artist"] = artist
                        self._media_info["title"] = track
                        track_info_changed = True
                        logging.info(f"Track info updated: {artist} - {track}")

        # Check if state has changed
        if (has_media_app != self._last_has_media_app or
            is_playing != self._last_is_playing or
            is_browser != self._is_browser_media or
            track_info_changed):

            if has_media_app != self._last_has_media_app or is_playing != self._last_is_playing or is_browser != self._is_browser_media:
                self._log.info(
                    f"Fallback state changed: has_media_app={has_media_app}, is_playing={is_playing}, is_browser={is_browser} "
                    f"(was: {self._last_has_media_app}, {self._last_is_playing}, {self._is_browser_media})"
                )

            # Update stored state
            self._last_has_media_app = has_media_app
            self._last_is_playing = is_playing
            self._is_browser_media = is_browser

            # Update media info with new state
            with self._media_info_lock:
                self._media_info["_has_media_app"] = has_media_app
                self._media_info["_initial_playing"] = is_playing

            # Update playback info
            with self._playback_info_lock:
                self._playback_info.playback_status = 4 if is_playing else 3

            # Notify subscribers of the change
            with self._subscription_channels_lock:
                media_callbacks = self._subscription_channels.get("media_info", [])

            for callback in media_callbacks:
                callback(self._media_info)

    @staticmethod
    def _is_process_running(process_name):
        """Check if a process is currently running."""
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False

    @staticmethod
    def _get_spotify_window_title():
        """Get the title of the Spotify window to determine playback state."""
        try:
            all_titles = []  # All Spotify windows including hidden ones
            visible_titles = []  # Only visible windows

            def enum_windows_callback(hwnd, lParam):
                try:
                    # Get the process ID for this window
                    process_id = ctypes.c_ulong()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

                    # Open the process to get its name
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
                    if h_process:
                        try:
                            # Get the process name
                            process_name_buffer = ctypes.create_unicode_buffer(260)
                            size = ctypes.c_ulong(260)
                            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, process_name_buffer, ctypes.byref(size)):
                                process_path = process_name_buffer.value
                                process_name = process_path.split('\\')[-1].lower()

                                # Check if this is Spotify
                                if process_name == "spotify.exe":
                                    # Get window title
                                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                                    if length > 0:
                                        buff = ctypes.create_unicode_buffer(length + 1)
                                        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                                        title = buff.value

                                        # Skip GDI+ and IME helper windows
                                        if title and ("gdi+" in title.lower() or "msctfime" in title.lower()):
                                            return True

                                        if title:
                                            # Get class name and visibility
                                            class_buff = ctypes.create_unicode_buffer(256)
                                            ctypes.windll.user32.GetClassNameW(hwnd, class_buff, 256)
                                            class_name = class_buff.value
                                            is_visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))

                                            # Store all windows for analysis
                                            all_titles.append((title, class_name, is_visible))
                                            visible_titles.append(title)
                        finally:
                            ctypes.windll.kernel32.CloseHandle(h_process)

                except Exception as e:
                    logging.debug(f"Error in enum callback: {e}")
                    pass
                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

            # Prioritize windows with track info (contain " - ")
            track_windows = [t for t in visible_titles if " - " in t and t.lower() not in ["spotify premium", "spotify free"]]
            if track_windows:
                return max(track_windows, key=len)

            # Otherwise return the longest title
            if visible_titles:
                return max(visible_titles, key=len)

            return None
        except Exception as e:
            logging.debug(f"Error getting Spotify window title: {e}")
            return None

    @staticmethod
    def _is_spotify_playing_from_title(title):
        """Determine if Spotify is playing based on window title."""
        if not title:
            return False

        title_lower = title.strip().lower()

        # If title is just "Spotify" or "Spotify Premium/Free", it's paused/idle
        if title_lower in ["spotify", "spotify premium", "spotify free"]:
            return False

        # If title contains song info (e.g., "Song Name - Artist"), it's playing
        # Spotify shows song info when playing, just "Spotify" when paused
        if " - " in title and "spotify" in title_lower:
            return True

        return False

    @staticmethod
    def _parse_spotify_title(title):
        """
        Parse Spotify window title to extract artist and track name.
        Format: "Artist - Track Title" or just "Spotify Premium/Free" when idle.
        Returns: (artist, track) tuple
        """
        if not title:
            return ("Unknown Artist", "Unknown Track")

        title = title.strip()

        # If title is just "Spotify" or "Spotify Premium/Free", no track loaded
        # Show Spotify Premium/Free as the title
        if title.lower() in ["spotify", "spotify premium", "spotify free"]:
            return ("Spotify", title)

        # Try to split by " - " to get artist and track
        # Format is usually "Artist - Track Title"
        if " - " in title:
            parts = title.split(" - ", 1)  # Split only on first occurrence
            if len(parts) == 2:
                artist = parts[0].strip()
                track = parts[1].strip()
                return (artist, track)

        # Fallback: use title as track name
        return ("Spotify", title)

    @staticmethod
    def _detect_audio_playing():
        """
        Detect if any desktop media player is currently active using pycaw audio sessions.
        Uses per-session audio peak detection (like cava) to detect playback state.
        Returns tuple: (has_media_app, is_playing, is_browser)
        - has_media_app: True if a desktop media app is detected
        - is_playing: True if audio is actively playing (peak > threshold)
        - is_browser: Always False (browser support removed for simplicity)
        """
        # Desktop media applications only
        DESKTOP_MEDIA_APPS = [
            "spotify.exe",
            "vlc.exe",
            "wmplayer.exe",
            "groove.exe",
            "itunes.exe",
            "musicbee.exe",
            "foobar2000.exe",
            "aimp.exe",
            "winamp.exe",
            "mediaplayer.exe",
            "potplayer.exe",
            "mpc-hc64.exe",
            "mpc-hc.exe",
        ]

        VOLUME_THRESHOLD = 0.05  # Ignore very quiet sessions
        PEAK_THRESHOLD = 0.01    # Peak threshold for detecting active audio playback

        try:
            from pycaw.pycaw import AudioUtilities
            from comtypes import GUID, COMMETHOD, POINTER as COM_POINTER
            from comtypes import IUnknown, HRESULT
            from ctypes import c_float

            # Define IAudioMeterInformation interface manually
            # This is part of Windows Core Audio API but not exposed by pycaw
            class IAudioMeterInformation(IUnknown):
                _iid_ = GUID('{C02216F6-8C67-4B5B-9D00-D008E73E0064}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'GetPeakValue',
                              (['out'], COM_POINTER(c_float), 'pfPeak')),
                    COMMETHOD([], HRESULT, 'GetMeteringChannelCount',
                              (['out'], COM_POINTER(c_float), 'pnChannelCount')),
                    COMMETHOD([], HRESULT, 'GetChannelsPeakValues',
                              (['in'], c_float, 'u32ChannelCount'),
                              (['out'], COM_POINTER(c_float), 'afPeakValues')),
                    COMMETHOD([], HRESULT, 'QueryHardwareSupport',
                              (['out'], COM_POINTER(c_float), 'pdwHardwareSupportMask')),
                ]

            sessions = AudioUtilities.GetAllSessions()

            # Find desktop media app sessions
            media_app_session_obj = None
            media_app_process_name = None

            for session in sessions:
                if session.Process and session.Process.name():
                    process_name = session.Process.name().lower()

                    # Check for desktop media apps only
                    if any(app.lower() == process_name for app in DESKTOP_MEDIA_APPS):
                        # Check session volume
                        try:
                            volume = session.SimpleAudioVolume
                            if volume and volume.GetMasterVolume() > VOLUME_THRESHOLD:
                                # Found media app with volume - store the session object
                                media_app_session_obj = session
                                media_app_process_name = process_name
                                break
                        except Exception:
                            pass

            # If we found a media app session, check its audio peak
            if media_app_session_obj:
                process_name = media_app_process_name
                is_playing = False

                try:
                    # Get the audio meter for this specific session
                    # This detects audio ONLY from this app, not global system audio
                    meter = media_app_session_obj._ctl.QueryInterface(IAudioMeterInformation)

                    if meter:
                        peak = meter.GetPeakValue()
                        is_playing = peak > PEAK_THRESHOLD
                        logging.debug(f"Detection: {process_name} peak={peak:.6f} → playing={is_playing}")
                    else:
                        # Fallback if meter not available
                        is_playing = True
                        logging.debug(f"Detection: {process_name} volume OK, no meter → assuming playing")

                except Exception as e:
                    # If peak detection fails, assume playing if session has volume
                    is_playing = True
                    logging.debug(f"Detection: {process_name} peak detection failed ({e}) → assuming playing")

                return (True, is_playing, False)

            # No audio session found, but check if Spotify is running as a process
            if WindowsMedia._is_process_running("spotify.exe"):
                # Spotify is running but has no audio session yet (not playing)
                logging.debug(f"Detection: Spotify process found (no audio session) → not playing")
                return (True, False, False)

            # No media app found
            return (False, False, False)
        except Exception as e:
            logging.debug(f"Could not detect audio playing state: {e}")
            return (False, False, False)

    async def _get_session_manager(self):
        return await SessionManager.request_async()

    def _run_setup(self):
        try:
            self._session_manager = asyncio.run(self._get_session_manager())
            self._session_manager.add_current_session_changed(self._on_current_session_changed)

            # Manually trigger the callback on startup
            self._on_current_session_changed(self._session_manager, None, is_setup=True)
        except OSError as e:
            # Handle WinRT API unavailability gracefully
            # Error -2147221164 (0x80040154): Class/Interface not registered
            # This can occur when:
            # - Windows Media components are not available
            # - Running in a custom shell environment without media services
            # - System COM registration issues
            self._log.warning(
                f"Failed to initialize Windows Media Session Manager: {e}. "
                "Switching to fallback mode with basic media controls. "
                "Full media information will not be available."
            )
            self._session_manager = None
            self._fallback_mode = True

            # Detect if media player is active and if audio is playing
            has_media_app, is_audio_playing, is_browser = self._detect_audio_playing()
            self._log.info(f"Fallback mode: has_media_app={has_media_app}, is_playing={is_audio_playing}, is_browser={is_browser}")

            # Store initial state for comparison
            self._last_has_media_app = has_media_app
            self._last_is_playing = is_audio_playing
            self._is_browser_media = is_browser

            # Get initial track info from Spotify if available
            artist = "Fallback Mode"
            title = "Controls Only"
            if has_media_app and self._is_process_running("spotify.exe"):
                window_title = self._get_spotify_window_title()
                if window_title:
                    artist, title = self._parse_spotify_title(window_title)

            # Set basic media info structure for fallback mode
            self._media_info = {
                "title": title,
                "artist": artist,
                "album_title": None,
                "thumbnail": None,
                "_fallback_mode": True,  # Flag to indicate fallback mode
                "_has_media_app": has_media_app,  # Whether a media app is detected
                "_initial_playing": is_audio_playing,  # Pass initial state to widget
            }
            # Create mock playback info with correct initial state
            self._playback_info = MockPlaybackInfo(initial_playing=is_audio_playing)
            self._timeline_info = {}

            # Notify subscribers that we're in fallback mode with basic controls available
            with self._subscription_channels_lock:
                session_callbacks = self._subscription_channels.get("session_status", [])
                media_callbacks = self._subscription_channels.get("media_info", [])

            # Notify session status - controls are available
            for callback in session_callbacks:
                callback(True)

            # Notify media info - send basic fallback info with flag
            for callback in media_callbacks:
                callback(self._media_info)

            # Start periodic detection timer for fallback mode
            self._fallback_detection_timer.start()
            self._log.info("Started fallback mode media detection timer")

    def _on_current_session_changed(
        self,
        manager: SessionManager,
        args: SessionsChangedEventArgs,
        is_setup=False,
        is_overridden=False,
    ):
        with self._current_session_lock:
            if not is_overridden:
                self._current_session = manager.get_current_session()

            if self._current_session is not None:
                # If the current session is not None, register callbacks
                self._register_session_callbacks()

                if not is_setup:
                    self._on_playback_info_changed(self._current_session, None)
                    self._on_timeline_properties_changed(self._current_session, None)
                    self._on_media_properties_changed(self._current_session, None)
            else:
                # Clear media info when there's no active session
                self._media_info = None
                self._playback_info = None
                self._timeline_info = None
                self._last_position = 0
                self._duration = 0
                if DEBUG:
                    logging.debug("MediaCallback: No active session")
            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels["session_status"]

            for callback in callbacks:
                callback(self._current_session is not None)

    def _current_session_only(fn):
        """
        Decorator to ensure that the function is only called if the session is the same as the current session
        """
        if asyncio.iscoroutinefunction(fn):

            async def wrapper(self: "WindowsMedia", session: Session, *args, **kwargs):
                with self._current_session_lock:
                    if self._are_same_sessions(session, self._current_session):
                        return await fn(self, session, *args, **kwargs)
                    return None  # Return None without awaiting
        else:

            def wrapper(self: "WindowsMedia", session: Session, *args, **kwargs):
                with self._current_session_lock:
                    if self._are_same_sessions(session, self._current_session):
                        return fn(self, session, *args, **kwargs)
                    return None

        return wrapper
        # def wrapper(self: "WindowsMedia", session: Session, *args, **kwargs):
        #     with self._current_session_lock:
        #         if self._are_same_sessions(session, self._current_session):
        #             return fn(self, session, *args, **kwargs)
        # return wrapper

    @_current_session_only
    def _on_playback_info_changed(self, session: Session, args: PlaybackInfoChangedEventArgs):
        with self._playback_info_lock:
            self._playback_info = session.get_playback_info()

            # Track play state for interpolation
            self._is_playing = self._playback_info.playback_status == 4  # 4 = Playing

            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels["playback_info"]

            # Perform callbacks
            for callback in callbacks:
                callback(self._playback_info)

    @_current_session_only
    def _on_timeline_properties_changed(self, session: Session, args: TimelinePropertiesChangedEventArgs):
        with self._timeline_info_lock:
            self._timeline_info = session.get_timeline_properties()
            # Store values for interpolation
            self._last_position = self._timeline_info.position.total_seconds()
            self._last_update_time = QDateTime.currentMSecsSinceEpoch()
            self._duration = self._timeline_info.end_time.total_seconds()

            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels["timeline_info"]

            # Perform callbacks
            for callback in callbacks:
                callback(self._timeline_info)

    @_current_session_only
    def _on_media_properties_changed(self, session: Session, args: MediaPropertiesChangedEventArgs):
        with self._media_info_lock:
            try:
                try:
                    running_loop = asyncio.get_running_loop()

                    async def process_media_and_check():
                        await self._update_media_properties(session)
                        if self._media_info and self._is_media_info_empty(self._media_info):
                            if self._session_manager is not None:
                                sessions = self._session_manager.get_sessions()
                                if not any(
                                    self._are_same_sessions(sessions[i], self._current_session)
                                    for i in range(sessions.size)
                                ):
                                    self.switch_session(1)

                    running_loop.create_task(process_media_and_check())

                except RuntimeError:
                    self._event_loop.run_until_complete(self._update_media_properties(session))

                    if self._media_info and self._is_media_info_empty(self._media_info):
                        if self._session_manager is not None:
                            sessions = self._session_manager.get_sessions()
                            if not any(
                                self._are_same_sessions(sessions[i], self._current_session)
                                for i in range(sessions.size)
                            ):
                                self.switch_session(1)

            except Exception as e:
                self._log.error(f"Error in _on_media_properties_changed: {e}")

    @_current_session_only
    async def _update_media_properties(self, session: Session):
        try:
            media_info = await session.try_get_media_properties_async()

            media_info = self._properties_2_dict(media_info)

            if media_info["thumbnail"] is not None:
                media_info["thumbnail"] = await self.get_thumbnail(media_info["thumbnail"])

        except Exception as e:
            self._log.error(f"MediaCallback: Error occurred whilst fetching media properties and thumbnail: {e}")
            return

        self._media_info = media_info

        # Get subscribers
        with self._subscription_channels_lock:
            callbacks = self._subscription_channels["media_info"]

        # Perform callbacks
        for callback in callbacks:
            callback(self._media_info)

    @staticmethod
    def _properties_2_dict(obj) -> dict[str, Any]:
        return {name: getattr(obj, name) for name in dir(obj) if not name.startswith("_")}

    @staticmethod
    async def get_thumbnail(thumbnail_stream_reference: IRandomAccessStreamReference) -> ImageFile:
        """
        Read the thumbnail for the IRandomAccessStreamReference and return it as PIL ImageFile
        :param thumbnail_stream_reference: Thumbnail stream reference
        :return: Loaded thumbnail
        """
        # Read the stream into the buffer
        readable_stream = await thumbnail_stream_reference.open_read_async()
        try:
            # Create buffer of stream size
            thumb_read_buffer = Buffer(readable_stream.size)

            # Read stream into buffer
            await readable_stream.read_async(
                thumb_read_buffer, thumb_read_buffer.capacity, InputStreamOptions.READ_AHEAD
            )

            # Convert bytearray to pillow image
            pillow_image = Image.open(io.BytesIO(thumb_read_buffer))

            # Remove buffer
            del thumb_read_buffer

            return pillow_image
        except Exception as e:
            logging.error(f"get_thumbnail(): Error occurred when loading the thumbnail: {e}")
            return None
        finally:
            # Close the stream
            readable_stream.close()

    @staticmethod
    def _is_media_info_empty(media_info: dict[str, Any]) -> bool:
        keys = [
            "album_artist",
            "album_title",
            "album_track_count",
            "artist",
            "playback_type",
            "subtitle",
            "title",
            "track_number",
        ]
        # Check if all keys have 'zero' values
        return all(not media_info.get(key) for key in keys)

    def _are_same_sessions(self, session1: Session, session2: Session) -> bool:
        if session1 is None or session2 is None:
            return session1 is session2
        return session1.source_app_user_model_id == session2.source_app_user_model_id

    @staticmethod
    def _send_media_key_sendinput(vk_code: int):
        """
        Send media key using SendInput (physical key simulation).
        Works better for browsers than WM_APPCOMMAND.
        """
        try:
            logging.info(f"Sending media key via SendInput: VK 0x{vk_code:X}")

            # Key down
            input_down = INPUT()
            input_down.type = INPUT_KEYBOARD
            input_down.ki.wVk = vk_code
            input_down.ki.dwFlags = KEYEVENTF_EXTENDEDKEY

            # Key up
            input_up = INPUT()
            input_up.type = INPUT_KEYBOARD
            input_up.ki.wVk = vk_code
            input_up.ki.dwFlags = KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP

            # Send both events
            inputs = (INPUT * 2)(input_down, input_up)
            result = ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(INPUT))

            if result == 2:
                logging.info(f"SendInput successful for VK 0x{vk_code:X}")
            else:
                logging.error(f"SendInput failed: sent {result}/2, error: {ctypes.get_last_error()}")
        except Exception as e:
            logging.error(f"Failed to send media key via SendInput: {e}")

    @staticmethod
    def _send_media_key(vk_code: int, use_sendinput: bool = False):
        """
        Send a media command using WM_APPCOMMAND or SendInput.

        Args:
            vk_code: Virtual key code for the media key
            use_sendinput: If True, use SendInput (for browsers), else use WM_APPCOMMAND (for desktop apps)
        """
        if use_sendinput:
            WindowsMedia._send_media_key_sendinput(vk_code)
            return

        try:
            # Map VK codes to APPCOMMAND constants
            appcommand_map = {
                VK_MEDIA_PLAY_PAUSE: APPCOMMAND_MEDIA_PLAY_PAUSE,
                VK_MEDIA_NEXT_TRACK: APPCOMMAND_MEDIA_NEXTTRACK,
                VK_MEDIA_PREV_TRACK: APPCOMMAND_MEDIA_PREVIOUSTRACK,
            }

            appcommand = appcommand_map.get(vk_code)
            if appcommand is None:
                logging.error(f"Unknown media key: {vk_code}")
                return

            logging.info(f"Sending WM_APPCOMMAND: {appcommand} (VK: 0x{vk_code:X})")

            # Use PostMessage instead of SendMessage to avoid blocking/deadlock
            # lParam = appcommand << 16 | device << 12 | keys
            lParam = appcommand << 16
            result = ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, lParam)

            if result:
                logging.info("WM_APPCOMMAND posted successfully")
            else:
                logging.error(f"PostMessage failed, error code: {ctypes.get_last_error()}")
        except Exception as e:
            logging.error(f"Failed to send media command {vk_code}: {e}")
            import traceback

            traceback.print_exc()

    def switch_session(self, direction: int):
        if self._session_manager is None:
            return
        sessions = self._session_manager.get_sessions()
        if len(sessions) == 0:
            return

        with self._current_session_lock:
            current_session_idx = -1
            for i, session in enumerate(sessions):
                if self._current_session is None or self._are_same_sessions(session, self._current_session):
                    current_session_idx = i
                    break

            idx = (current_session_idx + direction) % len(sessions)
            if self._are_same_sessions(sessions[idx], self._current_session):
                return
            self._current_session = sessions[idx]

        self._on_current_session_changed(self._session_manager, None, is_overridden=True)

    def play_pause(self):
        """Toggle play/pause. Uses fallback mode with media keys if Session Manager unavailable."""
        logging.info(f"play_pause() called, fallback_mode={self._fallback_mode}, is_browser={self._is_browser_media}")
        if self._fallback_mode:
            # Use WM_APPCOMMAND (SendInput is blocked by UIPI)
            # Icon updates automatically via detection timer
            self._send_media_key(VK_MEDIA_PLAY_PAUSE, use_sendinput=False)
            return

        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.try_toggle_play_pause_async()

    def prev(self):
        """Skip to previous track. Uses fallback mode with media keys if Session Manager unavailable."""
        logging.info(f"prev() called, fallback_mode={self._fallback_mode}, is_browser={self._is_browser_media}")
        if self._fallback_mode:
            self._send_media_key(VK_MEDIA_PREV_TRACK, use_sendinput=False)
            return

        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.try_skip_previous_async()

    def next(self):
        """Skip to next track. Uses fallback mode with media keys if Session Manager unavailable."""
        logging.info(f"next() called, fallback_mode={self._fallback_mode}, is_browser={self._is_browser_media}")
        if self._fallback_mode:
            self._send_media_key(VK_MEDIA_NEXT_TRACK, use_sendinput=False)
            return

        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.try_skip_next_async()

    def _interpolate_timeline(self):
        """Interpolate timeline between official updates from the Windows API."""
        if not self._is_playing or self._last_update_time == 0 or self._timeline_info is None:
            return

        # Calculate elapsed time since last update
        elapsed = (QDateTime.currentMSecsSinceEpoch() - self._last_update_time) / 1000

        # Estimate current position
        estimated_position = self._last_position + elapsed

        # Don't go beyond duration
        if self._duration > 0 and estimated_position > self._duration:
            estimated_position = self._duration

        # Create a new timeline info object with interpolated values
        interpolated_timeline = self._timeline_info

        # Notify subscribers with interpolated timeline data
        if interpolated_timeline is not None:
            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels.get("timeline_interpolated", [])

            # Perform callbacks
            for callback in callbacks:
                callback({"position": estimated_position, "duration": self._duration})

    def seek_to_position(self, position: float):
        """Seek to specific position in seconds."""
        try:
            with self._current_session_lock:
                if self._current_session is not None:
                    # Convert seconds to 100-nanosecond units (required by the Windows API)
                    position_in_100ns = int(position * 10000000)
                    self._current_session.try_change_playback_position_async(position_in_100ns)
                    # Update last known position for interpolation
                    self._last_position = position
                    self._last_update_time = QDateTime.currentMSecsSinceEpoch()
        except Exception as e:
            self._log.error(f"Error seeking to position: {e}")

    def is_seek_supported(self):
        with self._playback_info_lock:
            if self._playback_info and hasattr(self._playback_info, "controls"):
                return self._playback_info.controls.is_playback_position_enabled
        return False

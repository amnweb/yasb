import asyncio
import ctypes
import io
import logging
import re
import time
from functools import partial
from typing import Any, Callable

from PIL import Image
from pycaw.pycaw import AudioUtilities
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from qasync import asyncSlot  # type: ignore
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSession,
    GlobalSystemMediaTransportControlsSessionPlaybackInfo,
)
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winrt.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference

from core.utils.utilities import QSingleton

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)

type MediaSession = GlobalSystemMediaTransportControlsSession
type MediaPlaybackInfo = GlobalSystemMediaTransportControlsSessionPlaybackInfo

logger = logging.getLogger("WindowsMedia")

REFRESH_INTERVAL = 0.1
FALLBACK_CHECK_INTERVAL = 0.25  # 250ms for responsive fallback updates

# Virtual Key Codes for media controls
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_NEXT_TRACK = 0xB0

# Windows constants for SendInput
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

# Windows constants for WM_APPCOMMAND (more reliable than SendInput for media keys)
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
        self.playback_rate = 1.0
        self.controls = MockMediaControls()

    def toggle_playback_status(self):
        """Toggle between playing and paused"""
        if self.playback_status == 3:  # Was paused
            self.playback_status = 4  # Now playing
        else:  # Was playing
            self.playback_status = 3  # Now paused


class MockSession:
    """Mock session object for fallback mode"""

    def __init__(self, app_id: str):
        self.source_app_user_model_id = app_id


class SessionState:
    """Session state container for media info and cleanup callbacks"""

    def __init__(self, app_id: str):
        self.app_id = app_id
        self.title = ""
        self.artist = ""
        self.last_snapshot_pos = 0.0
        self.last_update_time = 0.0
        self.duration = 0.0
        self.current_pos = 0.0
        self.is_playing = False
        self.playback_rate = 1.0
        self.is_current = False
        self.timeline_enabled = False
        self.thumbnail: Image.Image | None = None
        self.cleanup_callbacks: list[Callable[..., None]] = []
        self.session: MediaSession | None = None
        self.playback_info: MediaPlaybackInfo | None = None


class WindowsMedia(QObject, metaclass=QSingleton):
    """Windows Media Control singleton"""

    media_data_changed = pyqtSignal(dict)
    current_session_changed = pyqtSignal()
    media_properties_changed = pyqtSignal()
    timeline_info_changed = pyqtSignal()
    playback_info_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._loop = asyncio.get_running_loop()
        self._running = False

        self._trackers: dict[str, SessionState] = {}
        self._current_session_id: str = ""

        # Fallback mode state
        self._fallback_mode = False
        self._fallback_timer: QTimer | None = None
        self._fallback_app_id = "FallbackMedia"
        self._fallback_is_playing = False
        self._fallback_title = ""
        self._fallback_artist = ""

        self._loop.create_task(self.run())

    @property
    def current_session(self) -> SessionState | None:
        """Get the current session state"""
        return self._trackers.get(self._current_session_id)

    async def run(self):
        """Start the WindowsMedia worker"""
        self._running = True
        try:
            manager = await SessionManager.request_async()
            await self._refresh_sessions(manager)

            manager.add_sessions_changed(self._create_callback_bridge(self._refresh_sessions))
            manager.add_current_session_changed(self._create_callback_bridge(self._on_current_session_changed))

            await self._on_current_session_changed(manager)

            # Start the refresh loop
            while self._running:
                self._interpolate_and_emit(self._trackers)
                await asyncio.sleep(REFRESH_INTERVAL)
        except Exception as e:
            logger.warning(f"Windows Media Session Manager unavailable: {e}")
            logger.info("Activating fallback mode with direct media controls")
            self._activate_fallback_mode()

    async def stop(self):
        """Stop the WindowsMedia worker refresh loop"""
        self._running = False
        if self._fallback_timer:
            self._fallback_timer.stop()

    def _activate_fallback_mode(self):
        """Activate fallback mode using direct audio detection"""
        self._fallback_mode = True
        logger.info("Fallback mode activated - using direct media key controls")

        # Create fallback session
        state = SessionState(self._fallback_app_id)
        state.session = MockSession(self._fallback_app_id)
        state.playback_info = MockPlaybackInfo(initial_playing=False)
        state.is_current = True
        self._trackers[self._fallback_app_id] = state
        self._current_session_id = self._fallback_app_id

        # Start fallback update timer
        self._fallback_timer = QTimer(self)  # Set parent to self
        self._fallback_timer.timeout.connect(self._check_fallback_media_state)
        interval_ms = int(FALLBACK_CHECK_INTERVAL * 1000)
        self._fallback_timer.start(interval_ms)
        logger.info(f"Fallback timer started with interval {interval_ms}ms")

        # Emit initial signals
        self.media_data_changed.emit(self._trackers)
        self.current_session_changed.emit()

        # Do an immediate check
        logger.info("Running initial fallback media state check")
        self._check_fallback_media_state()

    def _check_fallback_media_state(self):
        """Check for media playback in fallback mode using audio detection"""
        logger.debug("_check_fallback_media_state called")
        if not self._fallback_mode:
            logger.debug("Not in fallback mode, skipping check")
            return

        try:
            # Whitelist of known desktop media applications
            DESKTOP_MEDIA_APPS = [
                "spotify.exe", "vlc.exe", "wmplayer.exe", "groove.exe",
                "itunes.exe", "musicbee.exe", "foobar2000.exe", "aimp.exe",
                "winamp.exe", "mediaplayer.exe", "potplayer.exe",
                "mpc-hc64.exe", "mpc-hc.exe", "clementine.exe", "audacious.exe"
            ]

            # Get all audio sessions
            sessions = AudioUtilities.GetAllSessions()
            logger.debug(f"Found {len(sessions)} audio sessions")
            has_media = False
            current_app_name = None
            is_playing = False

            # First pass: check for active audio sessions from whitelisted apps (playing)
            for session in sessions:
                if session.Process and session.Process.name():
                    app_name = session.Process.name()

                    # Only check whitelisted media apps
                    if app_name.lower() not in [app.lower() for app in DESKTOP_MEDIA_APPS]:
                        continue

                    peak = self._get_audio_peak(session)

                    if peak and peak > 0.01:  # Audio is playing
                        # Try to parse window title to see if this is actually a media player
                        title, artist = self._parse_window_title_for_app(app_name)
                        logger.debug(f"Session with audio: {app_name}, peak: {peak}, title: '{title}', artist: '{artist}'")

                        if title or artist:  # Valid media information found
                            has_media = True
                            current_app_name = app_name
                            is_playing = True
                            logger.info(f"Active media detected: {app_name} - {artist} - {title}")
                            break
                        else:
                            logger.debug(f"Skipping {app_name} - has audio but no media info in window title")

            # Second pass: if no active audio, check whitelisted media players (paused state)
            if not has_media:
                logger.debug("First pass found no media, checking for paused media players from whitelist")
                import psutil

                # Only check whitelisted media apps
                for proc in psutil.process_iter(['name']):
                    try:
                        app_name = proc.info['name']
                        if not app_name:
                            continue

                        # Only check whitelisted media apps
                        if app_name.lower() not in [app.lower() for app in DESKTOP_MEDIA_APPS]:
                            continue

                        logger.debug(f"Checking whitelisted process: {app_name}")
                        title, artist = self._parse_window_title_for_app(app_name)
                        logger.debug(f"  -> title: '{title}', artist: '{artist}'")

                        if title or artist:  # Valid media information found
                            has_media = True
                            current_app_name = app_name
                            is_playing = False
                            logger.info(f"Paused media detected: {app_name} - {artist} - {title}")
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            if has_media:
                self._update_fallback_state(current_app_name, is_playing=is_playing)
            else:
                # No media detected at all - clear state if needed
                if self._fallback_is_playing or self._fallback_title or self._fallback_artist:
                    self._update_fallback_state(None, is_playing=False)

        except Exception as e:
            logger.debug(f"Error checking fallback media state: {e}")

    def _get_audio_peak(self, session) -> float | None:
        """Get audio peak level for a session"""
        try:
            if hasattr(session, "_ctl") and hasattr(session._ctl, "QueryInterface"):
                from ctypes import c_float
                from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
                from comtypes import POINTER as COM_POINTER

                # Define IAudioMeterInformation interface
                class IAudioMeterInformation(IUnknown):
                    _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
                    _methods_ = [
                        COMMETHOD([], HRESULT, "GetPeakValue", (["out"], COM_POINTER(c_float), "pfPeak")),
                    ]

                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak = meter.GetPeakValue()
                return peak
            else:
                logger.debug(f"Session missing _ctl or QueryInterface")
                return None
        except Exception as e:
            logger.debug(f"Error getting audio peak: {e}")
            return None

    def _update_fallback_state(self, app_name: str | None, is_playing: bool):
        """Update fallback session state"""
        state = self._trackers.get(self._fallback_app_id)
        if not state:
            return

        # Update playing state
        prev_playing = self._fallback_is_playing
        self._fallback_is_playing = is_playing

        if prev_playing != is_playing:
            logger.debug(f"Fallback playback state changed: {prev_playing} -> {is_playing}")

        if state.playback_info:
            state.is_playing = is_playing
            state.playback_info.playback_status = 4 if is_playing else 3

        # Update track info and session state
        state_changed = False
        if app_name:
            # Media player is open (playing or paused) - update track info
            title, artist = self._parse_window_title_for_app(app_name)
            if title or artist:
                # Check if track info changed
                if state.title != title or state.artist != artist:
                    logger.debug(f"Track info changed: '{state.artist} - {state.title}' -> '{artist} - {title}'")
                    state_changed = True
                state.title = title
                state.artist = artist
                self._fallback_title = title
                self._fallback_artist = artist
                state.is_current = True
        else:
            # No media player - clear track info
            state.title = ""
            state.artist = ""
            self._fallback_title = ""
            self._fallback_artist = ""
            if state.is_current:  # Only if it was current before
                state_changed = True
            state.is_current = False

        # Emit signals ONLY if state actually changed to avoid unnecessary updates
        if prev_playing != is_playing or state_changed:
            logger.debug(f"Emitting signals: prev_playing={prev_playing}, is_playing={is_playing}, state_changed={state_changed}")
            # In fallback mode, skip playback_info_changed to prevent UI conflicts
            self.media_data_changed.emit(self._trackers)
            self.media_properties_changed.emit()

    def _parse_window_title_for_app(self, app_name: str) -> tuple[str, str]:
        """Parse window title to extract artist and title - prioritizes windows with track info"""
        try:
            import win32gui
            import win32process

            def window_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            windows.append((hwnd, title, pid))
                        except:
                            pass

            windows = []
            win32gui.EnumWindows(window_callback, windows)

            # Get process name without .exe
            target_process = app_name.lower().replace('.exe', '')

            # Collect all windows belonging to this process
            process_windows = []
            for hwnd, title, pid in windows:
                try:
                    import psutil
                    process = psutil.Process(pid)
                    window_process = process.name().lower().replace('.exe', '')

                    # Check if this window belongs to our target process
                    if window_process == target_process:
                        process_windows.append(title)
                except:
                    continue

            if not process_windows:
                return "", ""

            # Spotify format: "Artist - Title"
            if "spotify" in target_process:
                # Prioritize windows with track info (contain " - " and are not generic Spotify titles)
                track_windows = [
                    t for t in process_windows
                    if " - " in t and not t.lower() in ["spotify", "spotify premium", "spotify free"]
                ]

                if track_windows:
                    # Return the longest track window (most complete info)
                    best_title = max(track_windows, key=len)
                    logger.debug(f"Found Spotify track window: '{best_title}'")
                    parts = best_title.split(" - ", 1)
                    if len(parts) == 2:
                        return parts[1].strip(), parts[0].strip()  # title, artist

                # No track windows found, check for generic Spotify window
                spotify_windows = [t for t in process_windows if "spotify" in t.lower()]
                if spotify_windows:
                    # Spotify is open but no track - return generic title
                    best_title = max(spotify_windows, key=len)
                    process_name = target_process.capitalize()
                    logger.debug(f"Spotify open but no track: '{best_title}'")
                    return best_title, process_name

            # Browser format varies - only detect media-playing tabs
            if any(browser in target_process for browser in ["chrome", "firefox", "edge", "brave"]):
                # Media site patterns (whitelist)
                media_patterns = [
                    "youtube", "spotify", "soundcloud", "twitch", "netflix",
                    "amazon prime", "disney+", "apple music", "tidal",
                    "deezer", "pandora", "bandcamp", "mixcloud"
                ]

                # Filter windows that match media patterns and have " - "
                media_windows = [
                    t for t in process_windows
                    if " - " in t and any(pattern in t.lower() for pattern in media_patterns)
                ]

                if media_windows:
                    best_title = max(media_windows, key=len)
                    parts = best_title.split(" - ")
                    if len(parts) >= 2:
                        return parts[0].strip(), parts[1].strip()  # title, artist

            # Fallback: return longest window title with process name as artist (but not for browsers)
            # For browsers, we already checked for media patterns above - don't return non-media tabs
            is_browser = any(browser in target_process for browser in ["chrome", "firefox", "edge", "brave"])
            if process_windows and not is_browser:
                best_title = max(process_windows, key=len)
                process_name = target_process.capitalize()
                return best_title, process_name

        except Exception as e:
            logger.debug(f"Error parsing window title: {e}")

        return "", ""

    def _send_media_key(self, vk_code: int):
        """Send a media command using WM_APPCOMMAND (more reliable than SendInput for UIPI)"""
        try:
            # Map VK codes to APPCOMMAND constants
            appcommand_map = {
                VK_MEDIA_PLAY_PAUSE: APPCOMMAND_MEDIA_PLAY_PAUSE,
                VK_MEDIA_NEXT_TRACK: APPCOMMAND_MEDIA_NEXTTRACK,
                VK_MEDIA_PREV_TRACK: APPCOMMAND_MEDIA_PREVIOUSTRACK,
            }

            appcommand = appcommand_map.get(vk_code)
            if appcommand is None:
                logger.error(f"Unknown media key: {vk_code}")
                return

            logger.info(f"Sending WM_APPCOMMAND: {appcommand} (VK: {vk_code:#x})")

            # Use PostMessage instead of SendMessage to avoid blocking/deadlock
            # lParam = appcommand << 16 | device << 12 | keys
            lParam = appcommand << 16
            result = ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, lParam)

            if result:
                logger.info("WM_APPCOMMAND posted successfully")
            else:
                logger.error(f"PostMessage failed, error code: {ctypes.get_last_error()}")

        except Exception as e:
            logger.error(f"Failed to send media command {vk_code}: {e}", exc_info=True)

    async def _refresh_sessions(self, manager: SessionManager):
        """Refresh session states from the manager"""
        sessions = manager.get_sessions()
        current_session = manager.get_current_session()
        current_ids = [s.source_app_user_model_id for s in sessions]

        # Cleanup old trackers
        to_remove = [app_id for app_id in self._trackers if app_id not in current_ids]
        for app_id in to_remove:
            old_state = self._trackers.pop(app_id)
            for cleanup_callback in old_state.cleanup_callbacks:
                try:
                    cleanup_callback()
                except Exception:
                    pass

        # Create new trackers
        for session in sessions:
            app_id = session.source_app_user_model_id
            if app_id not in self._trackers:
                self._trackers[app_id] = SessionState(app_id)
                self._trackers[app_id].session = session

                # Add callbacks to events
                t_mp = session.add_media_properties_changed(
                    self._create_callback_bridge(self._on_media_properties_changed),
                )
                t_tp = session.add_timeline_properties_changed(
                    self._create_callback_bridge(self._on_timeline_properties_changed),
                )
                t_pi = session.add_playback_info_changed(
                    self._create_callback_bridge(self._on_playback_info_changed),
                )

                # Store callbacks for cleanup
                self._trackers[app_id].cleanup_callbacks = [
                    partial(session.remove_media_properties_changed, t_mp),
                    partial(session.remove_timeline_properties_changed, t_tp),
                    partial(session.remove_playback_info_changed, t_pi),
                ]

            self.media_data_changed.emit(self._trackers)

            # Sync the session immediately
            await self._on_media_properties_changed(session)
            await self._on_timeline_properties_changed(session)
            await self._on_playback_info_changed(session)

        current_id = current_session.source_app_user_model_id if current_session else None
        for tracker in self._trackers.values():
            tracker.is_current = tracker.app_id == current_id

    async def _on_current_session_changed(self, manager: SessionManager):
        """Handle current session change"""
        await self._refresh_sessions(manager)
        for tracker in self._trackers.values():
            if tracker.is_current:
                self._current_session_id = tracker.app_id
                break
        self.media_data_changed.emit(self._trackers)
        self.current_session_changed.emit()

    async def _on_media_properties_changed(self, session: MediaSession):
        """Handle media properties change"""
        app_id = session.source_app_user_model_id
        if app_id not in self._trackers:
            return
        try:
            state = self._trackers[app_id]
            try:
                # This can fail if the app is not ready yet
                props = await session.try_get_media_properties_async()
                if not props:
                    return
            except Exception:
                return
            new_title = props.title
            state.title = new_title
            state.artist = props.artist
            if tn := props.thumbnail:
                state.thumbnail = await self._get_thumbnail_async(tn)
            else:
                state.thumbnail = None
            self.media_properties_changed.emit()
        except Exception as e:
            logger.error(f"Error syncing session: {e}", exc_info=True)

    async def _on_timeline_properties_changed(self, session: MediaSession):
        """Handle timeline properties change"""
        app_id = session.source_app_user_model_id
        if app_id not in self._trackers:
            return
        try:
            timeline = session.get_timeline_properties()
            if not timeline:
                return
            state = self._trackers[app_id]
            new_pos = timeline.position.total_seconds()
            new_update = timeline.last_updated_time.timestamp()
            state.duration = timeline.end_time.total_seconds()
            if new_update > state.last_update_time:
                state.last_snapshot_pos = new_pos
            state.last_update_time = new_update
            self.timeline_info_changed.emit()
        except Exception as e:
            logger.error(f"Error syncing session: {e}", exc_info=True)

    async def _on_playback_info_changed(self, session: MediaSession):
        """Handle playback info change"""
        app_id = session.source_app_user_model_id
        if app_id not in self._trackers:
            return
        try:
            state = self._trackers[app_id]
            playback = session.get_playback_info()
            if not playback:
                return
            state.is_playing = playback.playback_status == 4
            state.playback_rate = playback.playback_rate or 1.0  # Can be None
            state.playback_info = playback
            state.timeline_enabled = playback.controls.is_playback_position_enabled if playback.controls else False
            self.playback_info_changed.emit()
        except Exception as e:
            logger.error(f"Error syncing session: {e}", exc_info=True)

    def _interpolate_and_emit(self, trackers: dict[str, SessionState]):
        """Interpolate the timeline and emit media data"""
        # Update current position for each session
        for state in trackers.values():
            pos = state.last_snapshot_pos
            if state.is_playing:
                drift = time.time() - state.last_update_time
                pos += drift * state.playback_rate
            state.current_pos = pos

        self.media_data_changed.emit(trackers)

    def _create_callback_bridge(self, callback: Callable[[Any], Any]):
        """Create a callback bridge to run from WinRT thread"""

        def wrapper(s: Any, _a: Any) -> None:
            self._loop.call_soon_threadsafe(lambda: asyncio.create_task(callback(s)))

        return wrapper

    @staticmethod
    async def _get_thumbnail_async(thumbnail_stream_reference: IRandomAccessStreamReference) -> Image.Image | None:
        """Read the thumbnail for the IRandomAccessStreamReference and return it as PIL ImageFile"""
        # Read the stream into the buffer
        readable_stream = await thumbnail_stream_reference.open_read_async()
        try:
            # Create buffer of stream size
            thumb_read_buffer = Buffer(readable_stream.size)

            # Read stream into buffer
            await readable_stream.read_async(
                thumb_read_buffer,
                thumb_read_buffer.capacity,
                InputStreamOptions.READ_AHEAD,
            )

            # Convert bytearray to pillow image
            pillow_image = Image.open(io.BytesIO(thumb_read_buffer))

            return pillow_image
        except Exception as e:
            logging.error(f"get_thumbnail(): Error occurred when loading the thumbnail: {e}")
            return None
        finally:
            # Close the stream
            readable_stream.close()

    def force_update(self):
        """Force an immediate update of the media data and properties signals"""
        self.media_properties_changed.emit()
        self._interpolate_and_emit(self._trackers)

    def switch_current_session(self, direction: int):
        """Switch to the next/previous session in the list."""
        if not self._trackers:
            return

        sessions = list(self._trackers.values())

        idx = next((i for i, s in enumerate(sessions) if s.is_current), 0)
        next_session = sessions[(idx + direction) % len(sessions)]

        # No need to do anything if the next session is the current one
        if next_session is self.current_session:
            return

        for s in sessions:
            s.is_current = False

        next_session.is_current = True
        self._current_session_id = next_session.app_id

        self.media_data_changed.emit(self._trackers)
        self.media_properties_changed.emit()

        if next_session.playback_info:
            self.playback_info_changed.emit()

        self.current_session_changed.emit()

    @asyncSlot()
    async def play_pause(self):
        """Play/pause the current session"""
        try:
            if self._fallback_mode:
                self._send_media_key(VK_MEDIA_PLAY_PAUSE)
                # Toggle manual state tracking in fallback
                # The fallback detector will automatically detect the state change
                # and emit the necessary signals
                if self.current_session and self.current_session.playback_info:
                    self.current_session.playback_info.toggle_playback_status()
                    self._fallback_is_playing = not self._fallback_is_playing
            elif self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_toggle_play_pause_async()
        except Exception as e:
            logger.error(f"Error playing/pausing: {e}", exc_info=True)

    @asyncSlot()
    async def prev(self):
        """Skip to previous track"""
        logger.info(f"=== prev called! fallback_mode={self._fallback_mode} ===")
        try:
            if self._fallback_mode:
                logger.info("Sending VK_MEDIA_PREV_TRACK key")
                self._send_media_key(VK_MEDIA_PREV_TRACK)
            elif self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_skip_previous_async()
        except Exception as e:
            logger.error(f"Error skipping previous: {e}", exc_info=True)

    @asyncSlot()
    async def next(self):
        """Skip to next track"""
        logger.info(f"=== next called! fallback_mode={self._fallback_mode} ===")
        try:
            if self._fallback_mode:
                logger.info("Sending VK_MEDIA_NEXT_TRACK key")
                self._send_media_key(VK_MEDIA_NEXT_TRACK)
            elif self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_skip_next_async()
        except Exception as e:
            logger.error(f"Error skipping next: {e}", exc_info=True)

    async def seek_to_position(self, position: float):
        """Seek to specific position in seconds."""
        try:
            if self.current_session and self.current_session.session is not None:
                position_in_100ns = int(position * 10_000_000)  # Seconds -> 100-nanosecond units
                await self.current_session.session.try_change_playback_position_async(position_in_100ns)
                self.current_session.last_snapshot_pos = position
                self.current_session.last_update_time = time.time()
                self._interpolate_and_emit(self._trackers)
        except Exception as e:
            logger.error(f"Error seeking to position: {e}")

import asyncio
import io
import logging
import time
from functools import partial
from typing import Any, Callable

from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal
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
            logger.error(f"Failed to start WindowsMedia worker: {e}", exc_info=True)
            self._running = False

    async def stop(self):
        """Stop the WindowsMedia worker refresh loop"""
        self._running = False

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
            if self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_toggle_play_pause_async()
        except Exception as e:
            logger.error(f"Error playing/pausing: {e}")

    @asyncSlot()
    async def prev(self):
        """Skip to previous track"""
        try:
            if self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_skip_previous_async()
        except Exception as e:
            logger.error(f"Error skipping previous: {e}")

    @asyncSlot()
    async def next(self):
        """Skip to next track"""
        try:
            if self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_skip_next_async()
        except Exception as e:
            logger.error(f"Error skipping next: {e}")

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

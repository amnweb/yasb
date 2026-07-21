import asyncio
import io
import logging
import time
from collections.abc import Callable
from functools import partial
from typing import Any

from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from qasync import asyncSlot  # type: ignore
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSession,
)
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winrt.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference

from core.utils.singleton import QSingleton

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)

type MediaSession = GlobalSystemMediaTransportControlsSession

logger = logging.getLogger("WindowsMedia")

REFRESH_INTERVAL = 0.1
SESSION_GONE_GRACE_SEC = 1.0


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
        # Snapshotted from WinRT PlaybackInfo - plain Python only (do not retain COM objects).
        self.playback_ready = False
        self.controls_prev_enabled = True
        self.controls_play_enabled = True
        self.controls_next_enabled = True
        self.thumbnail: Image.Image | None = None
        self.cleanup_callbacks: list[Callable[..., None]] = []
        self.session: MediaSession | None = None
        # After next/prev: do not invent drift until SMTC posts a newer timeline snapshot.
        self._pause_interpolate = False


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
        # Keep selected tracker until this time if SMTC drops it briefly.
        self._hold_until: float = 0.0
        self._hold_timer: asyncio.TimerHandle | None = None
        self._manager: SessionManager | None = None

        self._loop.create_task(self.run())

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_quit)

    @property
    def current_session(self) -> SessionState | None:
        """Get the current session state"""
        return self._trackers.get(self._current_session_id)

    async def run(self):
        """Start the WindowsMedia worker"""
        self._running = True
        try:
            manager = await SessionManager.request_async()
            self._manager = manager
            await self._refresh_sessions(manager)

            manager.add_sessions_changed(self._create_callback_bridge(self._on_sessions_changed))
            manager.add_current_session_changed(self._create_callback_bridge(self._on_current_session_changed))

            await self._on_current_session_changed(manager)

            # Start the refresh loop
            while self._running:
                self._interpolate_and_emit(self._trackers)
                await asyncio.sleep(REFRESH_INTERVAL)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Failed to start WindowsMedia worker: %s", e, exc_info=True)
        finally:
            self._running = False

    def _on_quit(self):
        """Unsubscribe all WinRT event handlers on application quit"""
        self._running = False
        self._clear_hold()
        for state in list(self._trackers.values()):
            for cb in state.cleanup_callbacks:
                try:
                    cb()
                except Exception:
                    pass
        self._trackers.clear()

    def _clear_hold(self) -> None:
        self._hold_until = 0.0
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _schedule_hold_expiry(self) -> None:
        if self._hold_timer is not None:
            self._hold_timer.cancel()

        def _fire() -> None:
            self._hold_timer = None
            if self._hold_until <= 0 or self._manager is None:
                return
            self._safe_create_task(self._on_sessions_changed, self._manager)

        self._hold_timer = self._loop.call_later(SESSION_GONE_GRACE_SEC + 0.05, _fire)

    def _rebind_session(self, state: SessionState, session: MediaSession) -> None:
        """Replace WinRT session handle and re-register event callbacks."""
        for cleanup_callback in state.cleanup_callbacks:
            try:
                cleanup_callback()
            except Exception:
                pass
        state.session = session
        t_mp = session.add_media_properties_changed(
            self._create_callback_bridge(self._on_media_properties_changed),
        )
        t_tp = session.add_timeline_properties_changed(
            self._create_callback_bridge(self._on_timeline_properties_changed),
        )
        t_pi = session.add_playback_info_changed(
            self._create_callback_bridge(self._on_playback_info_changed),
        )
        state.cleanup_callbacks = [
            partial(session.remove_media_properties_changed, t_mp),
            partial(session.remove_timeline_properties_changed, t_tp),
            partial(session.remove_playback_info_changed, t_pi),
        ]

    def _sync_selection(self, system_id: str | None) -> bool:
        """Keep selection sticky while present; only adopt Windows current when it is gone."""
        prev_id = self._current_session_id

        if self._current_session_id not in self._trackers:
            if system_id in self._trackers:
                self._current_session_id = system_id
            elif self._trackers:
                self._current_session_id = next(iter(self._trackers))
            else:
                self._current_session_id = ""

        for tracker in self._trackers.values():
            tracker.is_current = bool(self._current_session_id) and tracker.app_id == self._current_session_id

        return prev_id != self._current_session_id

    async def _refresh_sessions(self, manager: SessionManager) -> bool:
        """Refresh SMTC sessions. Sticky selection + brief hold if selected drops out."""
        sessions = manager.get_sessions()
        current_session = manager.get_current_session()
        current_ids = [s.source_app_user_model_id for s in sessions]
        system_id = current_session.source_app_user_model_id if current_session else None

        selected = self._current_session_id
        rebind_id = ""
        hold_id = ""

        if selected and selected in current_ids:
            if self._hold_until > 0 and selected in self._trackers:
                rebind_id = selected
            self._clear_hold()
        elif selected and selected not in current_ids:
            now = time.time()
            if self._hold_until <= 0:
                self._hold_until = now + SESSION_GONE_GRACE_SEC
                self._schedule_hold_expiry()
            if now < self._hold_until:
                hold_id = selected
            else:
                self._clear_hold()

        to_remove = [app_id for app_id in self._trackers if app_id not in current_ids and app_id != hold_id]
        for app_id in to_remove:
            old_state = self._trackers.pop(app_id)
            for cleanup_callback in old_state.cleanup_callbacks:
                try:
                    cleanup_callback()
                except Exception:
                    pass

        for session in sessions:
            app_id = session.source_app_user_model_id
            if app_id not in self._trackers:
                self._trackers[app_id] = SessionState(app_id)
                self._rebind_session(self._trackers[app_id], session)
            elif app_id == rebind_id:
                self._rebind_session(self._trackers[app_id], session)

            await self._on_media_properties_changed(session)
            await self._on_timeline_properties_changed(session)
            await self._on_playback_info_changed(session)

        self.media_data_changed.emit(self._trackers)
        return self._sync_selection(system_id)

    async def _on_sessions_changed(self, manager: SessionManager):
        """Handle SMTC session list changes (session added/removed)."""
        selection_changed = await self._refresh_sessions(manager)
        self.media_data_changed.emit(self._trackers)
        if selection_changed:
            self.media_properties_changed.emit()
            if (session := self.current_session) is not None and session.playback_ready:
                self.playback_info_changed.emit()
            self.current_session_changed.emit()

    async def _on_current_session_changed(self, manager: SessionManager):
        """Handle Windows current-session change (selection stays sticky if still present)."""
        await self._refresh_sessions(manager)
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

            state.title = (props.title or "").strip()
            state.artist = (props.artist or "").strip()
            if tn := props.thumbnail:
                state.thumbnail = await self._get_thumbnail_async(tn)
            else:
                state.thumbnail = None

            self.media_properties_changed.emit()
        except Exception as e:
            logger.error("Error syncing session: %s", e, exc_info=True)

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
            new_duration = timeline.end_time.total_seconds()

            # Firefox/YouTube can emit pos=0,duration=0 after seek; ignore if we already have a duration.
            if new_duration <= 0 and new_pos <= 0 and state.duration > 0:
                return

            if new_update > state.last_update_time:
                state.last_snapshot_pos = new_pos
                state.last_update_time = new_update
                state._pause_interpolate = False
            state.duration = new_duration

            self.timeline_info_changed.emit()
        except Exception as e:
            logger.error("Error syncing session: %s", e, exc_info=True)

    async def _on_playback_info_changed(self, session: MediaSession):
        """Handle playback info change.

        Copy needed fields into plain Python state immediately, then drop the
        WinRT PlaybackInfo so UI code never re-touches a COM object later.
        """
        app_id = session.source_app_user_model_id
        if app_id not in self._trackers:
            return
        try:
            state = self._trackers[app_id]
            playback = session.get_playback_info()
            if not playback:
                return
            # Snapshot all WinRT properties into locals first, then assign.
            # playback_rate is required for timeline interpolation (e.g. YouTube 2x).
            is_playing = playback.playback_status == 4
            raw_rate = playback.playback_rate
            try:
                playback_rate = float(raw_rate) if raw_rate is not None else 1.0
            except TypeError, ValueError:
                playback_rate = 1.0
            if playback_rate <= 0:
                playback_rate = 1.0
            controls = playback.controls
            if controls:
                prev_enabled = controls.is_previous_enabled
                play_enabled = controls.is_play_pause_toggle_enabled
                next_enabled = controls.is_next_enabled
            else:
                prev_enabled = True
                play_enabled = True
                next_enabled = True

            state.is_playing = is_playing
            state.playback_rate = playback_rate
            state.controls_prev_enabled = prev_enabled
            state.controls_play_enabled = play_enabled
            state.controls_next_enabled = next_enabled
            state.playback_ready = True
            self.playback_info_changed.emit()
        except Exception as e:
            logger.error("Error syncing session: %s", e, exc_info=True)

    def _interpolate_and_emit(self, trackers: dict[str, SessionState]):
        """Interpolate the timeline and emit media data"""
        # Update current position for each session
        for state in trackers.values():
            pos = state.last_snapshot_pos
            if state.is_playing and not state._pause_interpolate:
                drift = time.time() - state.last_update_time
                pos += drift * state.playback_rate
            if state.duration > 0:
                pos = min(pos, state.duration)
            state.current_pos = pos

        self.media_data_changed.emit(trackers)

    def _safe_create_task(self, callback: Callable[[Any], Any], sender: Any) -> None:
        """Create a task on the loop, silently ignoring shutdown races."""
        try:
            self._loop.create_task(callback(sender))
        except RuntimeError:
            pass

    def _create_callback_bridge(self, callback: Callable[[Any], Any]):
        """Create a callback bridge to run from WinRT thread"""

        def wrapper(s: Any, _a: Any) -> None:
            try:
                self._loop.call_soon_threadsafe(self._safe_create_task, callback, s)
            except RuntimeError:
                pass

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
            logging.error("get_thumbnail(): Error occurred when loading the thumbnail: %s", e)
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

        # Use selected id (not is_current alone) so wheel works after a dead
        # session was removed but flags were briefly out of sync.
        idx = next((i for i, s in enumerate(sessions) if s.app_id == self._current_session_id), 0)
        next_session = sessions[(idx + direction) % len(sessions)]

        if next_session.app_id == self._current_session_id:
            return

        for s in sessions:
            s.is_current = False

        next_session.is_current = True
        self._current_session_id = next_session.app_id
        self._clear_hold()

        self.media_data_changed.emit(self._trackers)

        if next_session.playback_ready:
            self.playback_info_changed.emit()

        self.current_session_changed.emit()

    @asyncSlot()
    async def play_pause(self):
        """Play/pause the current session"""
        try:
            if self.current_session and self.current_session.session is not None:
                await self.current_session.session.try_toggle_play_pause_async()
        except Exception as e:
            logger.error("Error playing/pausing: %s", e)

    def _reset_timeline_for_skip(self, state: SessionState) -> None:
        """Show 0 and hold interpolate until SMTC posts a newer timeline snapshot."""
        state.last_snapshot_pos = 0.0
        state.current_pos = 0.0
        state.last_update_time = time.time()
        state._pause_interpolate = True
        self._interpolate_and_emit(self._trackers)
        self.playback_info_changed.emit()

    @asyncSlot()
    async def prev(self):
        """Skip to previous track"""
        try:
            if self.current_session and self.current_session.session is not None:
                self._reset_timeline_for_skip(self.current_session)
                await self.current_session.session.try_skip_previous_async()
        except Exception as e:
            logger.error("Error skipping previous: %s", e)

    @asyncSlot()
    async def next(self):
        """Skip to next track"""
        try:
            if self.current_session and self.current_session.session is not None:
                self._reset_timeline_for_skip(self.current_session)
                await self.current_session.session.try_skip_next_async()
        except Exception as e:
            logger.error("Error skipping next: %s", e)

    async def seek_to_position(self, position: float):
        """Seek to specific position in seconds."""
        try:
            if self.current_session and self.current_session.session is not None:
                position_in_100ns = int(position * 10_000_000)  # Seconds -> 100-nanosecond units
                await self.current_session.session.try_change_playback_position_async(position_in_100ns)
                self.current_session.last_snapshot_pos = position
                self.current_session.last_update_time = time.time()
                self.current_session._pause_interpolate = False
                self._interpolate_and_emit(self._trackers)
        except Exception as e:
            logger.error("Error seeking to position: %s", e)

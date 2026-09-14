import asyncio
import io
import logging
import threading
import time
from collections.abc import Callable
from functools import partial
from typing import Any

from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from qasync import asyncSlot  # type: ignore
from winrt.windows.media import MediaPlaybackAutoRepeatMode
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


def _iref_float(value: Any, default: float = 1.0) -> float:
    """Convert a WinRT IReference[float] (or None) once; never touch the property twice."""
    if value is None:
        return default
    try:
        result = float(value)
    except TypeError, ValueError:
        return default
    return result if result > 0 else default


def _iref_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    try:
        return bool(value)
    except TypeError, ValueError:
        return default


def _iref_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except TypeError, ValueError:
        return default


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
        # SMTC playback_status: 0=Closed, 1=Opened, 2=Changing, 3=Stopped, 4=Playing, 5=Paused
        self.playback_status = 0
        self.playback_rate = 1.0
        self.is_current = False
        self.timeline_enabled = False
        # Snapshotted from WinRT PlaybackInfo - plain Python only (do not retain COM objects).
        self.playback_ready = False
        self.controls_prev_enabled = True
        self.controls_play_enabled = True
        self.controls_next_enabled = True
        self.controls_shuffle_enabled = False
        self.controls_repeat_enabled = False
        self.is_shuffle_active = False
        # 0=None, 1=Track, 2=List (MediaPlaybackAutoRepeatMode)
        self.auto_repeat_mode = 0
        self.thumbnail: Image.Image | None = None
        self.cleanup_callbacks: list[Callable[..., None]] = []
        self.session: MediaSession | None = None


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
        self._manager: SessionManager | None = None
        # Serialize SMTC/COM reads so WinRT callback threads and asyncio never
        # release the same IReference / PlaybackInfo concurrently (heap double-free).
        self._smtc_lock = threading.RLock()

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

            manager.add_sessions_changed(self._bridge_manager_event(self._on_sessions_changed))
            manager.add_current_session_changed(self._bridge_manager_event(self._on_current_session_changed))

            await self._on_current_session_changed()

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
        for state in list(self._trackers.values()):
            for cb in state.cleanup_callbacks:
                try:
                    cb()
                except Exception:
                    pass
        self._trackers.clear()

    def _apply_current_selection(self, system_id: str | None, *, follow_system: bool) -> bool:
        """Keep _current_session_id and is_current flags aligned with live trackers.

        Returns True if the selected session id changed.
        """
        prev_id = self._current_session_id

        if follow_system or self._current_session_id not in self._trackers:
            # Follow Windows "current", or fall back when our selection was removed
            # (e.g. browser tab ended while user had switched to it via scroll).
            if system_id in self._trackers:
                self._current_session_id = system_id
            elif self._trackers:
                self._current_session_id = next(iter(self._trackers))
            else:
                self._current_session_id = ""
        # else: keep manual selection (still present in trackers)

        for tracker in self._trackers.values():
            tracker.is_current = bool(self._current_session_id) and tracker.app_id == self._current_session_id

        return prev_id != self._current_session_id

    def _bind_session(self, state: SessionState, session: MediaSession) -> None:
        """Register WinRT event callbacks for a session. Caller must hold _smtc_lock."""
        state.session = session
        t_mp = session.add_media_properties_changed(self._bridge_session_properties)
        t_tp = session.add_timeline_properties_changed(self._bridge_session_timeline)
        t_pi = session.add_playback_info_changed(self._bridge_session_playback)
        state.cleanup_callbacks = [
            partial(session.remove_media_properties_changed, t_mp),
            partial(session.remove_timeline_properties_changed, t_tp),
            partial(session.remove_playback_info_changed, t_pi),
        ]

    async def _refresh_sessions(self, manager: SessionManager, *, follow_system: bool = False) -> bool:
        """Refresh session states from the manager.

        Returns True if the selected session id changed.
        """
        with self._smtc_lock:
            sessions = list(manager.get_sessions())
            current_session = manager.get_current_session()
            current_ids = [s.source_app_user_model_id for s in sessions]
            system_id = current_session.source_app_user_model_id if current_session else None

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
                with self._smtc_lock:
                    self._bind_session(self._trackers[app_id], session)

            self.media_data_changed.emit(self._trackers)

            await self._sync_media_properties(app_id)

            state = self._trackers.get(app_id)
            if state is None or state.session is None:
                continue
            with self._smtc_lock:
                tracked = state.session
                timeline_snap = self._snapshot_timeline(tracked)
                playback_snap = self._snapshot_playback(tracked)
            if timeline_snap is not None:
                self._apply_timeline_snapshot(app_id, timeline_snap)
            if playback_snap is not None:
                self._apply_playback_snapshot(app_id, playback_snap)

        return self._apply_current_selection(system_id, follow_system=follow_system)

    async def _on_sessions_changed(self):
        """Handle SMTC session list changes (session added/removed)."""
        manager = self._manager
        if manager is None:
            return
        selection_changed = await self._refresh_sessions(manager, follow_system=False)
        self.media_data_changed.emit(self._trackers)
        if selection_changed:
            # e.g. selected browser session ended -> fell back to Spotify
            self.media_properties_changed.emit()
            if (session := self.current_session) is not None and session.playback_ready:
                self.playback_info_changed.emit()
            self.current_session_changed.emit()

    async def _on_current_session_changed(self):
        """Handle Windows current-session change (follow system)."""
        manager = self._manager
        if manager is None:
            return
        await self._refresh_sessions(manager, follow_system=True)
        self.media_data_changed.emit(self._trackers)
        self.current_session_changed.emit()

    async def _on_media_properties_app(self, app_id: str):
        """Properties event from WinRT: use tracked session only (never callback COM arg)."""
        await self._sync_media_properties(app_id)

    async def _sync_media_properties(self, app_id: str):
        """Fetch media properties via tracked session; never hold the SMTC lock across await."""
        state = self._trackers.get(app_id)
        if state is None or state.session is None:
            return
        try:
            with self._smtc_lock:
                session = state.session
                if session is None:
                    return
                op = session.try_get_media_properties_async()
            try:
                props = await op
            except Exception:
                return
            if not props:
                return

            with self._smtc_lock:
                title = props.title or ""
                artist = props.artist or ""
                thumb_ref = props.thumbnail
            del props

            if thumb_ref is not None:
                thumbnail = await self._get_thumbnail_async(thumb_ref)
            else:
                thumbnail = None
            del thumb_ref

            state = self._trackers.get(app_id)
            if state is None:
                return
            state.title = title
            state.artist = artist
            state.thumbnail = thumbnail
            self.media_properties_changed.emit()
        except Exception as e:
            logger.error("Error syncing session: %s", e, exc_info=True)

    @staticmethod
    def _snapshot_timeline(session: MediaSession) -> dict[str, float] | None:
        """Plain-Python timeline fields. Caller must hold _smtc_lock."""
        timeline = session.get_timeline_properties()
        if not timeline:
            return None
        snap = {
            "position": timeline.position.total_seconds(),
            "last_updated": timeline.last_updated_time.timestamp(),
            "duration": timeline.end_time.total_seconds(),
        }
        del timeline
        return snap

    def _apply_timeline_snapshot(self, app_id: str, snap: dict[str, float]) -> None:
        state = self._trackers.get(app_id)
        if state is None:
            return
        new_pos = snap["position"]
        new_update = snap["last_updated"]
        # WinRT unset DateTime is 1601-01-01 (unix -11644473600). Ignore it or
        # interpolate becomes now - (-11644473600) (~1.3e10 seconds).
        if new_update <= 0:
            return
        state.duration = snap["duration"]
        if new_update > state.last_update_time:
            state.last_snapshot_pos = new_pos
        state.last_update_time = new_update
        self.timeline_info_changed.emit()

    @staticmethod
    def _snapshot_playback(session: MediaSession) -> dict[str, Any] | None:
        """Plain-Python playback fields. Caller must hold _smtc_lock.

        Reads each IReference property exactly once, converts immediately, and
        does not retain the PlaybackInfo / IReference COM objects.
        """
        playback = session.get_playback_info()
        if not playback:
            return None

        try:
            playback_status = int(playback.playback_status)
        except TypeError, ValueError:
            playback_status = 0
        is_playing = playback_status == 4

        raw_rate = playback.playback_rate
        playback_rate = _iref_float(raw_rate, 1.0)
        del raw_rate

        controls = playback.controls
        if controls:
            prev_enabled = bool(controls.is_previous_enabled)
            play_enabled = bool(controls.is_play_pause_toggle_enabled)
            next_enabled = bool(controls.is_next_enabled)
            timeline_enabled = bool(controls.is_playback_position_enabled)
            shuffle_enabled = bool(controls.is_shuffle_enabled)
            repeat_enabled = bool(controls.is_repeat_enabled)
        else:
            prev_enabled = True
            play_enabled = True
            next_enabled = True
            timeline_enabled = False
            shuffle_enabled = False
            repeat_enabled = False
        del controls

        raw_shuffle = playback.is_shuffle_active
        shuffle_active = _iref_bool(raw_shuffle, False)
        del raw_shuffle

        raw_repeat = playback.auto_repeat_mode
        auto_repeat_mode = _iref_int(raw_repeat, 0)
        del raw_repeat

        del playback

        return {
            "is_playing": is_playing,
            "playback_status": playback_status,
            "playback_rate": playback_rate,
            "controls_prev_enabled": prev_enabled,
            "controls_play_enabled": play_enabled,
            "controls_next_enabled": next_enabled,
            "timeline_enabled": timeline_enabled,
            "controls_shuffle_enabled": shuffle_enabled,
            "controls_repeat_enabled": repeat_enabled,
            "is_shuffle_active": shuffle_active,
            "auto_repeat_mode": auto_repeat_mode,
        }

    def _apply_playback_snapshot(self, app_id: str, snap: dict[str, Any]) -> None:
        state = self._trackers.get(app_id)
        if state is None:
            return
        state.is_playing = snap["is_playing"]
        state.playback_status = snap["playback_status"]
        state.playback_rate = snap["playback_rate"]
        state.controls_prev_enabled = snap["controls_prev_enabled"]
        state.controls_play_enabled = snap["controls_play_enabled"]
        state.controls_next_enabled = snap["controls_next_enabled"]
        state.timeline_enabled = snap["timeline_enabled"]
        state.controls_shuffle_enabled = snap["controls_shuffle_enabled"]
        state.controls_repeat_enabled = snap["controls_repeat_enabled"]
        state.is_shuffle_active = snap["is_shuffle_active"]
        state.auto_repeat_mode = snap["auto_repeat_mode"]
        state.playback_ready = True
        self.playback_info_changed.emit()

    def _interpolate_and_emit(self, trackers: dict[str, SessionState]):
        """Interpolate the timeline and emit media data"""
        # Update current position for each session
        now = time.time()
        for state in trackers.values():
            pos = state.last_snapshot_pos
            # Require a real SMTC timestamp; unset WinRT DateTime is <= 0.
            if state.is_playing and state.last_update_time > 0:
                drift = now - state.last_update_time
                pos += drift * state.playback_rate
            state.current_pos = pos

        self.media_data_changed.emit(trackers)

    def _safe_create_task(self, callback: Callable[..., Any], *args: Any) -> None:
        """Create a task on the loop, silently ignoring shutdown races."""
        try:
            self._loop.create_task(callback(*args))
        except RuntimeError:
            pass

    def _bridge_manager_event(self, callback: Callable[[], Any]):
        """WinRT manager events: hop to asyncio with no COM args."""

        def wrapper(_sender: Any, _args: Any) -> None:
            try:
                self._loop.call_soon_threadsafe(self._safe_create_task, callback)
            except RuntimeError:
                pass

        return wrapper

    def _bridge_session_properties(self, session: Any, _args: Any) -> None:
        """Properties need async fetch; schedule by app_id only (tracked session)."""
        try:
            app_id = session.source_app_user_model_id
            self._loop.call_soon_threadsafe(self._safe_create_task, self._on_media_properties_app, app_id)
        except Exception:
            pass

    def _bridge_session_timeline(self, session: Any, _args: Any) -> None:
        """Snapshot timeline on the WinRT thread, apply plain data on asyncio."""
        try:
            app_id = session.source_app_user_model_id
            with self._smtc_lock:
                snap = self._snapshot_timeline(session)
            if snap is None:
                return
            self._loop.call_soon_threadsafe(self._apply_timeline_snapshot, app_id, snap)
        except Exception:
            pass

    def _bridge_session_playback(self, session: Any, _args: Any) -> None:
        """Snapshot playback on the WinRT thread, apply plain data on asyncio.

        Crash path from dumps: IReference[double] (playback_rate) double-freed when
        PlaybackInfo was read later on another thread.
        """
        try:
            app_id = session.source_app_user_model_id
            with self._smtc_lock:
                snap = self._snapshot_playback(session)
            if snap is None:
                return
            self._loop.call_soon_threadsafe(self._apply_playback_snapshot, app_id, snap)
        except Exception:
            pass

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

        self.media_data_changed.emit(self._trackers)
        self.media_properties_changed.emit()

        if next_session.playback_ready:
            self.playback_info_changed.emit()

        self.current_session_changed.emit()

    async def _invoke_session_async(self, starter: Callable[[MediaSession], Any]) -> None:
        """Start a session async op under the SMTC lock, await outside the lock."""
        state = self.current_session
        if state is None or state.session is None:
            return
        with self._smtc_lock:
            op = starter(state.session)
        await op

    @asyncSlot()
    async def play_pause(self):
        """Play/pause the current session"""
        try:
            await self._invoke_session_async(lambda s: s.try_toggle_play_pause_async())
        except Exception as e:
            logger.error("Error playing/pausing: %s", e)

    @asyncSlot()
    async def prev(self):
        """Skip to previous track"""
        try:
            await self._invoke_session_async(lambda s: s.try_skip_previous_async())
        except Exception as e:
            logger.error("Error skipping previous: %s", e)

    @asyncSlot()
    async def next(self):
        """Skip to next track"""
        try:
            await self._invoke_session_async(lambda s: s.try_skip_next_async())
        except Exception as e:
            logger.error("Error skipping next: %s", e)

    @asyncSlot()
    async def toggle_shuffle(self):
        """Toggle shuffle for the current session when supported."""
        try:
            state = self.current_session
            if state is None or state.session is None or not state.controls_shuffle_enabled:
                return
            want = not state.is_shuffle_active
            await self._invoke_session_async(lambda s: s.try_change_shuffle_active_async(want))
        except Exception as e:
            logger.error("Error toggling shuffle: %s", e)

    @asyncSlot()
    async def cycle_repeat(self):
        """Cycle repeat: None -> List -> Track -> None when supported."""
        try:
            state = self.current_session
            if state is None or state.session is None or not state.controls_repeat_enabled:
                return
            mode = state.auto_repeat_mode
            if mode == int(MediaPlaybackAutoRepeatMode.NONE):
                nxt = MediaPlaybackAutoRepeatMode.LIST
            elif mode == int(MediaPlaybackAutoRepeatMode.LIST):
                nxt = MediaPlaybackAutoRepeatMode.TRACK
            else:
                nxt = MediaPlaybackAutoRepeatMode.NONE
            await self._invoke_session_async(lambda s: s.try_change_auto_repeat_mode_async(nxt))
        except Exception as e:
            logger.error("Error cycling repeat: %s", e)

    async def seek_to_position(self, position: float):
        """Seek to specific position in seconds."""
        try:
            state = self.current_session
            if state is None or state.session is None:
                return
            position_in_100ns = int(position * 10_000_000)  # Seconds -> 100-nanosecond units
            await self._invoke_session_async(lambda s: s.try_change_playback_position_async(position_in_100ns))
            state.last_snapshot_pos = position
            state.last_update_time = time.time()
            self._interpolate_and_emit(self._trackers)
        except Exception as e:
            logger.error("Error seeking to position: %s", e)

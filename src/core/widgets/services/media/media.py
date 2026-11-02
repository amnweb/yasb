import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from functools import partial
from typing import Any

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal
from winrt.runtime import ApartmentType, init_apartment
from winrt.windows.media import MediaPlaybackAutoRepeatMode
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSession as MediaSession
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winrt.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference

from core.utils.win32.aumid_process import get_process_name_for_aumid
from core.widgets.services.media.art import keep_art
from core.widgets.services.media.source_apps import resolve_source_app_name

logger = logging.getLogger("WindowsMedia")

# SMTC playback_status: 0=Closed, 1=Opened, 2=Changing, 3=Stopped, 4=Playing, 5=Paused
PLAYING = 4
# HRESULT_FROM_WIN32(ERROR_NOT_READY), from an app whose session exists while the app is still starting
NOT_READY = -2147024875
REPEAT_MODES = {
    int(MediaPlaybackAutoRepeatMode.NONE): "none",
    int(MediaPlaybackAutoRepeatMode.TRACK): "track",
    int(MediaPlaybackAutoRepeatMode.LIST): "list",
}
NEXT_REPEAT_MODE = {
    "none": MediaPlaybackAutoRepeatMode.LIST,
    "list": MediaPlaybackAutoRepeatMode.TRACK,
    "track": MediaPlaybackAutoRepeatMode.NONE,
}


@dataclass(frozen=True)
class MediaInfo:
    """One player, as the UI sees it."""

    app_id: str
    app_name: str
    process: str
    title: str = ""
    artist: str = ""
    album: str = ""
    art: bytes | None = None
    art_revision: int = 0
    playing: bool = False
    # Seconds into the track at position_time, a Unix time; 0 when the player never said
    position: float = 0.0
    position_time: float = 0.0
    rate: float = 1.0
    duration: float = 0.0
    can_seek: bool = False
    can_play_pause: bool = True
    can_previous: bool = True
    can_next: bool = True
    can_shuffle: bool = False
    can_repeat: bool = False
    shuffle: bool = False
    repeat: str = "none"

    def position_at(self, now: float) -> float:
        position = self.position
        if self.playing and self.position_time > 0:
            position += (now - self.position_time) * self.rate
        position = max(position, 0.0)
        return min(position, self.duration) if self.duration > 0 else position


@dataclass(frozen=True)
class MediaState:
    players: tuple[MediaInfo, ...] = ()
    current: str = ""

    @property
    def player(self) -> MediaInfo | None:
        return next((player for player in self.players if player.app_id == self.current), None)


@dataclass(frozen=True)
class _Timeline:
    position: float
    updated: float
    duration: float


@dataclass(frozen=True)
class _Playback:
    playing: bool
    rate: float
    can_play_pause: bool
    can_previous: bool
    can_next: bool
    can_seek: bool
    can_shuffle: bool
    can_repeat: bool
    shuffle: bool
    repeat: str


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


def _read_timeline(session: MediaSession) -> _Timeline | None:
    """Caller must hold the SMTC lock."""
    timeline = session.get_timeline_properties()
    if not timeline:
        return None
    snapshot = _Timeline(
        timeline.position.total_seconds(),
        timeline.last_updated_time.timestamp(),
        timeline.end_time.total_seconds(),
    )
    del timeline
    return snapshot


def _read_playback(session: MediaSession) -> _Playback | None:
    """Caller must hold the SMTC lock. Reads each IReference once and keeps no COM object."""
    playback = session.get_playback_info()
    if not playback:
        return None
    try:
        status = int(playback.playback_status)
    except TypeError, ValueError:
        status = 0
    raw_rate = playback.playback_rate
    rate = _iref_float(raw_rate, 1.0)
    del raw_rate
    controls = playback.controls
    if controls:
        can = (
            bool(controls.is_play_pause_toggle_enabled),
            bool(controls.is_previous_enabled),
            bool(controls.is_next_enabled),
            bool(controls.is_playback_position_enabled),
            bool(controls.is_shuffle_enabled),
            bool(controls.is_repeat_enabled),
        )
    else:
        can = (True, True, True, False, False, False)
    del controls
    raw_shuffle = playback.is_shuffle_active
    shuffle = _iref_bool(raw_shuffle, False)
    del raw_shuffle
    raw_repeat = playback.auto_repeat_mode
    repeat = REPEAT_MODES.get(_iref_int(raw_repeat, 0), "none")
    del raw_repeat
    del playback
    return _Playback(status == PLAYING, rate, *can, shuffle, repeat)


async def _read_art(reference: IRandomAccessStreamReference) -> bytes | None:
    stream = await reference.open_read_async()
    try:
        buffer = Buffer(stream.size)
        await stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)
        return bytes(buffer)[: buffer.length]
    except Exception as e:
        logger.error("Could not read the album art: %s", e)
        return None
    finally:
        stream.close()


class MediaService(QObject):
    """Watches the Windows media sessions on a thread of its own. Everything that touches WinRT runs there or
    on WinRT's callback threads; the UI only gets MediaState, which never changes once made."""

    changed = pyqtSignal(object)

    _instance: MediaService | None = None

    @classmethod
    def instance(cls) -> MediaService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self.state = MediaState()
        # The rest belongs to the media thread
        self._loop = asyncio.new_event_loop()
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task[Any]] = set()
        # Serialize SMTC/COM reads so WinRT callback threads and the loop never
        # release the same IReference / PlaybackInfo concurrently (heap double-free).
        self._smtc_lock = threading.RLock()
        self._manager: SessionManager | None = None
        self._sessions: dict[str, MediaSession] = {}
        self._unsubscribe: dict[str, list[Callable[[], None]]] = {}
        self._players: dict[str, MediaInfo] = {}
        self._property_reads: dict[str, int] = {}
        self._current = ""
        self._art_revision = 0
        self._thread = threading.Thread(target=self._run, name="MediaService", daemon=True)
        self._thread.start()
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def stop(self) -> None:
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(2)

    def play_pause(self, app_id: str) -> None:
        self._spawn(self._command, app_id, "play or pause", MediaSession.try_toggle_play_pause_async)

    def previous(self, app_id: str) -> None:
        self._spawn(self._command, app_id, "skip back", MediaSession.try_skip_previous_async)

    def next(self, app_id: str) -> None:
        self._spawn(self._command, app_id, "skip", MediaSession.try_skip_next_async)

    def toggle_shuffle(self, app_id: str) -> None:
        self._spawn(self._toggle_shuffle, app_id)

    def cycle_repeat(self, app_id: str) -> None:
        self._spawn(self._cycle_repeat, app_id)

    def seek(self, app_id: str, seconds: float) -> None:
        self._spawn(self._seek, app_id, seconds)

    def switch(self, direction: int) -> None:
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._switch, direction)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            init_apartment(ApartmentType.MULTI_THREADED)
            self._loop.run_until_complete(self._watch())
        except Exception:
            logger.exception("The media service stopped")
        finally:
            self._loop.run_until_complete(self._cancel_tasks())
            self._loop.close()

    async def _watch(self) -> None:
        manager = await SessionManager.request_async()
        self._manager = manager
        sessions_changed = manager.add_sessions_changed(self._bridge(self._refresh, follow_system=False))
        current_changed = manager.add_current_session_changed(self._bridge(self._refresh, follow_system=True))
        try:
            await self._refresh(follow_system=True)
            await self._stop.wait()
        finally:
            manager.remove_sessions_changed(sessions_changed)
            manager.remove_current_session_changed(current_changed)
            for app_id in list(self._sessions):
                self._forget(app_id)
            self._manager = None

    async def _cancel_tasks(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _spawn(self, handler: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        """Runs handler on the media thread; safe from any thread, and a no-op once the service stopped."""
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._start_task, handler, *args)

    def _start_task(self, handler: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        task = self._loop.create_task(handler(*args))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _bridge(self, handler: Callable[..., Coroutine[Any, Any, Any]], **kwargs: Any) -> Callable[[Any, Any], None]:
        """WinRT manager events arrive on WinRT threads, with COM arguments that stay there."""

        def bridge(_sender: Any, _args: Any) -> None:
            self._spawn(partial(handler, **kwargs))

        return bridge

    async def _refresh(self, *, follow_system: bool) -> None:
        manager = self._manager
        if manager is None:
            return
        with self._smtc_lock:
            sessions = {session.source_app_user_model_id: session for session in manager.get_sessions()}
            current = manager.get_current_session()
            system_id = current.source_app_user_model_id if current else None
            del current
        for app_id in [app_id for app_id in self._sessions if app_id not in sessions]:
            self._forget(app_id)
        added = [app_id for app_id in sessions if app_id not in self._sessions]
        for app_id in added:
            self._track(app_id, sessions[app_id])
        del sessions
        for app_id in self._sessions:
            self._snapshot(app_id)
        self._select(system_id, follow_system=follow_system)
        self._publish()
        for app_id in added:
            await self._sync_properties(app_id)

    def _track(self, app_id: str, session: MediaSession) -> None:
        with self._smtc_lock:
            properties = session.add_media_properties_changed(self._on_properties_event)
            timeline = session.add_timeline_properties_changed(self._on_timeline_event)
            playback = session.add_playback_info_changed(self._on_playback_event)
        self._sessions[app_id] = session
        self._unsubscribe[app_id] = [
            partial(session.remove_media_properties_changed, properties),
            partial(session.remove_timeline_properties_changed, timeline),
            partial(session.remove_playback_info_changed, playback),
        ]
        self._players[app_id] = MediaInfo(
            app_id, resolve_source_app_name(app_id) or app_id, get_process_name_for_aumid(app_id) or ""
        )

    def _forget(self, app_id: str) -> None:
        for unsubscribe in self._unsubscribe.pop(app_id, []):
            with contextlib.suppress(Exception):
                unsubscribe()
        self._sessions.pop(app_id, None)
        self._players.pop(app_id, None)
        self._property_reads.pop(app_id, None)

    def _select(self, system_id: str | None, *, follow_system: bool) -> None:
        # Follow Windows' current player, or fall back when the one picked by switching went away
        if follow_system or self._current not in self._players:
            if system_id is not None and system_id in self._players:
                self._current = system_id
            else:
                self._current = next(iter(self._players), "")

    def _publish(self) -> None:
        players = tuple(self._players.values())
        keep_art({player.art_revision: player.art for player in players if player.art is not None})
        self.state = MediaState(players, self._current)
        self.changed.emit(self.state)

    def _snapshot(self, app_id: str) -> None:
        session = self._sessions.get(app_id)
        if session is None:
            return
        with self._smtc_lock:
            timeline = _read_timeline(session)
            playback = _read_playback(session)
        # Playback first: a player first seen while it plays has no position yet that a start could stop
        if playback is not None:
            self._apply_playback(app_id, playback)
        if timeline is not None:
            self._apply_timeline(app_id, timeline)

    def _apply_timeline(self, app_id: str, timeline: _Timeline) -> None:
        player = self._players.get(app_id)
        # WinRT's unset DateTime is 1601-01-01, a negative Unix time
        if player is None or timeline.updated <= 0:
            return
        if timeline.updated > player.position_time:
            player = replace(player, position=timeline.position, position_time=timeline.updated)
        self._players[app_id] = replace(player, duration=timeline.duration)

    def _apply_playback(self, app_id: str, playback: _Playback) -> None:
        player = self._players.get(app_id)
        if player is None:
            return
        if playback.playing != player.playing and player.position_time > 0:
            # Players often skip the timeline event on play and pause, so the position stops or starts here
            now = time.time()
            player = replace(player, position=player.position_at(now), position_time=now)
        self._players[app_id] = replace(
            player,
            playing=playback.playing,
            rate=playback.rate,
            can_play_pause=playback.can_play_pause,
            can_previous=playback.can_previous,
            can_next=playback.can_next,
            can_seek=playback.can_seek,
            can_shuffle=playback.can_shuffle,
            can_repeat=playback.can_repeat,
            shuffle=playback.shuffle,
            repeat=playback.repeat,
        )

    def _applied(self, apply: Callable[[str, Any], None], app_id: str, snapshot: Any) -> None:
        apply(app_id, snapshot)
        self._publish()

    def _on_properties_event(self, session: Any, _args: Any) -> None:
        try:
            self._spawn(self._sync_properties, session.source_app_user_model_id)
        except Exception:
            pass

    def _on_timeline_event(self, session: Any, _args: Any) -> None:
        try:
            app_id = session.source_app_user_model_id
            with self._smtc_lock:
                timeline = _read_timeline(session)
            if timeline is not None:
                self._loop.call_soon_threadsafe(self._applied, self._apply_timeline, app_id, timeline)
        except Exception:
            pass

    def _on_playback_event(self, session: Any, _args: Any) -> None:
        # Crash path from dumps: IReference[double] (playback_rate) double-freed when
        # PlaybackInfo was read later on another thread, so it is read here, once.
        try:
            app_id = session.source_app_user_model_id
            with self._smtc_lock:
                playback = _read_playback(session)
            if playback is not None:
                self._loop.call_soon_threadsafe(self._applied, self._apply_playback, app_id, playback)
        except Exception:
            pass

    async def _sync_properties(self, app_id: str) -> None:
        session = self._sessions.get(app_id)
        if session is None:
            return
        # A track change sends several events; only the newest read may land
        read = self._property_reads.get(app_id, 0) + 1
        self._property_reads[app_id] = read
        try:
            with self._smtc_lock:
                operation = session.try_get_media_properties_async()
            properties = await operation
            if not properties:
                return
            with self._smtc_lock:
                title = properties.title or ""
                artist = properties.artist or ""
                album = properties.album_title or ""
                thumbnail = properties.thumbnail
            del properties
            art = await _read_art(thumbnail) if thumbnail else None
            del thumbnail
        except Exception as e:
            if isinstance(e, OSError) and e.winerror == NOT_READY:
                logger.debug("%s is not ready to say what it plays", app_id)
            else:
                logger.error("Could not read what %s plays: %s", app_id, e)
            return
        player = self._players.get(app_id)
        if player is None or self._property_reads.get(app_id) != read:
            return
        if art is None:
            revision = 0
        elif art == player.art:
            revision = player.art_revision
        else:
            self._art_revision += 1
            revision = self._art_revision
        self._players[app_id] = replace(player, title=title, artist=artist, album=album, art=art, art_revision=revision)
        self._publish()

    async def _command(self, app_id: str, action: str, start: Callable[[MediaSession], Any]) -> bool:
        session = self._sessions.get(app_id)
        if session is None:
            return False
        try:
            with self._smtc_lock:
                operation = start(session)
            return bool(await operation)
        except Exception as e:
            logger.error("Could not %s %s: %s", action, app_id, e)
            return False

    async def _toggle_shuffle(self, app_id: str) -> None:
        player = self._players.get(app_id)
        if player is not None and player.can_shuffle:
            shuffle = not player.shuffle
            await self._command(app_id, "shuffle", lambda s: s.try_change_shuffle_active_async(shuffle))

    async def _cycle_repeat(self, app_id: str) -> None:
        player = self._players.get(app_id)
        if player is not None and player.can_repeat:
            mode = NEXT_REPEAT_MODE[player.repeat]
            await self._command(app_id, "repeat", lambda s: s.try_change_auto_repeat_mode_async(mode))

    async def _seek(self, app_id: str, seconds: float) -> None:
        ticks = int(seconds * 10_000_000)  # 100-nanosecond units
        if not await self._command(app_id, "seek", lambda s: s.try_change_playback_position_async(ticks)):
            return
        player = self._players.get(app_id)
        if player is not None:
            self._players[app_id] = replace(player, position=seconds, position_time=time.time())
            self._publish()

    def _switch(self, direction: int) -> None:
        players = list(self._players)
        if not players:
            return
        index = players.index(self._current) if self._current in players else 0
        self._current = players[(index + direction) % len(players)]
        self._publish()

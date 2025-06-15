import asyncio
import io
import logging
import threading
from typing import Any, Callable

from PIL import Image, ImageFile
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

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_NEXT_TRACK = 0xB0

# Make PIL logger not pollute logs
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


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

        # Create a timer for interpolation
        self._interpolation_timer = QTimer()
        self._interpolation_timer.setInterval(200)
        self._interpolation_timer.timeout.connect(self._interpolate_timeline)
        self._interpolation_timer.start()

        self._run_setup()

    def force_update(self):
        self._on_current_session_changed(self._session_manager, None)

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

    async def _get_session_manager(self):
        return await SessionManager.request_async()

    def _run_setup(self):
        self._session_manager = asyncio.run(self._get_session_manager())
        self._session_manager.add_current_session_changed(self._on_current_session_changed)

        # Manually trigger the callback on startup
        self._on_current_session_changed(self._session_manager, None, is_setup=True)

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
                        sessions = self._session_manager.get_sessions()
                        if not any(
                            self._are_same_sessions(sessions[i], self._current_session) for i in range(sessions.size)
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

    def switch_session(self, direction: int):
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
            if DEBUG:
                self._log.info(f"Switching to session {idx} ({sessions[idx].source_app_user_model_id})")
            self._current_session = sessions[idx]

        self._on_current_session_changed(self._session_manager, None, is_overridden=True)

    def play_pause(self):
        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.try_toggle_play_pause_async()

    def prev(self):
        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.try_skip_previous_async()

    def next(self):
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

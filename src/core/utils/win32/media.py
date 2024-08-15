import ctypes
import logging
from settings import DEBUG 
from typing import Any, Callable

import asyncio

import threading
from winsdk.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference
from PIL import Image, ImageFile
import io

from core.utils.utilities import Singleton
from core.utils.win32.system_function import KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP

from winsdk.windows.media.control import (GlobalSystemMediaTransportControlsSessionManager as SessionManager,
                                          GlobalSystemMediaTransportControlsSession as Session,
                                          SessionsChangedEventArgs, MediaPropertiesChangedEventArgs,
                                          TimelinePropertiesChangedEventArgs, PlaybackInfoChangedEventArgs)

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_NEXT_TRACK = 0xB0

# Make PIL logger not pollute logs
pil_logger = logging.getLogger('PIL')
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

        self._subscription_channels = {channel: [] for channel in ['media_info', 'playback_info', 'timeline_info',
                                                                   'session_status']}
        self._subscription_channels_lock = threading.RLock()
        self._registration_tokens = {}

        self._run_setup()

    def force_update(self):
        self._on_current_session_changed(self._session_manager, None)

    def subscribe(self, callback: Callable, channel: str):
        with self._subscription_channels_lock:
            try:
                self._subscription_channels[channel].append(callback)
            except KeyError:
                raise ValueError(f'Incorrect channel subscription type provided ({channel}). '
                                 f'Valid options are {list(self._subscription_channels.keys())}')

    def stop(self):
        # Clear subscriptions
        with self._subscription_channels_lock:
            self._subscription_channels = {k: [] for k in self._subscription_channels.keys()}

        with self._current_session_lock:
            session = self._current_session

        # Remove all our subscriptions
        if session is not None:
            session.remove_media_properties_changed(self._registration_tokens['media_info'])
            session.remove_timeline_properties_changed(self._registration_tokens['timeline_info'])
            session.remove_playback_info_changed(self._registration_tokens['playback_info'])

    def _register_session_callbacks(self):
        with self._current_session_lock:
            self._registration_tokens['playback_info'] = self._current_session.add_playback_info_changed(self._on_playback_info_changed)
            self._registration_tokens['timeline_info'] = self._current_session.add_timeline_properties_changed(self._on_timeline_properties_changed)
            self._registration_tokens['media_info'] = self._current_session.add_media_properties_changed(self._on_media_properties_changed)

    async def _get_session_manager(self):
        return await SessionManager.request_async()

    def _run_setup(self):
        self._session_manager = asyncio.run(self._get_session_manager())
        self._session_manager.add_current_session_changed(self._on_current_session_changed)

        # Manually trigger the callback on startup
        self._on_current_session_changed(self._session_manager, None, is_setup=True)

    def _on_current_session_changed(self, manager: SessionManager, args: SessionsChangedEventArgs, is_setup=False):
        if DEBUG:
            self._log.debug('MediaCallback: _on_current_session_changed')

        with self._current_session_lock:
            self._current_session = manager.get_current_session()

            if self._current_session is not None:

                # If the current session is not None, register callbacks
                self._register_session_callbacks()

                if not is_setup:
                    self._on_playback_info_changed(self._current_session, None)
                    self._on_timeline_properties_changed(self._current_session, None)
                    self._on_media_properties_changed(self._current_session, None)

            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels['session_status']

            for callback in callbacks:
                callback(self._current_session is not None)

    def _on_playback_info_changed(self, session: Session, args: PlaybackInfoChangedEventArgs):
        if DEBUG:
            self._log.info('MediaCallback: _on_playback_info_changed')
        with self._playback_info_lock:
            self._playback_info = session.get_playback_info()

            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels['playback_info']

            # Perform callbacks
            for callback in callbacks:
                callback(self._playback_info)

    def _on_timeline_properties_changed(self, session: Session, args: TimelinePropertiesChangedEventArgs):
        if DEBUG:
            self._log.info('MediaCallback: _on_timeline_properties_changed')
        with self._timeline_info_lock:
            self._timeline_info = session.get_timeline_properties()

            # Get subscribers
            with self._subscription_channels_lock:
                callbacks = self._subscription_channels['timeline_info']

            # Perform callbacks
            for callback in callbacks:
                callback(self._timeline_info)

    def _on_media_properties_changed(self, session: Session, args: MediaPropertiesChangedEventArgs):
        if DEBUG:
            self._log.debug('MediaCallback: _on_media_properties_changed')
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            with self._media_info_lock:
                self._event_loop.run_until_complete(self._update_media_properties(session))
        else:
            # Only for the initial timer based update, because it is called from an event loop
            asyncio.create_task(self._update_media_properties(session))

    async def _update_media_properties(self, session: Session):
        if DEBUG:
            self._log.debug('MediaCallback: Attempting media info update')

        try:
            media_info = await session.try_get_media_properties_async()

            media_info = self._properties_2_dict(media_info)

            # Skip initial change calls where the thumbnail is None. This prevents processing multiple updates.
            # Might prevent showing info for no-thumbnail media
            if media_info['thumbnail'] is None:
                if DEBUG:
                    self._log.debug('MediaCallback: Skipping media info update: no thumbnail')
                return

            media_info['thumbnail'] = await self.get_thumbnail(media_info['thumbnail'])
        except Exception as e:
            self._log.error(f'MediaCallback: Error occurred whilst fetching media properties and thumbnail: {e}')
            return

        self._media_info = media_info

        # Get subscribers
        with self._subscription_channels_lock:
            callbacks = self._subscription_channels['media_info']

        # Perform callbacks
        for callback in callbacks:
            callback(self._media_info)
        if DEBUG:
            self._log.debug('MediaCallback: Media info update finished')

    @staticmethod
    def _properties_2_dict(obj) -> dict[str, Any]:
        return {name: getattr(obj, name) for name in dir(obj) if not name.startswith('_')}

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
            await readable_stream.read_async(thumb_read_buffer, thumb_read_buffer.capacity, InputStreamOptions.READ_AHEAD)

            # Convert bytearray to pillow image
            pillow_image = Image.open(io.BytesIO(thumb_read_buffer))

            # Remove buffer
            del thumb_read_buffer

            return pillow_image
        except Exception as e:
            logging.error(f'get_thumbnail(): Error occurred when loading the thumbnail: {e}')
            return None
        finally:
            # Close the stream
            readable_stream.close()

    @staticmethod
    def play_pause():
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def prev():
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def next():
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, KEYEVENTF_KEYUP, 0)

# media.py
import ctypes
from typing import Dict, Union, Optional

import winsdk.windows.media.control
from winsdk.windows.storage.streams import Buffer, InputStreamOptions, IRandomAccessStreamReference
from PIL import Image, ImageFile
import io

from core.utils.win32.system_function import KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_NEXT_TRACK = 0xB0


# Buffer is set to 5 MB, which is a bit overkill. Haven't found a way yet to find the size of the stream up front.
BUFFER_SIZE = 5 * 1024 * 1024


class MediaOperations:

    @staticmethod
    async def read_stream_into_buffer(stream_ref, buffer):
        readable_stream = await stream_ref.open_read_async()
        await readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)

    @staticmethod
    async def get_thumbnail(thumbnail_stream_reference: IRandomAccessStreamReference) -> ImageFile:
        """
        Read the thumbnail for the IRandomAccessStreamReference and return it as PIL ImageFile
        :param thumbnail_stream_reference: Thumbnail stream reference
        :return: Loaded thumbnail
        """
        thumb_read_buffer = Buffer(5000000)

        # copies data from data stream reference into buffer created above
        await MediaOperations.read_stream_into_buffer(thumbnail_stream_reference, thumb_read_buffer)

        # Convert bytearray to pillow image
        pillow_image = Image.open(io.BytesIO(thumb_read_buffer))

        del thumb_read_buffer

        return pillow_image

    @staticmethod
    async def get_media_properties() -> Optional[Dict[str, Union[str, int, IRandomAccessStreamReference]]]:
        """
        Get media properties and the currently running media file
        """
        session_manager = await winsdk.windows.media.control.GlobalSystemMediaTransportControlsSessionManager.request_async()
        current_session = session_manager.get_current_session()

        # If no music is playing, return None
        if current_session is None:
            return None

        media_properties = await current_session.try_get_media_properties_async()
        playback_info = current_session.get_playback_info()
        timeline_properties = current_session.get_timeline_properties()

        media_info = {
            "album_artist": media_properties.album_artist,
            "album_title": media_properties.album_title,
            "album_track_count": media_properties.album_track_count,
            "artist": media_properties.artist,
            "title": media_properties.title,
            "playback_type": str(media_properties.playback_type),
            "subtitle": media_properties.subtitle,
            "album": media_properties.album_title,
            "track_number": media_properties.track_number,
            "thumbnail": media_properties.thumbnail,
            "playing": playback_info.playback_status == 4,
            "prev_available": playback_info.controls.is_previous_enabled,
            "next_available": playback_info.controls.is_next_enabled,
            "total_time": timeline_properties.end_time.total_seconds(),
            "current_time": timeline_properties.position.total_seconds()
            # genres
        }
        return media_info

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

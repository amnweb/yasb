"""
Media source applications mapping.

This file contains the mapping of source application identifiers to their
display names for the media widget. This allows easy addition of new media
applications without modifying the main media widget code.
"""

# Dictionary mapping source app IDs to their display names
MEDIA_SOURCE_APPS = {
    # Audio Players
    "AIMP.exe": "AIMP",
    "winamp.exe": "Winamp",
    "foobar2000.exe": "Foobar2000",
    "MusicBee.exe": "MusicBee",
    "mpv.exe": "NSMusicS",
    # Streaming Services
    "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify": "Spotify",
    "Spotify.exe": "Spotify",
    "AppleInc.AppleMusicWin_nzyj5cx40ttqa!App": "Apple Music",
    "com.badmanners.murglar": "Murglar",
    "com.squirrel.TIDAL.TIDAL": "Tidal",
    "com.squirrel.Qobuz.Qobuz": "Qobuz",
    "com.squirrel.youtube_music_desktop_app.youtube-music-desktop-app": "YouTube Music",
    # Web Browsers
    "308046B0AF4A39CB": "FireFox",
    "firefox.exe": "FireFox",
    "F0DC299D809B9700": "Zen",
    "MSEdge": "Edge",
    "msedge.exe": "Edge",
    "Chrome": "Chrome",
    "chrome.exe": "Chrome",
    "opera.exe": "Opera",
    "Brave": "Brave",
    "Brave.Q2QWMKZ4RMMIMDZ2JQ2NKBXFT4": "Brave",
    # System Media Players
    "Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic": "Media Player",
}


def get_source_app_display_name(source_app_id: str) -> str:
    """
    Get the display name for a source application ID.

    Args:
        source_app_id: The source application identifier

    Returns:
        The display name for the app, or None if not found
    """
    return MEDIA_SOURCE_APPS.get(source_app_id)


def get_source_app_class_name(display_name: str) -> str:
    """
    Get a CSS-friendly class name from a display name.

    Args:
        display_name: The display name of the app

    Returns:
        A CSS-friendly class name (lowercase, spaces replaced with hyphens)
    """
    if display_name:
        return display_name.lower().replace(" ", "-")
    return None


def add_source_app(source_app_id: str, display_name: str):
    """
    Add a new source application mapping.

    Args:
        source_app_id: The source application identifier
        display_name: The display name for the app
    """
    MEDIA_SOURCE_APPS[source_app_id] = display_name


def get_all_source_apps() -> dict:
    """
    Get all source application mappings.

    Returns:
        Dictionary of all source app mappings
    """
    return MEDIA_SOURCE_APPS.copy()

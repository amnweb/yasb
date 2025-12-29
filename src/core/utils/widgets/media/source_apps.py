"""
Media source applications mapping.

This file contains the mapping of source application identifiers to their
display names for the media widget.

For complex applications that have different process names than their AUMID,
use dictionary format:
    "aumid": {"name": "Display Name", "process": "executable.exe"}

For simple applications where AUMID matching is sufficient, use string format:
    "aumid": "Display Name"
"""

from typing import Any

MEDIA_SOURCE_APPS = {
    # Audio Players
    "AIMP.exe": "AIMP",
    "winamp.exe": "Winamp",
    "foobar2000.exe": "Foobar2000",
    "MusicBee.exe": "MusicBee",
    "mpv.exe": "NSMusicS",
    "PotPlayerMini64.exe": "PotPlayer",
    # Streaming Services
    "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify": "Spotify",
    "Spotify.exe": "Spotify",
    "AppleInc.AppleMusicWin_nzyj5cx40ttqa!App": "Apple Music",
    "com.badmanners.murglar": {
        "name": "Murglar",
        "process": "Murglar.exe",
    },
    "com.squirrel.TIDAL.TIDAL": {
        "name": "Tidal",
        "process": "TIDAL.exe",
    },
    "com.squirrel.Qobuz.Qobuz": {
        "name": "Qobuz",
        "process": "Qobuz.exe",
    },
    "com.squirrel.youtube_music_desktop_app.youtube-music-desktop-app": {
        "name": "YouTube Music",
        "process": "youtube-music-desktop-app.exe",
    },
    "com.github.th-ch.youtube-music": {
        "name": "YouTube Music",
        "process": "YouTube Music.exe",
    },
    # Web Browsers
    "308046B0AF4A39CB": {
        "name": "FireFox",
        "process": "firefox.exe",
    },
    "firefox.exe": "FireFox",
    "F0DC299D809B9700": {
        "name": "Zen",
        "process": "zen.exe",
    },
    "A5B78042B5B03693": {
        "name": "Zen",
        "process": "zen.exe",
    },
    "zen.exe": "Zen",
    "MSEdge": {
        "name": "Edge",
        "process": "msedge.exe",
    },
    "msedge.exe": "Edge",
    "Chrome": {
        "name": "Chrome",
        "process": "chrome.exe",
    },
    "chrome.exe": "Chrome",
    "opera.exe": "Opera",
    "Brave": {
        "name": "Brave",
        "process": "brave.exe",
    },
    "Brave.Q2QWMKZ4RMMIMDZ2JQ2NKBXFT4": {
        "name": "Brave",
        "process": "brave.exe",
    },
    # System Media Players
    "Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic": "Media Player",
}


def _match_aumid_by_regex(source_app_id: str) -> dict[str, str | None] | None:
    """
    Attempt to match common AUMID patterns using regex when an exact
    dictionary lookup fails.

    Returns a mapping dict with 'name' and optional 'process', or None.
    """
    import re

    if not source_app_id:
        return None

    if re.match(r"^music\.youtube\.com-[^!]+!App$", source_app_id, re.IGNORECASE):
        return {"name": "YouTube Music", "process": "msedge.exe"}

    if re.match(r"^(?:www\.)?youtube\.com-[^!]+!App$", source_app_id, re.IGNORECASE):
        return {"name": "YouTube", "process": "msedge.exe"}

    if re.match(r"^Brave\._crx_[A-Za-z0-9_-]+$", source_app_id, re.IGNORECASE):
        return {"name": "Brave", "process": "brave.exe"}

    if re.match(r"^Chrome\._crx_[A-Za-z0-9_-]+$", source_app_id, re.IGNORECASE):
        return {"name": "Chrome", "process": "chrome.exe"}

    # Match Opera and Opera GX with version numbers
    # Examples: OperaSoftware.OperaStable.12345, OperaSoftware.OperaGXStable.67890
    #           OperaSoftware.OperaGXWebBrowser.1759345670
    if re.match(r"^OperaSoftware\.Opera(?:GX|Stable|WebBrowser)", source_app_id, re.IGNORECASE):
        if "GX" in source_app_id:
            return {"name": "Opera GX", "process": "opera.exe"}
        return {"name": "Opera", "process": "opera.exe"}

    return None


def get_source_app_display_name(source_app_id: str) -> str:
    """
    Get the display name for a source application ID.

    Args:
        source_app_id: The source application identifier

    Returns:
        The display name for the app, or None if not found
    """
    entry = MEDIA_SOURCE_APPS.get(source_app_id)
    if isinstance(entry, dict):
        return entry.get("name")
    if isinstance(entry, str):
        return entry

    fallback = _match_aumid_by_regex(source_app_id)
    if fallback:
        return fallback.get("name")
    return None


def get_source_app_mapping(source_app_id: str) -> dict[str, Any] | None:
    """
    Get the complete mapping information for a source application ID.

    Args:
        source_app_id: The source application identifier

    Returns:
        Dictionary with 'name' and 'process' keys, or None if not found
    """
    entry = MEDIA_SOURCE_APPS.get(source_app_id)
    if isinstance(entry, dict):
        return entry
    elif isinstance(entry, str):
        return {"name": entry, "process": None}

    fallback = _match_aumid_by_regex(source_app_id)
    if fallback:
        return fallback

    return None


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

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.widgets.services.lyrics.session import TrackInfo

# Patterns used to reject video and release-file titles.
NON_SONG_PATTERNS: list[str] = [
    r"\.(?:mkv|mp4|avi|mov|wmv|webm|flv|ts|m4v|vob|iso)$",
    r"\b(?:\d{3,4}[pi]|2160p|1080p|1080i|720p|540p|480p|360p|4k|8k|uhd|fhd|hd|10-?bit|8-?bit|60fps|120fps|hdr(?:10(?:\+)?)?|dolby\s*vision|dovi)\b",
    r"\b(?:web-?dl|webrip|webrp|web-?hd|bluray|blu-ray|brrip|bdrip|bd\d{3,4}p|dvdrip|dvd|hdtv|pdtv|hdrip|tvrip|camrip|telesync|hdcam|remux|hc(?:\.web-dl)?)\b",
    r"\b(?:[xh]\.?26[45]|hevc|avc|xvid|divx|av1|vp9|prores)\b",
    r"\b(?:[268]ch|5\.1|7\.1|2\.0|ddp?5\.1(?:\.atmos)?|dd\+?5\.1|dts(?:-hd)?|atmos|truehd|ac3|eac3)\b",
    r"\b(?:nf|dsnp|amzn|atvp|hmax|max|tving|friday|wavve|iqiyi|wetv|viu|peacock|paramount\+)\.(?:web-dl|webrip)\b",
    r"(\s*[-|]\s*(?:youtube|netflix|twitch|prime\s+video|disney\+|crunchyroll|hulu)$)",
    r"\b\d{2,4}\s*(?:mb|gb|kbps)\b",
    r"\b(?:e-?subs?|eng-?sub|multi-?sub|dual-?audio|multi-?audio|unrated|remastered|extended(?:\s+cut)?|director'?s\.?cut|proper|repack|rerip|internal)\b",
    r"\b(?:s\d{1,2}e\d{1,2}|s\d{1,2}|e\d{1,2}(?:\.end)?|season\s*\d+|episode\s*\d+|chapter\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+))\b",
    r"^\d{1,3}\.\s",
    r"\b(?:pahe\.(?:in|me|li)|psa|yify(?:\+hi)?|yts(?:\.[a-z]{2})?|galaxyrg|mkvking|bone|phanteam|dramaday(?:\.me)?|revolt|mrhulk|sin|deeplife|aric|adweb|rel1vin|ao|mkvdrama\.org|rarbg|tgx|fgt|flux|ntb|ion10|qxr|utr|animekaizoku|subsplease|judas|erai-raws|horriblesubs|hevcbay\.com|moviesrush\.(?:org|in)|privatemoviez|x265movies\.com)\b",
    r"\b(?:official\s+trailer|teaser(?:\s+trailer)?|movie\s+clip|film\s+clip|deleted\s+scene|sneak\s+peek|full\s+movie|short\s+film|blooper(?:s)?)\b",
    r"\b(?:walkthrough|gameplay|playthrough|let's\s+play|speedrun|stream\s+vod|twitch\s+vod|livestream|live\s+stream|no\s+commentary)\b",
    r"\b(?:review|unboxing|vlog|daily\s+vlog|podcast|interview|reaction|tutorial|how\s+to|diy|explained|documentary|video\s+essay|tier\s+list|ranking\s+every|compilation|top\s+10|top\s+5|q&a|haul)\b",
    r"\b(?:breaking\s+news|press\s+conference|webinar|live\s+broadcast)\b",
    r"(?:watch\s+cartoons\s+online|watch\s+anime\s+online|english\s+dub\s+anime)",
]

_COMPILED_BLACKLIST = re.compile("|".join(NON_SONG_PATTERNS), re.IGNORECASE)

SAFE_MUSIC_VIDEO_TAGS = re.compile(
    r"\s*[\(\[\{]\s*(?:official\s+music\s+video|official\s+video|music\s+video|official\s+audio|lyric\s+video|audio|visualizer|mv)\s*[\)\]\}]",
    re.IGNORECASE,
)


def is_blacklisted_media(title: str, artist: str = "") -> bool:
    """
    Returns True if the title or artist matches any non-song/video/movie pattern.
    Checks both original string and dot-delimited scene release variants.
    """
    if not title:
        return True

    if _COMPILED_BLACKLIST.search(title) or (artist and _COMPILED_BLACKLIST.search(artist)):
        return True

    title_spaced = title.replace(".", " ")
    if _COMPILED_BLACKLIST.search(title_spaced):
        return True

    return False


def should_search_lyrics(track: TrackInfo | None) -> bool:
    """
    Determines whether the given SMTC TrackInfo qualifies as an actual song
    and should trigger lyrics provider searches.
    """
    if not track or not track.title or not track.title.strip():
        return False

    if is_blacklisted_media(track.title, track.artist):
        return False

    return True


def sanitize_song_title(title: str) -> str:
    """
    Removes harmless music video tags (like '(Official Music Video)')
    to yield clean song search terms.
    """
    if not title:
        return ""
    cleaned = SAFE_MUSIC_VIDEO_TAGS.sub("", title).strip()
    return cleaned or title

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, cast

from settings import APP_NAME, GITHUB_URL

from ..http import get
from ..models import Hit, Lyrics, Query
from ..normalize import normalize_lines
from ..parsing.lrc import parse_lrc
from ..parsing.yrc import parse_yrc
from .base import LyricsProvider

logger = logging.getLogger("core.widgets.services.lyrics.providers.netease")

SOURCE = "NetEase"
SEARCH_URL = "https://music.163.com/api/search/get"
LYRIC_URL = "https://music.163.com/api/song/lyric/v1"
USER_AGENT = f"{APP_NAME} ({GITHUB_URL})"
REFERER = "https://music.163.com"
MAX_CANDIDATES = 3


class NetEaseProvider(LyricsProvider):
    name: str = SOURCE
    trust: int = 0

    def __init__(self, timeout: float = 6.0) -> None:
        self._timeout = timeout

    def search(self, query: Query) -> list[Hit]:
        hits: list[Hit] = []

        try:
            wanted = f"{query.title} {query.artist}".strip()
            params = {
                "s": wanted,
                "type": "1",
                "limit": "5",
            }
            headers = {
                "User-Agent": USER_AGENT,
                "Referer": REFERER,
            }

            resp = get(SEARCH_URL, params=params, headers=headers, timeout=self._timeout)
            if resp.status_code != 200:
                return []

            data = cast("dict[str, Any]", resp.json())
            result = cast("dict[str, Any]", data.get("result") or {})
            songs: list[dict[str, Any]] = cast("list[dict[str, Any]]", result.get("songs") or [])
            if not songs:
                return []

            shortlisted_songs = self._shortlist(songs, query.duration_s)
            results: list[dict[str, Any] | None] = []
            if shortlisted_songs:
                with ThreadPoolExecutor(max_workers=len(shortlisted_songs)) as pool:
                    fetcher = partial(self._fetch_sheet, headers=headers)
                    results = list(pool.map(fetcher, shortlisted_songs))

            for song, result in zip(shortlisted_songs, results):
                if isinstance(result, dict):
                    hit = self._build_hit(song, result, query)
                    if hit:
                        hits.append(hit)
        except Exception as e:
            logger.debug("NetEase search error: %s", e)

        return hits

    def _shortlist(self, songs: list[dict[str, Any]], duration_s: float | None) -> list[dict[str, Any]]:
        if duration_s is None or duration_s <= 0:
            return songs[:MAX_CANDIDATES]

        def diff(s: dict[str, Any]) -> float:
            d_ms = s.get("duration", 0)
            return abs((d_ms / 1000.0) - duration_s)

        sorted_songs = sorted(songs, key=diff)
        return sorted_songs[:MAX_CANDIDATES]

    def _fetch_sheet(self, song: dict[str, Any], headers: dict[str, str]) -> dict[str, Any] | None:
        song_id = song.get("id")
        if not song_id:
            return None

        params = {
            "id": str(song_id),
            "cp": "false",
            "lv": "0",
            "tv": "0",
            "rv": "0",
            "kv": "0",
            "yv": "0",
            "ytv": "0",
            "yrv": "0",
        }

        try:
            resp = get(LYRIC_URL, params=params, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _build_hit(self, song: dict[str, Any], sheet: dict[str, Any], query: Query) -> Hit | None:
        pure_music = bool(sheet.get("pureMusic", False))
        yrc_data: dict[str, Any] = sheet.get("yrc") or {}
        lrc_data: dict[str, Any] = sheet.get("lrc") or {}

        yrc_text = str(yrc_data.get("lyric") or "").strip()
        lrc_text = str(lrc_data.get("lyric") or "").strip()

        writers: list[str] = []
        lines = None

        if yrc_text:
            lines, w = parse_yrc(yrc_text, title=query.title, artists=[query.artist])
            writers.extend(w)

        if not lines and lrc_text:
            raw = parse_lrc(lrc_text)
            if raw:
                lines = normalize_lines(raw, title=query.title, artists=[query.artist])

        if pure_music:
            lyrics = Lyrics(plain="")
            instrumental = True
        elif lines:
            lyrics = Lyrics(lines=lines)
            instrumental = False
        else:
            return None

        artists_raw = cast("list[dict[str, Any]]", song.get("artists") or [])
        artists_list = [str(a.get("name")) for a in artists_raw if a.get("name")]
        artist_str = ", ".join(artists_list) if artists_list else query.artist
        dur_ms = int(song.get("duration") or 0)
        dur_s = (dur_ms / 1000.0) if dur_ms > 0 else None

        return Hit(
            source=SOURCE,
            trust=self.trust,
            lyrics=lyrics,
            instrumental=instrumental,
            title=song.get("name") or query.title,
            artist=artist_str,
            duration_s=dur_s,
            writers=writers,
        )

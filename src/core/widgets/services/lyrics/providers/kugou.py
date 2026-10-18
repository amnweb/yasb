from __future__ import annotations

import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from urllib.parse import quote

from settings import APP_NAME, GITHUB_URL

from ..http import get
from ..models import Hit, Lyrics, Query
from ..normalize import normalize_lines
from ..parsing.krc import decode_krc, parse_krc
from ..parsing.lrc import parse_lrc
from .base import LyricsProvider

logger = logging.getLogger("core.widgets.services.lyrics.providers.kugou")

SOURCE = "Kugou"
SEARCH_URL = "https://mobiles.kugou.com/api/v3/search/song"
CANDIDATES_URL = "https://lyrics.kugou.com/search"
DOWNLOAD_URL = "https://lyrics.kugou.com/download"


USER_AGENT = f"{APP_NAME} ({GITHUB_URL})"


class KugouProvider(LyricsProvider):
    name: str = SOURCE
    trust: int = 0

    def __init__(self, timeout: float = 8.0) -> None:
        self._timeout = timeout

    def search(self, query: Query) -> list[Hit]:
        hits: list[Hit] = []

        try:
            clean_title = (
                re.sub(
                    r"\s*[\(\[][^\)\]]*(?:feat|ft|with|remix|version|edit|live|bonus|deluxe)[^\)\]]*[\)\]]",
                    "",
                    query.title,
                    flags=re.I,
                )
                .split(" - ")[0]
                .strip()
                or query.title
            )

            primary_artist = query.artist
            if primary_artist:
                for delim in (",", "&", "feat.", "ft.", "/"):
                    if delim in primary_artist:
                        primary_artist = primary_artist.split(delim)[0].strip()

            wanted = f"{clean_title} {primary_artist}".strip()
            if not wanted:
                wanted = (query.title or query.artist).strip()
            encoded_kw = quote(wanted)
            headers = {"User-Agent": USER_AGENT}

            search_url = f"{SEARCH_URL}?format=json&keyword={encoded_kw}&page=1&pagesize=10&showtype=1"
            resp = get(search_url, headers=headers, timeout=self._timeout)
            if resp.status_code != 200:
                return []

            data = cast("dict[str, Any]", resp.json())
            payload = cast("dict[str, Any]", data.get("data") or {})
            songs: list[dict[str, Any]] = cast("list[dict[str, Any]]", payload.get("info") or [])
            if not songs:
                return []

            if query.duration_s and query.duration_s > 0:
                songs.sort(key=lambda s: abs(s.get("duration", 0) - query.duration_s))

            artists = [a for a in (query.artist, primary_artist) if a]

            def _fetch_song_hits(song: dict[str, Any]) -> list[Hit]:
                song_hash = song.get("hash")
                dur_s = song.get("duration", 0)
                dur_ms = dur_s * 1000
                if not song_hash:
                    return []

                cand_params = {
                    "ver": "1",
                    "man": "yes",
                    "client": "mobi",
                    "hash": song_hash,
                    "duration": str(dur_ms),
                }

                try:
                    cand_resp = get(CANDIDATES_URL, params=cand_params, headers=headers, timeout=self._timeout)
                    if cand_resp.status_code != 200:
                        return []
                    cand_data = cand_resp.json()
                    candidates: list[dict[str, Any]] = cand_data.get("candidates") or []
                    if not candidates:
                        return []

                    candidates.sort(key=lambda c: 0 if c.get("krctype") == 2 else 1)

                    song_hits: list[Hit] = []
                    for cand in candidates[:2]:
                        cand_id = cand.get("id")
                        accesskey = cand.get("accesskey")
                        krctype = cand.get("krctype")

                        if not cand_id or not accesskey:
                            continue

                        is_krc = krctype == 2
                        dl_params = {
                            "ver": "1",
                            "client": "pc",
                            "id": str(cand_id),
                            "accesskey": str(accesskey),
                            "fmt": "krc" if is_krc else "lrc",
                            "charset": "utf8",
                        }

                        dl_resp = get(DOWNLOAD_URL, params=dl_params, headers=headers, timeout=self._timeout)
                        if dl_resp.status_code != 200:
                            continue

                        dl_data = dl_resp.json()
                        b64_content = dl_data.get("content")
                        if not b64_content:
                            continue

                        lines = []
                        if is_krc:
                            try:
                                krc_text = decode_krc(b64_content)
                                lines = parse_krc(krc_text, title=query.title, artists=artists)
                            except Exception as e:
                                logger.debug("Failed to decode Kugou KRC: %s", e)

                        if not lines:
                            try:
                                raw_bytes = base64.b64decode(b64_content)
                                lrc_text = raw_bytes.decode("utf-8", errors="replace")
                                raw_lines = parse_lrc(lrc_text)
                                if raw_lines:
                                    lines = normalize_lines(raw_lines, title=query.title, artists=artists)
                            except Exception:
                                continue

                        if not lines:
                            continue

                        song_hits.append(
                            Hit(
                                source=SOURCE,
                                trust=self.trust,
                                lyrics=Lyrics(lines=lines),
                                instrumental=False,
                                title=song.get("songname") or query.title,
                                artist=song.get("singername") or query.artist,
                                duration_s=float(dur_s) if dur_s > 0 else None,
                            )
                        )
                        if song_hits and song_hits[-1].lyrics.worded():
                            break

                    return song_hits
                except Exception as e:
                    logger.debug("Error fetching candidates for song %s: %s", song_hash, e)
                    return []

            shortlist = songs[:4]
            if shortlist:
                with ThreadPoolExecutor(max_workers=len(shortlist)) as pool:
                    for song_hits in pool.map(_fetch_song_hits, shortlist):
                        hits.extend(song_hits)
        except Exception as e:
            logger.debug("Kugou search error: %s", e)

        return hits

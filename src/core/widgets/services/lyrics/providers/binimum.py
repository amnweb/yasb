from __future__ import annotations

import logging
from typing import Any

from settings import APP_NAME, GITHUB_URL

from ..http import get
from ..models import Hit, Lyrics, Query
from ..parsing.ttml import parse_ttml
from .base import LyricsProvider

logger = logging.getLogger("core.widgets.services.lyrics.providers.binimum")

SOURCE = "Apple Music"
SEARCH_URL = "https://lyrics-api.binimum.org/"
TRUST = 180
USER_AGENT = f"{APP_NAME} ({GITHUB_URL})"


class BinimumProvider(LyricsProvider):
    name: str = SOURCE
    trust: int = TRUST
    supports_multi_voice: bool = True

    def __init__(self, timeout: float = 6.0) -> None:
        self._timeout = timeout

    def search(self, query: Query) -> list[Hit]:
        hits: list[Hit] = []

        try:
            params: dict[str, Any] = {
                "track": query.title,
                "artist": query.artist,
            }
            if query.duration_s is not None and query.duration_s > 0:
                params["duration"] = str(round(query.duration_s))

            headers = {"User-Agent": USER_AGENT}

            resp = get(SEARCH_URL, params=params, headers=headers, timeout=self._timeout)
            if resp.status_code == 404:
                return []
            if resp.status_code != 200:
                return []

            data = resp.json()
            results: list[dict[str, Any]] = data.get("results") or []
            if not results:
                return []

            def is_worded(item: dict[str, Any]) -> int:
                t = item.get("timing_type", "")
                return 0 if t in ("word", "syllable") else 1

            results.sort(key=is_worded)

            best = None
            url = None
            for item in results:
                u = item.get("lyricsUrl")
                if u and u.startswith("https://"):
                    best = item
                    url = u
                    break

            if not best or not url:
                return []

            sheet_resp = get(url, headers=headers, timeout=self._timeout)
            if sheet_resp.status_code != 200:
                return []

            lines, writers = parse_ttml(sheet_resp.text, title=query.title, artists=[query.artist])
            if not lines:
                return []

            lyrics = Lyrics(lines=lines)
            dur_s = float(best["duration"]) if best.get("duration") else None

            hits.append(
                Hit(
                    source=SOURCE,
                    trust=self.trust,
                    lyrics=lyrics,
                    instrumental=False,
                    title=best.get("track_name") or query.title,
                    artist=best.get("artist_name") or query.artist,
                    duration_s=dur_s,
                    writers=writers,
                )
            )
        except Exception as e:
            logger.debug("Binimum search error: %s", e)

        return hits

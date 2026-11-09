from __future__ import annotations

import logging
from typing import Any

from settings import APP_NAME, GITHUB_URL

from ..http import get
from ..models import Hit, Lyrics, Query
from ..parsing.lrc import parse_lrc
from ..parsing.ttml import parse_ttml
from ..rank import alike, artists_alike
from .base import LyricsProvider

logger = logging.getLogger("core.widgets.services.lyrics.providers.lrcred")

SOURCE = "lrc.red"
SEARCH_URL = "https://lrc.red/search.json"
BASE_URL = "https://lrc.red/s"
TRUST = 175
USER_AGENT = f"{APP_NAME} ({GITHUB_URL})"


class LrcRedProvider(LyricsProvider):
    name: str = SOURCE
    trust: int = TRUST
    supports_multi_voice: bool = True

    def __init__(self, timeout: float = 6.0) -> None:
        self._timeout = timeout

    def search(self, query: Query) -> list[Hit]:
        hits: list[Hit] = []
        if not query.title:
            return hits

        try:
            q_str = f"{query.title} {query.artist or ''}".strip()
            headers = {"User-Agent": USER_AGENT}

            resp = get(SEARCH_URL, params={"q": q_str}, headers=headers, timeout=self._timeout)
            if resp.status_code != 200:
                return []

            data = resp.json()
            raw_hits: list[dict[str, Any]] = data.get("hits") or []
            if not raw_hits:
                return []

            # Filter candidates by title & artist likeness
            matching_hits: list[dict[str, Any]] = []
            for h in raw_hits:
                h_title = h.get("title")
                h_artist = h.get("artist")
                if alike(h_title, query.title):
                    if not query.artist or artists_alike(h_artist, query.artist):
                        matching_hits.append(h)

            if not matching_hits:
                matching_hits = [h for h in raw_hits if alike(h.get("title"), query.title)] or raw_hits[:3]

            if query.duration_s is not None and query.duration_s > 0:
                target_dur: float = query.duration_s
                matching_hits.sort(
                    key=lambda h: abs(float(h.get("duration", 0)) - target_dur) if h.get("duration") else 999.0
                )

            for cand in matching_hits[:2]:
                isrc = cand.get("isrc")
                if not isrc:
                    continue

                # 1. Try TTML (word-level timing with multi-voice vocal lanes)
                ttml_url = f"{BASE_URL}/{isrc}.ttml"
                ttml_resp = get(ttml_url, headers=headers, timeout=self._timeout)

                lines = []
                writers: list[str] = []

                if ttml_resp.status_code == 200 and ttml_resp.text.strip():
                    lines, writers = parse_ttml(
                        ttml_resp.text,
                        title=query.title,
                        artists=[query.artist] if query.artist else None,
                    )

                # 2. If TTML wasn't available, fallback to LRC
                if not lines:
                    lrc_url = f"{BASE_URL}/{isrc}.lrc"
                    lrc_resp = get(lrc_url, headers=headers, timeout=self._timeout)
                    if lrc_resp.status_code == 200 and lrc_resp.text.strip():
                        lines = parse_lrc(lrc_resp.text)

                if not lines:
                    continue

                lyrics = Lyrics(lines=lines)
                dur_s = float(cand["duration"]) if cand.get("duration") else None

                hits.append(
                    Hit(
                        source=SOURCE,
                        trust=self.trust,
                        lyrics=lyrics,
                        instrumental=False,
                        title=cand.get("title") or query.title,
                        artist=cand.get("artist") or query.artist,
                        duration_s=dur_s,
                        writers=writers,
                    )
                )

                if lyrics.worded():
                    break

        except Exception as e:
            logger.debug("lrc.red search error: %s", e)

        return hits

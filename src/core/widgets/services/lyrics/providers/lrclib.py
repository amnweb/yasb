from __future__ import annotations

from typing import Any, cast

from settings import APP_NAME, GITHUB_URL

from ..http import get
from ..models import Hit, Lyrics, Query
from ..normalize import normalize_lines
from ..parsing.lrc import parse_lrc
from .base import LyricsProvider

USER_AGENT = f"{APP_NAME} ({GITHUB_URL})"

BASE_URL = "https://lrclib.net"


class LrcLibProvider(LyricsProvider):
    name: str = "LrcLib"
    trust: int = 50

    def __init__(self, timeout: float = 6.0) -> None:
        self._timeout = timeout

    def search(self, query: Query) -> list[Hit]:
        hits: list[Hit] = []

        try:
            get_params: dict[str, Any] = {
                "track_name": query.title,
                "artist_name": query.artist,
            }
            if query.duration_s is not None and query.duration_s > 0:
                get_params["duration"] = round(query.duration_s)

            resp = get(
                f"{BASE_URL}/api/get",
                params=get_params,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
            )

            if resp.status_code == 200:
                data = resp.json()
                hit = self._parse_hit(data, query)
                if hit:
                    hits.append(hit)
                    return hits

            search_params: dict[str, Any] = {
                "track_name": query.title,
                "artist_name": query.artist,
            }
            resp_search = get(
                f"{BASE_URL}/api/search",
                params=search_params,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
            )

            if resp_search.status_code == 200:
                items = resp_search.json()
                if isinstance(items, list):
                    for item in cast("list[dict[str, Any]]", items):
                        h = self._parse_hit(item, query)
                        if h:
                            hits.append(h)
        except Exception:
            pass

        return hits

    def _parse_hit(self, data: dict[str, Any], query: Query) -> Hit | None:
        synced_raw = data.get("syncedLyrics")
        plain_raw = data.get("plainLyrics")
        instrumental = bool(data.get("instrumental", False))

        if not synced_raw and not plain_raw and not instrumental:
            return None

        lines = None
        if synced_raw:
            raw_lines = parse_lrc(synced_raw)
            if raw_lines:
                lines = normalize_lines(raw_lines, title=query.title, artists=[query.artist])

        lyrics = Lyrics(lines=lines, plain=plain_raw if not lines else None)
        duration_s = float(data["duration"]) if data.get("duration") is not None else None

        return Hit(
            source=self.name,
            trust=self.trust,
            lyrics=lyrics,
            instrumental=instrumental,
            title=str(data.get("trackName") or query.title),
            artist=str(data.get("artistName") or query.artist),
            duration_s=duration_s,
        )

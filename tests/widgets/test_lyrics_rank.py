from __future__ import annotations

import time
from typing import Any

from core.widgets.services.lyrics.cache import LyricsCache
from core.widgets.services.lyrics.models import Hit, Lane, Line, Lyrics, Query, Word
from core.widgets.services.lyrics.orchestrator import LyricsOrchestrator
from core.widgets.services.lyrics.providers.base import LyricsProvider
from core.widgets.services.lyrics.rank import (
    DUET_BONUS,
    has_multi_voice,
    rank_hits,
    score_hit,
)


def test_has_multi_voice_empty_or_mono() -> None:
    assert not has_multi_voice(Lyrics())
    assert not has_multi_voice(Lyrics(lines=[]))

    mono_lyrics = Lyrics(
        lines=[
            Line(start_ms=1000, end_ms=2000, text="Line 1", voice="lead"),
            Line(start_ms=2000, end_ms=3000, text="Line 2", voice="lead"),
        ]
    )
    assert not has_multi_voice(mono_lyrics)


def test_has_multi_voice_duet_and_lanes() -> None:
    # Multiple distinct voices
    duet_lyrics = Lyrics(
        lines=[
            Line(start_ms=1000, end_ms=2000, text="Lead vocal", voice="lead"),
            Line(start_ms=2000, end_ms=3000, text="Counter vocal", voice="counter"),
        ]
    )
    assert has_multi_voice(duet_lyrics)

    # Secondary background lane
    lane_lyrics = Lyrics(
        lines=[
            Line(
                start_ms=1000,
                end_ms=2000,
                text="Main text",
                voice="lead",
                secondary=[Lane(start_ms=1200, end_ms=1800, text="Echo background")],
            )
        ]
    )
    assert has_multi_voice(lane_lyrics)


def test_duet_bonus_scoring() -> None:
    query = Query(title="APT.", artist="ROSÉ & Bruno Mars", duration_s=170.0)

    words_mono = [Word(start_ms=1000, end_ms=2000, text="아파트")]
    mono_hit = Hit(
        source="Kugou",
        trust=70,
        lyrics=Lyrics(
            lines=[
                Line(start_ms=1000, end_ms=2000, text="아파트", words=words_mono, voice="lead"),
            ]
        ),
        instrumental=False,
        title="APT.",
        artist="ROSÉ & Bruno Mars",
        duration_s=170.0,
    )

    words_duet = [Word(start_ms=1000, end_ms=2000, text="아파트")]
    duet_hit = Hit(
        source="Apple Music",
        trust=70,  # same trust for comparison
        lyrics=Lyrics(
            lines=[
                Line(start_ms=1000, end_ms=2000, text="아파트", words=words_duet, voice="lead"),
                Line(start_ms=2000, end_ms=3000, text="Kissy face", words=words_duet, voice="counter"),
            ]
        ),
        instrumental=False,
        title="APT.",
        artist="ROSÉ & Bruno Mars",
        duration_s=170.0,
    )

    score_mono = score_hit(query, mono_hit)
    score_duet = score_hit(query, duet_hit)

    assert score_duet == score_mono + DUET_BONUS

    ranked = rank_hits(query, [mono_hit, duet_hit])
    assert ranked[0].source == "Apple Music"


class _FastMonoProvider(LyricsProvider):
    name = "FastMono"
    trust = 50
    supports_multi_voice = False

    def search(self, query: Query) -> list[Hit]:
        time.sleep(0.01)
        return [
            Hit(
                source=self.name,
                trust=self.trust,
                lyrics=Lyrics(
                    lines=[
                        Line(
                            start_ms=0,
                            end_ms=1000,
                            text="Solo line",
                            words=[Word(0, 1000, "Solo")],
                            voice="lead",
                        )
                    ]
                ),
                instrumental=False,
                title=query.title,
                artist=query.artist,
                duration_s=query.duration_s,
            )
        ]


class _SlowDuetProvider(LyricsProvider):
    name = "SlowDuet"
    trust = 50
    supports_multi_voice = True

    def search(self, query: Query) -> list[Hit]:
        time.sleep(0.1)
        return [
            Hit(
                source=self.name,
                trust=self.trust,
                lyrics=Lyrics(
                    lines=[
                        Line(
                            start_ms=0,
                            end_ms=1000,
                            text="Lead line",
                            words=[Word(0, 1000, "Lead")],
                            voice="lead",
                        ),
                        Line(
                            start_ms=1000,
                            end_ms=2000,
                            text="Counter line",
                            words=[Word(1000, 2000, "Counter")],
                            voice="counter",
                        ),
                    ]
                ),
                instrumental=False,
                title=query.title,
                artist=query.artist,
                duration_s=query.duration_s,
            )
        ]


def test_orchestrator_waits_for_duet_upgrade(tmp_path: Any) -> None:
    cache = LyricsCache(db_path=tmp_path / "test_lyrics.db")
    orchestrator = LyricsOrchestrator(
        cache=cache,
        providers=[_FastMonoProvider(), _SlowDuetProvider()],
        per_provider_timeout_s=2.0,
    )

    query = Query(title="Duet Track", artist="Artist A & Artist B", duration_s=180.0)
    candidates_streamed: list[str] = []

    def on_cand(hits: list[Hit]) -> None:
        if hits:
            candidates_streamed.append(hits[0].source)

    final_hits = orchestrator.fetch(query, on_candidate=on_cand)
    orchestrator.close()

    assert len(final_hits) > 0
    assert final_hits[0].source == "SlowDuet"
    assert has_multi_voice(final_hits[0].lyrics)
    # Streamed fast mono first for instant UI, then upgraded to SlowDuet
    assert "FastMono" in candidates_streamed
    assert candidates_streamed[-1] == "SlowDuet"


def test_orchestrator_default_providers() -> None:
    orch = LyricsOrchestrator()
    provider_names = [p.name for p in orch.providers]
    orch.close()
    assert "lrc.red" in provider_names
    assert "Apple Music" in provider_names


def test_lrcred_provider_search(monkeypatch: Any) -> None:
    from core.widgets.services.lyrics.http import Response
    from core.widgets.services.lyrics.providers.lrcred import LrcRedProvider

    sample_search_json = """{
        "hits": [
            {
                "isrc": "TEST12345",
                "title": "Duet Hit",
                "artist": "Artist 1 & Artist 2",
                "album": "Test Album",
                "duration": 180.0
            }
        ]
    }"""

    sample_ttml = """<?xml version="1.0" encoding="utf-8"?>
    <tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttm="http://www.w3.org/ns/ttml#metadata">
      <head>
        <metadata>
          <ttm:agent xml:id="v1" type="person"/>
          <ttm:agent xml:id="v2" type="person"/>
          <ttm:songwriter>Song Writer</ttm:songwriter>
        </metadata>
      </head>
      <body>
        <div>
          <p begin="00:01.000" end="00:03.000" ttm:agent="v1">
            <span begin="00:01.000" end="00:02.000">Lead </span>
            <span begin="00:02.000" end="00:03.000">verse</span>
          </p>
          <p begin="00:03.500" end="00:05.500" ttm:agent="v2">
            <span begin="00:03.500" end="00:04.500">Counter </span>
            <span begin="00:04.500" end="00:05.500">verse</span>
          </p>
        </div>
      </body>
    </tt>"""

    def mock_get(url: str, **kwargs: Any) -> Response:
        if "search.json" in url:
            return Response(200, sample_search_json)
        elif ".ttml" in url:
            return Response(200, sample_ttml)
        return Response(404, "")

    import core.widgets.services.lyrics.providers.lrcred as lrcred_mod

    monkeypatch.setattr(lrcred_mod, "get", mock_get)

    provider = LrcRedProvider()
    hits = provider.search(Query(title="Duet Hit", artist="Artist 1 & Artist 2", duration_s=180.0))

    assert len(hits) == 1
    hit = hits[0]
    assert hit.source == "lrc.red"
    assert hit.lyrics.worded()
    assert has_multi_voice(hit.lyrics)
    assert hit.writers == ["Song Writer"]
    assert len(hit.lyrics.lines or []) == 2


def test_cross_script_artist_matching() -> None:
    from core.widgets.services.lyrics.rank import artists_alike

    # Korean Hangul vs English romanization
    assert artists_alike("전소미", "JEON SOMI")
    assert artists_alike("JEON SOMI", "전소미")

    # Sinhala vs English romanization
    assert artists_alike("යොහානි", "Yohani")

    # Hindi Devanagari vs English romanization
    assert artists_alike("अरिजीत सिंह", "Arijit Singh")

    # Japanese Kana/Kanji vs English romanization
    assert artists_alike("あいみょん", "Aimyon")

    # Verify ranking eligibility & preference for worded hit with Hangul artist
    query = Query(title="Anymore", artist="JEON SOMI", duration_s=198.0)
    words = [Word(start_ms=12000, end_ms=13000, text="You")]
    kugou_hit = Hit(
        source="Kugou",
        trust=0,
        lyrics=Lyrics(lines=[Line(start_ms=12000, end_ms=14000, text="You mess me up", words=words)]),
        instrumental=False,
        title="Anymore",
        artist="전소미",
        duration_s=198.0,
    )
    apple_hit = Hit(
        source="Apple Music",
        trust=180,
        lyrics=Lyrics(lines=[Line(start_ms=12000, end_ms=14000, text="You mess me up")]),  # line-only
        instrumental=False,
        title="Anymore",
        artist="JEON SOMI",
        duration_s=198.0,
    )

    ranked = rank_hits(query, [apple_hit, kugou_hit])
    assert len(ranked) == 2
    # Kugou's worded karaoke wins despite 0 base trust vs 180 base trust
    assert ranked[0].source == "Kugou"
    assert ranked[0].lyrics.worded()

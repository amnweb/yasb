from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from .models import Hit, Lyrics, Query
from .normalize import matching_keys

logger = logging.getLogger("core.widgets.services.lyrics.rank")

CLOSE_ENOUGH_S = 3
WAY_OFF_S = 10
TITLE_BONUS = 40
ARTIST_BONUS = 30
SYNCED_BONUS = 200
WORDED_BONUS = 400
DUET_BONUS = 250
LINE_DUET_BONUS = 50
DRIFT_PENALTY = 50
TRUNCATED_PENALTY = 500


def alike(a: str | None, b: str | None) -> bool:
    """Fuzzy equality between two titles or albums using normalized alphanumeric keys."""
    if not a or not b:
        return False
    keys_a = matching_keys(a)
    keys_b = matching_keys(b)
    if not keys_a or not keys_b:
        return False
    for ka in keys_a:
        for kb in keys_b:
            if ka == kb:
                return True
            if len(ka) >= 3 and len(kb) >= 3:
                if ka in kb or kb in ka:
                    return True
    return False


def artists_alike(a: str | None, b: str | None) -> bool:
    """Fuzzy equality between artists, allowing for collaborations or multi-artist lists."""
    if not a or not b:
        return False
    if alike(a, b):
        return True

    delims = r"[,/&;]|\bfeat\b|\bft\b"
    parts_a = [p for p in re.split(delims, a, flags=re.IGNORECASE) if p.strip()]
    parts_b = [p for p in re.split(delims, b, flags=re.IGNORECASE) if p.strip()]

    for pa in parts_a:
        for pb in parts_b:
            if alike(pa, pb):
                return True

    return False


def matched(query: Query, hit: Hit) -> bool:
    """Verifies that the hit matches the query title, artist, and acceptable duration range."""
    if not alike(hit.title, query.title):
        return False
    if not artists_alike(hit.artist, query.artist):
        return False

    if query.duration_s is not None and query.duration_s > 0 and hit.duration_s is not None and hit.duration_s > 0:
        drift = abs(hit.duration_s - query.duration_s)
        if drift > WAY_OFF_S:
            return False

    return True


def is_truncated(lyrics: Lyrics, duration_s: float | None) -> bool:
    """Detects if lyrics end significantly before the song finishes (less than 60% of duration)."""
    if duration_s is None or duration_s <= 0:
        return False
    span_ms = lyrics.span_ms()
    if span_ms is None:
        return False
    return (span_ms / 1000.0) < (duration_s * 0.6)


def is_low_quality(lyrics: Lyrics) -> bool:
    """Filters out low quality/junk lyrics (e.g., stretched all-caps shouting or spam)."""
    if not lyrics.lines:
        return False

    noisy_count = 0
    total_count = len(lyrics.lines)

    for line in lyrics.lines:
        txt = line.text.strip()
        if not txt:
            continue
        if re.search(r"(.)\1{5,}", txt):
            noisy_count += 1
        elif len(txt) > 8 and txt.isupper():
            noisy_count += 1

    return noisy_count >= 3 and (noisy_count * 5 >= total_count)


def is_eligible(query: Query, hit: Hit) -> bool:
    """A hit is eligible if it matches the song, is not empty, and has clean quality."""
    if not matched(query, hit):
        return False
    if hit.lyrics.is_empty() and not hit.instrumental:
        return False
    if is_low_quality(hit.lyrics):
        return False
    return True


def has_multi_voice(lyrics: Lyrics) -> bool:
    """Checks whether the lyrics contain multiple voices or secondary vocal lanes (duets/backing)."""
    if not lyrics.lines:
        return False

    voices: set[str] = set()
    for line in lyrics.lines:
        if line.secondary:
            return True
        v = (line.voice or "lead").strip().lower()
        if v in ("counter", "v2", "right"):
            return True
        voices.add(v)

    return len(voices) > 1


def score_hit(query: Query, hit: Hit) -> int:
    """
    Computes a numerical ranking score:
    Trust + Title (+40) + Artist (+30) + Synced (+200) + Worded (+400) + Duet/Multi-voice (+250)
    + Duration bonus (up to +100 within 3s, -10/s) / penalty (-50 if >10s)
    - Truncated (-500)
    """
    score = hit.trust

    if alike(hit.title, query.title):
        score += TITLE_BONUS

    if artists_alike(hit.artist, query.artist):
        score += ARTIST_BONUS

    is_synced = hit.lyrics.synced() if callable(hit.lyrics.synced) else bool(hit.lyrics.synced)
    if is_synced:
        score += SYNCED_BONUS

    is_worded = hit.lyrics.worded() if callable(hit.lyrics.worded) else bool(hit.lyrics.worded)
    if is_worded:
        score += WORDED_BONUS

    if has_multi_voice(hit.lyrics):
        score += DUET_BONUS if is_worded else LINE_DUET_BONUS

    if query.duration_s is not None and query.duration_s > 0 and hit.duration_s is not None and hit.duration_s > 0:
        drift = int(round(abs(hit.duration_s - query.duration_s)))
        if drift <= CLOSE_ENOUGH_S:
            score += max(0, 100 - (drift * 10))
        elif drift > WAY_OFF_S:
            score -= DRIFT_PENALTY

    if is_truncated(hit.lyrics, query.duration_s):
        score -= TRUNCATED_PENALTY

    return score


def fingerprint(lyrics: Lyrics) -> str:
    """Generates an alphanumeric fingerprint of the lyric text for deduplication."""
    if not lyrics.lines:
        return (lyrics.plain or "").strip().lower()

    words: list[str] = []
    for line in lyrics.lines[:10]:
        clean = "".join(c.lower() for c in line.text if c.isalnum())
        if clean:
            words.append(clean)

    worded_flag = "1" if lyrics.worded() else "0"
    return f"{worded_flag}:{':'.join(words)}"


def is_instrumental_result(query: Query, hits: Sequence[Hit]) -> bool:
    """True if matching hits declare the song is instrumental and no hit has non-empty lyrics."""
    matching = [h for h in hits if matched(query, h)]
    has_instrumental_claim = any(h.instrumental for h in matching)
    has_actual_lyrics = any(not h.lyrics.is_empty() for h in matching)
    return has_instrumental_claim and not has_actual_lyrics


def rank_hits(query: Query, hits: Sequence[Hit]) -> list[Hit]:
    """
    Filters, scores, sorts, and deduplicates lyric candidates.
    Returns the ordered candidate hit list with the best candidate first.
    """
    eligible_hits = [h for h in hits if is_eligible(query, h)]
    if not eligible_hits:
        return []

    scored: list[tuple[int, Hit]] = [(score_hit(query, h), h) for h in eligible_hits]

    scored.sort(
        key=lambda pair: (
            pair[0],
            pair[1].trust,
            pair[1].source,
            pair[1].title,
        ),
        reverse=True,
    )

    seen: set[str] = set()
    ranked: list[Hit] = []

    for _s, hit in scored:
        fp = fingerprint(hit.lyrics)
        if fp not in seen:
            seen.add(fp)
            ranked.append(hit)

    return ranked

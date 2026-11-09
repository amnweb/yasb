from .cache import LyricsCache
from .engine import (
    BreakRow,
    LyricRow,
    SyncEngine,
    SyncStatus,
    active_instrumental_gap,
    active_row,
    build_rows,
    instrumental_gap_before,
    row_for_line,
)
from .models import Hit, Lane, Line, Lyrics, Query, Word
from .normalize import clean_for_matching, matching_keys, normalize_lines
from .orchestrator import LyricsOrchestrator
from .parsing.lrc import parse_lrc
from .parsing.ttml import parse_ttml
from .parsing.yrc import parse_yrc
from .providers.base import LyricsProvider
from .providers.binimum import BinimumProvider
from .providers.kugou import KugouProvider
from .providers.lrclib import LrcLibProvider
from .providers.lrcred import LrcRedProvider
from .providers.netease import NetEaseProvider
from .rank import has_multi_voice, is_eligible, is_instrumental_result, rank_hits, score_hit
from .session import PlaybackSnapshot, PlaybackStatus, TrackInfo

__all__ = [
    "Word",
    "Lane",
    "Line",
    "Lyrics",
    "Hit",
    "Query",
    "parse_lrc",
    "parse_yrc",
    "parse_ttml",
    "normalize_lines",
    "clean_for_matching",
    "matching_keys",
    "LyricsCache",
    "LyricsProvider",
    "LrcLibProvider",
    "LrcRedProvider",
    "NetEaseProvider",
    "BinimumProvider",
    "KugouProvider",
    "has_multi_voice",
    "rank_hits",
    "score_hit",
    "is_eligible",
    "is_instrumental_result",
    "LyricsOrchestrator",
    "TrackInfo",
    "PlaybackSnapshot",
    "PlaybackStatus",
    "SyncEngine",
    "SyncStatus",
    "LyricRow",
    "BreakRow",
    "build_rows",
    "instrumental_gap_before",
    "active_instrumental_gap",
    "active_row",
    "row_for_line",
]

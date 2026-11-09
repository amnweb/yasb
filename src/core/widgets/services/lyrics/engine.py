from __future__ import annotations

import bisect
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .models import Line, Lyrics, Word
from .session import PlaybackSnapshot

INSTRUMENTAL_BREAK_MS = 5000  # Minimum duration for an instrumental break.
OUTRO_HOLD_MS = 3500  # Hold the last lyric line for 3.5s before transitioning to outro break


@dataclass
class LyricRow:
    line_index: int
    line: Line
    start_ms: int
    end_ms: int

    @property
    def is_break(self) -> bool:
        return False


@dataclass
class BreakRow:
    next_line_index: int
    start_ms: int
    end_ms: int
    duration_ms: int

    @property
    def is_break(self) -> bool:
        return True


Row = LyricRow | BreakRow


def instrumental_gap_before(lines: Sequence[Line], index: int) -> int:
    if not lines or index < 0 or index >= len(lines):
        return 0
    start = lines[index].start_ms
    if index == 0:
        return start
    prev_end = lines[index - 1].sung_end()
    return max(0, start - prev_end)


def active_instrumental_gap(
    lines: Sequence[Line],
    position_ms: int,
    total_duration_ms: int | None = None,
) -> tuple[int, int, int, float] | None:
    """Return the active instrumental gap, if there is one."""
    if not lines:
        return None

    starts = [l.start_ms for l in lines]
    next_idx = bisect.bisect_right(starts, position_ms)
    if next_idx < len(lines):
        gap = instrumental_gap_before(lines, next_idx)
        if gap >= INSTRUMENTAL_BREAK_MS:
            break_start = lines[next_idx].start_ms - gap
            if break_start <= position_ms < lines[next_idx].start_ms:
                progress = max(0.0, min(1.0, (position_ms - break_start) / max(1, gap)))
                return next_idx, break_start, lines[next_idx].start_ms, progress
        return None

    if total_duration_ms is not None and total_duration_ms > 0:
        last_line = lines[-1]
        outro_start = last_line.sung_end() + OUTRO_HOLD_MS
        gap = total_duration_ms - outro_start
        if gap >= INSTRUMENTAL_BREAK_MS and outro_start <= position_ms < total_duration_ms:
            progress = max(0.0, min(1.0, (position_ms - outro_start) / max(1, gap)))
            return len(lines), outro_start, total_duration_ms, progress

    return None


def build_rows(
    lines: Sequence[Line],
    total_duration_ms: int | None = None,
) -> list[Row]:
    """Build lyric and instrumental rows from the parsed lines."""
    rows: list[Row] = []
    for i, line in enumerate(lines):
        gap = instrumental_gap_before(lines, i)
        if gap >= INSTRUMENTAL_BREAK_MS:
            b_start = line.start_ms - gap
            rows.append(
                BreakRow(
                    next_line_index=i,
                    start_ms=b_start,
                    end_ms=line.start_ms,
                    duration_ms=gap,
                )
            )
        rows.append(
            LyricRow(
                line_index=i,
                line=line,
                start_ms=line.start_ms,
                end_ms=line.sung_end(),
            )
        )

    if lines and total_duration_ms is not None and total_duration_ms > 0:
        last_line = lines[-1]
        outro_start = last_line.sung_end() + OUTRO_HOLD_MS
        gap = total_duration_ms - outro_start
        if gap >= INSTRUMENTAL_BREAK_MS:
            rows.append(
                BreakRow(
                    next_line_index=len(lines),
                    start_ms=outro_start,
                    end_ms=total_duration_ms,
                    duration_ms=gap,
                )
            )
    return rows


def row_for_line(rows: Sequence[Row], line_index: int) -> int | None:
    for idx, r in enumerate(rows):
        if not r.is_break and getattr(r, "line_index", -1) == line_index:
            return idx
    return None


def active_row(rows: Sequence[Row], position_ms: int) -> int | None:
    """Return the row shown for the current playback position."""
    if not rows:
        return None

    if position_ms < rows[0].start_ms:
        return 0

    for idx, r in enumerate(rows):
        is_last = idx == len(rows) - 1
        next_start = rows[idx + 1].start_ms if not is_last else None

        if r.start_ms <= position_ms:
            if not is_last and next_start is not None and position_ms < next_start:
                if r.is_break:
                    return idx - 1 if idx > 0 else idx
                return idx
            elif is_last:
                return idx

    return len(rows) - 1


@dataclass
class SyncStatus:
    position_ms: int
    effective_position_ms: int
    state: Literal["idle", "playing", "paused", "break"]
    active_line_index: int | None = None
    active_line: Line | None = None
    active_word_index: int | None = None
    active_word: Word | None = None
    word_progress: float = 0.0
    is_break: bool = False
    break_progress: float = 0.0
    break_next_line_index: int | None = None
    break_row_index: int | None = None
    active_row_index: int | None = None
    line_changed: bool = False
    is_seeking: bool = False
    is_singing: bool = False


class SyncEngine:
    """Keep parsed lyrics aligned with playback."""

    def __init__(self) -> None:
        self.total_duration_ms = 0

        self.lyrics: Lyrics | None = None
        self.lines: list[Line] = []
        self.rows: list[Row] = []

        self._snapshot: PlaybackSnapshot | None = None
        self._last_line_index: int | None = None
        self._last_estimated_pos: int = 0
        self._is_seeking: bool = False

    def set_lyrics(
        self,
        lyrics: Lyrics | None,
        total_duration_ms: int = 0,
    ) -> None:
        self.lyrics = lyrics
        self.lines = list(lyrics.lines) if lyrics and lyrics.lines else []
        self.total_duration_ms = total_duration_ms
        self.rows = build_rows(self.lines, total_duration_ms=self.total_duration_ms)
        self._last_line_index = None

    def set_total_duration(self, total_duration_ms: int) -> None:
        if self.total_duration_ms != total_duration_ms:
            self.total_duration_ms = total_duration_ms
            self.rows = build_rows(self.lines, total_duration_ms=self.total_duration_ms)

    @property
    def snapshot(self) -> PlaybackSnapshot | None:
        return self._snapshot

    def update_snapshot(self, snapshot: PlaybackSnapshot) -> None:
        prev_snap = self._snapshot
        self._snapshot = snapshot
        now = snapshot.wall_time

        if prev_snap is not None and prev_snap.status == "playing" and snapshot.status == "playing":
            expected_pos = prev_snap.estimated_position_ms(now=now)
            if abs(snapshot.position_ms - expected_pos) > 1200:
                self._is_seeking = True
                self._last_estimated_pos = snapshot.position_ms
        elif prev_snap is not None and snapshot.status != prev_snap.status:
            if abs(snapshot.position_ms - prev_snap.position_ms) > 1200:
                self._is_seeking = True
                self._last_estimated_pos = snapshot.position_ms
        else:
            self._last_estimated_pos = snapshot.position_ms

    def tick(self, now: float | None = None) -> SyncStatus:
        if now is None:
            now = time.time()

        if not self._snapshot:
            return SyncStatus(
                position_ms=0,
                effective_position_ms=0,
                state="idle",
            )

        base_pos = self._snapshot.estimated_position_ms(now=now)
        if not self._is_seeking and self._snapshot.status == "playing":
            if base_pos < self._last_estimated_pos and (self._last_estimated_pos - base_pos) < 1200:
                base_pos = self._last_estimated_pos
        self._last_estimated_pos = base_pos

        effective_pos = max(0, base_pos)

        state: Literal["idle", "playing", "paused", "break"] = (
            "playing" if self._snapshot.status == "playing" else "paused"
        )

        if not self.lines:
            return SyncStatus(
                position_ms=base_pos,
                effective_position_ms=effective_pos,
                state=state,
            )

        break_info = active_instrumental_gap(self.lines, effective_pos, total_duration_ms=self.total_duration_ms)
        is_break = False
        break_progress = 0.0
        break_next_idx = None
        break_row_idx = None

        if break_info:
            is_break = True
            break_next_idx, _, _, break_progress = break_info
            if state == "playing":
                state = "break"
            for r_idx, r in enumerate(self.rows):
                if r.is_break and getattr(r, "next_line_index", -1) == break_next_idx:
                    break_row_idx = r_idx
                    break

        active_row_idx = active_row(self.rows, effective_pos)

        line_starts = [l.start_ms for l in self.lines]
        idx = bisect.bisect_right(line_starts, effective_pos) - 1

        active_line_idx = None
        active_line = None
        active_word_idx = None
        active_word = None
        word_progress = 0.0
        is_singing = False

        if not is_break and 0 <= idx < len(self.lines):
            cand = self.lines[idx]
            active_line_idx = idx
            active_line = cand
            is_singing = cand.start_ms <= effective_pos <= cand.sung_end()

            if is_singing and active_line.words:
                for w_i, w in enumerate(active_line.words):
                    if w.start_ms <= effective_pos <= w.end_ms:
                        active_word_idx = w_i
                        active_word = w
                        span = max(1, w.end_ms - w.start_ms)
                        word_progress = max(0.0, min(1.0, (effective_pos - w.start_ms) / span))
                        break
                    elif effective_pos < w.start_ms:
                        break

        line_changed = active_line_idx != self._last_line_index
        self._last_line_index = active_line_idx
        seeking = self._is_seeking
        self._is_seeking = False

        return SyncStatus(
            position_ms=base_pos,
            effective_position_ms=effective_pos,
            state=state,
            active_line_index=active_line_idx,
            active_line=active_line,
            active_word_index=active_word_idx,
            active_word=active_word,
            word_progress=word_progress,
            is_break=is_break,
            break_progress=break_progress,
            break_next_line_index=break_next_idx,
            break_row_index=break_row_idx,
            active_row_index=active_row_idx,
            line_changed=line_changed,
            is_seeking=seeking,
            is_singing=is_singing,
        )

    def active_row(self, position_ms: int | None = None) -> int | None:
        """Helper to get active row for a given or current effective position."""
        if position_ms is None:
            position_ms = max(0, self._last_estimated_pos)
        return active_row(self.rows, position_ms)

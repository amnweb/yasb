"""Media session data used by the lyrics widget."""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.widgets.services.media.media import SessionState

logger = logging.getLogger("core.widgets.services.lyrics.widget")

PlaybackStatus = Literal["playing", "paused", "stopped", "closed", "unknown"]

_STATUS_MAP: dict[int, PlaybackStatus] = {0: "closed", 3: "stopped", 4: "playing", 5: "paused"}


@dataclass
class TrackInfo:
    title: str
    artist: str
    app_id: str = ""
    duration_ms: int | None = None
    thumbnail_bytes: bytes | None = None


@dataclass
class PlaybackSnapshot:
    position_ms: int
    rate: float
    status: PlaybackStatus
    wall_time: float
    can_seek: bool = False

    def estimated_position_ms(self, now: float | None = None) -> int:
        if now is None:
            now = time.time()
        if self.status == "playing":
            elapsed = max(0.0, now - self.wall_time)
            return self.position_ms + int(elapsed * 1000 * self.rate)
        return self.position_ms


def app_id_allowed(app_id: str, allowed_apps: list[str] | None, blocked_apps: list[str] | None) -> bool:
    low = app_id.lower()
    if blocked_apps and any(b.lower() in low for b in blocked_apps):
        return False
    if allowed_apps:
        return any(a.lower() in low for a in allowed_apps)
    return True


def select_session(
    trackers: dict[str, SessionState],
    allowed_apps: list[str] | None = None,
    blocked_apps: list[str] | None = None,
) -> SessionState | None:
    candidates = [s for s in trackers.values() if s.app_id and app_id_allowed(s.app_id, allowed_apps, blocked_apps)]
    if not candidates:
        return None
    current = next((s for s in candidates if s.is_current), None)
    if current is not None:
        return current
    playing = next((s for s in candidates if s.is_playing or s.playback_status == 4), None)
    return playing or candidates[0]


def track_from_session(state: SessionState) -> TrackInfo:
    return TrackInfo(
        title=state.title.strip(),
        artist=state.artist.strip(),
        app_id=state.app_id,
        duration_ms=int(state.duration * 1000) if state.duration and state.duration > 0 else None,
        thumbnail_bytes=_thumbnail_bytes(state),
    )


def snapshot_from_session(state: SessionState) -> PlaybackSnapshot:
    status: PlaybackStatus
    if state.is_playing or state.playback_status == 4:
        status = "playing"
    else:
        status = _STATUS_MAP.get(state.playback_status, "unknown")
    return PlaybackSnapshot(
        position_ms=int(max(0.0, state.current_pos) * 1000),
        rate=state.playback_rate or 1.0,
        status=status,
        wall_time=time.time(),
        can_seek=bool(state.timeline_enabled),
    )


def _thumbnail_bytes(state: SessionState) -> bytes | None:
    image = state.thumbnail
    if image is None:
        return None
    try:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.debug("Failed to encode thumbnail bytes: %s", e)
        return None

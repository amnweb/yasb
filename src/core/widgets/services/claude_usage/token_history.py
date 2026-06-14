"""Local Claude Code token-usage history.

Claude Code writes a JSONL transcript per session under
``~/.claude/projects/**/*.jsonl``. Every assistant message line carries a
``message.usage`` block with token counts. This module scans those files and
aggregates the token counts into per-day (local time) and per-session buckets,
which the widget turns into Session / Today / Week / Month / Year totals.

Only numeric token counts, timestamps, the model name and the session id are
read — never message content. The scan is incremental: each file's parsed
contribution is cached keyed by (mtime, size), so a steady-state poll only
re-parses the session file(s) that actually changed.
"""

import glob
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from core.utils.system import app_data_path
from core.widgets.services.claude_usage.claude_api import _claude_config_dir

logger = logging.getLogger("claude_usage")

CACHE_VERSION = 1
# Token count order used throughout: input, output, cache_creation, cache_read.
_TOKEN_SLOTS = 4


def _projects_dir() -> str:
    return os.path.join(_claude_config_dir(), "projects")


def _history_cache_path() -> str:
    return str(app_data_path("claude_token_history.json"))


def _read_json(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, data: dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug("failed to write token history cache: %s", e)


def _add4(dst: list[int], src: list[int]) -> None:
    for i in range(_TOKEN_SLOTS):
        dst[i] += src[i]


def _merge_daily(into: dict[str, dict[str, list[int]]], src: dict[str, dict[str, list[int]]]) -> None:
    for date, models in src.items():
        bucket = into.setdefault(date, {})
        for model, counts in models.items():
            slot = bucket.setdefault(model, [0, 0, 0, 0])
            _add4(slot, counts)


def _merge_sessions(into: dict[str, dict[str, Any]], src: dict[str, dict[str, Any]]) -> None:
    for sid, info in src.items():
        cur = into.get(sid)
        if cur is None:
            into[sid] = {"t": list(info["t"]), "first": info["first"], "last": info["last"]}
        else:
            _add4(cur["t"], info["t"])
            cur["first"] = min(cur["first"], info["first"])
            cur["last"] = max(cur["last"], info["last"])


def _parse_file(path: str) -> dict[str, Any]:
    """Parse one JSONL transcript into its daily + session token contribution."""
    daily: dict[str, dict[str, list[int]]] = {}
    sessions: dict[str, dict[str, Any]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                message = obj.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                counts = [
                    int(usage.get("input_tokens") or 0),
                    int(usage.get("output_tokens") or 0),
                    int(usage.get("cache_creation_input_tokens") or 0),
                    int(usage.get("cache_read_input_tokens") or 0),
                ]
                if not any(counts):
                    continue
                iso = obj.get("timestamp")
                if not iso:
                    continue
                try:
                    local = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
                except Exception:
                    continue
                date_key = f"{local:%Y-%m-%d}"
                tsec = local.timestamp()
                model = message.get("model") or "unknown"
                sid = obj.get("sessionId") or "unknown"

                slot = daily.setdefault(date_key, {}).setdefault(model, [0, 0, 0, 0])
                _add4(slot, counts)

                sess = sessions.get(sid)
                if sess is None:
                    sessions[sid] = {"t": list(counts), "first": tsec, "last": tsec}
                else:
                    _add4(sess["t"], counts)
                    sess["first"] = min(sess["first"], tsec)
                    sess["last"] = max(sess["last"], tsec)
    except Exception as e:
        logger.debug("failed to parse %s: %s", path, e)
    return {"daily": daily, "sessions": sessions}


def scan(cache_path: str) -> dict[str, Any]:
    """Incrementally scan all session transcripts and return the merged aggregate.

    Returns a dict with ``daily`` (date -> model -> [in, out, cache_create,
    cache_read]) and ``sessions`` (id -> {t, first, last}). Unchanged files reuse
    their cached contribution; only new/modified files are re-parsed.
    """
    cache = _read_json(cache_path) or {}
    prev_files: dict[str, Any] = cache.get("files", {}) if cache.get("version") == CACHE_VERSION else {}

    current_files: dict[str, Any] = {}
    pattern = os.path.join(_projects_dir(), "**", "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        try:
            st = os.stat(path)
        except OSError:
            continue
        prev = prev_files.get(path)
        if prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            current_files[path] = prev
        else:
            contrib = _parse_file(path)
            current_files[path] = {
                "mtime": st.st_mtime,
                "size": st.st_size,
                "daily": contrib["daily"],
                "sessions": contrib["sessions"],
            }

    daily: dict[str, dict[str, list[int]]] = {}
    sessions: dict[str, dict[str, Any]] = {}
    for fc in current_files.values():
        _merge_daily(daily, fc["daily"])
        _merge_sessions(sessions, fc["sessions"])

    _write_json(
        cache_path,
        {
            "version": CACHE_VERSION,
            "files": current_files,
            "daily": daily,
            "sessions": sessions,
            "updated_at": int(time.time()),
        },
    )
    return {"daily": daily, "sessions": sessions, "scanned_at": int(time.time())}


def _date_keys_in_range(start: datetime, end: datetime) -> list[str]:
    """Local YYYY-MM-DD keys from start.date() through end.date(), inclusive."""
    keys = []
    day = start.date()
    last = end.date()
    while day <= last:
        keys.append(f"{day:%Y-%m-%d}")
        day += timedelta(days=1)
    return keys


def _sum_daily(daily: dict[str, dict[str, list[int]]], date_key: str, count_cache_read: bool) -> int:
    bucket = daily.get(date_key)
    if not bucket:
        return 0
    total = 0
    for counts in bucket.values():
        total += counts[0] + counts[1] + counts[2]
        if count_cache_read:
            total += counts[3]
    return total


def summarize(
    agg: dict[str, Any],
    *,
    count_cache_read: bool = True,
    week_starts_on: str = "monday",
    graph_period: str = "month",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive Session/Today/Week/Month/Year totals and a daily series from an aggregate.

    ``now`` (local, tz-aware) is injectable for deterministic tests.
    """
    now = now or datetime.now().astimezone()
    daily = agg.get("daily", {})
    sessions = agg.get("sessions", {})

    def window_total(start: datetime) -> int:
        return sum(_sum_daily(daily, k, count_cache_read) for k in _date_keys_in_range(start, now))

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = now.weekday()  # Mon=0
    back = (weekday + 1) % 7 if week_starts_on == "sunday" else weekday
    week_start = today_start - timedelta(days=back)
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    # Session = the most recently active session id.
    session_total = 0
    session_id = None
    if sessions:
        session_id, info = max(sessions.items(), key=lambda kv: kv[1]["last"])
        t = info["t"]
        session_total = t[0] + t[1] + t[2] + (t[3] if count_cache_read else 0)

    span_days = {"week": 7, "month": 30, "year": 365}.get(graph_period, 30)
    series_start = today_start - timedelta(days=span_days - 1)
    series = [_sum_daily(daily, k, count_cache_read) for k in _date_keys_in_range(series_start, now)]

    return {
        "totals": {
            "session": session_total,
            "today": window_total(today_start),
            "week": window_total(week_start),
            "month": window_total(month_start),
            "year": window_total(year_start),
        },
        "series": series,
        "session_id": session_id,
    }


class _ScanWorker(QThread):
    """Runs the (blocking) transcript scan off the UI thread."""

    data_ready = pyqtSignal(dict)

    def __init__(self, cache_path: str, parent: Any = None):
        super().__init__(parent)
        self._cache_path = cache_path

    def run(self) -> None:
        try:
            self.data_ready.emit(scan(self._cache_path))
        except Exception as e:
            logger.debug("token history scan failed: %s", e)
            self.data_ready.emit({"daily": {}, "sessions": {}, "scanned_at": int(time.time())})


class TokenHistoryService(QObject):
    """Shared local token-history poller (mirrors ClaudeUsageService).

    One instance per ``scan_interval`` scans the transcripts on a timer and
    shares the merged aggregate with every widget on the same interval.
    """

    data_ready = pyqtSignal(dict)

    _instances: ClassVar[dict[int, TokenHistoryService]] = {}

    @classmethod
    def get_instance(cls, scan_interval_s: int) -> TokenHistoryService:
        key = int(scan_interval_s)
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls(scan_interval_s=key, _key=key)
            cls._instances[key] = inst
        inst._refcount += 1
        return inst

    def __init__(self, scan_interval_s: int, _key: int):
        super().__init__()
        self._key = _key
        self._refcount = 0
        self._cache_path = _history_cache_path()
        self._worker: _ScanWorker | None = None
        cached = _read_json(self._cache_path) or {}
        self._data: dict[str, Any] = {
            "daily": cached.get("daily", {}),
            "sessions": cached.get("sessions", {}),
            "scanned_at": cached.get("updated_at", 0),
        }

        self._timer = QTimer(self)
        self._timer.setInterval(max(int(scan_interval_s), 1) * 1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def latest(self) -> dict[str, Any]:
        return self._data

    def release(self) -> None:
        self._refcount -= 1
        if self._refcount > 0:
            return
        self._timer.stop()
        TokenHistoryService._instances.pop(self._key, None)
        if self._worker is not None and self._worker.isRunning():
            self._worker.finished.connect(self.deleteLater)
        else:
            self.deleteLater()

    def _tick(self) -> None:
        if self._worker is not None:
            return  # a scan is already in flight
        worker = _ScanWorker(self._cache_path, self)
        worker.data_ready.connect(self._on_data)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def _on_data(self, data: dict[str, Any]) -> None:
        self._data = data
        self.data_ready.emit(data)

    def _on_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

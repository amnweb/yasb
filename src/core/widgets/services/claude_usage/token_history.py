"""Local Claude Code token-usage history.

Claude Code writes a JSONL transcript per session under
``~/.claude/projects/**/*.jsonl``. Every assistant message line carries a
``message.usage`` block with token counts. This module scans those files and
aggregates the token counts into per-day (local time), per-hour and per-session
buckets, which the widget turns into Session / Today / Week / Month / Year totals.

Only numeric token counts, timestamps, the model name, the request speed and the
session id are read; message content is never touched. The scan is incremental: each file's
parsed contribution is cached keyed by (mtime, size), so a steady-state poll
only re-parses the session file(s) that actually changed.
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

CACHE_VERSION = 4
# Token count order used throughout: input, output, cache_creation, cache_read.
_TOKEN_SLOTS = 4
# Retention caps applied on every scan so the cache and per-tick merge stay bounded over time.
# Hourly only feeds the Today/Session graphs (Session spans at most 14 days); daily feeds up to
# the Year view (one calendar year).
HOURLY_RETENTION_DAYS = 15
DAILY_RETENTION_DAYS = 400


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


def _merge_hourly(into: dict[str, list[int]], src: dict[str, list[int]]) -> None:
    for hour, counts in src.items():
        _add4(into.setdefault(hour, [0, 0, 0, 0]), counts)


def _merge_sessions(into: dict[str, dict[str, Any]], src: dict[str, dict[str, Any]]) -> None:
    for sid, info in src.items():
        cur = into.get(sid)
        if cur is None:
            into[sid] = {
                "t": list(info["t"]),
                "models": {m: list(c) for m, c in info.get("models", {}).items()},
                "first": info["first"],
                "last": info["last"],
            }
        else:
            _add4(cur["t"], info["t"])
            models = cur.setdefault("models", {})
            for m, c in info.get("models", {}).items():
                _add4(models.setdefault(m, [0, 0, 0, 0]), c)
            cur["first"] = min(cur["first"], info["first"])
            cur["last"] = max(cur["last"], info["last"])


def _parse_file(path: str) -> dict[str, Any]:
    """Parse one JSONL transcript into its daily + hourly + session token contribution."""
    daily: dict[str, dict[str, list[int]]] = {}
    hourly: dict[str, list[int]] = {}
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
                hour_key = f"{local:%Y-%m-%dT%H}"
                tsec = local.timestamp()
                model = message.get("model") or "unknown"
                if usage.get("speed") == "fast":
                    # Fast mode keeps the same model id but bills at a premium, so track it apart.
                    model = f"{model}[fast]"
                sid = obj.get("sessionId") or "unknown"

                slot = daily.setdefault(date_key, {}).setdefault(model, [0, 0, 0, 0])
                _add4(slot, counts)
                _add4(hourly.setdefault(hour_key, [0, 0, 0, 0]), counts)

                sess = sessions.get(sid)
                if sess is None:
                    sessions[sid] = {
                        "t": list(counts),
                        "models": {model: list(counts)},
                        "first": tsec,
                        "last": tsec,
                    }
                else:
                    _add4(sess["t"], counts)
                    _add4(sess["models"].setdefault(model, [0, 0, 0, 0]), counts)
                    sess["first"] = min(sess["first"], tsec)
                    sess["last"] = max(sess["last"], tsec)
    except Exception as e:
        logger.debug("failed to parse %s: %s", path, e)
    return {"daily": daily, "hourly": hourly, "sessions": sessions}


def _prune(daily: dict[str, Any], hourly: dict[str, Any], now: datetime) -> None:
    """Drop daily buckets older than DAILY_RETENTION_DAYS and hourly older than HOURLY_RETENTION_DAYS.

    Bucket keys are zero-padded local timestamps, so they sort chronologically and compare against
    a cutoff key directly.
    """
    day_cutoff = f"{now - timedelta(days=DAILY_RETENTION_DAYS):%Y-%m-%d}"
    hour_cutoff = f"{now - timedelta(days=HOURLY_RETENTION_DAYS):%Y-%m-%dT%H}"
    for key in [k for k in daily if k < day_cutoff]:
        del daily[key]
    for key in [k for k in hourly if k < hour_cutoff]:
        del hourly[key]


def scan(cache_path: str) -> dict[str, Any]:
    """Incrementally scan all session transcripts and return the merged aggregate.

    Unchanged files reuse their cached contribution; only new or modified files
    (by mtime/size) are re-parsed.
    """
    cache = _read_json(cache_path) or {}
    prev_files: dict[str, Any] = cache.get("files", {}) if cache.get("version") == CACHE_VERSION else {}

    now = datetime.now().astimezone()
    file_cutoff = now.timestamp() - DAILY_RETENTION_DAYS * 86400
    current_files: dict[str, Any] = {}
    pattern = os.path.join(_projects_dir(), "**", "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_mtime < file_cutoff:
            # The whole transcript predates the daily window; skipping it keeps `files` bounded.
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
                "hourly": contrib["hourly"],
                "sessions": contrib["sessions"],
            }

    daily: dict[str, dict[str, list[int]]] = {}
    hourly: dict[str, list[int]] = {}
    sessions: dict[str, dict[str, Any]] = {}
    for fc in current_files.values():
        _merge_daily(daily, fc["daily"])
        _merge_hourly(hourly, fc.get("hourly", {}))
        _merge_sessions(sessions, fc["sessions"])

    _prune(daily, hourly, now)
    _write_json(
        cache_path,
        {
            "version": CACHE_VERSION,
            "files": current_files,
            "daily": daily,
            "hourly": hourly,
            "sessions": sessions,
            "updated_at": int(time.time()),
        },
    )
    return {"daily": daily, "hourly": hourly, "sessions": sessions, "scanned_at": int(time.time())}


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


def _sum_hourly(hourly: dict[str, list[int]], hour_key: str, count_cache_read: bool) -> int:
    counts = hourly.get(hour_key)
    if not counts:
        return 0
    return counts[0] + counts[1] + counts[2] + (counts[3] if count_cache_read else 0)


def _hour_keys_in_range(start: datetime, end: datetime) -> list[str]:
    """Local YYYY-MM-DDTHH keys from start's hour through end's hour, inclusive."""
    keys = []
    cur = start.replace(minute=0, second=0, microsecond=0)
    last = end.replace(minute=0, second=0, microsecond=0)
    while cur <= last:
        keys.append(f"{cur:%Y-%m-%dT%H}")
        cur += timedelta(hours=1)
    return keys


def _month_keys_in_range(start: datetime, end: datetime) -> list[str]:
    """Local YYYY-MM keys from start's month through end's month, inclusive."""
    keys = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return keys


def _sum_month(daily: dict[str, dict[str, list[int]]], month_key: str, count_cache_read: bool) -> int:
    prefix = f"{month_key}-"
    return sum(_sum_daily(daily, dk, count_cache_read) for dk in daily if dk.startswith(prefix))


def _sorted_models(totals: dict[str, int]) -> list[tuple[str, int]]:
    """Per-model (model_id, tokens) pairs sorted descending; drops zero totals and <synthetic>."""
    items = [(m, n) for m, n in totals.items() if n > 0 and m != "<synthetic>"]
    items.sort(key=lambda kv: kv[1], reverse=True)
    return items


def _models_in_range(
    daily: dict[str, dict[str, list[int]]], start: datetime, end: datetime, count_cache_read: bool
) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    for date_key in _date_keys_in_range(start, end):
        for model, counts in daily.get(date_key, {}).items():
            total = counts[0] + counts[1] + counts[2] + (counts[3] if count_cache_read else 0)
            totals[model] = totals.get(model, 0) + total
    return _sorted_models(totals)


def summarize(
    agg: dict[str, Any],
    *,
    count_cache_read: bool = True,
    week_starts_on: str = "monday",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive Session/Today/Week/Month/Year totals and a per-period graph series.

    Each period's series matches its window: Today is hourly (midnight to now), Session
    is hourly across the session's span (capped to 14 days), Week and Month are daily,
    and Year is monthly. ``now`` (local, tz-aware) is injectable for deterministic tests.
    """
    now = now or datetime.now().astimezone()
    daily = agg.get("daily", {})
    hourly = agg.get("hourly", {})
    sessions = agg.get("sessions", {})
    ccr = count_cache_read

    def window_total(start: datetime) -> int:
        return sum(_sum_daily(daily, k, ccr) for k in _date_keys_in_range(start, now))

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = now.weekday()  # Mon=0
    back = (weekday + 1) % 7 if week_starts_on == "sunday" else weekday
    week_start = today_start - timedelta(days=back)
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    # Session = the most recently active session id.
    session_total = 0
    session_id = None
    session_series: list[float] = []
    session_models: list[tuple[str, int]] = []
    if sessions:
        session_id, info = max(sessions.items(), key=lambda kv: kv[1]["last"])
        t = info["t"]
        session_total = t[0] + t[1] + t[2] + (t[3] if ccr else 0)
        first = datetime.fromtimestamp(info["first"]).astimezone()
        last = datetime.fromtimestamp(info["last"]).astimezone()
        s_start = max(first, now - timedelta(days=14))
        session_series = [_sum_hourly(hourly, k, ccr) for k in _hour_keys_in_range(s_start, last)]
        session_models = _sorted_models(
            {m: c[0] + c[1] + c[2] + (c[3] if ccr else 0) for m, c in info.get("models", {}).items()}
        )

    series_by_period = {
        "session": session_series,
        "today": [_sum_hourly(hourly, k, ccr) for k in _hour_keys_in_range(today_start, now)],
        "week": [_sum_daily(daily, k, ccr) for k in _date_keys_in_range(week_start, now)],
        "month": [_sum_daily(daily, k, ccr) for k in _date_keys_in_range(month_start, now)],
        "year": [_sum_month(daily, k, ccr) for k in _month_keys_in_range(year_start, now)],
    }
    models_by_period = {
        "session": session_models,
        "today": _models_in_range(daily, today_start, now, ccr),
        "week": _models_in_range(daily, week_start, now, ccr),
        "month": _models_in_range(daily, month_start, now, ccr),
        "year": _models_in_range(daily, year_start, now, ccr),
    }

    return {
        "totals": {
            "session": session_total,
            "today": window_total(today_start),
            "week": window_total(week_start),
            "month": window_total(month_start),
            "year": window_total(year_start),
        },
        "series_by_period": series_by_period,
        "models_by_period": models_by_period,
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
            self.data_ready.emit({"daily": {}, "hourly": {}, "sessions": {}, "scanned_at": int(time.time())})


class TokenHistoryService(QObject):
    """Shared local token-history poller (mirrors ClaudeUsageService).

    One instance per ``scan_interval`` scans the transcripts on a timer and shares
    the merged aggregate with every widget on the same interval.
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
            "hourly": cached.get("hourly", {}),
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

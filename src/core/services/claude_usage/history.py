"""Claude Code's token use, from the session logs it writes on this computer.

Claude Code keeps a JSONL log per session in projects/**/*.jsonl under its folder, and every answer in it carries a
message.usage block of token counts. Only those counts, the times, the model and the session id are read; what was
said is never touched. Each log's counts are cached by its size and change time, so a scan only reads the logs that
changed since the last one.
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.services.claude_usage.api import config_dir
from core.utils.system import app_data_path

HISTORY_FILE = "claude_token_history.json"
CACHE_VERSION = 4
# Hours feed only Today and Session, which spans at most SESSION_DAYS; days feed up to the Year
HOURLY_RETENTION_DAYS = 15
DAILY_RETENTION_DAYS = 400
SESSION_DAYS = 14
PERIODS = ("session", "today", "week", "month", "year")
# Token counts are kept in this order throughout
KINDS = ("input", "output", "cacheCreation", "cacheRead")
FAST = "[fast]"

type Counts = list[int]
type Daily = dict[str, dict[str, Counts]]
type Hourly = dict[str, Counts]
type Sessions = dict[str, dict[str, Any]]


def _add(into: Counts, counts: Counts) -> None:
    for index, count in enumerate(counts):
        into[index] += count


def _total(counts: Counts, count_cache_read: bool) -> int:
    return counts[0] + counts[1] + counts[2] + (counts[3] if count_cache_read else 0)


def model_name(model: str) -> str:
    """A model id as people say it: claude-opus-4-1-20250805 is Opus 4.1, and Opus 4.1 (fast) in fast mode."""
    fast = model.endswith(FAST)
    base = re.sub(r"\[[^\]]*\]", "", model)
    parts = [part for part in base.removeprefix("claude-").split("-") if not (part.isdigit() and len(part) == 8)]
    family = next((part for part in parts if part.isalpha()), "")
    numbers = [part for part in parts if part.isdigit()]
    name = f"{family.capitalize()} {'.'.join(numbers)}".strip() if family else base
    return f"{name} (fast)" if fast else name


def parse_log(path: Path) -> dict[str, Any]:
    """One session log's token counts by day and model, by hour, and by session."""
    daily: Daily = {}
    hourly: Hourly = {}
    sessions: Sessions = {}
    try:
        with path.open(encoding="utf-8") as lines:
            for line in lines:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = cast(dict[str, Any], entry).get("message") if isinstance(entry, dict) else None
                usage = cast(dict[str, Any], message).get("usage") if isinstance(message, dict) else None
                if not isinstance(usage, dict):
                    continue
                usage = cast(dict[str, Any], usage)
                counts = [
                    int(usage.get("input_tokens") or 0),
                    int(usage.get("output_tokens") or 0),
                    int(usage.get("cache_creation_input_tokens") or 0),
                    int(usage.get("cache_read_input_tokens") or 0),
                ]
                entry = cast(dict[str, Any], entry)
                stamp = entry.get("timestamp")
                if not any(counts) or not isinstance(stamp, str):
                    continue
                try:
                    local = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
                except ValueError:
                    continue
                model = cast(dict[str, Any], message).get("model") or "unknown"
                if usage.get("speed") == "fast":
                    # Fast mode keeps the model id but costs more, so it is counted apart
                    model = f"{model}{FAST}"
                second = local.timestamp()
                _add(daily.setdefault(f"{local:%Y-%m-%d}", {}).setdefault(model, [0, 0, 0, 0]), counts)
                _add(hourly.setdefault(f"{local:%Y-%m-%dT%H}", [0, 0, 0, 0]), counts)
                session = sessions.setdefault(
                    entry.get("sessionId") or "unknown",
                    {"t": [0, 0, 0, 0], "models": {}, "first": second, "last": second},
                )
                _add(session["t"], counts)
                _add(session["models"].setdefault(model, [0, 0, 0, 0]), counts)
                session["first"] = min(session["first"], second)
                session["last"] = max(session["last"], second)
    except OSError:
        logging.debug("Could not read the Claude Code log %s", path, exc_info=True)
    return {"daily": daily, "hourly": hourly, "sessions": sessions}


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return cast(dict[str, Any], data) if isinstance(data, dict) else {}


def scan() -> dict[str, Any]:
    """Every session log's token counts merged: {daily, hourly, sessions}, reading only the logs that changed."""
    cache_path = app_data_path(HISTORY_FILE)
    cache = _read_cache(cache_path)
    known: dict[str, Any] = cache.get("files", {}) if cache.get("version") == CACHE_VERSION else {}
    now = datetime.now().astimezone()
    oldest = now.timestamp() - DAILY_RETENTION_DAYS * 86400
    files: dict[str, Any] = {}
    for log in (config_dir() / "projects").glob("**/*.jsonl"):
        try:
            stat = log.stat()
        except OSError:
            continue
        if stat.st_mtime < oldest:
            continue
        key = str(log)
        before = known.get(key)
        if before and before.get("mtime") == stat.st_mtime and before.get("size") == stat.st_size:
            files[key] = before
        else:
            files[key] = {"mtime": stat.st_mtime, "size": stat.st_size, **parse_log(log)}

    daily: Daily = {}
    hourly: Hourly = {}
    sessions: Sessions = {}
    for counted in files.values():
        for day, models in counted["daily"].items():
            for model, counts in models.items():
                _add(daily.setdefault(day, {}).setdefault(model, [0, 0, 0, 0]), counts)
        for hour, counts in counted.get("hourly", {}).items():
            _add(hourly.setdefault(hour, [0, 0, 0, 0]), counts)
        for session_id, info in counted["sessions"].items():
            session = sessions.setdefault(
                session_id, {"t": [0, 0, 0, 0], "models": {}, "first": info["first"], "last": info["last"]}
            )
            _add(session["t"], info["t"])
            for model, counts in info.get("models", {}).items():
                _add(session["models"].setdefault(model, [0, 0, 0, 0]), counts)
            session["first"] = min(session["first"], info["first"])
            session["last"] = max(session["last"], info["last"])

    day_cutoff = f"{now - timedelta(days=DAILY_RETENTION_DAYS):%Y-%m-%d}"
    hour_cutoff = f"{now - timedelta(days=HOURLY_RETENTION_DAYS):%Y-%m-%dT%H}"
    daily = {day: models for day, models in daily.items() if day >= day_cutoff}
    hourly = {hour: counts for hour, counts in hourly.items() if hour >= hour_cutoff}
    try:
        cache_path.write_text(
            json.dumps(
                {
                    "version": CACHE_VERSION,
                    "files": files,
                    "daily": daily,
                    "hourly": hourly,
                    "sessions": sessions,
                    "updated_at": int(time.time()),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        logging.debug("Could not save the Claude token history", exc_info=True)
    return {"daily": daily, "hourly": hourly, "sessions": sessions}


def cached_history() -> dict[str, Any]:
    """The counts the last scan saved, {daily, hourly, sessions}, for showing before a new scan ends."""
    cache = _read_cache(app_data_path(HISTORY_FILE))
    return {name: cache.get(name, {}) for name in ("daily", "hourly", "sessions")}


def _hours(start: datetime, end: datetime) -> list[datetime]:
    hour = start.replace(minute=0, second=0, microsecond=0)
    hours: list[datetime] = []
    while hour <= end:
        hours.append(hour)
        hour += timedelta(hours=1)
    return hours


def _days(start: datetime, end: datetime) -> list[str]:
    day, last = start.date(), end.date()
    days: list[str] = []
    while day <= last:
        days.append(f"{day:%Y-%m-%d}")
        day += timedelta(days=1)
    return days


def _months(start: datetime, end: datetime) -> list[str]:
    year, month = start.year, start.month
    months: list[str] = []
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _models(totals: dict[str, Counts], count_cache_read: bool) -> list[dict[str, Any]]:
    """Each model's tokens, most first, leaving out Claude Code's own <synthetic> answers."""
    counted = [(model, _total(counts, count_cache_read)) for model, counts in totals.items() if model != "<synthetic>"]
    counted.sort(key=lambda item: item[1], reverse=True)
    return [{"model": model, "name": model_name(model), "tokens": tokens} for model, tokens in counted if tokens > 0]


def _period(
    models: dict[str, Counts], series: list[int], start: datetime, step: str, count_cache_read: bool
) -> dict[str, Any]:
    kinds = [0, 0, 0, 0]
    for counts in models.values():
        _add(kinds, counts)
    return {
        "total": _total(kinds, count_cache_read),
        "kinds": dict(zip(KINDS, kinds, strict=True)),
        "series": series,
        "start": int(start.timestamp() * 1000),
        "step": step,
        "models": _models(models, count_cache_read),
    }


def summarize(
    history: dict[str, Any], count_cache_read: bool, week_starts_on: str, now: datetime | None = None
) -> dict[str, Any]:
    """Each period's tokens: {sessionId, periods: {session, today, week, month, year}}.

    A period is {total, kinds, series, start, step, models}: total counts cache reads only when count_cache_read;
    kinds splits every token by input, output, cacheCreation and cacheRead; series is the tokens per step (hour,
    day or month) from start, in ms since the epoch; models is each model's {model, name, tokens}, most first.
    Session is the last session used, across its whole life up to SESSION_DAYS.
    """
    now = now or datetime.now().astimezone()
    daily: Daily = history.get("daily", {})
    hourly: Hourly = history.get("hourly", {})
    sessions: Sessions = history.get("sessions", {})

    def day_models(days: list[str]) -> dict[str, Counts]:
        models: dict[str, Counts] = {}
        for day in days:
            for model, counts in daily.get(day, {}).items():
                _add(models.setdefault(model, [0, 0, 0, 0]), counts)
        return models

    def day_total(day: str) -> int:
        return sum(_total(counts, count_cache_read) for counts in daily.get(day, {}).values())

    def hour_total(hour: datetime) -> int:
        return _total(hourly.get(f"{hour:%Y-%m-%dT%H}", [0, 0, 0, 0]), count_cache_read)

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    back = (now.weekday() + 1) % 7 if week_starts_on == "sunday" else now.weekday()
    starts = {
        "today": today,
        "week": today - timedelta(days=back),
        "month": today.replace(day=1),
        "year": today.replace(month=1, day=1),
    }
    periods: dict[str, Any] = {}
    for name in ("today", "week", "month"):
        start = starts[name]
        days = _days(start, now)
        series = [hour_total(hour) for hour in _hours(start, now)] if name == "today" else [day_total(d) for d in days]
        periods[name] = _period(day_models(days), series, start, "hour" if name == "today" else "day", count_cache_read)
    year = starts["year"]
    months = [sum(day_total(day) for day in daily if day.startswith(f"{month}-")) for month in _months(year, now)]
    periods["year"] = _period(day_models(_days(year, now)), months, year, "month", count_cache_read)

    session_id = ""
    if sessions:
        session_id, info = max(sessions.items(), key=lambda item: item[1]["last"])
        first = max(datetime.fromtimestamp(info["first"]).astimezone(), now - timedelta(days=SESSION_DAYS))
        last = datetime.fromtimestamp(info["last"]).astimezone()
        hours = _hours(first, last)
        periods["session"] = _period(
            info.get("models", {}),
            [hour_total(hour) for hour in hours],
            hours[0] if hours else first,
            "hour",
            count_cache_read,
        )
    else:
        periods["session"] = _period({}, [], now, "hour", count_cache_read)
    return {"sessionId": session_id, "periods": {name: periods[name] for name in PERIODS}}


def compact(tokens: int) -> str:
    """A token count in a few characters: 950, 12.3K, 4.5M, 1.2B."""
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if tokens >= size:
            return f"{tokens / size:.1f}".removesuffix(".0") + suffix
    return str(tokens)


class ScanSignals(QObject):
    finished = pyqtSignal(dict)


class ScanJob(QRunnable):
    """Scans the session logs off the GUI thread."""

    def __init__(self) -> None:
        super().__init__()
        self.signals = ScanSignals()

    def run(self) -> None:
        try:
            history = scan()
        except Exception:
            logging.exception("Could not scan the Claude Code logs")
            history = cached_history()
        self.signals.finished.emit(history)

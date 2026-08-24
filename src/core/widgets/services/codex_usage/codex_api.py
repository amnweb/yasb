import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from core.utils.system import app_data_path

logger = logging.getLogger("codex_usage")

APP_NAME = "yasb-codex-usage"
APP_VERSION = "1.0.0"

EMPTY_RECORD: dict[str, Any] = {
    "primary": None,
    "secondary": None,
    "plan": None,
    "credits": None,
    "reset_credits": None,
    "limit_name": "Codex",
    "fetched_at": 0,
    "stale": True,
    "error": None,
    "tokens": None,
}

_TOKEN_FILE_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}
_TOKEN_CACHE_LOCK = threading.Lock()


def _cache_path() -> str:
    return str(app_data_path("codex_usage_widget_cache.json"))


def _read_cache(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as cache_file:
            value = json.load(cache_file)
        return value if isinstance(value, dict) else None
    except OSError, ValueError, TypeError:
        return None


def _write_cache(path: str, data: dict[str, Any]) -> None:
    """Persist only normalized usage values, never Codex credentials or protocol messages."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary_path = f"{path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file)
        os.replace(temporary_path, path)
    except OSError as error:
        logger.debug("failed to write Codex usage cache: %s", error)


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME", "").strip()
    return Path(os.path.expandvars(os.path.expanduser(configured or "~/.codex")))


def _event_date(timestamp: Any) -> str | None:
    if not isinstance(timestamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed.astimezone().date().isoformat()
    except ValueError:
        return None


def _parse_token_file(path: Path) -> dict[str, Any]:
    """Read only model, timestamp, and token-count metadata from one Codex session."""
    daily: defaultdict[str, int] = defaultdict(int)
    model_daily: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    current_model = "Codex"
    previous: dict[str, int] = {}
    fields = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")

    try:
        with path.open(encoding="utf-8") as session_file:
            for line in session_file:
                if "token_count" not in line and "session_meta" not in line and "turn_context" not in line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError, TypeError:
                    continue
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    continue
                if event.get("type") in {"session_meta", "turn_context"}:
                    model = payload.get("model")
                    if isinstance(model, str) and model.strip():
                        current_model = model.strip()
                    continue
                if payload.get("type") != "token_count":
                    continue
                info = payload.get("info")
                total_usage = info.get("total_token_usage") if isinstance(info, dict) else None
                if not isinstance(total_usage, dict):
                    continue
                event_day = _event_date(event.get("timestamp"))
                if event_day is None:
                    continue
                delta: dict[str, int] = {}
                for field in fields:
                    value = total_usage.get(field)
                    if not isinstance(value, (int, float)):
                        continue
                    current = max(0, int(value))
                    delta[field] = current if field not in previous else max(0, current - previous[field])
                    previous[field] = current
                token_delta = delta.get("total_tokens", 0)
                if token_delta <= 0:
                    continue
                daily[event_day] += token_delta
                model_daily[event_day][current_model] += token_delta
    except OSError:
        pass
    return {"daily": dict(daily), "model_daily": {day: dict(values) for day, values in model_daily.items()}}


def read_local_token_usage() -> dict[str, Any] | None:
    """Aggregate token metadata without parsing message content or opening credentials."""
    roots = (_codex_home() / "sessions", _codex_home() / "archived_sessions")
    paths: list[Path] = []
    for root in roots:
        if root.is_dir():
            paths.extend(root.rglob("*.jsonl"))
    if not paths:
        return None

    daily: defaultdict[str, int] = defaultdict(int)
    model_daily: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    active_paths: set[str] = set()
    with _TOKEN_CACHE_LOCK:
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            key = str(path)
            active_paths.add(key)
            cached = _TOKEN_FILE_CACHE.get(key)
            if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
                parsed = cached[2]
            else:
                parsed = _parse_token_file(path)
                _TOKEN_FILE_CACHE[key] = (stat.st_size, stat.st_mtime_ns, parsed)
            for day, count in parsed["daily"].items():
                daily[day] += count
            for day, values in parsed["model_daily"].items():
                for model, count in values.items():
                    model_daily[day][model] += count
        for key in tuple(_TOKEN_FILE_CACHE):
            if key not in active_paths:
                _TOKEN_FILE_CACHE.pop(key, None)

    today = datetime.now().date()
    periods = {"today": 1, "week": 7, "month": 30, "year": 365}
    totals: dict[str, int] = {}
    for name, days in periods.items():
        cutoff = today - timedelta(days=days - 1)
        totals[name] = sum(
            count for day, count in daily.items() if cutoff <= datetime.fromisoformat(day).date() <= today
        )

    month_cutoff = today - timedelta(days=29)
    models: defaultdict[str, int] = defaultdict(int)
    for day, values in model_daily.items():
        parsed_day = datetime.fromisoformat(day).date()
        if month_cutoff <= parsed_day <= today:
            for model, count in values.items():
                models[model] += count

    year_cutoff = today - timedelta(days=364)
    daily_year = {
        day: count for day, count in daily.items() if year_cutoff <= datetime.fromisoformat(day).date() <= today
    }
    return {
        "periods": totals,
        "daily": dict(sorted(daily_year.items())),
        "history_start": min(daily_year, default=today.isoformat()),
        "models": dict(sorted(models.items(), key=lambda item: item[1], reverse=True)[:5]),
    }


def _safe_token_usage(enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        return None
    try:
        return read_local_token_usage()
    except Exception as error:
        logger.debug("failed to aggregate local Codex token metadata: %s", error)
        return None


def _find_codex_command(configured_path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(configured_path.strip()))
    if expanded and os.path.isfile(expanded):
        return expanded
    found = shutil.which(expanded or "codex")
    if found:
        return found
    raise RuntimeError("Codex CLI was not found; install it or set codex_path")


def _send_message(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise RuntimeError("Codex app-server input is unavailable")
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


def _response_reader(process: subprocess.Popen[str], messages: queue.Queue[dict[str, Any] | None]) -> None:
    if process.stdout is None:
        messages.put(None)
        return
    for line in process.stdout:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict):
            messages.put(message)
    messages.put(None)


def _receive_response(messages: queue.Queue[dict[str, Any] | None], response_id: int, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Codex usage request timed out")
        try:
            message = messages.get(timeout=remaining)
        except queue.Empty as error:
            raise RuntimeError("Codex usage request timed out") from error
        if message is None:
            raise RuntimeError("Codex app-server closed unexpectedly")
        if message.get("id") == response_id:
            return message


def _response_result(message: dict[str, Any], operation: str) -> dict[str, Any]:
    if "error" in message:
        error: Any = message["error"]
        if isinstance(error, dict):
            error = error.get("message") or error.get("code")
        raise RuntimeError(f"Codex {operation} failed: {error}")
    result = message.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Codex returned an invalid {operation} response")
    return result


def read_rate_limits(codex_path: str, timeout: float) -> dict[str, Any]:
    """Read account limits through Codex app-server without accessing its credential files."""
    process_options: dict[str, Any] = {}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NO_WINDOW

    command = _find_codex_command(codex_path)
    try:
        process = subprocess.Popen(
            [command, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            **process_options,
        )
    except OSError as error:
        raise RuntimeError(f"Unable to start Codex CLI: {error}") from error

    messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
    threading.Thread(target=_response_reader, args=(process, messages), daemon=True).start()

    try:
        _send_message(
            process,
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": APP_NAME,
                        "title": "YASB Codex Usage",
                        "version": APP_VERSION,
                    }
                },
            },
        )
        _response_result(_receive_response(messages, 1, timeout), "initialization")
        _send_message(process, {"method": "initialized"})
        _send_message(process, {"id": 2, "method": "account/rateLimits/read"})
        return _response_result(_receive_response(messages, 2, timeout), "rate-limit request")
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()


def _normalize_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    used = value.get("usedPercent")
    if not isinstance(used, (int, float)):
        return None
    used = max(0.0, min(100.0, float(used)))
    return {
        "used": used,
        "remaining": 100.0 - used,
        "duration_mins": value.get("windowDurationMins"),
        "resets_at": value.get("resetsAt"),
    }


def _normalize_reset_credits(value: Any) -> dict[str, Any] | None:
    """Keep display metadata for reset credits while discarding redeemable identifiers."""
    if not isinstance(value, dict):
        return None
    available_count = value.get("availableCount")
    if not isinstance(available_count, (int, float)):
        return None

    normalized_credits: list[dict[str, Any]] | None = None
    credits = value.get("credits")
    if isinstance(credits, list):
        normalized_credits = []
        for credit in credits:
            if not isinstance(credit, dict):
                continue
            normalized_credits.append(
                {
                    "reset_type": credit.get("resetType"),
                    "status": credit.get("status"),
                    "granted_at": credit.get("grantedAt"),
                    "expires_at": credit.get("expiresAt"),
                    "title": credit.get("title"),
                    "description": credit.get("description"),
                }
            )
    return {"available_count": max(0, int(available_count)), "credits": normalized_credits}


def normalize_rate_limits(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the app-server response into a stable, cache-safe widget record."""
    limits_by_id = payload.get("rateLimitsByLimitId")
    limits: dict[str, Any] | None = None
    if isinstance(limits_by_id, dict):
        preferred = limits_by_id.get("codex")
        if isinstance(preferred, dict):
            limits = preferred
        else:
            limits = next((item for item in limits_by_id.values() if isinstance(item, dict)), None)
    if limits is None and isinstance(payload.get("rateLimits"), dict):
        limits = payload["rateLimits"]
    if limits is None:
        raise RuntimeError("Codex returned no account rate limits; sign in with ChatGPT")

    credits = limits.get("credits")
    credit_value: str | float | int | None = None
    if isinstance(credits, dict):
        if credits.get("unlimited"):
            credit_value = "Unlimited"
        elif isinstance(credits.get("balance"), (int, float)):
            credit_value = credits["balance"]

    return {
        "primary": _normalize_window(limits.get("primary")),
        "secondary": _normalize_window(limits.get("secondary")),
        "plan": limits.get("planType"),
        "credits": credit_value,
        "reset_credits": _normalize_reset_credits(payload.get("rateLimitResetCredits")),
        "limit_name": limits.get("limitName") or limits.get("limitId") or "Codex",
        "fetched_at": int(time.time()),
        "stale": False,
        "error": None,
    }


def fetch_usage(
    codex_path: str, cache_path: str, cache_ttl: int, timeout: float, show_token_usage: bool = True
) -> dict[str, Any]:
    """Return live limits, falling back to the last normalized cache on errors."""
    cached = _read_cache(cache_path)
    now = int(time.time())
    if cached and now - int(cached.get("fetched_at", 0)) < cache_ttl:
        record = dict(cached)
        record["tokens"] = _safe_token_usage(show_token_usage)
        return record

    try:
        record = normalize_rate_limits(read_rate_limits(codex_path, timeout))
        record["tokens"] = _safe_token_usage(show_token_usage)
        _write_cache(cache_path, record)
        return record
    except Exception as error:
        message = str(error).replace("\n", " ").strip()
        logger.debug("Codex usage fetch failed: %s", message)
        record = dict(cached or EMPTY_RECORD)
        record["stale"] = True
        record["error"] = message
        record["tokens"] = _safe_token_usage(show_token_usage)
        return record


class _UsageWorker(QThread):
    """Run the blocking app-server exchange away from the Qt UI thread."""

    data_ready = pyqtSignal(dict)

    def __init__(
        self,
        codex_path: str,
        cache_path: str,
        cache_ttl: int,
        timeout: float,
        show_token_usage: bool,
        parent: Any = None,
    ):
        super().__init__(parent)
        self._codex_path = codex_path
        self._cache_path = cache_path
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._show_token_usage = show_token_usage

    def run(self) -> None:
        self.data_ready.emit(
            fetch_usage(
                self._codex_path,
                self._cache_path,
                self._cache_ttl,
                self._timeout,
                self._show_token_usage,
            )
        )


class CodexUsageService(QObject):
    """Reference-counted background poller shared by identical Codex widgets."""

    data_ready = pyqtSignal(dict)

    _instances: ClassVar[dict[tuple, CodexUsageService]] = {}

    @classmethod
    def get_instance(
        cls,
        codex_path: str,
        update_interval_s: int,
        cache_ttl: int,
        timeout: float,
        show_token_usage: bool = True,
    ) -> CodexUsageService:
        key = (codex_path, int(update_interval_s), int(cache_ttl), float(timeout), bool(show_token_usage))
        instance = cls._instances.get(key)
        if instance is None:
            instance = cls(codex_path, update_interval_s, cache_ttl, timeout, show_token_usage, key)
            cls._instances[key] = instance
        instance._refcount += 1
        return instance

    def __init__(
        self,
        codex_path: str,
        update_interval_s: int,
        cache_ttl: int,
        timeout: float,
        show_token_usage: bool,
        key: tuple,
    ):
        super().__init__()
        self._key = key
        self._refcount = 0
        self._codex_path = codex_path
        self._cache_path = _cache_path()
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._show_token_usage = show_token_usage
        self._worker: _UsageWorker | None = None
        self._data: dict[str, Any] = _read_cache(self._cache_path) or dict(EMPTY_RECORD)

        self._timer = QTimer(self)
        self._timer.setInterval(max(int(update_interval_s), 1) * 1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def latest(self) -> dict[str, Any]:
        return self._data

    def refresh_now(self) -> None:
        self._start_worker(0)

    def release(self) -> None:
        self._refcount -= 1
        if self._refcount > 0:
            return
        self._timer.stop()
        CodexUsageService._instances.pop(self._key, None)
        if self._worker is not None and self._worker.isRunning():
            self._worker.finished.connect(self.deleteLater)
        else:
            self.deleteLater()

    def _tick(self) -> None:
        self._start_worker(self._cache_ttl)

    def _start_worker(self, cache_ttl: int) -> None:
        if self._worker is not None:
            return
        worker = _UsageWorker(
            self._codex_path,
            self._cache_path,
            cache_ttl,
            self._timeout,
            self._show_token_usage,
            self,
        )
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

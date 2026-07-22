import json
import logging
import os
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from core.utils.system import app_data_path

logger = logging.getLogger("codex_usage")

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

EMPTY_RECORD: dict[str, Any] = {
    "five": None,
    "five_raw": None,
    "five_reset_iso": None,
    "weekly": None,
    "weekly_raw": None,
    "weekly_reset_iso": None,
    "fetched_at": 0,
}


def _codex_home() -> str:
    return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def _cache_path() -> str:
    return str(app_data_path("codex_usage_cache.json"))


def _read_cache(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(path: str, data: dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug("failed to write cache: %s", e)


def _epoch_to_iso(value: Any) -> str | None:
    """Convert a Unix epoch (seconds) reset timestamp to an ISO 8601 UTC string."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
    except TypeError, ValueError, OSError:
        return None


def fetch_usage(cache_path: str, cache_ttl: int) -> dict[str, Any]:
    """Return a usage record, hitting the network only when the cache is stale.

    On any error (including HTTP 429 rate limiting) the last cached record is
    returned so the widget keeps showing the most recent known values. The OAuth
    token is read from Codex CLI's credentials store and is never logged.
    """
    cache = _read_cache(cache_path)
    now = int(time.time())
    if cache and (now - int(cache.get("fetched_at", 0))) < cache_ttl:
        return cache

    try:
        auth_path = os.path.join(_codex_home(), "auth.json")
        with open(auth_path, encoding="utf-8") as f:
            tokens = json.load(f)["tokens"]
        access_token = tokens["access_token"]
        account_id = tokens["account_id"]

        request = urllib.request.Request(
            USAGE_URL,
            headers={"Authorization": f"Bearer {access_token}", "ChatGPT-Account-ID": account_id},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        rate_limit = payload["rate_limit"]
        primary = rate_limit.get("primary_window")
        secondary = rate_limit.get("secondary_window")

        five_raw = float(primary["used_percent"]) if primary else None
        weekly_raw = float(secondary["used_percent"]) if secondary else None
        record = {
            "five": round(five_raw) if five_raw is not None else None,
            "five_raw": five_raw,
            "five_reset_iso": _epoch_to_iso(primary.get("reset_at")) if primary else None,
            "weekly": round(weekly_raw) if weekly_raw is not None else None,
            "weekly_raw": weekly_raw,
            "weekly_reset_iso": _epoch_to_iso(secondary.get("reset_at")) if secondary else None,
            "fetched_at": now,
        }
        _write_cache(cache_path, record)
        return record
    except Exception as e:
        logger.debug("usage fetch failed: %s", e)
        if cache:
            return cache
        return dict(EMPTY_RECORD)


class _UsageWorker(QThread):
    """Runs the (blocking) credential read + HTTP request off the UI thread."""

    data_ready = pyqtSignal(dict)

    def __init__(self, cache_path: str, cache_ttl: int, parent: Any = None):
        super().__init__(parent)
        self._cache_path = cache_path
        self._cache_ttl = cache_ttl

    def run(self) -> None:
        self.data_ready.emit(fetch_usage(self._cache_path, self._cache_ttl))


class CodexUsageService(QObject):
    """Shared Codex usage poller.

    One service instance fetches the usage record on a timer and shares it with
    every widget that requests the same ``(update_interval, cache_ttl)`` pair, so
    multiple Codex widgets never duplicate the network request or the on-disk
    cache. Instances are reference-counted and released when the last widget goes
    away (mirrors ``ClaudeUsageService``).
    """

    data_ready = pyqtSignal(dict)

    _instances: ClassVar[dict[tuple, CodexUsageService]] = {}

    @classmethod
    def get_instance(cls, update_interval_s: int, cache_ttl: int) -> CodexUsageService:
        key = (int(update_interval_s), int(cache_ttl))
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls(update_interval_s=int(update_interval_s), cache_ttl=int(cache_ttl), _key=key)
            cls._instances[key] = inst
        inst._refcount += 1
        return inst

    def __init__(self, update_interval_s: int, cache_ttl: int, _key: tuple):
        super().__init__()
        self._key = _key
        self._refcount = 0
        self._cache_path = _cache_path()
        self._cache_ttl = cache_ttl
        self._worker: _UsageWorker | None = None
        self._data: dict[str, Any] = _read_cache(self._cache_path) or dict(EMPTY_RECORD)

        self._timer = QTimer(self)
        self._timer.setInterval(max(int(update_interval_s), 1) * 1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def latest(self) -> dict[str, Any]:
        """The most recent usage record (cached value, available immediately)."""
        return self._data

    def release(self) -> None:
        self._refcount -= 1
        if self._refcount > 0:
            return
        self._timer.stop()
        CodexUsageService._instances.pop(self._key, None)
        if self._worker is not None and self._worker.isRunning():
            # Tear down only once the in-flight fetch finishes, so we never block the
            # GUI thread (or destroy a running QThread) during a config reload.
            self._worker.finished.connect(self.deleteLater)
        else:
            self.deleteLater()

    def _tick(self) -> None:
        if self._worker is not None:
            return  # a fetch is already in flight
        worker = _UsageWorker(self._cache_path, self._cache_ttl, self)
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

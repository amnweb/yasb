"""DeepSeek platform balance poller.

Reads ``GET /user/balance`` with the user's platform API key and folds each result
into the local spend ledger (see ``spend_history``), which turns a sequence of
balance readings into real per-period spend.

The key is resolved at fetch time and never leaves this module: it is not logged,
not written to the cache, and not included in the emitted record. The on-disk cache
holds normalized balance figures only.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from core.utils.system import app_data_path
from core.widgets.services.deepseek_usage.spend_history import (
    empty_ledger,
    ledger_path,
    load_ledger,
    record_snapshot,
    save_ledger,
    trim,
)

logger = logging.getLogger("deepseek_usage")

BALANCE_URL = "https://api.deepseek.com/user/balance"
# Checked in order, so a YASB-specific key can override a shell-wide one.
API_KEY_ENV_VARS = ("YASB_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")

EMPTY_RECORD: dict[str, Any] = {
    "available": None,
    "currency": "",
    "total": None,
    "granted": None,
    "topped_up": None,
    "fetched_at": 0,
    "error": "no_key",
    "stale": True,
}


def fingerprint_api_key(key: str | None) -> str:
    """A short, non-reversible label for a key, e.g. ``sk-...1e06``.

    DeepSeek's API carries no account identity - ``/user/balance`` returns money and
    nothing else - so on a machine holding more than one key this is the only thing that
    says whose balance is on screen. Four trailing characters is the usual convention for
    naming a secret without exposing it, and is far too little to reconstruct one.
    """
    value = (key or "").strip()
    if len(value) < 8:
        return ""
    prefix = "sk-" if value.startswith("sk-") else ""
    return f"{prefix}…{value[-4:]}"


def resolve_api_key(configured: str | None) -> str:
    """The API key to use, from config or the environment.

    ``"env"`` (the documented default) reads the environment, and so does an empty
    value, so a user who exports a key never has to touch their config at all.
    """
    value = (configured or "").strip()
    if value and value.lower() != "env":
        return value
    for name in API_KEY_ENV_VARS:
        from_env = (os.getenv(name) or "").strip()
        if from_env:
            return from_env
    return ""


def select_balance(payload: dict[str, Any], preferred_currency: str = "auto") -> dict[str, Any]:
    """Pick the balance entry to display from the ``balance_infos`` array.

    An account can carry both CNY and USD entries. ``auto`` prefers the first one
    holding actual money, so a zeroed-out secondary currency never hides the real
    balance; an explicit currency wins when present, and falls back to auto.
    """
    entries = [entry for entry in (payload.get("balance_infos") or []) if isinstance(entry, dict)]
    if not entries:
        return {}

    wanted = (preferred_currency or "auto").strip().upper()
    if wanted and wanted != "AUTO":
        for entry in entries:
            if str(entry.get("currency") or "").upper() == wanted:
                return entry

    for entry in entries:
        try:
            if float(entry.get("total_balance") or 0) > 0:
                return entry
        except TypeError, ValueError:
            continue
    return entries[0]


def _cache_path() -> str:
    return str(app_data_path("deepseek_usage_cache.json"))


def _read_cache(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as cache_file:
            value = json.load(cache_file)
        return value if isinstance(value, dict) else None
    except OSError, ValueError:
        return None


def _write_cache(path: str, data: dict[str, Any]) -> None:
    """Persist normalized balance figures only, never the API key."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary_path = f"{path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file)
        os.replace(temporary_path, path)
    except OSError as error:
        logger.debug("failed to write DeepSeek usage cache: %s", error)


def _stale(record: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    served = dict(record)
    served["stale"] = True
    if error:
        served["error"] = error
    return served


def fetch_balance(
    api_key: str,
    cache_path: str,
    cache_ttl: int,
    preferred_currency: str = "auto",
) -> dict[str, Any]:
    """Return a balance record, hitting the network only when the cache is stale.

    On any failure the last cached record is served with ``stale`` set, so the widget
    keeps showing the most recent known balance instead of blanking out.
    """
    cache = _read_cache(cache_path)
    now = int(time.time())

    if not api_key:
        record = dict(cache or EMPTY_RECORD)
        record["error"] = "no_key"
        record["stale"] = True
        return record

    if cache and (now - int(cache.get("fetched_at", 0) or 0)) < cache_ttl:
        return cache

    try:
        request = urllib.request.Request(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        entry = select_balance(payload, preferred_currency)
        record = {
            "available": bool(payload.get("is_available")),
            "currency": str(entry.get("currency") or ""),
            "total": entry.get("total_balance"),
            "granted": entry.get("granted_balance"),
            "topped_up": entry.get("topped_up_balance"),
            "fetched_at": now,
            "error": None,
            "stale": False,
        }
        _write_cache(cache_path, record)
        return record
    except urllib.error.HTTPError as error:
        # 401/403 means the key is wrong or revoked - worth telling the user apart
        # from a flaky network, which resolves itself.
        reason = "auth" if error.code in (401, 403) else "http"
        logger.debug("DeepSeek balance fetch failed with HTTP %s", error.code)
        return _stale(cache or EMPTY_RECORD, reason)
    except Exception as error:
        logger.debug("DeepSeek balance fetch failed: %s", error)
        return _stale(cache or EMPTY_RECORD, "network")


class _BalanceWorker(QThread):
    """Runs the blocking HTTP request and the ledger write off the UI thread."""

    data_ready = pyqtSignal(dict)

    def __init__(
        self,
        api_key: str,
        cache_path: str,
        cache_ttl: int,
        preferred_currency: str,
        count_granted: bool,
        parent: Any = None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._cache_path = cache_path
        self._cache_ttl = cache_ttl
        self._preferred_currency = preferred_currency
        self._count_granted = count_granted

    def run(self) -> None:
        record = fetch_balance(self._api_key, self._cache_path, self._cache_ttl, self._preferred_currency)
        ledger = self._update_ledger(record)
        self.data_ready.emit({**record, "ledger": ledger})

    def _update_ledger(self, record: dict[str, Any]) -> dict[str, Any]:
        """Fold a fresh reading into the spend ledger and persist it.

        Only a live reading is recorded. Replaying a cached or stale record would
        difference a balance against itself and, worse, re-attribute old spend to
        the current hour.
        """
        path = ledger_path()
        ledger = load_ledger(path)
        if record.get("stale") or record.get("error") or not record.get("fetched_at"):
            return ledger

        snapshot = {
            "ts": int(record.get("fetched_at") or 0),
            "total": record.get("total"),
            "granted": record.get("granted"),
            "topped_up": record.get("topped_up"),
            "currency": record.get("currency") or "",
        }
        record_snapshot(ledger, snapshot, count_granted=self._count_granted)
        trim(ledger)
        save_ledger(path, ledger)
        return ledger


class DeepSeekUsageService(QObject):
    """Shared DeepSeek balance poller.

    One instance serves every widget requesting the same configuration, so multiple
    DeepSeek widgets never duplicate the request, the cache or the ledger write.
    Instances are reference-counted and released when the last widget goes away
    (mirrors ``ClaudeUsageService``).
    """

    data_ready = pyqtSignal(dict)

    _instances: ClassVar[dict[tuple, DeepSeekUsageService]] = {}

    @classmethod
    def get_instance(
        cls,
        update_interval_s: int,
        cache_ttl: int,
        api_key: str,
        preferred_currency: str = "auto",
        count_granted: bool = True,
    ) -> DeepSeekUsageService:
        # The key itself is part of the identity (two widgets on two accounts must
        # not share a poller) but is never logged or displayed.
        key = (int(update_interval_s), int(cache_ttl), api_key, preferred_currency, bool(count_granted))
        instance = cls._instances.get(key)
        if instance is None:
            instance = cls(
                update_interval_s=int(update_interval_s),
                cache_ttl=int(cache_ttl),
                api_key=api_key,
                preferred_currency=preferred_currency,
                count_granted=bool(count_granted),
                _key=key,
            )
            cls._instances[key] = instance
        instance._refcount += 1
        return instance

    def __init__(
        self,
        update_interval_s: int,
        cache_ttl: int,
        api_key: str,
        preferred_currency: str,
        count_granted: bool,
        _key: tuple,
    ):
        super().__init__()
        self._key = _key
        self._refcount = 0
        self._api_key = api_key
        self._preferred_currency = preferred_currency
        self._count_granted = count_granted
        self._cache_path = _cache_path()
        self._cache_ttl = cache_ttl
        self._worker: _BalanceWorker | None = None

        cached = _read_cache(self._cache_path) or dict(EMPTY_RECORD)
        self._data: dict[str, Any] = {**cached, "ledger": load_ledger(ledger_path()) or empty_ledger()}

        self._timer = QTimer(self)
        self._timer.setInterval(max(int(update_interval_s), 1) * 1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def latest(self) -> dict[str, Any]:
        """The most recent record (cached value, available immediately)."""
        return self._data

    def release(self) -> None:
        self._refcount -= 1
        if self._refcount > 0:
            return
        self._timer.stop()
        DeepSeekUsageService._instances.pop(self._key, None)
        if self._worker is not None and self._worker.isRunning():
            # Tear down only once the in-flight fetch finishes, so we never block the
            # GUI thread (or destroy a running QThread) during a config reload.
            self._worker.finished.connect(self.deleteLater)
        else:
            self.deleteLater()

    def _tick(self) -> None:
        self._start_worker(self._cache_ttl)

    def refresh_now(self) -> None:
        """Force an immediate fetch, bypassing the cache TTL."""
        self._start_worker(0)

    def _start_worker(self, cache_ttl: int) -> None:
        if self._worker is not None:
            return  # a fetch is already in flight
        worker = _BalanceWorker(
            self._api_key,
            self._cache_path,
            cache_ttl,
            self._preferred_currency,
            self._count_granted,
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

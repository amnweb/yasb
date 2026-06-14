"""Claude API status polling.

Reads the public Anthropic/Claude status page (an Atlassian Statuspage) at
``https://status.claude.com/api/v2/status.json``. The ``status.indicator`` field
is one of ``none`` / ``minor`` / ``major`` / ``critical`` and maps to a coloured
dot in the widget. No authentication is required.
"""

import json
import logging
import time
import urllib.request
from typing import Any, ClassVar

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

logger = logging.getLogger("claude_usage")

STATUS_URL = "https://status.claude.com/api/v2/status.json"
# Indicator values an Atlassian Statuspage can report, worst-first.
STATUS_LEVELS = ("critical", "major", "minor", "none", "unknown")

EMPTY_STATUS: dict[str, Any] = {"indicator": "unknown", "description": "Status unavailable", "fetched_at": 0}


def fetch_status() -> dict[str, Any]:
    """Return the current Claude API status, or an 'unknown' record on any error."""
    try:
        request = urllib.request.Request(STATUS_URL, headers={"User-Agent": "yasb-claude-usage-widget"})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        status = payload.get("status") or {}
        indicator = status.get("indicator") or "none"
        if indicator not in STATUS_LEVELS:
            indicator = "unknown"
        return {
            "indicator": indicator,
            "description": status.get("description") or "",
            "fetched_at": int(time.time()),
        }
    except Exception as e:
        logger.debug("status fetch failed: %s", e)
        return dict(EMPTY_STATUS, fetched_at=int(time.time()))


class _StatusWorker(QThread):
    """Runs the (blocking) status request off the UI thread."""

    data_ready = pyqtSignal(dict)

    def run(self) -> None:
        self.data_ready.emit(fetch_status())


class ClaudeStatusService(QObject):
    """Shared Claude API status poller (mirrors ClaudeUsageService).

    One instance per ``poll_interval`` fetches the status page on a timer and
    shares it with every widget on the same interval. The last known non-error
    status is kept when a fetch fails, so a transient network blip doesn't flip
    the dot to grey.
    """

    data_ready = pyqtSignal(dict)

    _instances: ClassVar[dict[int, ClaudeStatusService]] = {}

    @classmethod
    def get_instance(cls, poll_interval_s: int) -> ClaudeStatusService:
        key = int(poll_interval_s)
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls(poll_interval_s=key, _key=key)
            cls._instances[key] = inst
        inst._refcount += 1
        return inst

    def __init__(self, poll_interval_s: int, _key: int):
        super().__init__()
        self._key = _key
        self._refcount = 0
        self._worker: _StatusWorker | None = None
        self._data: dict[str, Any] = dict(EMPTY_STATUS)

        self._timer = QTimer(self)
        self._timer.setInterval(max(int(poll_interval_s), 1) * 1000)
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
        ClaudeStatusService._instances.pop(self._key, None)
        if self._worker is not None and self._worker.isRunning():
            self._worker.finished.connect(self.deleteLater)
        else:
            self.deleteLater()

    def _tick(self) -> None:
        if self._worker is not None:
            return  # a fetch is already in flight
        worker = _StatusWorker(self)
        worker.data_ready.connect(self._on_data)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def _on_data(self, data: dict[str, Any]) -> None:
        # Keep the last known good status if this fetch failed.
        if data.get("indicator") == "unknown" and self._data.get("indicator") not in (None, "unknown"):
            data = dict(self._data, fetched_at=data.get("fetched_at", 0))
        self._data = data
        self.data_ready.emit(data)

    def _on_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

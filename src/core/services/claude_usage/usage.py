import json
import logging
import time
from typing import Any, ClassVar

from PyQt6.QtCore import QDateTime, QLocale, QObject, QThreadPool, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtNetwork import QNetworkAccessManager

from core.services.claude_usage import history as logs
from core.services.claude_usage.api import (
    STATUS_URL,
    USAGE_URL,
    get_json,
    parse_status,
    parse_usage,
    read_credentials,
)
from core.utils.feed import Feed
from core.utils.qml import qml_property
from core.utils.system import app_data_path

USAGE_FILE = "claude_usage.json"
# Anthropic limits how often its usage endpoint answers, so it is never asked more often than this
MIN_INTERVAL_MS = 30000
MAX_INTERVAL_MS = 3600000
MIN_STATUS_INTERVAL_MS = 60000
# The countdowns to each reset are written again this often
TICK_MS = 30000
TIME_FORMATS = ("24h", "12h")
WEEK_STARTS = ("monday", "sunday")
UNKNOWN_STATUS = {"indicator": "unknown", "description": ""}
# The Claude app keeps its sign-in to itself; only the Claude Code CLI leaves one the usage can be fetched with
SIGNED_OUT = "Install the Claude Code CLI and sign in once (run claude, then /login) to see your usage limits."


def now_ms() -> int:
    return int(time.time() * 1000)


class UsageFeed(Feed[int]):
    """Claude Code's usage limits from Anthropic, kept on disk so a restart or another bar does not ask again."""

    _feeds: ClassVar[dict[int, Any]] = {}

    def __init__(self, key: int) -> None:
        super().__init__(key)
        self.usage: dict[str, Any] | None = None
        # When the usage was fetched, in ms since the epoch
        self.fetched_at = 0
        token, self.expires_at = read_credentials()
        self.signed_in = bool(token)
        if not token:
            self.error = SIGNED_OUT
        self._network = QNetworkAccessManager(self)
        try:
            cached = json.loads(app_data_path(USAGE_FILE).read_text(encoding="utf-8"))
            self.usage, self.fetched_at = parse_usage(cached["usage"]), int(cached["fetchedAt"])
        except OSError, ValueError, KeyError, TypeError:
            pass
        # The cached usage is shown until it is due
        self._timer.start(max(0, min(key - (now_ms() - self.fetched_at), key)))

    @pyqtSlot()
    def fetch(self) -> None:
        self._timer.stop()
        token, self.expires_at = read_credentials()
        self.signed_in = bool(token)
        self._request += 1
        if not token:
            self.loading, self.error = False, SIGNED_OUT
            self._timer.start(self.key)
            self.changed.emit()
            return
        request = self._request
        self.loading = True
        self.changed.emit()
        get_json(self._network, USAGE_URL, lambda data, error: self._receive(request, data, error), token)

    def _receive(self, request: int, data: Any, error: str) -> None:
        if request != self._request:
            return
        if not error:
            self.usage, self.fetched_at = parse_usage(data), now_ms()
            try:
                app_data_path(USAGE_FILE).write_text(
                    json.dumps({"usage": data, "fetchedAt": self.fetched_at}), encoding="utf-8"
                )
            except OSError:
                logging.debug("Could not save the Claude usage", exc_info=True)
        # A failed fetch keeps the last usage; Anthropic is not asked again sooner, as it may be limiting requests
        self._timer.start(self.key)
        self.loading, self.error = False, error
        self.changed.emit()


class StatusFeed(Feed[int]):
    """Claude's status from status.claude.com, keeping the last one known while the page cannot be reached."""

    _feeds: ClassVar[dict[int, Any]] = {}

    def __init__(self, key: int) -> None:
        super().__init__(key)
        self.status: dict[str, str] = dict(UNKNOWN_STATUS)
        self._network = QNetworkAccessManager(self)
        self._timer.start(0)

    @pyqtSlot()
    def fetch(self) -> None:
        self._timer.stop()
        self._request += 1
        request = self._request
        self.loading = True
        self.changed.emit()
        get_json(self._network, STATUS_URL, lambda data, error: self._receive(request, data, error))

    def _receive(self, request: int, data: Any, error: str) -> None:
        if request != self._request:
            return
        status = parse_status(data) if not error else None
        if status is not None:
            self.status = status
        elif not error:
            error = "The Claude status page sent an answer YASB could not read."
        self._timer.start(self.key)
        self.loading, self.error = False, error
        self.changed.emit()


_pool: QThreadPool | None = None


def _scans() -> QThreadPool:
    """One thread for scanning the logs, so scans never run side by side."""
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(1)
    return _pool


class HistoryFeed(Feed[int]):
    """The token counts in Claude Code's session logs, scanned off the GUI thread."""

    _feeds: ClassVar[dict[int, Any]] = {}

    def __init__(self, key: int) -> None:
        super().__init__(key)
        self.history: dict[str, Any] | None = None
        self.scanned_at = 0
        self._job: logs.ScanJob | None = None
        self._timer.start(0)

    @pyqtSlot()
    def fetch(self) -> None:
        if self._job is not None:
            return
        self._timer.stop()
        self._request += 1
        request = self._request
        job = logs.ScanJob()

        def finished(history: dict[str, Any]) -> None:
            self._receive(request, history)

        job.signals.finished.connect(finished)
        self._job = job
        self.loading = True
        self.changed.emit()
        _scans().start(job)

    def _receive(self, request: int, history: dict[str, Any]) -> None:
        self._job = None
        if request != self._request:
            return
        self.history, self.scanned_at = history, now_ms()
        self._timer.start(self.key)
        self.loading = False
        self.changed.emit()


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(usage: ClaudeUsageMonitor) -> Any:
        return usage.setting(name)

    def set_value(usage: ClaudeUsageMonitor, value: Any) -> None:
        usage.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


class ClaudeUsageMonitor(QObject):
    """Claude Code's usage limits, its token use on this computer and Claude's status, for one widget.

    The data comes from feeds every widget with the same intervals shares: Anthropic's usage endpoint, signed in
    with Claude Code's own sign-in; the session logs Claude Code writes; and status.claude.com.
    """

    settingsChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    usageChanged = pyqtSignal()
    historyChanged = pyqtSignal()
    statusChanged = pyqtSignal()

    # How often the usage is fetched, in milliseconds; Anthropic limits how often it answers
    updateInterval = _setting(int, "updateInterval", settingsChanged)
    # Whether Claude Code's session logs are scanned for the tokens it used
    tokenHistory = _setting(bool, "tokenHistory", settingsChanged)
    # How often the logs are scanned, in milliseconds
    scanInterval = _setting(int, "scanInterval", settingsChanged)
    # Whether tokens read back from the prompt cache count in the totals; they are most of a long session's tokens
    countCacheRead = _setting(bool, "countCacheRead", settingsChanged)
    # monday or sunday
    weekStartsOn = _setting(str, "weekStartsOn", settingsChanged)
    # Whether Claude's status is checked on status.claude.com
    checkStatus = _setting(bool, "checkStatus", settingsChanged)
    # How often the status is checked, in milliseconds
    statusInterval = _setting(int, "statusInterval", settingsChanged)
    # 24h or 12h, for the times the limits reset
    timeFormat = _setting(str, "timeFormat", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "updateInterval": 120000,
            "tokenHistory": True,
            "scanInterval": 120000,
            "countCacheRead": True,
            "weekStartsOn": "monday",
            "checkStatus": True,
            "statusInterval": 300000,
            "timeFormat": "24h",
        }
        self._usage_feed: UsageFeed | None = None
        self._history_feed: HistoryFeed | None = None
        self._status_feed: StatusFeed | None = None
        self._state: tuple[Any, ...] = (False, False, False, "", 0)
        self._limits: dict[str, Any] = {"fiveHour": {}, "sevenDay": {}, "models": [], "all": [], "fetched": False}
        self._values: dict[str, str] = {}
        self._history: dict[str, Any] = {}
        self._history_state: tuple[bool, int] = (False, 0)
        self._status: dict[str, Any] = dict(UNKNOWN_STATUS)

        # QML sets the settings after creating the object, so the feeds are joined once they are in
        self._join_timer = QTimer(self)
        self._join_timer.setSingleShot(True)
        self._join_timer.setInterval(0)
        self._join_timer.timeout.connect(self._join)
        self._join_timer.start()
        # The countdowns to each reset move on without a fetch
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._publish)
        self._tick.start()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if name in ("updateInterval", "scanInterval"):
            value = _clamp(int(value), MIN_INTERVAL_MS, MAX_INTERVAL_MS)
        elif name == "statusInterval":
            value = _clamp(int(value), MIN_STATUS_INTERVAL_MS, MAX_INTERVAL_MS)
        elif name == "weekStartsOn" and value not in WEEK_STARTS:
            value = "monday"
        elif name == "timeFormat" and value not in TIME_FORMATS:
            value = "24h"
        if value == self._settings[name]:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name in ("updateInterval", "tokenHistory", "scanInterval", "checkStatus", "statusInterval"):
            self._join_timer.start()
        else:
            self._publish()

    # Whether Claude Code is signed in on this computer; without it there is no usage
    @qml_property(bool, notify=stateChanged)
    def signedIn(self) -> bool:
        return self._state[0]

    # Whether Claude Code's sign-in has run out; it renews it the next time it runs, and until then the last usage
    # fetched stays
    @qml_property(bool, notify=stateChanged)
    def tokenExpired(self) -> bool:
        return self._state[1]

    @qml_property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._state[2]

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._state[3]

    # When the usage shown was fetched; invalid without one
    @qml_property(QDateTime, notify=stateChanged)
    def updated(self) -> QDateTime:
        return QDateTime.fromMSecsSinceEpoch(self._state[4]) if self._state[4] else QDateTime()

    # Whether Anthropic answered; it can leave out a window or every limit, so limits may still be empty
    @qml_property(bool, notify=usageChanged)
    def ready(self) -> bool:
        return self._limits["fetched"]

    # A limit is {name, percent, value, level, resetsAt, resetIn, resetOn}: percent of it used, value that rounded,
    # level low under 50, medium under 80 and high from 80, resetsAt a QDateTime (invalid when unknown), resetIn a
    # countdown such as "4h 27m" and resetOn a time such as "Sat 06:00". Empty when Anthropic sent none.

    # The 5-hour window every model shares
    @qml_property("QVariantMap", notify=usageChanged)
    def fiveHour(self) -> dict[str, Any]:
        return self._limits["fiveHour"]

    # The 7-day window every model shares
    @qml_property("QVariantMap", notify=usageChanged)
    def sevenDay(self) -> dict[str, Any]:
        return self._limits["sevenDay"]

    # Weekly caps a plan gives single models, each named by its model, such as Fable
    @qml_property("QVariantList", notify=usageChanged)
    def modelLimits(self) -> list[dict[str, Any]]:
        return self._limits["models"]

    # Every limit above in order: 5-hour, 7-day, then each model's
    @qml_property("QVariantList", notify=usageChanged)
    def limits(self) -> list[dict[str, Any]]:
        return self._limits["all"]

    # The label placeholders as text: five_hour, seven_day, five_hour_reset, seven_day_reset, session_tokens,
    # today_tokens, week_tokens, month_tokens, year_tokens and status_text
    @qml_property("QVariantMap", notify=usageChanged)
    def values(self) -> dict[str, str]:
        return self._values

    # Tokens by period while tokenHistory is on: {sessionId, periods: {session, today, week, month, year}}, a period
    # being {total, kinds, series, start, step, models}; see history.summarize. Empty before the first scan
    @qml_property("QVariantMap", notify=historyChanged)
    def history(self) -> dict[str, Any]:
        return self._history

    @qml_property(bool, notify=historyChanged)
    def scanning(self) -> bool:
        return self._history_state[0]

    # When the logs were last scanned; invalid before the first scan
    @qml_property(QDateTime, notify=historyChanged)
    def scanned(self) -> QDateTime:
        return QDateTime.fromMSecsSinceEpoch(self._history_state[1]) if self._history_state[1] else QDateTime()

    # Claude's status while checkStatus is on: {indicator, description, error}, indicator none, minor, major,
    # critical or unknown, and description as the page words it, such as "All Systems Operational"
    @qml_property("QVariantMap", notify=statusChanged)
    def status(self) -> dict[str, Any]:
        return self._status

    def _join(self) -> None:
        settings = self._settings
        self._usage_feed = self._swap(self._usage_feed, UsageFeed, settings["updateInterval"])
        # Whether Claude Code is signed in is known now, and a widget can turn the other feeds on or off by it
        self._publish()
        self._history_feed = self._swap(
            self._history_feed, HistoryFeed, settings["scanInterval"] if settings["tokenHistory"] else None
        )
        self._status_feed = self._swap(
            self._status_feed, StatusFeed, settings["statusInterval"] if settings["checkStatus"] else None
        )
        self._publish()

    def _swap[F: Feed[int]](self, feed: F | None, kind: type[F], key: int | None) -> F | None:
        """The feed for key, leaving the one joined before when it is another; None leaves it without a new one."""
        if feed is not None and feed.key == key:
            return feed
        if feed is not None:
            feed.changed.disconnect(self._publish)
            feed.leave(self)
        if key is None:
            return None
        feed = kind.join(key, self)
        feed.changed.connect(self._publish)
        return feed

    def _limit(self, limit: dict[str, Any] | None, now: int) -> dict[str, Any]:
        if limit is None:
            return {}
        percent = limit["percent"]
        value = int(percent + 0.5)
        resets = limit["resetsAt"]
        return {
            "name": limit["name"],
            "percent": percent,
            "value": value,
            "level": "low" if value < 50 else "medium" if value < 80 else "high",
            "resetsAt": QDateTime.fromMSecsSinceEpoch(resets) if resets else QDateTime(),
            "resetIn": self._countdown(resets - now) if resets else "",
            "resetOn": self._clock(resets) if resets else "",
        }

    @staticmethod
    def _countdown(ms: int) -> str:
        minutes = max(0, ms) // 60000
        days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
        if days:
            return f"{days}d {hours}h"
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"

    def _clock(self, ms: int) -> str:
        pattern = "ddd h:mm AP" if self._settings["timeFormat"] == "12h" else "ddd HH:mm"
        return QLocale().toString(QDateTime.fromMSecsSinceEpoch(ms), pattern)

    def _publish(self) -> None:
        now = now_ms()
        usage_feed, history_feed, status_feed = self._usage_feed, self._history_feed, self._status_feed
        usage = usage_feed.usage if usage_feed is not None else None
        five = self._limit(usage["fiveHour"] if usage else None, now)
        seven = self._limit(usage["sevenDay"] if usage else None, now)
        models = [self._limit(model, now) for model in usage["models"]] if usage else []
        limits = {
            "fiveHour": five,
            "sevenDay": seven,
            "models": models,
            "all": [lim for lim in (five, seven, *models) if lim],
            "fetched": usage is not None,
        }

        history: dict[str, Any] = {}
        if history_feed is not None and history_feed.history is not None:
            try:
                history = logs.summarize(
                    history_feed.history, self._settings["countCacheRead"], self._settings["weekStartsOn"]
                )
            except AttributeError, IndexError, KeyError, TypeError, ValueError:
                logging.exception("Could not read the Claude token history")
        status: dict[str, Any] = dict(UNKNOWN_STATUS, error="")
        if status_feed is not None:
            status = {**status_feed.status, "error": status_feed.error}

        def reset(limit: dict[str, Any]) -> str:
            # A countdown within a day, the day and time after that
            if not limit or not limit["resetIn"]:
                return "--"
            return limit["resetIn"] if limit["resetsAt"].toMSecsSinceEpoch() - now < 86400000 else limit["resetOn"]

        periods = history.get("periods", {})
        values = {
            "five_hour": str(five["value"]) if five else "--",
            "seven_day": str(seven["value"]) if seven else "--",
            "five_hour_reset": reset(five),
            "seven_day_reset": reset(seven),
            **{f"{name}_tokens": logs.compact(periods[name]["total"]) if periods else "--" for name in logs.PERIODS},
            "status_text": status["description"],
        }
        if (limits, values) != (self._limits, self._values):
            self._limits, self._values = limits, values
            self.usageChanged.emit()

        history_state = (
            history_feed is not None and history_feed.loading,
            history_feed.scanned_at if history_feed is not None else 0,
        )
        if (history, history_state) != (self._history, self._history_state):
            self._history, self._history_state = history, history_state
            self.historyChanged.emit()
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

        state = (False, False, False, "", 0)
        if usage_feed is not None:
            expires = usage_feed.expires_at
            state = (
                usage_feed.signed_in,
                usage_feed.signed_in and 0 < expires < now,
                usage_feed.loading,
                usage_feed.error,
                usage_feed.fetched_at if usage else 0,
            )
        if state != self._state:
            self._state = state
            self.stateChanged.emit()

    # Fetches the usage and the status again now, and scans the logs again, whatever the intervals; the usage is not
    # asked for again while a fetch is under way
    @pyqtSlot()
    def refresh(self) -> None:
        for feed in (self._usage_feed, self._history_feed, self._status_feed):
            if feed is not None and not feed.loading:
                feed.fetch()

"""Local DeepSeek spend history, derived from balance snapshots.

DeepSeek's platform API exposes a balance (``GET /user/balance``) but no usage or
billing history, so there is nothing to scan the way Claude Code's transcripts are
scanned. What it does give us is an exact number that only ever moves down as the
API is used: differencing consecutive balance snapshots yields real spend, with no
pricing table and no token estimation involved.

Two limits are inherent to that approach and are documented rather than papered over:

* A top-up between two polls masks the spend that preceded it (spend 2, top up 100,
  and the net movement reads as +98). Unrecoverable without a usage endpoint.
* Granted credit is drawn down *before* topped-up credit, so a granted balance
  falling looks identical to a granted balance expiring. Rather than guess between
  them, ``count_granted`` decides: the default counts every drop as spend, while
  ``count_granted=False`` tracks only money actually paid and is immune to expiry
  by construction.

Everything here is pure and Qt-free: amounts are ``Decimal`` end to end (the API
returns decimal strings, and money must not round-trip through float), and ``now``
is injectable so period boundaries are testable.
"""

import json
import logging
import math
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from core.utils.system import app_data_path

logger = logging.getLogger("deepseek_usage")

CACHE_VERSION = 1
# Retention caps applied after every recorded snapshot so the ledger stays bounded.
# Hourly only feeds the Today graph; daily feeds everything up to the Year view.
HOURLY_RETENTION_DAYS = 15
DAILY_RETENTION_DAYS = 400

_DAY_FORMAT = "%Y-%m-%d"
_HOUR_FORMAT = "%Y-%m-%dT%H"


def empty_ledger() -> dict[str, Any]:
    """A ledger with no recorded history."""
    return {"version": CACHE_VERSION, "currency": "", "last": None, "daily": {}, "hourly": {}}


def parse_amount(value: Any) -> Decimal:
    """Coerce an API amount to Decimal, treating anything unusable as zero.

    Balances arrive as decimal strings. A missing key, a blank string, a non-finite
    float or outright junk must never raise here: a parsing quirk should read as
    'no money moved', never as a crash or a phantom charge.
    """
    if isinstance(value, bool):
        return Decimal(0)
    if isinstance(value, Decimal):
        return value if value.is_finite() else Decimal(0)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value)) if math.isfinite(value) else Decimal(0)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return Decimal(0)
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return Decimal(0)
        return parsed if parsed.is_finite() else Decimal(0)
    return Decimal(0)


def compute_spend(previous: Any, current: Any, *, count_granted: bool = True) -> Decimal:
    """Spend between two consecutive balance snapshots.

    Only downward movement counts, so a top-up never registers as negative spend.
    Snapshots in different currencies are not differenced at all, since subtracting
    a USD balance from a CNY one produces a number that means nothing.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return Decimal(0)
    if (previous.get("currency") or "") != (current.get("currency") or ""):
        return Decimal(0)

    field = "total" if count_granted else "topped_up"
    delta = parse_amount(previous.get(field)) - parse_amount(current.get(field))
    return delta if delta > 0 else Decimal(0)


def record_snapshot(ledger: dict[str, Any], snapshot: dict[str, Any], *, count_granted: bool = True) -> Decimal:
    """Fold one balance snapshot into the ledger and return the spend it recorded.

    The spend is attributed to the local day and hour of the *current* snapshot: it
    accumulated at some point across the poll interval, and the closing edge is the
    only instant we can actually name.
    """
    spend = compute_spend(ledger.get("last"), snapshot, count_granted=count_granted)

    if spend > 0:
        moment = _snapshot_moment(snapshot)
        day_key = moment.strftime(_DAY_FORMAT)
        hour_key = moment.strftime(_HOUR_FORMAT)
        daily = ledger.setdefault("daily", {})
        hourly = ledger.setdefault("hourly", {})
        daily[day_key] = str(parse_amount(daily.get(day_key)) + spend)
        hourly[hour_key] = str(parse_amount(hourly.get(hour_key)) + spend)

    ledger["last"] = dict(snapshot)
    currency = snapshot.get("currency")
    if currency:
        ledger["currency"] = currency
    return spend


def trim(ledger: dict[str, Any], now: datetime | None = None) -> None:
    """Drop buckets past their retention window, and any key that no longer parses."""
    now = now or datetime.now().astimezone()
    day_cutoff = (now - timedelta(days=DAILY_RETENTION_DAYS)).date()
    hour_cutoff = (now - timedelta(days=HOURLY_RETENTION_DAYS)).strftime(_HOUR_FORMAT)

    ledger["daily"] = {
        key: value
        for key, value in (ledger.get("daily") or {}).items()
        if (parsed := _parse_day(key)) is not None and parsed >= day_cutoff
    }
    # Hour keys are zero-padded and big-endian, so lexical order is chronological order.
    ledger["hourly"] = {
        key: value
        for key, value in (ledger.get("hourly") or {}).items()
        if _parse_hour(key) is not None and key >= hour_cutoff
    }


def summarize(
    ledger: dict[str, Any],
    *,
    week_starts_on: str = "monday",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive Today/Week/Month/Year spend totals and a per-period graph series.

    Periods are calendar-anchored, matching the Claude widget's token history: Today
    starts at local midnight, Week at the configured weekday, Month on the 1st and
    Year on Jan 1. Each series matches its window - Today is hourly, Week and Month
    are daily, and Year is monthly.
    """
    now = now or datetime.now().astimezone()
    daily = ledger.get("daily") or {}
    hourly = ledger.get("hourly") or {}

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = now.weekday()  # Mon=0
    back = (weekday + 1) % 7 if week_starts_on == "sunday" else weekday
    week_start = today_start - timedelta(days=back)
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    def window_total(start: datetime) -> Decimal:
        return sum((parse_amount(daily.get(key)) for key in _date_keys_in_range(start, now)), Decimal(0))

    series_by_period = {
        "today": [float(parse_amount(hourly.get(key))) for key in _hour_keys_in_range(today_start, now)],
        "week": [float(parse_amount(daily.get(key))) for key in _date_keys_in_range(week_start, now)],
        "month": [float(parse_amount(daily.get(key))) for key in _date_keys_in_range(month_start, now)],
        "year": [float(_sum_month(daily, key)) for key in _month_keys_in_range(year_start, now)],
    }

    return {
        "totals": {
            "today": window_total(today_start),
            "week": window_total(week_start),
            "month": window_total(month_start),
            "year": window_total(year_start),
        },
        "series_by_period": series_by_period,
        "currency": ledger.get("currency") or "",
    }


def budget_percent(spend: Any, budget: Any) -> float | None:
    """Spend as a percentage of budget, or None when no usable budget is set.

    Deliberately uncapped: overspending should read as 120%, not as a silent 100%.
    Callers clamp the bar fill; the number itself stays honest.
    """
    amount = parse_amount(budget)
    if amount <= 0:
        return None
    return float(parse_amount(spend) / amount * 100)


def ledger_path() -> str:
    return str(app_data_path("deepseek_spend_history.json"))


def load_ledger(path: str) -> dict[str, Any]:
    """Read the ledger, falling back to an empty one on any problem or version bump."""
    try:
        with open(path, encoding="utf-8") as ledger_file:
            data = json.load(ledger_file)
    except OSError, ValueError:
        return empty_ledger()

    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return empty_ledger()

    ledger = empty_ledger()
    ledger["currency"] = data.get("currency") or ""
    ledger["last"] = data.get("last") if isinstance(data.get("last"), dict) else None
    ledger["daily"] = data.get("daily") if isinstance(data.get("daily"), dict) else {}
    ledger["hourly"] = data.get("hourly") if isinstance(data.get("hourly"), dict) else {}
    return ledger


def save_ledger(path: str, ledger: dict[str, Any]) -> None:
    """Persist the ledger atomically, so a crash mid-write cannot truncate history."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary_path = f"{path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as ledger_file:
            json.dump(ledger, ledger_file)
        os.replace(temporary_path, path)
    except OSError as error:
        logger.debug("failed to write DeepSeek spend history: %s", error)


def _snapshot_moment(snapshot: dict[str, Any]) -> datetime:
    try:
        timestamp = int(snapshot.get("ts") or 0)
    except TypeError, ValueError:
        timestamp = 0
    if timestamp <= 0:
        return datetime.now().astimezone()
    return datetime.fromtimestamp(timestamp).astimezone()


def _parse_day(key: Any) -> date | None:
    if not isinstance(key, str):
        return None
    try:
        return datetime.strptime(key, _DAY_FORMAT).date()
    except ValueError:
        return None


def _parse_hour(key: Any) -> datetime | None:
    if not isinstance(key, str):
        return None
    try:
        return datetime.strptime(key, _HOUR_FORMAT)
    except ValueError:
        return None


def _date_keys_in_range(start: datetime, end: datetime) -> list[str]:
    """Local YYYY-MM-DD keys from start's day through end's day, inclusive."""
    keys = []
    current = start.date()
    last = end.date()
    while current <= last:
        keys.append(current.strftime(_DAY_FORMAT))
        current += timedelta(days=1)
    return keys


def _hour_keys_in_range(start: datetime, end: datetime) -> list[str]:
    """Local YYYY-MM-DDTHH keys from start's hour through end's hour, inclusive."""
    keys = []
    current = start.replace(minute=0, second=0, microsecond=0)
    last = end.replace(minute=0, second=0, microsecond=0)
    while current <= last:
        keys.append(current.strftime(_HOUR_FORMAT))
        current += timedelta(hours=1)
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


def _sum_month(daily: dict[str, Any], month_key: str) -> Decimal:
    prefix = f"{month_key}-"
    return sum(
        (parse_amount(value) for key, value in daily.items() if key.startswith(prefix)),
        Decimal(0),
    )

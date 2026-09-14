"""Pure (Qt-free) helpers for turning an Aladhan API payload into local datetimes.

The Aladhan API returns bare ``HH:MM`` strings expressed in the *location's*
timezone, not the machine's.  It also returns a few entries (``Midnight``,
``Lastthird``) that belong to the following calendar day.  Everything in this
module exists to resolve those two ambiguities before any comparison against
``datetime.now()`` happens.

Kept free of Qt imports so the logic can be unit tested without a QApplication.
"""

import logging
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Canonical ordering as returned by the Aladhan API.  Times are monotonically
# increasing in this order, wrapping past midnight for the trailing entries.
ALL_PRAYER_NAMES: list[str] = [
    "Imsak",
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Sunset",
    "Maghrib",
    "Isha",
    "Firstthird",
    "Midnight",
    "Lastthird",
]

_MISSING_TIME = "--:--"
_HHMM_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})")
_GREGORIAN_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")

# The solar moments the day ribbon's light is built from.  Requested separately from
# the prayers on show, because the day is lit the same whether or not you list Sunrise.
SOLAR_NAMES: list[str] = ["Fajr", "Sunrise", "Sunset", "Maghrib", "Isha"]

# Roles a ribbon gradient stop can carry.  Declared here, in the Qt-free module, so
# the painter imports the vocabulary rather than the other way round.
NIGHT = "night"
DAWN = "dawn"
DAY = "day"
DUSK = "dusk"


@dataclass(frozen=True)
class PrayerTime:
    """A single prayer resolved to an absolute moment in the machine's local timezone."""

    name: str
    time_str: str  # "HH:MM" exactly as returned by the API, for display
    at: datetime  # timezone-aware, converted to local time


def parse_hhmm(time_str: str) -> tuple[int, int] | None:
    """Parse a 'HH:MM' string, returning (hour, minute) or None if unusable."""
    if not time_str or time_str == _MISSING_TIME:
        return None
    match = _HHMM_RE.match(time_str)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def parse_gregorian_date(date_str: str | None) -> date | None:
    """Parse Aladhan's 'DD-MM-YYYY' gregorian date, returning None if unusable."""
    if not date_str:
        return None
    match = _GREGORIAN_RE.match(date_str)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def resolve_timezone(tz_name: str | None) -> ZoneInfo | None:
    """Return a ZoneInfo for an IANA name, or None to fall back to local wall-clock time."""
    if not tz_name:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logging.warning("Prayer times: unknown timezone %r from API, falling back to local time.", tz_name)
        return None


def build_schedule(
    timings: dict[str, str],
    base_date: date,
    tz_name: str | None,
    names: list[str],
) -> list[PrayerTime]:
    """Resolve raw API timings into local, absolute, chronologically sorted PrayerTimes.

    Times are anchored to *base_date* in the API's timezone, then converted to the
    machine's local timezone.  Entries whose time-of-day goes backwards relative to
    the previous canonical entry (``Midnight`` at 00:00, ``Lastthird`` at 02:02, ...)
    are rolled onto the following day so they compare correctly against ``now``.

    Args:
        timings: The ``data.timings`` mapping from the API response.
        base_date: The gregorian date the timings were requested for.
        tz_name: IANA timezone from ``data.meta.timezone``, or None for local time.
        names: The prayers to return, in any order.

    Returns:
        Chronologically sorted PrayerTime entries for the requested *names* that
        had a parseable time.
    """
    tzinfo = resolve_timezone(tz_name)
    wanted = set(names)
    resolved: list[PrayerTime] = []

    day_offset = 0
    previous: tuple[int, int] | None = None

    # Walk the full canonical list (not just the requested subset) so the
    # midnight wrap is detected from the API's own ordering.
    for name in ALL_PRAYER_NAMES:
        time_str = timings.get(name, "")
        parsed = parse_hhmm(time_str)
        if parsed is None:
            continue
        if previous is not None and parsed < previous:
            day_offset += 1
        previous = parsed

        if name not in wanted:
            continue

        hour, minute = parsed
        day = base_date + timedelta(days=day_offset)
        moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tzinfo)
        # astimezone() converts an aware datetime; a naive one is assumed to be local.
        resolved.append(PrayerTime(name=name, time_str=time_str, at=moment.astimezone()))

    resolved.sort(key=lambda entry: entry.at)
    return resolved


def _format_remaining(seconds: float) -> str:
    """Format a non-negative number of seconds as 'in 1h 03m' or 'in 42m'."""
    hours, mins = divmod(int(seconds // 60), 60)
    if hours > 0:
        return f"in {hours}h {mins:02d}m"
    return f"in {mins}m"


def format_delta(entry_at: datetime, now: datetime, grace: timedelta, passed_text: str) -> str:
    """Return a human-readable remaining/elapsed label for a prayer moment."""
    delta = entry_at - now
    if delta.total_seconds() < 0:
        if abs(delta) < grace:
            elapsed_min = int(abs(delta).total_seconds() // 60)
            return f"{elapsed_min}m ago"
        return passed_text
    return _format_remaining(delta.total_seconds())


def format_countdown(entry_at: datetime, now: datetime) -> str:
    """Return the hero countdown: 'in 1h 03m' before a prayer, 'started 5m ago' once it has begun."""
    seconds = (entry_at - now).total_seconds()
    if abs(seconds) < 60:
        return "now"
    if seconds < 0:
        return f"started {int(-seconds // 60)}m ago"
    return _format_remaining(seconds)


def shift_days(entry: PrayerTime, days: int) -> PrayerTime:
    """Return *entry* moved by whole days, keeping its name and displayed time.

    Prayer times drift by a minute or two between days, which is close enough for a
    countdown that is about to be replaced by the real schedule for that day.
    """
    return replace(entry, at=entry.at + timedelta(days=days))


def previous_entry(schedule: list[PrayerTime], current: PrayerTime) -> PrayerTime:
    """Return the prayer before *current* in a chronological schedule.

    Before the first prayer the span starts at the previous night's last prayer, which a
    single day's schedule does not hold, so the last entry is shifted back one day.

    *current* may be an entry ``shift_days`` has moved off the schedule, which is what the
    widget hands over once every prayer in the day has passed. It is matched by name and
    the same shift is carried onto the entry that comes back, so the span stays the real
    one: last night's Isha through to tomorrow morning's first prayer.
    """
    index = next((i for i, entry in enumerate(schedule) if entry.name == current.name), 0)
    shift = current.at - schedule[index].at
    if index > 0:
        previous = schedule[index - 1]
        return replace(previous, at=previous.at + shift)
    last = schedule[-1]
    return replace(last, at=last.at + shift - timedelta(days=1))


def progress_fraction(start: datetime, end: datetime, now: datetime) -> float:
    """Return how much of the start-to-end span has elapsed at *now*, clamped to 0..1."""
    span = (end - start).total_seconds()
    if span <= 0:
        return 1.0
    return min(max((now - start).total_seconds() / span, 0.0), 1.0)


def format_span(start: datetime, end: datetime) -> str:
    """Format the distance between two moments as '13h 48m', or '' if they are out of order."""
    minutes = int((end - start).total_seconds() // 60)
    if minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


def day_window(base_date: date, tz_name: str | None, schedule: list[PrayerTime]) -> tuple[datetime, datetime]:
    """Return the ribbon's window: *base_date*'s own midnight to midnight, in local time.

    Anchored in the API's timezone rather than the machine's, so a schedule calculated for
    another city still starts its band at that city's midnight. Entries that roll past the
    end (``Midnight``, ``Lastthird``) stretch it rather than falling off the edge.
    """
    tzinfo = resolve_timezone(tz_name)
    start = datetime(base_date.year, base_date.month, base_date.day, tzinfo=tzinfo).astimezone()
    end = start + timedelta(days=1)
    if schedule:
        end = max(end, schedule[-1].at)
    return start, end


def light_stops(solar: dict[str, PrayerTime], start: datetime, end: datetime) -> list[tuple[float, str]]:
    """Return the ribbon's gradient stops as (fraction, role) across the *start*-to-*end* window.

    Night holds until Fajr, warms through dawn to full daylight by sunrise, holds flat all
    day, warms again at sunset and is back to night by Isha. Every boundary is a moment the
    API returned, so the band's proportions belong to this location and this date; nothing
    here is a nominal dawn or a stock golden hour.

    Missing moments only cost their own transition: without Sunrise there is no dawn wash,
    and with nothing at all the band is flat night rather than an invented day.
    """
    span = (end - start).total_seconds()
    if span <= 0:
        return []

    def fraction(moment: datetime) -> float:
        return min(max((moment - start).total_seconds() / span, 0.0), 1.0)

    fajr = solar.get("Fajr")
    sunrise = solar.get("Sunrise")
    sunset = solar.get("Sunset") or solar.get("Maghrib")
    isha = solar.get("Isha")

    stops: list[tuple[float, str]] = [(0.0, NIGHT)]
    if sunrise is not None:
        if fajr is not None:
            # First light at Fajr, peaking midway to sunrise: the wash is as wide as
            # this latitude's twilight actually is.
            stops.append((fraction(fajr.at), NIGHT))
            stops.append(((fraction(fajr.at) + fraction(sunrise.at)) / 2, DAWN))
        stops.append((fraction(sunrise.at), DAY))
    if sunset is not None:
        if sunrise is not None:
            stops.append((fraction(sunset.at), DAY))
        if isha is not None and isha.at > sunset.at:
            stops.append(((fraction(sunset.at) + fraction(isha.at)) / 2, DUSK))
            stops.append((fraction(isha.at), NIGHT))
        else:
            stops.append((fraction(sunset.at), DUSK))
    stops.append((1.0, NIGHT))

    # Qt reads stops in the order given; a clock that disagrees with the canonical
    # ordering must not be allowed to fold the gradient back on itself.
    stops.sort(key=lambda stop: stop[0])
    return stops

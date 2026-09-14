"""Tests for the Qt-free prayer times schedule helpers.

Timings below are real Aladhan API responses for 2026-07-21.
"""

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from core.utils.widgets.prayer_times.schedule import (  # noqa: E402
    DAWN,
    DAY,
    DUSK,
    NIGHT,
    SOLAR_NAMES,
    build_schedule,
    day_window,
    format_countdown,
    format_delta,
    format_span,
    light_stops,
    parse_gregorian_date,
    parse_hhmm,
    previous_entry,
    progress_fraction,
    shift_days,
)

JAKARTA_TIMINGS = {
    "Fajr": "04:44",
    "Sunrise": "06:06",
    "Dhuhr": "12:00",
    "Asr": "15:22",
    "Sunset": "17:54",
    "Maghrib": "17:54",
    "Isha": "19:08",
    "Imsak": "04:34",
    "Midnight": "00:00",
    "Firstthird": "21:58",
    "Lastthird": "02:02",
}

LONDON_TIMINGS = {
    "Fajr": "03:08",
    "Sunrise": "05:09",
    "Dhuhr": "13:07",
    "Asr": "17:23",
    "Sunset": "21:05",
    "Maghrib": "21:05",
    "Isha": "23:06",
    "Imsak": "02:58",
    "Midnight": "01:07",
    "Firstthird": "23:46",
    "Lastthird": "02:27",
}

BASE_DATE = date(2026, 7, 21)
JAKARTA = ZoneInfo("Asia/Jakarta")
LONDON = ZoneInfo("Europe/London")
FIVE_PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


class ParseHhmmTest(unittest.TestCase):
    def test_parses_valid_time(self) -> None:
        self.assertEqual(parse_hhmm("04:44"), (4, 44))
        self.assertEqual(parse_hhmm("00:00"), (0, 0))
        self.assertEqual(parse_hhmm("23:59"), (23, 59))

    def test_tolerates_trailing_timezone_suffix(self) -> None:
        # Some Aladhan configurations append the zone, e.g. "05:04 (BST)".
        self.assertEqual(parse_hhmm("05:04 (BST)"), (5, 4))

    def test_rejects_unusable_values(self) -> None:
        for value in ("", "--:--", "nonsense", "25:00", "12:99", "1234"):
            with self.subTest(value=value):
                self.assertIsNone(parse_hhmm(value))


class ParseGregorianDateTest(unittest.TestCase):
    def test_parses_api_format(self) -> None:
        self.assertEqual(parse_gregorian_date("21-07-2026"), date(2026, 7, 21))

    def test_rejects_unusable_values(self) -> None:
        for value in (None, "", "2026-07-21", "32-07-2026", "garbage"):
            with self.subTest(value=value):
                self.assertIsNone(parse_gregorian_date(value))


class BuildScheduleTest(unittest.TestCase):
    def test_resolves_times_in_api_timezone(self) -> None:
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", ["Fajr"])

        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0].name, "Fajr")
        self.assertEqual(schedule[0].time_str, "04:44")
        # Aware datetimes compare as absolute instants, so this holds regardless
        # of the timezone the test machine happens to be in.
        self.assertEqual(schedule[0].at, datetime(2026, 7, 21, 4, 44, tzinfo=JAKARTA))

    def test_ignores_machine_timezone(self) -> None:
        """The same payload must resolve to the same instant whatever the API zone says."""
        jakarta = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", ["Dhuhr"])[0]
        london = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Europe/London", ["Dhuhr"])[0]

        # Identical wall-clock string, different zones => different instants.
        self.assertEqual(jakarta.time_str, london.time_str)
        self.assertNotEqual(jakarta.at, london.at)
        self.assertEqual(jakarta.at, datetime(2026, 7, 21, 12, 0, tzinfo=JAKARTA))
        self.assertEqual(london.at, datetime(2026, 7, 21, 12, 0, tzinfo=LONDON))

    def test_midnight_rolls_onto_the_next_day(self) -> None:
        """Midnight 00:00 belongs to the night *after* base_date, not its start."""
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", ["Isha", "Midnight"])
        by_name = {entry.name: entry for entry in schedule}

        self.assertEqual(by_name["Isha"].at, datetime(2026, 7, 21, 19, 8, tzinfo=JAKARTA))
        self.assertEqual(by_name["Midnight"].at, datetime(2026, 7, 22, 0, 0, tzinfo=JAKARTA))
        self.assertGreater(by_name["Midnight"].at, by_name["Isha"].at)

    def test_lastthird_stays_with_midnight_on_the_next_day(self) -> None:
        schedule = build_schedule(LONDON_TIMINGS, BASE_DATE, "Europe/London", ["Midnight", "Lastthird"])
        by_name = {entry.name: entry for entry in schedule}

        self.assertEqual(by_name["Midnight"].at, datetime(2026, 7, 22, 1, 7, tzinfo=LONDON))
        self.assertEqual(by_name["Lastthird"].at, datetime(2026, 7, 22, 2, 27, tzinfo=LONDON))

    def test_equal_sunset_and_maghrib_do_not_trigger_a_wrap(self) -> None:
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", ["Sunset", "Maghrib", "Isha"])
        by_name = {entry.name: entry for entry in schedule}

        self.assertEqual(by_name["Sunset"].at, by_name["Maghrib"].at)
        self.assertEqual(by_name["Isha"].at, datetime(2026, 7, 21, 19, 8, tzinfo=JAKARTA))

    def test_output_is_chronological_regardless_of_input_order(self) -> None:
        shuffled = ["Isha", "Fajr", "Maghrib", "Asr", "Dhuhr"]
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", shuffled)

        self.assertEqual([entry.name for entry in schedule], FIVE_PRAYERS)
        self.assertEqual(schedule, sorted(schedule, key=lambda entry: entry.at))

    def test_skips_unknown_and_unparseable_names(self) -> None:
        timings = dict(JAKARTA_TIMINGS, Asr="--:--")
        schedule = build_schedule(timings, BASE_DATE, "Asia/Jakarta", ["Fajr", "Asr", "Nonexistent"])

        self.assertEqual([entry.name for entry in schedule], ["Fajr"])

    def test_unknown_timezone_falls_back_to_local(self) -> None:
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Not/AZone", ["Fajr"])

        self.assertEqual(len(schedule), 1)
        # Naive local interpretation of 04:44 on the base date.
        self.assertEqual(schedule[0].at, datetime(2026, 7, 21, 4, 44).astimezone())

    def test_empty_timings_yields_empty_schedule(self) -> None:
        self.assertEqual(build_schedule({}, BASE_DATE, "Asia/Jakarta", FIVE_PRAYERS), [])


class FormatDeltaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 12, 0, tzinfo=JAKARTA)
        self.grace = timedelta(minutes=15)

    def test_future_within_the_hour(self) -> None:
        target = self.now + timedelta(minutes=42)
        self.assertEqual(format_delta(target, self.now, self.grace, "passed"), "in 42m")

    def test_future_beyond_an_hour(self) -> None:
        target = self.now + timedelta(hours=3, minutes=5)
        self.assertEqual(format_delta(target, self.now, self.grace, "passed"), "in 3h 05m")

    def test_inside_grace_window_shows_elapsed(self) -> None:
        target = self.now - timedelta(minutes=5)
        self.assertEqual(format_delta(target, self.now, self.grace, "passed"), "5m ago")

    def test_beyond_grace_window_is_passed(self) -> None:
        target = self.now - timedelta(minutes=20)
        self.assertEqual(format_delta(target, self.now, self.grace, "passed"), "passed")


class PreviousEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", FIVE_PRAYERS)
        self.by_name = {entry.name: entry for entry in self.schedule}

    def test_returns_the_prayer_before(self) -> None:
        self.assertEqual(previous_entry(self.schedule, self.by_name["Asr"]), self.by_name["Dhuhr"])

    def test_before_the_first_prayer_uses_the_last_one_a_day_earlier(self) -> None:
        """Before Fajr the span starts at the previous night's Isha, which the schedule does not hold."""
        isha = self.by_name["Isha"]

        previous = previous_entry(self.schedule, self.by_name["Fajr"])

        self.assertEqual(previous.name, "Isha")
        self.assertEqual(previous.time_str, isha.time_str)
        self.assertEqual(previous.at, isha.at - timedelta(days=1))

    def test_single_prayer_schedule_uses_itself_a_day_earlier(self) -> None:
        only = self.schedule[:1]

        self.assertEqual(previous_entry(only, only[0]).at, only[0].at - timedelta(days=1))


class ProgressFractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 7, 21, 12, 0, tzinfo=JAKARTA)
        self.end = datetime(2026, 7, 21, 15, 0, tzinfo=JAKARTA)

    def test_midway_is_half(self) -> None:
        now = datetime(2026, 7, 21, 13, 30, tzinfo=JAKARTA)
        self.assertAlmostEqual(progress_fraction(self.start, self.end, now), 0.5)

    def test_clamps_to_empty_before_the_span(self) -> None:
        now = self.start - timedelta(minutes=1)
        self.assertEqual(progress_fraction(self.start, self.end, now), 0.0)

    def test_stays_full_after_the_span(self) -> None:
        """Inside the grace window the prayer has arrived, so the bar reads full."""
        now = self.end + timedelta(minutes=5)
        self.assertEqual(progress_fraction(self.start, self.end, now), 1.0)

    def test_empty_span_reads_full(self) -> None:
        self.assertEqual(progress_fraction(self.end, self.end, self.start), 1.0)


class FormatCountdownTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 12, 0, tzinfo=JAKARTA)

    def test_future_within_the_hour(self) -> None:
        self.assertEqual(format_countdown(self.now + timedelta(minutes=42), self.now), "in 42m")

    def test_future_beyond_an_hour(self) -> None:
        self.assertEqual(format_countdown(self.now + timedelta(hours=1, minutes=3), self.now), "in 1h 03m")

    def test_started_prayer_shows_elapsed_minutes(self) -> None:
        self.assertEqual(format_countdown(self.now - timedelta(minutes=5), self.now), "started 5m ago")

    def test_within_a_minute_either_side_reads_now(self) -> None:
        for offset in (timedelta(seconds=30), timedelta(seconds=-30), timedelta(0)):
            with self.subTest(offset=offset):
                self.assertEqual(format_countdown(self.now + offset, self.now), "now")


class ShiftDaysTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", FIVE_PRAYERS)

    def test_keeps_the_name_and_the_displayed_time(self) -> None:
        first = self.schedule[0]

        rolled = shift_days(first, 1)

        self.assertEqual(rolled.name, first.name)
        self.assertEqual(rolled.time_str, first.time_str)
        self.assertEqual(rolled.at, first.at + timedelta(days=1))

    def test_previous_entry_carries_the_shift(self) -> None:
        """Once the whole day has passed the span is last night's Isha to tomorrow's Fajr."""
        first, isha = self.schedule[0], self.schedule[-1]

        previous = previous_entry(self.schedule, shift_days(first, 1))

        self.assertEqual(previous.name, "Isha")
        self.assertEqual(previous.at, isha.at)


class FormatSpanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 7, 21, 6, 6, tzinfo=JAKARTA)

    def test_hours_and_padded_minutes(self) -> None:
        self.assertEqual(format_span(self.start, self.start + timedelta(hours=11, minutes=48)), "11h 48m")

    def test_under_an_hour_drops_the_hours(self) -> None:
        self.assertEqual(format_span(self.start, self.start + timedelta(minutes=42)), "42m")

    def test_out_of_order_is_empty_rather_than_negative(self) -> None:
        self.assertEqual(format_span(self.start, self.start - timedelta(hours=1)), "")


class DayWindowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", FIVE_PRAYERS)

    def test_starts_at_the_api_timezone_midnight(self) -> None:
        start, _ = day_window(BASE_DATE, "Asia/Jakarta", self.schedule)

        self.assertEqual(start, datetime(2026, 7, 21, 0, 0, tzinfo=JAKARTA))

    def test_spans_a_full_day(self) -> None:
        start, end = day_window(BASE_DATE, "Asia/Jakarta", self.schedule)

        self.assertEqual(end - start, timedelta(days=1))

    def test_stretches_for_entries_that_roll_past_midnight(self) -> None:
        """Lastthird falls at 02:02 the next morning; it must sit inside the band, not past its end."""
        schedule = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", ["Fajr", "Lastthird"])

        start, end = day_window(BASE_DATE, "Asia/Jakarta", schedule)

        self.assertEqual(end, schedule[-1].at)
        self.assertGreater(end - start, timedelta(days=1))


class LightStopsTest(unittest.TestCase):
    def setUp(self) -> None:
        solar = build_schedule(JAKARTA_TIMINGS, BASE_DATE, "Asia/Jakarta", SOLAR_NAMES)
        self.solar = {entry.name: entry for entry in solar}
        self.start, self.end = day_window(BASE_DATE, "Asia/Jakarta", solar)
        self.stops = light_stops(self.solar, self.start, self.end)

    def test_fractions_never_go_backwards(self) -> None:
        """Qt reads gradient stops in the order given, so a fold would paint the day inside out."""
        fractions = [fraction for fraction, _ in self.stops]

        self.assertEqual(fractions, sorted(fractions))

    def test_spans_the_whole_band(self) -> None:
        self.assertEqual(self.stops[0][0], 0.0)
        self.assertEqual(self.stops[-1][0], 1.0)

    def test_walks_night_dawn_day_dusk_night(self) -> None:
        """Night holds to Fajr, warms to full day by sunrise, holds, warms again at sunset, dark by Isha."""
        self.assertEqual(
            [role for _, role in self.stops],
            [NIGHT, NIGHT, DAWN, DAY, DAY, DUSK, NIGHT, NIGHT],
        )

    def test_daylight_is_lit_and_the_small_hours_are_not(self) -> None:
        by_role = {}
        for fraction, role in self.stops:
            by_role.setdefault(role, []).append(fraction)

        noon = (datetime(2026, 7, 21, 12, 0, tzinfo=JAKARTA) - self.start).total_seconds() / 86400
        self.assertLess(by_role[DAY][0], noon)
        self.assertGreater(by_role[DAY][1], noon)

    def test_a_response_without_sunrise_draws_no_dawn(self) -> None:
        """Missing moments cost their own transition; nothing is invented to fill the gap."""
        solar = {name: entry for name, entry in self.solar.items() if name != "Sunrise"}

        roles = [role for _, role in light_stops(solar, self.start, self.end)]

        self.assertNotIn(DAWN, roles)
        self.assertNotIn(DAY, roles)

    def test_an_empty_window_has_no_stops(self) -> None:
        self.assertEqual(light_stops(self.solar, self.start, self.start), [])


if __name__ == "__main__":
    unittest.main()

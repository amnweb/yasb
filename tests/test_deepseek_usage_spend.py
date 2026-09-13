"""Tests for the Qt-free DeepSeek spend-ledger helpers.

Balance figures below mirror real ``GET /user/balance`` responses, where every
amount is a decimal *string* (the API never returns floats, so neither do we).

Timestamps are built from local-time datetimes rather than fixed epoch numbers,
so the day/hour bucket keys these tests assert on hold on any machine timezone.
"""

import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from core.widgets.services.deepseek_usage.spend_history import (  # noqa: E402
    DAILY_RETENTION_DAYS,
    HOURLY_RETENTION_DAYS,
    budget_percent,
    compute_spend,
    empty_ledger,
    parse_amount,
    record_snapshot,
    summarize,
    trim,
)


def local(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    """A tz-aware local datetime, so derived bucket keys are machine-independent."""
    return datetime(year, month, day, hour, minute).astimezone()


def snapshot(total: str, granted: str, topped_up: str, when: datetime, currency: str = "CNY") -> dict:
    return {
        "ts": int(when.timestamp()),
        "total": total,
        "granted": granted,
        "topped_up": topped_up,
        "currency": currency,
    }


class ParseAmountTests(unittest.TestCase):
    def test_parses_decimal_strings_exactly(self):
        # 0.1 + 0.2 as floats would not equal 0.3; Decimal keeps money exact.
        self.assertEqual(parse_amount("0.1") + parse_amount("0.2"), Decimal("0.3"))

    def test_accepts_numeric_types(self):
        self.assertEqual(parse_amount(5), Decimal("5"))
        self.assertEqual(parse_amount(Decimal("2.50")), Decimal("2.50"))

    def test_junk_and_missing_values_are_zero(self):
        for value in (None, "", "  ", "abc", "1.2.3", [], {}, float("nan"), float("inf")):
            self.assertEqual(parse_amount(value), Decimal("0"), msg=repr(value))


class ComputeSpendTests(unittest.TestCase):
    def setUp(self):
        self.t0 = local(2026, 9, 13, 10)
        self.t1 = local(2026, 9, 13, 11)

    def test_normal_drop_is_spend(self):
        previous = snapshot("100.00", "0.00", "100.00", self.t0)
        current = snapshot("98.50", "0.00", "98.50", self.t1)
        self.assertEqual(compute_spend(previous, current), Decimal("1.50"))

    def test_no_movement_is_zero(self):
        previous = snapshot("84.20", "0.00", "84.20", self.t0)
        current = snapshot("84.20", "0.00", "84.20", self.t1)
        self.assertEqual(compute_spend(previous, current), Decimal("0"))

    def test_top_up_is_not_negative_spend(self):
        previous = snapshot("10.00", "0.00", "10.00", self.t0)
        current = snapshot("110.00", "0.00", "110.00", self.t1)
        self.assertEqual(compute_spend(previous, current), Decimal("0"))

    def test_missing_previous_snapshot_is_zero(self):
        current = snapshot("98.50", "0.00", "98.50", self.t1)
        self.assertEqual(compute_spend(None, current), Decimal("0"))

    def test_currency_change_is_not_differenced(self):
        # A CNY balance minus a USD balance is a meaningless number, not spend.
        previous = snapshot("100.00", "0.00", "100.00", self.t0, currency="CNY")
        current = snapshot("14.00", "0.00", "14.00", self.t1, currency="USD")
        self.assertEqual(compute_spend(previous, current), Decimal("0"))

    def test_malformed_amounts_are_zero(self):
        previous = snapshot("oops", "0.00", "0.00", self.t0)
        current = snapshot("98.50", "0.00", "98.50", self.t1)
        self.assertEqual(compute_spend(previous, current), Decimal("0"))

    def test_granted_spend_counts_by_default(self):
        # DeepSeek draws down granted credit first: total falls, topped_up does not move.
        previous = snapshot("84.20", "10.00", "74.20", self.t0)
        current = snapshot("83.20", "9.00", "74.20", self.t1)
        self.assertEqual(compute_spend(previous, current), Decimal("1.00"))

    def test_granted_spend_excluded_when_counting_paid_money_only(self):
        previous = snapshot("84.20", "10.00", "74.20", self.t0)
        current = snapshot("83.20", "9.00", "74.20", self.t1)
        self.assertEqual(compute_spend(previous, current, count_granted=False), Decimal("0"))

    def test_paid_spend_still_counts_when_excluding_granted(self):
        previous = snapshot("84.20", "10.00", "74.20", self.t0)
        current = snapshot("83.20", "10.00", "73.20", self.t1)
        self.assertEqual(compute_spend(previous, current, count_granted=False), Decimal("1.00"))

    def test_granted_expiry_is_immune_when_counting_paid_money_only(self):
        # The whole point of count_granted=False: an expiring grant is a balance
        # cliff with no usage behind it, and must not land in the budget.
        previous = snapshot("84.20", "10.00", "74.20", self.t0)
        current = snapshot("74.20", "0.00", "74.20", self.t1)
        self.assertEqual(compute_spend(previous, current, count_granted=True), Decimal("10.00"))
        self.assertEqual(compute_spend(previous, current, count_granted=False), Decimal("0"))


class RecordSnapshotTests(unittest.TestCase):
    def test_first_snapshot_records_no_spend(self):
        ledger = empty_ledger()
        when = local(2026, 9, 13, 14, 30)
        recorded = record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", when))
        self.assertEqual(recorded, Decimal("0"))
        self.assertEqual(ledger["daily"], {})
        self.assertEqual(ledger["hourly"], {})
        self.assertIsNotNone(ledger["last"])

    def test_spend_lands_in_local_day_and_hour_buckets(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 14, 0)))
        record_snapshot(ledger, snapshot("98.50", "0.00", "98.50", local(2026, 9, 13, 14, 30)))
        self.assertEqual(parse_amount(ledger["daily"]["2026-09-13"]), Decimal("1.50"))
        self.assertEqual(parse_amount(ledger["hourly"]["2026-09-13T14"]), Decimal("1.50"))

    def test_repeated_spend_accumulates_in_the_same_bucket(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 14, 0)))
        record_snapshot(ledger, snapshot("99.00", "0.00", "99.00", local(2026, 9, 13, 14, 20)))
        record_snapshot(ledger, snapshot("97.75", "0.00", "97.75", local(2026, 9, 13, 14, 40)))
        self.assertEqual(parse_amount(ledger["hourly"]["2026-09-13T14"]), Decimal("2.25"))
        self.assertEqual(parse_amount(ledger["daily"]["2026-09-13"]), Decimal("2.25"))

    def test_spend_splits_across_hours_and_days(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 23, 50)))
        record_snapshot(ledger, snapshot("99.00", "0.00", "99.00", local(2026, 9, 14, 0, 10)))
        self.assertNotIn("2026-09-13", ledger["daily"])
        self.assertEqual(parse_amount(ledger["daily"]["2026-09-14"]), Decimal("1.00"))
        self.assertEqual(parse_amount(ledger["hourly"]["2026-09-14T00"]), Decimal("1.00"))

    def test_zero_spend_creates_no_buckets(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 14, 0)))
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 15, 0)))
        self.assertEqual(ledger["daily"], {})
        self.assertEqual(ledger["hourly"], {})

    def test_last_snapshot_is_always_advanced(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("100.00", "0.00", "100.00", local(2026, 9, 13, 14, 0)))
        record_snapshot(ledger, snapshot("110.00", "0.00", "110.00", local(2026, 9, 13, 15, 0)))
        self.assertEqual(ledger["last"]["total"], "110.00")

    def test_currency_is_tracked_on_the_ledger(self):
        ledger = empty_ledger()
        record_snapshot(ledger, snapshot("10.00", "0.00", "10.00", local(2026, 9, 13), currency="USD"))
        self.assertEqual(ledger["currency"], "USD")


class TrimTests(unittest.TestCase):
    def test_drops_buckets_past_retention_and_keeps_recent_ones(self):
        now = local(2026, 9, 13, 12)
        ledger = empty_ledger()
        fresh_day = (now - timedelta(days=DAILY_RETENTION_DAYS - 1)).strftime("%Y-%m-%d")
        stale_day = (now - timedelta(days=DAILY_RETENTION_DAYS + 1)).strftime("%Y-%m-%d")
        fresh_hour = (now - timedelta(days=HOURLY_RETENTION_DAYS - 1)).strftime("%Y-%m-%dT%H")
        stale_hour = (now - timedelta(days=HOURLY_RETENTION_DAYS + 1)).strftime("%Y-%m-%dT%H")
        ledger["daily"] = {fresh_day: "1.00", stale_day: "2.00"}
        ledger["hourly"] = {fresh_hour: "3.00", stale_hour: "4.00"}

        trim(ledger, now=now)

        self.assertIn(fresh_day, ledger["daily"])
        self.assertNotIn(stale_day, ledger["daily"])
        self.assertIn(fresh_hour, ledger["hourly"])
        self.assertNotIn(stale_hour, ledger["hourly"])

    def test_malformed_keys_are_discarded(self):
        ledger = empty_ledger()
        ledger["daily"] = {"not-a-date": "1.00"}
        ledger["hourly"] = {"also-not-a-date": "1.00"}
        trim(ledger, now=local(2026, 9, 13))
        self.assertEqual(ledger["daily"], {})
        self.assertEqual(ledger["hourly"], {})


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        # Sunday 2026-09-13, so the monday/sunday week split is observable.
        self.now = local(2026, 9, 13, 15, 30)
        self.ledger = empty_ledger()
        self.ledger["currency"] = "CNY"
        self.ledger["daily"] = {
            "2026-09-13": "1.50",  # today (Sunday)
            "2026-09-12": "2.00",  # Saturday, same monday-week
            "2026-09-07": "4.00",  # Monday, start of the monday-week
            "2026-09-06": "8.00",  # previous Sunday, only in the sunday-week
            "2026-09-01": "16.00",  # earlier this month
            "2026-08-15": "32.00",  # earlier this year
            "2025-12-31": "64.00",  # previous year, must never be counted
        }
        self.ledger["hourly"] = {"2026-09-13T09": "0.50", "2026-09-13T15": "1.00"}

    def test_totals_are_calendar_anchored(self):
        totals = summarize(self.ledger, now=self.now)["totals"]
        self.assertEqual(totals["today"], Decimal("1.50"))
        self.assertEqual(totals["week"], Decimal("7.50"))  # Mon 09-07 .. Sun 09-13
        self.assertEqual(totals["month"], Decimal("31.50"))  # 09-01 .. 09-13
        self.assertEqual(totals["year"], Decimal("63.50"))  # 01-01 .. 09-13

    def test_week_start_is_configurable(self):
        totals = summarize(self.ledger, week_starts_on="sunday", now=self.now)["totals"]
        # A sunday-week beginning 09-13 contains only today.
        self.assertEqual(totals["week"], Decimal("1.50"))

    def test_previous_year_is_never_counted(self):
        totals = summarize(self.ledger, now=self.now)["totals"]
        self.assertNotIn(Decimal("64.00"), totals.values())

    def test_today_series_is_hourly_from_midnight_to_now(self):
        result = summarize(self.ledger, now=self.now)
        series = result["series_by_period"]["today"]
        self.assertEqual(len(series), 16)  # hours 00..15 inclusive
        self.assertEqual(series[9], 0.5)
        self.assertEqual(series[15], 1.0)
        self.assertEqual(series[0], 0.0)

    def test_week_and_month_series_are_daily(self):
        result = summarize(self.ledger, now=self.now)
        self.assertEqual(len(result["series_by_period"]["week"]), 7)  # Mon..Sun
        self.assertEqual(len(result["series_by_period"]["month"]), 13)  # 09-01..09-13

    def test_year_series_is_monthly(self):
        result = summarize(self.ledger, now=self.now)
        series = result["series_by_period"]["year"]
        self.assertEqual(len(series), 9)  # Jan..Sep
        self.assertEqual(series[7], 32.0)  # August
        self.assertEqual(series[8], 1.5 + 2.0 + 4.0 + 8.0 + 16.0)  # September

    def test_empty_ledger_summarizes_to_zeroes(self):
        result = summarize(empty_ledger(), now=self.now)
        self.assertEqual(result["totals"]["year"], Decimal("0"))
        self.assertEqual(set(result["series_by_period"]), {"today", "week", "month", "year"})

    def test_currency_is_passed_through(self):
        self.assertEqual(summarize(self.ledger, now=self.now)["currency"], "CNY")


class BudgetTests(unittest.TestCase):
    def test_percent_is_spend_over_budget(self):
        self.assertEqual(budget_percent(Decimal("25.00"), Decimal("100.00")), 25.0)

    def test_percent_is_uncapped_so_overspend_stays_visible(self):
        self.assertEqual(budget_percent(Decimal("120.00"), Decimal("100.00")), 120.0)

    def test_zero_or_missing_budget_yields_none(self):
        self.assertIsNone(budget_percent(Decimal("5.00"), Decimal("0")))
        self.assertIsNone(budget_percent(Decimal("5.00"), None))


if __name__ == "__main__":
    unittest.main()
